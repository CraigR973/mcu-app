"""The daily check, against Postgres — Batch X2's guards (DS44-01, UX48-02, DS44-05).

**What this proves:** each check trips on crafted rows and passes on others: a job quiet past
its cadence or never run, an eBay scan that read nothing in six runs, a person with no live
device or whose recent notifications all went undelivered, readiness not configured, the spec
integration halted, the database over half its cap, a PIN locked in the last day, Identify
proposals older than a fortnight, an identified film a page says is another year, and a deal
older than its source's freshness. A new problem is pushed to the admin once, not every
morning it persists, and pushed again if it clears and comes back. Home's row lists the
problems, and says so when the check itself has not run for a day; Mark cannot read it. The
attention push ignores every toggle. The jobs beat when they do nothing.

Each test reads only the rows it made: the checks read whole tables, so they assert on the
keys of their own people and on tables the rolled-back transaction starts with empty.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.deal import Deal
from src.models.ebay_watch import EbayWatchRun
from src.models.health import HealthCheck, JobHeartbeat
from src.models.identify import IdentifyLookup
from src.models.movie import Movie
from src.models.notification import (
    Notification,
    NotificationCategory,
    NotificationPreference,
    PushSubscription,
)
from src.models.profile import Profile, UserRole
from src.models.reviews import FilmReview
from src.models.specs_backfill import SpecLookup
from src.models.specs_state import SINGLETON_ID, SpecsIntegrationState
from src.services import health_checks
from src.services.health_checks import run_daily_check
from src.services.heartbeat import beat
from src.services.notifications import queue_notification

NOW = datetime(2026, 10, 13, 8, 0)


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    # The checks read whole tables; start the ones these tests count from empty.
    for model in (JobHeartbeat, HealthCheck, EbayWatchRun, IdentifyLookup, Deal):
        await session.execute(delete(model))
    await session.flush()
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


async def _person(db: AsyncSession, role: UserRole = UserRole.viewer, **fields: Any) -> Profile:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"Tester {uuid.uuid4().hex[:6]}",
        role=role,
        pin_hash="test-pin-hash",
        **fields,
    )
    db.add(person)
    await db.flush()
    return person


async def _device(db: AsyncSession, person: Profile) -> None:
    db.add(
        PushSubscription(
            id=uuid.uuid4(),
            user_id=person.id,
            endpoint=f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}",
            p256dh="p" * 87,
            auth="a" * 22,
        )
    )
    await db.flush()


async def _note(db: AsyncSession, person: Profile, status: str, *, age: timedelta) -> None:
    db.add(
        Notification(
            id=uuid.uuid4(),
            user_id=person.id,
            category="deals",
            status=status,
            title="A deal",
            body="",
            created_at_utc=NOW - age,
            sent_at_utc=NOW - age if status == "sent" else None,
            delivered_count=1 if status == "sent" else 0,
        )
    )
    await db.flush()


def _by_key(results: list[tuple[str, str | None]]) -> dict[str, str | None]:
    return dict(results)


# ---------------------------------------------------------------------------
# Each check, tripped and passed
# ---------------------------------------------------------------------------


async def test_a_job_quiet_past_its_cadence_or_never_run_is_named(db: AsyncSession) -> None:
    await beat(db, "cron-scrape", "ran", now=NOW - timedelta(hours=27))
    await beat(db, "cron-specs", "nothing due", now=NOW - timedelta(hours=6))
    await beat(db, "cron-ebay", "finished, 0 listings read", now=NOW - timedelta(hours=1))

    found = _by_key(await health_checks.check_jobs(db, NOW))

    assert found["job:cron-scrape"] == "The nightly shop price check hasn't run since 12 Oct."
    # "Nothing due" is a beat like any other: idle reads as alive.
    assert found["job:cron-specs"] is None
    assert found["job:cron-ebay"] is None
    assert found["job:cron-values"] == "The valuation job has never run."


async def test_a_run_started_from_the_app_counts_as_the_job_running(db: AsyncSession) -> None:
    db.add(
        EbayWatchRun(
            id=uuid.uuid4(),
            trigger="admin",
            status="finished",
            started_utc=NOW - timedelta(hours=2),
            heartbeat_utc=NOW - timedelta(hours=2),
            budget=50,
            calls=1,
        )
    )
    await db.flush()
    assert _by_key(await health_checks.check_jobs(db, NOW))["job:cron-ebay"] is None


def _scan(started: datetime, seen: int) -> EbayWatchRun:
    return EbayWatchRun(
        id=uuid.uuid4(),
        trigger="job",
        status="finished",
        started_utc=started,
        heartbeat_utc=started,
        budget=50,
        calls=1,
        listings_seen=seen,
    )


async def test_six_scans_that_read_nothing_are_named(db: AsyncSession) -> None:
    """CR43-01's guard: 45 blind scans from 9 Oct each ended "finished"."""
    db.add_all(_scan(NOW - timedelta(hours=2 * hours), 0) for hours in range(1, 7))
    await db.flush()
    (result,) = await health_checks.check_ebay_listings(db, NOW)
    assert result == ("ebay:listings", "No eBay listings read in the last 6 scans (since 12 Oct).")

    db.add(_scan(NOW - timedelta(minutes=30), 2709))
    await db.flush()
    assert await health_checks.check_ebay_listings(db, NOW) == [("ebay:listings", None)]


