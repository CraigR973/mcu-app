"""Real advisory locks/leases, disabled job, and reminder commit boundary."""

import uuid
from datetime import UTC, date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select, update
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

    async def beat(*args, **kwargs):
        events.append("reminder heartbeat")

    async def child(*args):
        assert events[-2:] == ["reminder heartbeat", "session closed"]
        assert events.count("commit") == 2
        return {"status": "failed"}

    monkeypatch.setattr(run_reminders.heartbeat, "beat", beat)
    monkeypatch.setattr(run_reminders, "refresh_due", child)
    # #381: the cinema rows are checked again once the refresh has written today's run.
    cinema_check = AsyncMock(return_value=CheckSummary())
    monkeypatch.setattr(run_reminders, "run_cinema_check", cinema_check)
    assert await run_reminders._run(as_of=None, deliver=False) == 0
    cinema_check.assert_awaited_once()
    engine.dispose.assert_awaited_once()


async def test_the_cinema_rows_are_checked_after_the_refresh_and_their_push_delivered(
    monkeypatch,
):
    """#381: a cinema that fails this morning reaches Craig this morning."""
    events = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def commit(self):
            events.append("commit")

    class Sender:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(run_reminders, "create_async_engine", lambda *args: engine)
    monkeypatch.setattr(run_reminders, "AsyncSession", lambda *args, **kwargs: Session())
    monkeypatch.setattr(run_reminders, "run_reminders", AsyncMock(return_value=ReminderSummary()))
    monkeypatch.setattr(run_reminders, "run_daily_check", AsyncMock(return_value=CheckSummary()))
    monkeypatch.setattr(run_reminders, "sync_due", AsyncMock(return_value=[]))
    monkeypatch.setattr(run_reminders.heartbeat, "beat", AsyncMock())
    monkeypatch.setattr(run_reminders, "push_sender", lambda: Sender())

    async def refresh(*args):
        events.append("refresh")
        return {"status": "partial"}

    async def cinema_check(*args, **kwargs):
        events.append("cinema check")
        return CheckSummary(checked=5, problems=1, new=["ODEON Braehead's listings failed"])

    async def digest(*args):
        events.append("digest")
        return SimpleNamespace(sent=0, failed=0)

    async def deliver(*args, **kwargs):
        events.append("deliver")
        return SimpleNamespace(sent=1, failed=0)

    monkeypatch.setattr(run_reminders, "refresh_due", refresh)
    monkeypatch.setattr(run_reminders, "run_cinema_check", cinema_check)
    monkeypatch.setattr(run_reminders, "deliver_cinema_digest", digest)
    monkeypatch.setattr(run_reminders, "deliver_pending", deliver)
    assert await run_reminders._run(as_of=None, deliver=True) == 0
    after = events[events.index("refresh") :]
    assert after == ["refresh", "cinema check", "commit", "digest", "deliver", "commit"]


def _prepared(**snapshots):
    start = date(2026, 11, 17)
    return SimpleNamespace(
        date_from=start, date_to=start + timedelta(days=13), snapshots=dict(snapshots)
    )


def test_partial_means_a_cinema_read_less_than_its_source_can():
    """AG2 (CR49-04): 14 of 14 runs from 3 Nov were ``partial``, nine with nothing wrong,
    because only Vue's two days could ever be proven of a 14-day window. A run is now
    ``partial`` only when a cinema read less than its source can."""
    start = date(2026, 11, 17)
    vue_both = Snapshot(complete_dates={start, start + timedelta(days=1)})
    listings = Snapshot(observed_dates={start})  # a listings page proves no day complete
    assert refresh.provable_days("vue", start, start + timedelta(days=13), start) == {
        start,
        start + timedelta(days=1),
    }
    assert refresh.provable_days("cinematimes", start, start + timedelta(days=13), start) == set()

    every = _prepared(**{"vue-st-enoch": vue_both, "gft": listings, "odeon-braehead": listings})
    assert refresh.run_status(every) == "healthy"
    assert refresh.read_short(every) == []

    vue_one = Snapshot(complete_dates={start})
    short = _prepared(**{"vue-st-enoch": vue_one, "gft": listings})
    assert refresh.run_status(short) == "partial"
    assert refresh.read_short(short) == ["vue-st-enoch"]

    one_failed = _prepared(gft=listings, **{"odeon-braehead": Snapshot(failed=True)})
    assert refresh.run_status(one_failed) == "partial"
    assert refresh.read_short(one_failed) == ["odeon-braehead"]

    all_failed = _prepared(gft=Snapshot(failed=True), **{"odeon-braehead": Snapshot(failed=True)})
    assert refresh.run_status(all_failed) == "failed"


