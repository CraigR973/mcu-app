"""Valuation runs and the total — Batch T6, snag 7. Postgres-backed, so these run in CI.

**What this proves:** one eBay search per film and format however many copies there are;
each disc valued as a used copy, a value from before Batch X6 priced again at once, and the
used-to-New factor measured from the stored values and applied to all of them at a run's end;
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
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.config import settings
from src.database import get_db
from src.ebay.client import EbayError
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.ebay_sold import EbayUsedRun
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.valuation import DiscValuation, ValuationRun
from src.services.valuation import (
    DAILY_SHARE,
    FALLBACK_FACTOR,
    MIN_FACTOR_PAIRS,
    MIN_RUN_BUDGET,
    UsedFactor,
    collection_value,
    count_due,
    day_start,
    due_films,
    rescale,
    start_run,
    used_factors,
    valuations_for_movie,
    work_run,
)

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
    db: AsyncSession,
    film: Movie,
    format_code: str,
    price: str | None,
    *,
    checked: datetime,
    before_x6: bool = False,
) -> DiscValuation:
    """A stored value as a run since Batch X6 writes one: ten used listings, or one.

    ``before_x6`` writes one as runs did before it, with no groups: the largest group's
    median, which X6 makes due and leaves out of every total.
    """
    amount = Decimal(price) if price is not None else None
    groups: dict[str, Any] = {}
    if not before_x6:
        groups = {
            "value_basis": "used" if amount is not None else None,
            "low": amount,
            "high": amount,
            "used_median": amount,
            "used_count": 10 if amount is not None else 1,
            "new_count": 0,
        }
    stored = DiscValuation(
        id=uuid.uuid4(),
        movie_id=film.id,
        format_code=format_code,
        status="priced" if price is not None else "not_priced",
        price=amount,
        currency="GBP",
        sample_size=10 if price is not None else 1,
        matched=10,
        considered=200,
        basis="current asking prices",
        search_query=f"{film.title} {format_code}",
        checked_utc=checked,
        **groups,
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
    # AA10b: postage-in lower quartile of standard used Buy It Now listings.
    blu_ray = stored[(blade_runner.id, "blu_ray")]
    assert (blu_ray.status, blu_ray.price, blu_ray.sample_size) == ("priced", Decimal("7.05"), 24)
    assert (blu_ray.value_basis, blu_ray.condition_label, blu_ray.factor) == (
        "used_quartile",
        "Used",
        None,
    )
    assert (blu_ray.low, blu_ray.high) == (Decimal("3.72"), Decimal("65.99"))
    assert (blu_ray.used_count, blu_ray.new_median, blu_ray.new_count) == (24, Decimal("9.99"), 29)
    assert blu_ray.basis == "current asking prices"
    assert blu_ray.checked_utc == NOW and blu_ray.run_id == run.id
    assert stored[(blade_runner.id, "4k_uhd")].price == Decimal("20.34")
    assert stored[(jaws.id, "blu_ray")].price == Decimal("8.18")
    assert stored[(jaws.id, "dvd")].status == "not_priced"
    assert stored[(jaws.id, "dvd")].price is None
    assert (stored[(jaws.id, "dvd")].used_count, stored[(jaws.id, "dvd")].new_count) == (0, 0)
    assert stored[(mummy.id, "dvd")].search_query == "The Mummy DVD"
    assert (digital.id, "dvd") not in stored

    value = await collection_value(db, now=NOW)
    assert value.total == Decimal("7.05") * 2 + Decimal("20.34") + Decimal("8.18")
    assert (value.discs, value.priced, value.not_priced, value.unchecked) == (6, 4, 2, 0)
    assert value.checked_from == value.checked_to == NOW
    assert value.due == 0
    assert value.latest_run is not None and value.latest_run.id == run.id


async def test_a_value_from_before_x6_is_due_counts_nowhere_and_is_replaced(
    db: AsyncSession,
) -> None:
    """Batch X6: a stored value from before it is a new copy's price (#209), so it is priced
    again at once rather than in 30 days, and until then no total, list or page shows it."""
    film = await _film(db, "Blade Runner 2049", tmdb_id=990_335_985)
    await _disc(db, film, "blu_ray")
    await _price(db, film, "blu_ray", "9.99", checked=NOW - timedelta(days=1), before_x6=True)

    assert [due.movie_id for due in await due_films(db, now=NOW, limit=10)] == [film.id]
    value = await collection_value(db, now=NOW)
    assert (value.total, value.priced, value.not_priced, value.unchecked) == (None, 0, 0, 1)
    assert await valuations_for_movie(db, film.id) == {}

    await _run_now(db, FakeEbay({"Blade Runner 2049 Blu-ray": BLADE_RUNNER}))

    value = await collection_value(db, now=NOW)
    assert (value.total, value.priced, value.unchecked) == (Decimal("7.05"), 1, 0)
    assert (await valuations_for_movie(db, film.id))["blu_ray"].value_basis == "used_quartile"


async def test_aa10b_reprice_waits_for_admin_and_replaces_the_old_median(
    db: AsyncSession,
) -> None:
    film = await _film(db, "Blade Runner 2049", tmdb_id=990_335_986)
    await _disc(db, film, "blu_ray")
    old = await _price(db, film, "blu_ray", "5.45", checked=NOW - timedelta(seconds=1))
    await db.commit()

    assert await count_due(db, now=NOW) == 0
    assert await count_due(db, now=NOW, include_reprice=True) == 1
    assert (await start_run(db, trigger="job", now=NOW)).reason == "nothing_due"

    started = await start_run(db, trigger="admin", now=NOW)
    assert started.reason == "started" and started.run is not None
    await work_run(
        db,
        FakeEbay({"Blade Runner 2049 Blu-ray": BLADE_RUNNER}),
        started.run.id,
        clock=lambda: NOW,
    )
    await db.refresh(old)
    assert (old.price, old.value_basis) == (Decimal("7.05"), "used_quartile")
    assert await count_due(db, now=NOW, include_reprice=True) == 0


async def test_aa10b_one_admin_start_continues_legacy_reprice_on_later_days(
    db: AsyncSession,
) -> None:
    films = await _films_due(db, 6)
    for film in films:
        await _price(db, film, "blu_ray", "5.45", checked=NOW - timedelta(seconds=1))
    scarce = await db.scalar(select(DiscValuation).where(DiscValuation.movie_id == films[-1].id))
    assert scarce is not None
    scarce.value_basis = "new_scaled"
    scarce.factor = Decimal("0.50")
    scarce.used_count = 1
    scarce.new_count = 3
    scarce.new_median = Decimal("10.90")
    db.add(_spent_today(DAILY_SHARE - 3))
    await db.commit()

    assert await count_due(db, now=NOW, include_reprice=True) == 6
    assert (await start_run(db, trigger="job", now=NOW)).reason == "nothing_due"
    first = await start_run(db, trigger="admin", now=NOW)
    assert first.run is not None and first.run.budget == 3
    finished = await work_run(db, FakeEbay(), first.run.id, clock=lambda: NOW)
    assert finished.remaining == 3

    second = await start_run(db, trigger="job", now=NOW + timedelta(days=1))
    assert second.run is not None
    assert second.run.report == {"priceRule": "used_quartile"}
    continued = await work_run(db, FakeEbay(), second.run.id, clock=lambda: NOW + timedelta(days=1))
    assert (continued.calls, continued.remaining) == (3, 0)
    await db.refresh(scarce)
    assert scarce.value_basis is None


async def _scaled(db: AsyncSession, film: Movie, *, new: str, factor: str) -> DiscValuation:
    """A New-based value: two used listings, five New at ``new``, at ``factor``."""
    stored = await _price(db, film, "4k_uhd", "1.00", checked=NOW - timedelta(days=1))
    stored.value_basis, stored.factor = "new_scaled", Decimal(factor)
    stored.price = (Decimal(new) * Decimal(factor)).quantize(Decimal("0.01"))
    stored.used_count, stored.used_median = 2, Decimal("5.00")
    stored.new_count, stored.new_median = 5, Decimal(new)
    await db.flush()
    return stored


async def test_the_factor_is_measured_from_the_stored_values_and_every_run_moves_to_it(
    db: AsyncSession,
) -> None:
    """Below 20 films with both groups the fallback stands; from 20, their median ratio, and
    the end of a run re-scales every New-based value of that format to it."""
    for index in range(MIN_FACTOR_PAIRS - 1):
        film = await _film(db, f"Paired {index:02d}", tmdb_id=990_100_000 + index)
        await _disc(db, film, "4k_uhd")
        stored = await _price(db, film, "4k_uhd", "7.00", checked=NOW - timedelta(days=1))
        stored.new_median, stored.new_count = Decimal("10.00"), 4
    scaled_film = await _film(db, "Thinly Used", tmdb_id=990_100_100)
    await _disc(db, scaled_film, "4k_uhd")
    scaled = await _scaled(db, scaled_film, new="20.00", factor="0.60")
    await db.flush()

    assert (await used_factors(db))["4k_uhd"] == UsedFactor(FALLBACK_FACTOR, 0)

    twentieth = await _film(db, "Paired 19", tmdb_id=990_100_019)
    await _disc(db, twentieth, "4k_uhd")
    stored = await _price(db, twentieth, "4k_uhd", "7.00", checked=NOW - timedelta(days=1))
    stored.new_median, stored.new_count = Decimal("10.00"), 4
    await db.flush()

    assert (await used_factors(db))["4k_uhd"] == UsedFactor(Decimal("0.70"), MIN_FACTOR_PAIRS)

    # These synthetic stored figures represent an already completed AA10b campaign;
    # the new film alone is due, and its run ends by re-scaling the others.
    await db.execute(
        update(DiscValuation)
        .where(DiscValuation.value_basis == "used")
        .values(value_basis="used_quartile")
    )
    added = await _film(db, "Blade Runner 2049", tmdb_id=990_335_986)
    await _disc(db, added, "blu_ray")
    run = await _run_now(db, FakeEbay({"Blade Runner 2049 Blu-ray": BLADE_RUNNER}))
    assert run.status == "finished"

    await db.refresh(scaled)
    assert (scaled.price, scaled.factor) == (Decimal("14.00"), Decimal("0.70"))
    assert await rescale(db, await used_factors(db)) == 0


async def test_a_value_reached_from_new_carries_its_factor_by_the_tables_own_rule(
    db: AsyncSession,
) -> None:
    film = await _film(db, "Heat", tmdb_id=990_000_950)
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add(
                DiscValuation(
                    id=uuid.uuid4(),
                    movie_id=film.id,
                    format_code="blu_ray",
                    status="priced",
                    price=Decimal("6.00"),
                    value_basis="new_scaled",
                    factor=None,
                    used_count=0,
                    new_count=4,
                    basis="current asking prices",
                    search_query="Heat Blu-ray",
                    checked_utc=NOW,
                )
            )


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

    started = await start_run(db, trigger="admin", now=NOW)
    assert started.run is not None
    run = await work_run(db, ebay, started.run.id, clock=lambda: NOW)

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
    assert body["valuedAs"] == "as used copies"
    assert (body["discs"], body["pricedDiscs"], body["uncheckedDiscs"]) == (2, 1, 1)
    # The unpriced DVD and the older-rule Blu-ray both need the one-time re-price.
    assert body["due"] == 2
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


async def test_used_sales_first_pass_is_admin_only_and_does_not_run_on_read(
    db: AsyncSession, ebay_keys: None
) -> None:
    mark = await _person(db, UserRole.viewer)
    async with _as(db, mark) as client:
        read = await client.get("/api/v1/collection/value")
        refused = await client.post("/api/v1/collection/value/sales/refresh")
    assert read.status_code == 200
    assert read.json()["salesRun"] is None
    assert refused.status_code == 403
    assert await db.scalar(select(func.count()).select_from(EbayUsedRun)) == 0

    craig = await _person(db, UserRole.admin)
    async with _as(db, craig) as client:
        started = await client.post("/api/v1/collection/value/sales/refresh")
        again = await client.post("/api/v1/collection/value/sales/refresh")
    assert started.status_code == 200, started.text
    assert started.json()["outcome"] == "started"
    assert again.json()["outcome"] == "running"
    run = await db.scalar(select(EbayUsedRun))
    assert run is not None and run.trigger == "admin" and run.calls == 0


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
    # Batch X6: how the value was reached, its range, and both groups' sizes.
    assert (priced["valueBasis"], priced["factor"], priced["low"], priced["high"]) == (
        "used",
        None,
        "19.50",
        "19.50",
    )
    assert (priced["usedCount"], priced["newCount"], priced["valuedAs"]) == (
        10,
        0,
        "as used copies",
    )
    # Batch V8: eBay's own sold listings, searched with the words the value was.
    assert priced["soldListingsUrl"] == (
        "https://www.ebay.co.uk/sch/i.html?_nkw=Heat+4k_uhd&_sacat=617&LH_Sold=1&LH_Complete=1"
    )
    assert copies[str(digital.id)]["valuation"] is None