async def test_a_person_with_no_live_device_or_only_undelivered_notifications(
    db: AsyncSession,
) -> None:
    none = await _person(db)
    silent = await _person(db)
    await _device(db, silent)
    for _ in range(3):
        await _note(db, silent, "suppressed", age=timedelta(days=1))
    await _note(db, silent, "suppressed", age=timedelta(days=5))  # outside the window
    fine = await _person(db)
    await _device(db, fine)
    await _note(db, fine, "suppressed", age=timedelta(days=1))
    await _note(db, fine, "sent", age=timedelta(days=2))
    revoked = await _person(db)
    await _device(db, revoked)
    await db.execute(
        PushSubscription.__table__.update()
        .where(PushSubscription.user_id == revoked.id)
        .values(revoked_at_utc=NOW, revoked_reason="refused")
    )

    found = _by_key(await health_checks.check_people(db, NOW))

    assert found[f"person:{none.id}:notifications"] == (
        f"{none.display_name} has no phone getting notifications."
    )
    assert found[f"person:{silent.id}:notifications"] == (
        f"None of {silent.display_name}'s 3 notifications since 10 Oct reached a phone."
    )
    assert found[f"person:{fine.id}:notifications"] is None
    assert found[f"person:{revoked.id}:notifications"] == (
        f"{revoked.display_name} has no phone getting notifications."
    )


async def test_readiness_not_configured_is_named(db: AsyncSession) -> None:
    assert await health_checks.check_readiness(db, NOW) == [("api:readiness", None)]
    await beat(
        db,
        "api",
        "booted",
        detail={"push": "invalid", "ai": "not_configured", "ebay": "configured"},
        now=NOW,
    )
    assert await health_checks.check_readiness(db, NOW) == [
        ("api:readiness", "Notifications, The assistant isn't set up on the server.")
    ]


async def test_a_halted_spec_integration_is_named(db: AsyncSession) -> None:
    await db.merge(
        SpecsIntegrationState(
            id=SINGLETON_ID,
            halted=True,
            halted_reason="Blu-ray.com answered 403",
            halted_at_utc=NOW,
            fetch_count=0,
        )
    )
    await db.flush()
    assert await health_checks.check_specs(db, NOW) == [
        ("specs:halted", "Disc spec lookups are halted: Blu-ray.com answered 403.")
    ]
    await db.merge(
        SpecsIntegrationState(
            id=SINGLETON_ID, halted=False, halted_reason=None, halted_at_utc=None, fetch_count=0
        )
    )
    await db.flush()
    assert await health_checks.check_specs(db, NOW) == [("specs:halted", None)]


async def test_a_database_over_half_its_cap_is_named(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await health_checks.check_database_size(db, NOW) == [("database:size", None)]
    monkeypatch.setattr(health_checks, "DATABASE_CAP_BYTES", 2)
    ((key, message),) = await health_checks.check_database_size(db, NOW)
    assert key == "database:size" and message and message.endswith("over half its 1 GB.")


async def test_a_pin_locked_in_the_last_day_is_named(db: AsyncSession) -> None:
    locked = await _person(db, lockout_count=2, last_lockout_utc=NOW - timedelta(hours=3))
    earlier = await _person(db, lockout_count=1, last_lockout_utc=NOW - timedelta(days=2))
    found = _by_key(await health_checks.check_lockouts(db, NOW))
    assert found[f"person:{locked.id}:lockout"] == (
        f"{locked.display_name}'s PIN locked 2 times, last at 13 Oct, 05:00 UTC."
    )
    assert found[f"person:{earlier.id}:lockout"] is None


async def _film(db: AsyncSession, title: str, *, tmdb_id: int | None = None) -> Movie:
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=2007,
        media_type="film",
    )
    db.add(film)
    await db.flush()
    return film


