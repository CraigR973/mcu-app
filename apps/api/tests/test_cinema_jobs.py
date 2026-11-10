"""Real advisory locks/leases, disabled job, and reminder commit boundary."""

import uuid
from datetime import UTC, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.cinema import CinemaCoverage, CinemaFilm, CinemaRefreshRun, CinemaVenue
from src.models.health import JobHeartbeat
from src.models.profile import Profile, UserRole
from src.scripts import refresh_cinemas, run_reminders
from src.services.cinemas import refresh
from src.services.cinemas.domain import LONDON, Showing, Snapshot, SourceError
from src.services.cinemas.venues import VENUES
from src.services.health_checks import CheckSummary
from src.services.reminders import ReminderSummary


async def test_disabled_seeds_make_zero_requests_and_no_run(db_engine, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled cinema job must never construct an HTTP client")

    monkeypatch.setattr(refresh.httpx, "AsyncClient", forbidden)
    factory = async_sessionmaker(db_engine)
    async with factory() as db:
        before = await db.scalar(select(func.count()).select_from(CinemaRefreshRun))
    assert await refresh.refresh_due(db_engine) == {"status": "disabled", "requests": 0}
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(CinemaRefreshRun)) == before


async def test_real_lock_blocks_overlap_and_failed_worker_records_outcome(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    run_id = None
    try:
        async with (
            refresh.exclusive(db_engine, "test", {"test": True}) as run_id,
            refresh.exclusive(db_engine, None, {}),
        ):
            pytest.fail("The second worker must never enter")
    except SourceError as exc:
        assert "global lock" in str(exc)
    finally:
        assert run_id is not None
        async with factory() as db, db.begin():
            run = await db.get(CinemaRefreshRun, run_id)
            assert run.status == "failed"
            await db.delete(run)
    # The same process may run again after releasing its dedicated connection lock.
    async with refresh.exclusive(db_engine, None, {}):
        pass


async def test_live_lease_blocks_and_expired_lease_is_abandoned(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    old_id = uuid.uuid4()
    new_id = None
    now = utcnow()
    try:
        async with factory() as db, db.begin():
            db.add(
                CinemaRefreshRun(
                    id=old_id,
                    trigger="test",
                    adapter_version="ab6-1",
                    status="running",
                    started_utc=now,
                    heartbeat_utc=now,
                    lease_expires_utc=now + timedelta(minutes=10),
                    report={},
                )
            )
        with pytest.raises(SourceError, match="live cinema refresh lease"):
            async with refresh.exclusive(db_engine, "test", {}):
                pytest.fail("Live lease cannot be replaced")
        async with factory() as db, db.begin():
            old = await db.get(CinemaRefreshRun, old_id)
            old.lease_expires_utc = now - timedelta(seconds=1)
        async with refresh.exclusive(db_engine, "test", {}) as new_id:
            assert new_id != old_id
            async with factory() as db:
                assert (await db.get(CinemaRefreshRun, old_id)).status == "abandoned"
    finally:
        async with factory() as db, db.begin():
            await db.execute(
                delete(CinemaRefreshRun).where(
                    CinemaRefreshRun.id.in_([i for i in (old_id, new_id) if i is not None])
                )
            )


async def test_reviewed_nine_venue_import_exact_enable_and_separate_heartbeat(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    now = utcnow()
    start = (now.replace(tzinfo=UTC) + timedelta(hours=2)).astimezone(LONDON)
    day = start.date()
    async with factory() as db:
        actor = await db.scalar(select(Profile.id).where(Profile.role == UserRole.admin))
        assert actor is not None
        previous_audits = set((await db.scalars(select(AdminAction.id))).all())
        assert await db.get(JobHeartbeat, refresh.HEARTBEAT) is None
    snapshots = {
        v.slug: Snapshot(
            rows=[
                Showing(
                    "job-test",
                    "job-test:" + v.slug,
                    "Fixture film",
                    start,
                    None,
                    start.isoformat(),
                )
            ],
            observed_dates={day},
            complete_dates={day},
            observed_utc=now,
        )
        for v in VENUES
    }
    prepared = refresh.PreparedRun(
        prepared_utc=now,
        date_from=day,
        date_to=day,
        snapshots=snapshots,
        requests=10,
        decoded_bytes=100,
    )
    try:
        report = await refresh.apply_prepared(db_engine, prepared, actor)
        # AE4 (#355): ten venues since the Omniplex joined the nine.
        assert report["status"] == "healthy" and report["rows"] == 10
        async with factory() as db:
            heartbeat = await db.get(JobHeartbeat, refresh.HEARTBEAT)
            assert heartbeat.outcome == "healthy"
            assert heartbeat.detail["rows"] == 10
        with pytest.raises(SourceError, match="row count"):
            await refresh.set_enabled(db_engine, actor, True, 9)
        assert await refresh.set_enabled(db_engine, actor, True, 10) == 10
        async with factory() as db:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(CinemaVenue)
                    .where(CinemaVenue.collection_enabled.is_(True))
                )
                == 10
            )
        assert await refresh.set_enabled(db_engine, actor, False, 10) == 10
    finally:
        async with factory() as db, db.begin():
            for venue in (await db.scalars(select(CinemaVenue))).all():
                venue.collection_enabled = False
            await db.execute(delete(CinemaFilm).where(CinemaFilm.source_key.like("job-test:%")))
            await db.execute(delete(CinemaCoverage))
            await db.execute(delete(CinemaRefreshRun).where(CinemaRefreshRun.trigger == "manual"))
            await db.execute(delete(JobHeartbeat).where(JobHeartbeat.job == refresh.HEARTBEAT))
            await db.execute(delete(AdminAction).where(AdminAction.id.not_in(previous_audits)))


async def test_cinema_child_runs_after_reminder_commit_and_failure_is_separate(monkeypatch):
    events = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            events.append("session closed")

        async def commit(self):
            events.append("commit")

    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(run_reminders, "create_async_engine", lambda *args: engine)
    monkeypatch.setattr(run_reminders, "AsyncSession", lambda *args, **kwargs: Session())
    monkeypatch.setattr(run_reminders, "run_reminders", AsyncMock(return_value=ReminderSummary()))
    monkeypatch.setattr(run_reminders, "run_daily_check", AsyncMock(return_value=CheckSummary()))
    monkeypatch.setattr(run_reminders, "sync_due", AsyncMock(return_value=[]))

    async def beat(*args):
        events.append("reminder heartbeat")

    async def child(*args):
        assert events[-2:] == ["reminder heartbeat", "session closed"]
        assert events.count("commit") == 2
        return {"status": "failed"}

    monkeypatch.setattr(run_reminders.heartbeat, "beat", beat)
    monkeypatch.setattr(run_reminders, "refresh_due", child)
    assert await run_reminders._run(as_of=None, deliver=False) == 0
    engine.dispose.assert_awaited_once()


@pytest.mark.parametrize(
    "args",
    [
        ["--write"],
        ["--enable"],
        ["--dry-run"],
        [
            "--write",
            "--snapshot",
            "review.json",
            "--confirm-count",
            "4",
            "--actor-profile-id",
            str(uuid.UUID(int=1)),
        ],
        ["--enable", "--actor-profile-id", str(uuid.UUID(int=1)), "--confirm-count", "-1"],
    ],
)
def test_cli_rejects_missing_or_invalid_owner_controls(args):
    with pytest.raises(SystemExit) as error:
        refresh_cinemas.arguments(args)
    assert error.value.code == 2
