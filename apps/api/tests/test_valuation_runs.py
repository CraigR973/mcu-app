"""Valuation runs and the total — Batch T6, snag 7. Postgres-backed, so these run in CI.

**What this proves:** one eBay search per film and format however many copies there are;
downloads, sold discs and deleted discs left out; a run that stops at its share of the day
and a next run that carries on without re-pricing anything; one run at a time, and a dead
one given up after 30 minutes; old prices kept when eBay fails; a price that needs three
listings, enforced by the table itself; the total and its counts; the Home button; and a
copy on a film's page carrying its stored price.

**What it does not:** a live eBay search. The first full run spends about 1,460 real calls
and is the owner's to authorise. eBay here is the two captured 200-listing payloads the
estimator is already tested against.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.config import settings
from src.database import get_db
from src.ebay.client import EbayError
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.valuation import DiscValuation, ValuationRun
from src.services.valuation import (
    DAILY_SHARE,
    MIN_RUN_BUDGET,
    collection_value,
    count_due,
    day_start,
    due_films,
    start_run,
    work_run,
)

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 9, 23, 12, 0)
FIXTURES = Path(__file__).parent / "fixtures"
BLADE_RUNNER = json.loads((FIXTURES / "ebay_browse_blade_runner_2049.json").read_text())
JAWS = json.loads((FIXTURES / "ebay_browse_jaws.json").read_text())
EMPTY: dict[str, Any] = {"itemSummaries": []}


class FakeEbay:
    """Answers by query, counts every call, and never retries."""

    marketplace_id = "EBAY_GB"
    attempts_per_search = 1

    def __init__(self, answers: dict[str, dict[str, Any] | Exception] | None = None) -> None:
        self.answers = answers or {}
        self.default: dict[str, Any] | Exception = EMPTY
        self.queries: list[str] = []
        self.search_calls = 0

    async def search(
        self, query: str, *, limit: int = 200, category_ids: str | None = None
    ) -> dict[str, Any]:
        del limit, category_ids
        self.search_calls += 1
        self.queries.append(query)
        answer = self.answers.get(query, self.default)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        # The counts below are exact, so they need a database with no owned discs of its
        # own. Anything here was committed by another test, and that is the bug to fix.
        assert await count_due(session, now=NOW) == 0, "owned discs leaked into the test DB"
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


async def _film(db: AsyncSession, title: str, *, tmdb_id: int | None = None) -> Movie:
    film = Movie(
        id=uuid.uuid4(), tmdb_id=tmdb_id, title=title, original_title=title, media_type="film"
    )
    db.add(film)
    await db.flush()
    return film


async def _disc(
    db: AsyncSession,
    film: Movie,
    *formats: str,
    listing_status: str = "in_collection",
    deleted: bool = False,
) -> CollectionItem:
    disc = CollectionItem(
        id=uuid.uuid4(),
        movie_id=film.id,
        formats=list(formats),
        listing_status=listing_status,
        deleted_at=NOW if deleted else None,
    )
    db.add(disc)
    await db.flush()
    return disc


async def _price(
    db: AsyncSession, film: Movie, format_code: str, price: str | None, *, checked: datetime
) -> DiscValuation:
    stored = DiscValuation(
        id=uuid.uuid4(),
        movie_id=film.id,
        format_code=format_code,
        status="priced" if price is not None else "not_priced",
        price=Decimal(price) if price is not None else None,
        currency="GBP",
        sample_size=10 if price is not None else 1,
        matched=10,
        considered=200,
        basis="current asking prices",
        search_query=f"{film.title} {format_code}",
        checked_utc=checked,
    )
    db.add(stored)
    await db.flush()
    return stored


async def _run_now(db: AsyncSession, ebay: FakeEbay, *, now: datetime = NOW) -> ValuationRun:
    outcome = await start_run(db, trigger="job", now=now)
    assert outcome.reason == "started", outcome
    assert outcome.run is not None
    return await work_run(db, ebay, outcome.run.id, clock=lambda: now)


async def _films_due(db: AsyncSession, count: int) -> list[Movie]:
    films = []
    for index in range(count):
        film = await _film(db, f"Due Film {index:02d}", tmdb_id=990_000_000 + index)
        await _disc(db, film, "blu_ray")
        films.append(film)
    return films


# ---------------------------------------------------------------------------
# A run
# ---------------------------------------------------------------------------


async def test_a_run_prices_each_film_and_format_once_and_counts_every_disc(
    db: AsyncSession,
) -> None:
    blade_runner = await _film(db, "Blade Runner 2049", tmdb_id=990_335_984)
    jaws = await _film(db, "Jaws", tmdb_id=990_000_578)
    mummy = await _film(db, "Mummy, The (Brendan Fraser)")
    digital = await _film(db, "Digital Only", tmdb_id=990_000_001)

    await _disc(db, blade_runner, "blu_ray")
    await _disc(db, blade_runner, "blu_ray")  # a second copy: a second disc, no second search
    await _disc(db, blade_runner, "4k_uhd", "blu_ray")  # a 4K box is priced as a 4K
    await _disc(db, blade_runner, "blu_ray", listing_status="sold")
    await _disc(db, jaws, "blu_ray", "download")
    await _disc(db, jaws, "dvd")
    await _disc(db, jaws, "blu_ray", deleted=True)
    await _disc(db, mummy, "dvd")
    await _disc(db, digital, "download")

    ebay = FakeEbay(
        {
            "Blade Runner 2049 Blu-ray": BLADE_RUNNER,
            "Blade Runner 2049 4K": BLADE_RUNNER,
            "Jaws Blu-ray": JAWS,
            "Jaws DVD": JAWS,
        }
    )
    run = await _run_now(db, ebay)

    assert ebay.queries == [
        "Blade Runner 2049 4K",
        "Blade Runner 2049 Blu-ray",
        "Jaws Blu-ray",
        "Jaws DVD",
        "The Mummy DVD",
    ]
    assert (run.status, run.calls, run.priced, run.not_priced, run.failed, run.remaining) == (
        "finished",
        5,
        3,
        2,
        0,
        0,
    )

    stored = {
        (row.movie_id, row.format_code): row
        for row in (await db.scalars(select(DiscValuation))).all()
    }
    blu_ray = stored[(blade_runner.id, "blu_ray")]
    assert (blu_ray.status, blu_ray.price, blu_ray.sample_size) == ("priced", Decimal("9.99"), 29)
    assert blu_ray.basis == "current asking prices"
    assert blu_ray.checked_utc == NOW and blu_ray.run_id == run.id
    assert stored[(blade_runner.id, "4k_uhd")].price == Decimal("24.99")
    assert stored[(jaws.id, "blu_ray")].price == Decimal("6.73")
    assert stored[(jaws.id, "dvd")].status == "not_priced"
    assert stored[(jaws.id, "dvd")].price is None
    assert stored[(mummy.id, "dvd")].search_query == "The Mummy DVD"
    assert (digital.id, "dvd") not in stored

    value = await collection_value(db, now=NOW)
    assert value.total == Decimal("9.99") * 2 + Decimal("24.99") + Decimal("6.73")
    assert (value.discs, value.priced, value.not_priced, value.unchecked) == (6, 4, 2, 0)
    assert value.checked_from == value.checked_to == NOW
    assert value.due == 0
    assert value.latest_run is not None and value.latest_run.id == run.id


async def test_a_priced_row_without_a_price_cannot_be_stored(db: AsyncSession) -> None:
    """ "Never guessed", held by the table as well as the code."""
    film = await _film(db, "Heat", tmdb_id=990_000_949)
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add(
                DiscValuation(
                    id=uuid.uuid4(),
                    movie_id=film.id,
                    format_code="blu_ray",
                    status="priced",
                    price=None,
                    basis="current asking prices",
                    search_query="Heat Blu-ray",
                    checked_utc=NOW,
                )
            )


# ---------------------------------------------------------------------------
# The budget
# ---------------------------------------------------------------------------


def _spent_today(calls: int) -> ValuationRun:
    earlier = day_start(NOW) + timedelta(hours=1)
    return ValuationRun(
        id=uuid.uuid4(),
        trigger="admin",
        status="finished",
        started_utc=earlier,
        heartbeat_utc=earlier,
        finished_utc=earlier,
        budget=DAILY_SHARE,
        calls=calls,
        remaining=5,
    )


async def test_a_run_stops_at_the_days_share_and_the_next_day_carries_on(
    db: AsyncSession,
) -> None:
    await _films_due(db, 5)
    db.add(_spent_today(DAILY_SHARE - 3))
    await db.commit()

    first_day = FakeEbay()
    first = await _run_now(db, first_day)

    assert (first.budget, first.calls, first.status, first.remaining) == (3, 3, "budget_spent", 2)
    assert first_day.queries == [f"Due Film {index:02d} Blu-ray" for index in (0, 1, 2)]

    later = await start_run(db, trigger="job", now=NOW + timedelta(hours=2))
    assert later.reason == "budget_spent" and later.run is None

    next_day = FakeEbay()
    second = await _run_now(db, next_day, now=NOW + timedelta(days=1))

    assert second.budget == DAILY_SHARE
    assert (second.calls, second.status, second.remaining) == (2, "finished", 0)
    assert next_day.queries == ["Due Film 03 Blu-ray", "Due Film 04 Blu-ray"]
    assert await count_due(db, now=NOW + timedelta(days=1)) == 0


async def test_no_run_starts_on_less_than_one_search_and_its_retries(db: AsyncSession) -> None:
    """A run stops when its next search might overrun, so it can leave two calls unspent.
    A run started on those would stop before searching anything."""
    await _films_due(db, 1)
    db.add(_spent_today(DAILY_SHARE - (MIN_RUN_BUDGET - 1)))
    await db.commit()

    outcome = await start_run(db, trigger="admin", now=NOW)

    assert (outcome.reason, outcome.run, outcome.budget_left) == ("budget_spent", None, 0)


async def test_prices_fall_due_again_after_30_days(db: AsyncSession) -> None:
    stale = await _film(db, "Stale", tmdb_id=990_000_010)
    fresh = await _film(db, "Fresh", tmdb_id=990_000_011)
    await _disc(db, stale, "blu_ray")
    await _disc(db, fresh, "blu_ray")
    await _price(db, stale, "blu_ray", "5.00", checked=NOW - timedelta(days=31))
    await _price(db, fresh, "blu_ray", "5.00", checked=NOW - timedelta(days=29))

    due = await due_films(db, now=NOW, limit=10)

    assert [film.movie_id for film in due] == [stale.id]


async def test_nothing_due_starts_nothing(db: AsyncSession) -> None:
    film = await _film(db, "Fresh", tmdb_id=990_000_012)
    await _disc(db, film, "blu_ray")
    await _price(db, film, "blu_ray", "5.00", checked=NOW - timedelta(days=1))

    outcome = await start_run(db, trigger="job", now=NOW)

    assert (outcome.reason, outcome.run, outcome.due) == ("nothing_due", None, 0)
    assert await db.scalar(select(func.count()).select_from(ValuationRun)) == 0


# ---------------------------------------------------------------------------
# One at a time
# ---------------------------------------------------------------------------


async def test_a_second_run_cannot_start_while_one_is_running(db: AsyncSession) -> None:
    await _films_due(db, 2)
    first = await start_run(db, trigger="job", now=NOW)
    assert first.reason == "started"

    second = await start_run(db, trigger="admin", now=NOW + timedelta(minutes=1))

    assert (second.reason, second.run) == ("running", None)
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add(
                ValuationRun(
                    id=uuid.uuid4(),
                    trigger="admin",
                    status="running",
                    started_utc=NOW,
                    heartbeat_utc=NOW,
                    budget=1,
                )
            )


async def test_a_run_nobody_has_heard_from_for_30_minutes_is_abandoned(
    db: AsyncSession,
) -> None:
    await _films_due(db, 1)
    dead = ValuationRun(
        id=uuid.uuid4(),
        trigger="job",
        status="running",
        started_utc=NOW - timedelta(hours=2),
        heartbeat_utc=NOW - timedelta(minutes=31),
        budget=DAILY_SHARE,
        calls=40,
    )
    db.add(dead)
    await db.commit()

    outcome = await start_run(db, trigger="job", now=NOW)

    assert outcome.reason == "started"
    await db.refresh(dead)
    assert (dead.status, dead.finished_utc) == ("abandoned", NOW)
    # Its 40 calls were spent today and still count against the share.
    assert outcome.run is not None and outcome.run.budget == DAILY_SHARE - 40


async def test_reading_the_total_closes_a_dead_run(db: AsyncSession) -> None:
    """Otherwise Home shows it pricing for ever, and hides the button that would replace it."""
    await _films_due(db, 1)
    dead = ValuationRun(
        id=uuid.uuid4(),
        trigger="admin",
        status="running",
        started_utc=NOW - timedelta(hours=1),
        heartbeat_utc=NOW - timedelta(minutes=45),
        budget=DAILY_SHARE,
        calls=12,
    )
    db.add(dead)
    await db.commit()

    value = await collection_value(db, now=NOW)

    assert value.latest_run is not None
    assert (value.latest_run.id, value.latest_run.status) == (dead.id, "abandoned")


# ---------------------------------------------------------------------------
# When eBay fails
# ---------------------------------------------------------------------------


async def test_five_failures_in_a_row_stop_the_run_and_old_prices_are_kept(
    db: AsyncSession,
) -> None:
    films = await _films_due(db, 7)
    await _price(db, films[0], "blu_ray", "5.00", checked=NOW - timedelta(days=40))
    ebay = FakeEbay()
    ebay.default = EbayError("eBay search failed (HTTP 500)", 500)

    run = await _run_now(db, ebay)

    assert (run.status, run.calls, run.failed, run.priced) == ("stopped", 5, 5, 0)
    assert run.last_error is not None and "HTTP 500" in run.last_error
    assert run.remaining == 7
    kept = await db.scalar(select(DiscValuation).where(DiscValuation.movie_id == films[0].id))
    assert kept is not None
    assert (kept.price, kept.checked_utc) == (Decimal("5.00"), NOW - timedelta(days=40))


async def test_ebay_saying_too_many_requests_stops_the_run_at_once(db: AsyncSession) -> None:
    await _films_due(db, 3)
    ebay = FakeEbay()
    ebay.default = EbayError("eBay search failed (HTTP 429)", 429)

    run = await _run_now(db, ebay)

    assert (run.status, run.calls, run.failed) == ("stopped", 1, 1)


async def test_a_crash_mid_run_is_recorded_rather_than_left_running(db: AsyncSession) -> None:
    await _films_due(db, 2)
    ebay = FakeEbay()
    ebay.default = RuntimeError("the network went away")
    outcome = await start_run(db, trigger="job", now=NOW)
    assert outcome.run is not None

    with pytest.raises(RuntimeError):
        await work_run(db, ebay, outcome.run.id, clock=lambda: NOW)

    run = await db.get(ValuationRun, outcome.run.id)
    assert run is not None
    assert run.status == "stopped"
    assert run.last_error == "RuntimeError: the network went away"


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------


async def _person(db: AsyncSession, role: UserRole) -> Profile:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"{role.value} {uuid.uuid4().hex[:6]}",
        role=role,
        pin_hash="test-pin-hash",
    )
    db.add(person)
    await db.flush()
    return person


def _as(db: AsyncSession, person: Profile) -> AsyncClient:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return person

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def ebay_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ebay_client_id", "an-id")
    monkeypatch.setattr(settings, "ebay_client_secret", "a-secret")


@pytest.fixture
def no_ebay_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ebay_client_id", "")
    monkeypatch.setattr(settings, "ebay_client_secret", "")


@pytest.fixture
def background(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    import src.routers.valuation as valuation_router

    started: list[uuid.UUID] = []

    async def record(run_id: uuid.UUID) -> None:
        started.append(run_id)

    monkeypatch.setattr(valuation_router, "continue_run_in_background", record)
    return started


async def test_both_people_can_read_the_total(db: AsyncSession) -> None:
    mark = await _person(db, UserRole.viewer)
    film = await _film(db, "Heat", tmdb_id=990_000_949)
    await _disc(db, film, "blu_ray")
    await _disc(db, film, "dvd")
    # The endpoint reads the real clock, so the price is dated from it rather than NOW.
    await _price(db, film, "blu_ray", "9.99", checked=utcnow())

    async with _as(db, mark) as client:
        response = await client.get("/api/v1/collection/value")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == "9.99"
    assert body["basis"] == "current asking prices"
    assert (body["discs"], body["pricedDiscs"], body["uncheckedDiscs"]) == (2, 1, 1)
    assert body["due"] == 1
    assert body["minSample"] == 3


async def test_only_an_admin_can_start_a_run(
    db: AsyncSession, ebay_keys: None, background: list[uuid.UUID]
) -> None:
    mark = await _person(db, UserRole.viewer)
    async with _as(db, mark) as client:
        response = await client.post("/api/v1/collection/value/refresh")
    assert response.status_code == 403
    assert background == []


async def test_the_button_claims_a_run_and_carries_it_on_after_the_response(
    db: AsyncSession, ebay_keys: None, background: list[uuid.UUID]
) -> None:
    craig = await _person(db, UserRole.admin)
    await _films_due(db, 2)

    async with _as(db, craig) as client:
        response = await client.post("/api/v1/collection/value/refresh")
        again = await client.post("/api/v1/collection/value/refresh")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "started"
    assert body["due"] == 2
    run = await db.get(ValuationRun, uuid.UUID(body["run"]["id"]))
    assert run is not None
    assert (run.trigger, run.started_by, run.status) == ("admin", craig.id, "running")
    assert background == [run.id]
    assert again.json()["outcome"] == "running"
    assert len(background) == 1


async def test_the_button_says_so_when_ebay_is_not_configured(
    db: AsyncSession, no_ebay_keys: None, background: list[uuid.UUID]
) -> None:
    craig = await _person(db, UserRole.admin)
    await _films_due(db, 1)

    async with _as(db, craig) as client:
        response = await client.post("/api/v1/collection/value/refresh")

    assert response.status_code == 503
    assert await db.scalar(select(func.count()).select_from(ValuationRun)) == 0
    assert background == []


async def test_a_copy_carries_its_stored_price(db: AsyncSession) -> None:
    mark = await _person(db, UserRole.viewer)
    film = await _film(db, "Heat", tmdb_id=990_000_949)
    boxed = await _disc(db, film, "4k_uhd", "blu_ray")
    digital = await _disc(db, film, "download")
    await _price(db, film, "4k_uhd", "19.50", checked=utcnow())
    await _price(db, film, "blu_ray", "4.00", checked=utcnow())

    async with _as(db, mark) as client:
        response = await client.get(f"/api/v1/movies/{film.id}/copies")

    assert response.status_code == 200, response.text
    copies = {copy["id"]: copy for copy in response.json()}
    priced = copies[str(boxed.id)]["valuation"]
    assert (priced["formatCode"], priced["price"], priced["status"]) == (
        "4k_uhd",
        "19.50",
        "priced",
    )
    assert priced["basis"] == "current asking prices"
    assert copies[str(digital.id)]["valuation"] is None