async def test_old_proposals_and_films_a_page_says_are_another_year(db: AsyncSession) -> None:
    """CT46-03's guard."""
    before = _by_key(await health_checks.check_identification(db, NOW))
    assert before == {"identify:waiting": None, "identify:year-doubt": None}

    old = await _film(db, "The Bridge on the River Kwai")
    new = await _film(db, "A recent film")
    for film, age in ((old, timedelta(days=15)), (new, timedelta(days=2))):
        db.add(
            IdentifyLookup(
                id=uuid.uuid4(), movie_id=film.id, status="needs_you", created_utc=NOW - age
            )
        )
    by_page = await _film(db, "Kwai", tmdb_id=990_000_001)
    item = CollectionItem(id=uuid.uuid4(), movie_id=by_page.id, formats=["blu_ray"])
    db.add(item)
    await db.flush()
    db.add(
        SpecLookup(
            id=uuid.uuid4(),
            collection_item_id=item.id,
            status="needs_you",
            note="The page is for a 1957 film and this one is from 2007, so its specs were not "
            "used. Pick the right page.",
        )
    )
    by_review = await _film(db, "Dead Man's Shoes", tmdb_id=990_000_002)
    db.add(
        FilmReview(
            id=uuid.uuid4(),
            movie_id=by_review.id,
            site="bluray_com",
            status="mismatch",
            found_via="brave",
            url="https://www.blu-ray.com/movies/dead-mans-shoes/1/",
            found_utc=NOW,
        )
    )
    await db.flush()

    after = _by_key(await health_checks.check_identification(db, NOW))
    assert after["identify:waiting"] == "1 Identify proposal has waited more than a fortnight."
    assert after["identify:year-doubt"] == (
        "2 identified films have a disc page or review for another year."
    )


async def test_a_deal_older_than_its_sources_freshness_is_named(db: AsyncSession) -> None:
    assert await health_checks.check_deal_freshness(db, NOW) == [("deals:freshness", None)]
    db.add(
        Deal(
            id=uuid.uuid4(),
            retailer_id=None,
            retailer_name_snapshot="eBay",
            title_snapshot="An old find kept alive",
            url="https://www.ebay.co.uk/itm/990000000201",
            price=Decimal("5.00"),
            currency="GBP",
            first_seen_at_utc=NOW - timedelta(days=4),
            last_seen_at_utc=NOW - timedelta(days=4),
            expires_at_utc=datetime(2099, 1, 1),
        )
    )
    await db.flush()
    assert await health_checks.check_deal_freshness(db, datetime.now()) == [
        ("deals:freshness", "1 deal on the page is older than its source's freshness.")
    ]


# ---------------------------------------------------------------------------
# Recorded, and pushed once
# ---------------------------------------------------------------------------


async def _attention(db: AsyncSession, person: Profile) -> list[Notification]:
    return list(
        (
            await db.scalars(
                select(Notification).where(
                    Notification.user_id == person.id, Notification.category == "attention"
                )
            )
        ).all()
    )