async def test_the_0800_job_refreshes_tmdbs_old_and_never_synced_films_and_beats(
    db_conn, monkeypatch
):
    """AG2 (DS50-05): the TMDB refresh moved into the 08:00 job, never-synced films first, and
    its heartbeat counts what TMDB would not give."""
    from sqlalchemy.ext.asyncio import AsyncSession as RealSession

    from src.models.movie import Movie
    from src.tmdb.models import Movie as TmdbMovie

    db = RealSession(bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint")

    class Shared:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *args):
            return None

    class FakeTmdb:
        asked: list[int] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get_movie_full(self, movie_id, language="en-US"):
            FakeTmdb.asked.append(movie_id)
            if movie_id == 9_800_003:
                raise RuntimeError("TMDB has removed it")
            return TmdbMovie(id=movie_id, title="Fresh", original_title="Fresh", overview="New.")

    now = utcnow()
    await db.execute(update(Movie).values(last_tmdb_sync_utc=now))
    films = {
        9_800_001: None,
        9_800_002: now - timedelta(days=200),
        9_800_003: now - timedelta(days=300),
        9_800_004: now - timedelta(days=10),
    }
    for tmdb_id, synced in films.items():
        db.add(
            Movie(
                id=uuid.uuid4(),
                tmdb_id=tmdb_id,
                title="Stale",
                original_title="Stale",
                media_type="film",
                last_tmdb_sync_utc=synced,
            )
        )
    await db.flush()
    monkeypatch.setattr(run_reminders, "AsyncSession", lambda *args, **kwargs: Shared())
    monkeypatch.setattr(run_reminders, "TMDBClient", FakeTmdb)
    monkeypatch.setattr(run_reminders.settings, "tmdb_read_token", "a-token")
    try:
        result = await run_reminders._refresh_tmdb(SimpleNamespace())
        assert FakeTmdb.asked == [9_800_001, 9_800_003, 9_800_002]
        assert result is not None and (result.refreshed, result.failed) == (2, 1)
        row = await db.get(JobHeartbeat, "tmdb-refresh")
        assert row is not None and row.outcome == "2 refreshed, 1 still due"
        assert row.detail["failures"] == 1
    finally:
        await db.close()


#: The 08:00 job's guarded steps, in the order they run, and the name each prints on failure.
MORNING_STEPS = [
    ("sync_due", "watch history"),
    ("refresh_due", "cinema programme"),
    ("run_cinema_check", "cinema check"),
    ("deliver_cinema_digest", "cinema digest"),
    ("_refresh_tmdb", "TMDB refresh"),
]


@pytest.mark.parametrize(("broken", "printed"), MORNING_STEPS)
async def test_the_morning_job_survives_a_failure_in_any_guarded_step(
    monkeypatch, capsys, broken, printed
):
    """AG1 (CR49-01): one step's exception never skips the steps after it.

    Wave 2 proved that a failed Letterboxd sync skipped delivery, the reminders heartbeat, the
    cinema refresh and the digest. Each guarded step is broken in turn; every other step,
    delivery and the heartbeat still run, and the job still exits 0.
    """
    events = []
    beats = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def commit(self):
            return None

    class Sender:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    async def heartbeat(db, job, outcome, **kwargs):
        events.append("heartbeat")
        beats.append((job, outcome, kwargs.get("failures"), kwargs.get("detail")))

    def step(name, result):
        async def run(*args, **kwargs):
            events.append(name)
            if name == broken:
                raise RuntimeError(f"{name} broke")
            return result

        return run

    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(run_reminders, "create_async_engine", lambda *args: engine)
    monkeypatch.setattr(run_reminders, "AsyncSession", lambda *args, **kwargs: Session())
    monkeypatch.setattr(run_reminders, "run_reminders", AsyncMock(return_value=ReminderSummary()))
    monkeypatch.setattr(run_reminders, "run_daily_check", AsyncMock(return_value=CheckSummary()))
    monkeypatch.setattr(run_reminders, "push_sender", lambda: Sender())
    monkeypatch.setattr(run_reminders.heartbeat, "beat", heartbeat)
    monkeypatch.setattr(run_reminders, "_refresh_tmdb", step("_refresh_tmdb", None))
    monkeypatch.setattr(
        run_reminders, "deliver_pending", step("deliver", SimpleNamespace(sent=0, failed=0))
    )
    monkeypatch.setattr(run_reminders, "sync_due", step("sync_due", []))
    monkeypatch.setattr(run_reminders, "refresh_due", step("refresh_due", {"status": "ok"}))
    monkeypatch.setattr(
        run_reminders,
        "run_cinema_check",
        step("run_cinema_check", CheckSummary(checked=1, problems=1, new=["a cinema failed"])),
    )
    monkeypatch.setattr(
        run_reminders,
        "deliver_cinema_digest",
        step("deliver_cinema_digest", SimpleNamespace(sent=1, failed=0)),
    )

    assert await run_reminders._run(as_of=None, deliver=True) == 0

    expected = ["sync_due", "deliver", "heartbeat", "refresh_due", "run_cinema_check"]
    expected += ["deliver_cinema_digest"]
    if broken != "run_cinema_check":
        expected += ["deliver"]  # the cinema check's new problem, pushed this morning
    expected += ["_refresh_tmdb"]
    if broken != "sync_due":
        expected += ["heartbeat"]  # AG2: written again, so a later step's failure is counted
    assert events == expected
    assert f"{printed}: failed, RuntimeError: {broken} broke" in capsys.readouterr().err
    engine.dispose.assert_awaited_once()
    # AG2: the job's last heartbeat names the step that failed, for the next daily check.
    job, outcome, failures, detail = beats[-1]
    assert (job, outcome, failures) == ("cron-reminders", "ran, 1 failed", 1)
    assert detail["failedSteps"] == [printed]


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