async def test_a_new_problem_is_pushed_once_and_again_when_it_returns(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    mark = await _person(db)
    db.add_all(_scan(NOW - timedelta(hours=2 * hours), 0) for hours in range(1, 7))
    await db.flush()

    summary = await run_daily_check(db, now=NOW)

    assert "No eBay listings read in the last 6 scans (since 12 Oct)." in (summary.new or [])
    pushes = await _attention(db, craig)
    blind = [note for note in pushes if note.body.startswith("No eBay listings")]
    assert [(note.title, note.url) for note in blind] == [("Needs attention", "/")]
    assert await _attention(db, mark) == []
    row = await db.get(HealthCheck, "ebay:listings")
    assert row is not None and (row.ok, row.failing_since_utc, row.pushed_utc) == (False, NOW, NOW)

    # The next morning it persists: recorded, not pushed again.
    await run_daily_check(db, now=NOW + timedelta(days=1))
    again = [n for n in await _attention(db, craig) if n.body.startswith("No eBay listings")]
    assert len(again) == 1
    await db.refresh(row)
    assert (row.failing_since_utc, row.checked_utc) == (NOW, NOW + timedelta(days=1))

    # It clears, then comes back: a new appearance, a new push.
    db.add(_scan(NOW + timedelta(days=1, hours=1), 300))
    await db.flush()
    await run_daily_check(db, now=NOW + timedelta(days=1, hours=2))
    await db.refresh(row)
    assert (row.ok, row.failing_since_utc) == (True, None)
    db.add_all(_scan(NOW + timedelta(days=2, hours=hours), 0) for hours in range(1, 7))
    await db.flush()
    await run_daily_check(db, now=NOW + timedelta(days=3))
    returned = [n for n in await _attention(db, craig) if n.body.startswith("No eBay listings")]
    assert len(returned) == 2


async def test_the_attention_push_ignores_every_toggle(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    db.add(
        NotificationPreference(
            id=uuid.uuid4(),
            user_id=craig.id,
            deals_enabled=False,
            sale_events_enabled=False,
            releases_enabled=False,
            loans_enabled=False,
            movie_night_enabled=False,
        )
    )
    await db.flush()
    note = await queue_notification(
        db,
        user_id=craig.id,
        category=NotificationCategory.attention,
        title="Needs attention",
        body="The eBay scan hasn't run since 12 Oct.",
        now=NOW,
    )
    assert note is not None and note.status == "queued"


# ---------------------------------------------------------------------------
# Home's row
# ---------------------------------------------------------------------------


def _as(db: AsyncSession, person_id: uuid.UUID) -> AsyncClient:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        fresh = await db.get(Profile, person_id)
        assert fresh is not None
        return fresh

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_home_lists_the_problems_and_a_check_that_has_stopped(db: AsyncSession) -> None:
    craig_id = (await _person(db, UserRole.admin)).id
    mark_id = (await _person(db)).id

    async with _as(db, craig_id) as client:
        never = (await client.get("/api/v1/attention")).json()
    assert never == {
        "items": [
            {
                "key": "check:stale",
                "message": "The daily check hasn't run yet.",
                "since": None,
                "noteId": None,
            }
        ],
        "checkedAt": None,
    }

    now = datetime.now().replace(microsecond=0)
    db.add_all(_scan(now - timedelta(hours=2 * hours), 0) for hours in range(1, 7))
    await db.flush()
    await run_daily_check(db, now=now)
    async with _as(db, craig_id) as client:
        fresh = (await client.get("/api/v1/attention")).json()
    keys = [item["key"] for item in fresh["items"]]
    assert "ebay:listings" in keys and "check:stale" not in keys
    (blind,) = [item for item in fresh["items"] if item["key"] == "ebay:listings"]
    assert blind["message"].startswith("No eBay listings read in the last 6 scans")
    assert blind["since"] is not None

    # A day and more without a check: the row says so, first.
    await db.execute(HealthCheck.__table__.update().values(checked_utc=now - timedelta(hours=30)))
    async with _as(db, craig_id) as client:
        late = (await client.get("/api/v1/attention")).json()
    assert late["items"][0]["key"] == "check:stale"
    assert late["items"][0]["message"].startswith("The daily check hasn't run since ")

    async with _as(db, mark_id) as client:
        assert (await client.get("/api/v1/attention")).status_code == 403


# ---------------------------------------------------------------------------
# The jobs beat when they do nothing
# ---------------------------------------------------------------------------


class _Session:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def __aenter__(self) -> AsyncSession:
        return self.db

    async def __aexit__(self, *_: object) -> None:
        return None


class _ConfiguredEbay:
    configured = True

    async def __aenter__(self) -> _ConfiguredEbay:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


async def test_the_valuation_and_ebay_jobs_beat_when_nothing_is_due(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """X2: an idle job wrote no row before, so idle and stopped looked alike."""
    from src.scripts import ebay_watch, value_collection

    for module in (value_collection, ebay_watch):
        monkeypatch.setattr(module, "AsyncSessionLocal", lambda: _Session(db))
        monkeypatch.setattr(module, "EbayClient", _ConfiguredEbay)

    async def nothing_due(_db: AsyncSession, **_: object) -> SimpleNamespace:
        return SimpleNamespace(reason="nothing_due", run=None, due=0, budget_left=500)

    async def budget_spent(_db: AsyncSession, **_: object) -> SimpleNamespace:
        return SimpleNamespace(reason="budget_spent", run=None, budget_left=0)

    monkeypatch.setattr(value_collection, "start_run", nothing_due)
    monkeypatch.setattr(ebay_watch, "start_run", budget_spent)

    assert await value_collection.main() == 0
    assert await ebay_watch.main() == 0

    values = await db.get(JobHeartbeat, "cron-values")
    ebay = await db.get(JobHeartbeat, "cron-ebay")
    assert values is not None and values.outcome == "nothing due"
    assert ebay is not None and ebay.outcome == "budget spent"
    assert (await health_checks.check_jobs(db, values.beat_utc))[1:3] == [
        ("job:cron-specs", "The nightly disc spec and review job has never run."),
        ("job:cron-ebay", None),
    ]


async def test_the_spec_job_beats_when_nothing_is_due(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.scripts import spec_backfill

    monkeypatch.setattr(spec_backfill, "AsyncSessionLocal", lambda: _Session(db))

    async def nothing_due(_db: AsyncSession, **_: object) -> SimpleNamespace:
        return SimpleNamespace(reason="nothing_due", run=None)

    async def no_reviews(_db: AsyncSession, **_: object) -> None:
        return None

    async def counts(_db: AsyncSession) -> Any:
        return await original_coverage(_db)

    original_coverage = spec_backfill.coverage
    monkeypatch.setattr(spec_backfill, "start_run", nothing_due)
    monkeypatch.setattr(spec_backfill.reviews, "start_run", no_reviews)
    monkeypatch.setattr(spec_backfill, "coverage", counts)

    await spec_backfill.main()

    specs = await db.get(JobHeartbeat, "cron-specs")
    assert specs is not None and specs.outcome == "nothing due"


# ---------------------------------------------------------------------------
# Batch X12a — "Tell Craig"
# ---------------------------------------------------------------------------


async def test_a_line_from_mark_lands_in_craigs_row_until_he_clears_it(db: AsyncSession) -> None:
    craig_id = (await _person(db, UserRole.admin)).id
    mark = await _person(db)

    async with _as(db, mark.id) as client:
        sent = await client.post(
            "/api/v1/attention/notes", json={"message": "  The Alien disc is in the Lounge  "}
        )
        assert sent.status_code == 204
        # Clearing is Craig's, not the sender's.
        assert (await client.get("/api/v1/attention")).status_code == 403

    async with _as(db, craig_id) as client:
        items = (await client.get("/api/v1/attention")).json()["items"]
        (note,) = [item for item in items if item["noteId"]]
        assert note["message"] == f"{mark.display_name} says: The Alien disc is in the Lounge"
        assert note["key"] == f"note:{note['noteId']}"

        assert (await client.delete(f"/api/v1/attention/notes/{note['noteId']}")).status_code == 204
        again = (await client.get("/api/v1/attention")).json()["items"]
        assert all(item["noteId"] is None for item in again)
        # Clearing twice, or something that was never there, is harmless or a 404.
        assert (await client.delete(f"/api/v1/attention/notes/{note['noteId']}")).status_code == 204
        missing = await client.delete(f"/api/v1/attention/notes/{uuid.uuid4()}")
        assert missing.status_code == 404

    async with _as(db, mark.id) as client:
        assert (await client.delete(f"/api/v1/attention/notes/{note['noteId']}")).status_code == 403


async def test_a_note_must_have_words_and_stay_short(db: AsyncSession) -> None:
    mark = await _person(db)
    async with _as(db, mark.id) as client:
        assert (
            await client.post("/api/v1/attention/notes", json={"message": "   "})
        ).status_code == 422
        long = await client.post("/api/v1/attention/notes", json={"message": "x" * 301})
        assert long.status_code == 422
        assert (
            await client.post("/api/v1/attention/notes", json={"message": "x" * 300})
        ).status_code == 204


async def test_one_person_cannot_fill_craigs_home(db: AsyncSession) -> None:
    craig_id = (await _person(db, UserRole.admin)).id
    mark = await _person(db)
    async with _as(db, mark.id) as client:
        for number in range(5):
            sent = await client.post("/api/v1/attention/notes", json={"message": f"note {number}"})
            assert sent.status_code == 204
        sixth = await client.post("/api/v1/attention/notes", json={"message": "one more"})
        assert sixth.status_code == 429

    # Craig clearing one makes room.
    async with _as(db, craig_id) as client:
        first = next(
            item
            for item in (await client.get("/api/v1/attention")).json()["items"]
            if item["noteId"]
        )
        await client.delete(f"/api/v1/attention/notes/{first['noteId']}")
    async with _as(db, mark.id) as client:
        assert (
            await client.post("/api/v1/attention/notes", json={"message": "again"})
        ).status_code == 204
