"""The bid trial — Batch V6, snag 2's first step. Postgres-backed where it needs to be.

**What this proves:** a sample of priced, owned films, a third per format; one search per
film asking for Buy It Now and auctions together; an auction counted only with a bid and
past the same matcher (the right film and format, a UK seller, a standard edition); the
asking price taken by the valuation's own rule from the same search; how many auctions end
within a day; whether auctions took Buy It Now listings' places; the totals on each basis;
calls counted against the day's share; never overlapping a valuation run; **no price
saved**; the report kept on the run row; and the two admin-only routes.

**What it does not:** a live eBay search. The trial is Craig's to run (#228). Every payload
here is eBay's own captured shape: the Blade Runner 2049 search
(`fixtures/ebay_browse_blade_runner_2049.json`) and, for auctions, **edited copies of the one
auction it holds**. Nobody had bid on that one, so each auction with bids below is that
listing with its bid count, current bid, end date, and sometimes title or country changed.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.config import settings
from src.database import get_db
from src.ebay.bids import BUY_IT_NOW_AND_AUCTIONS, auction_from_summary
from src.ebay.client import EbayError
from src.ebay.estimate import estimate_price
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.valuation import DiscValuation, ValuationRun
from src.schemas.bid_trial import BidTrialReport, TrialBids, TrialResults
from src.services.bid_trial import (
    SAMPLE_SIZE,
    SampledFilm,
    available_films,
    judge_search,
    quotas,
    sample_films,
    start_trial,
    summarise_trial,
    work_trial,
)
from src.services.valuation import (
    DAILY_SHARE,
    budget_left,
    collection_value,
    start_run,
    valuation_from,
)

NOW = datetime(2026, 10, 1, 1, 0)
FIXTURES = Path(__file__).parent / "fixtures"
BLADE_RUNNER = json.loads((FIXTURES / "ebay_browse_blade_runner_2049.json").read_text())
JAWS = json.loads((FIXTURES / "ebay_browse_jaws.json").read_text())
EMPTY: dict[str, Any] = {"itemSummaries": []}
#: The one auction in the captured search: Buy It Now at £8.12 too, no bids, opening at £5.45.
REAL_AUCTION = next(
    entry for entry in BLADE_RUNNER["itemSummaries"] if "AUCTION" in entry["buyingOptions"]
)


def _auction(
    item: int,
    *,
    bids: int,
    bid: str,
    ends_in: timedelta = timedelta(days=3),
    title: str = "Blade Runner 2049 Blu-ray",
    country: str = "GB",
    now: datetime = NOW,
) -> dict[str, Any]:
    """The captured auction, edited into an auction-only listing with these bids."""
    entry = copy.deepcopy(REAL_AUCTION)
    current = {"value": bid, "currency": "GBP"}
    entry.update(
        itemId=f"v1|{item}|0",
        title=title,
        buyingOptions=["AUCTION"],
        bidCount=bids,
        currentBidPrice=current,
        price=current,
        itemEndDate=(now + ends_in).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        itemLocation={**entry["itemLocation"], "country": country},
    )
    return entry


def _auctions(now: datetime = NOW) -> list[dict[str, Any]]:
    """Eight auctions: three count, and the rest do not, each for its own reason."""
    return [
        _auction(1, bids=2, bid="6.00", ends_in=timedelta(hours=3), now=now),
        _auction(2, bids=1, bid="4.00", ends_in=timedelta(days=3), now=now),
        _auction(3, bids=5, bid="9.50", ends_in=timedelta(days=6), now=now),
        _auction(4, bids=0, bid="0.99", now=now),  # nobody has bid: the opening price
        _auction(5, bids=3, bid="7.00", country="US", now=now),  # overseas
        _auction(6, bids=4, bid="20.00", title="Blade Runner 2049 Steelbook Blu-ray", now=now),
        _auction(7, bids=2, bid="1.50", title="Blade Runner 2049 DVD", now=now),  # format
        _auction(8, bids=6, bid="3.00", title="Blade Runner Final Cut Blu-ray", now=now),  # film
    ]


def _with_auctions(now: datetime = NOW) -> dict[str, Any]:
    """The captured search with its last eight listings swapped for the eight auctions, so
    it still returns 200 of eBay's 304."""
    return {**BLADE_RUNNER, "itemSummaries": BLADE_RUNNER["itemSummaries"][:192] + _auctions(now)}


AUCTIONS = _auctions()
WITH_AUCTIONS = _with_auctions()


def _sampled(
    title: str = "Blade Runner 2049",
    format_code: str = "blu_ray",
    *,
    copies: int = 1,
    stored: str = "11.50",
    stored_sample: int = 25,
) -> SampledFilm:
    return SampledFilm(
        movie_id=uuid.uuid4(),
        format_code=format_code,
        title=title,
        identified=True,
        copies=copies,
        stored_price=Decimal(stored),
        stored_sample=stored_sample,
    )


class FakeEbay:
    """Answers by query, records each search's filter, counts every call, never retries."""

    marketplace_id = "EBAY_GB"
    attempts_per_search = 1

    def __init__(self, answers: dict[str, dict[str, Any] | Exception] | None = None) -> None:
        self.answers = answers or {}
        self.default: dict[str, Any] | Exception = EMPTY
        self.searches: list[tuple[str, str | None]] = []
        self.search_calls = 0

    async def search(
        self,
        query: str,
        *,
        limit: int = 200,
        category_ids: str | None = None,
        filter: str | None = None,  # noqa: A002 - Browse's own parameter name
    ) -> dict[str, Any]:
        del limit, category_ids
        self.search_calls += 1
        self.searches.append((query, filter))
        answer = self.answers.get(query, self.default)
        if isinstance(answer, Exception):
            raise answer
        return answer


# ---------------------------------------------------------------------------
# Reading an auction
# ---------------------------------------------------------------------------


async def test_the_captured_auction_reads_as_one_with_no_bids_at_its_opening_price() -> None:
    auction = auction_from_summary(REAL_AUCTION)

    assert auction is not None
    assert auction.bid_count == 0
    # The current bid, not its Buy It Now price of £8.12, is the listing's price.
    assert auction.listing.price == Decimal("5.45")
    assert auction.ends_utc == datetime(2026, 9, 18, 10, 57, 23)


async def test_a_buy_it_now_listing_is_not_an_auction_and_an_auction_needs_a_current_bid() -> None:
    buy_it_now = next(
        entry
        for entry in BLADE_RUNNER["itemSummaries"]
        if entry["buyingOptions"] == ["FIXED_PRICE"]
    )
    assert auction_from_summary(buy_it_now) is None

    no_bid_price = {key: value for key, value in AUCTIONS[0].items() if key != "currentBidPrice"}
    assert auction_from_summary(no_bid_price) is None

    # An auction summary without a ``price`` still reads, on its current bid.
    no_price = {key: value for key, value in AUCTIONS[0].items() if key != "price"}
    auction = auction_from_summary(no_price)
    assert auction is not None
    assert auction.listing.price == Decimal("6.00")


# ---------------------------------------------------------------------------
# One search, judged
# ---------------------------------------------------------------------------


async def test_the_asking_price_is_the_one_a_valuation_takes_from_the_same_search() -> None:
    """Without auctions in it, the trial's asking price is exactly what a run would store."""
    film = _sampled()
    stored_rule = valuation_from(
        await estimate_price(
            FakeEbay({"Blade Runner 2049 Blu-ray": BLADE_RUNNER}),
            film_title="Blade Runner 2049",
            format_code="blu_ray",
        ),
        "blu_ray",
    )

    result = judge_search(BLADE_RUNNER, film=film, marketplace_id="EBAY_GB", now=NOW)

    assert result.asking is not None
    assert (result.asking.price, result.asking.sampleSize) == ("9.99", 29)
    assert (Decimal(result.asking.price), result.asking.sampleSize) == (
        stored_rule.price,
        stored_rule.sample_size,
    )
    # The captured auction matches and has no bids, so it is counted as neither.
    assert result.bids == TrialBids(counted=0, withoutBids=1, rejected=0, price=None, endingSoon=0)


async def test_an_auction_counts_only_with_a_bid_and_past_the_same_matcher() -> None:
    result = judge_search(WITH_AUCTIONS, film=_sampled(), marketplace_id="EBAY_GB", now=NOW)

    # Counted: £6.00, £4.00 and £9.50, so a bid price of £6.00; one ends within 24 hours.
    # Without bids: the edited one and the captured one. Turned away: overseas, a
    # steelbook, a DVD and another film.
    assert result.bids == TrialBids(
        counted=3, withoutBids=2, rejected=4, price="6.00", endingSoon=1
    )
    assert result.results == TrialResults(total=304, returned=200, buyItNow=192, auctionOnly=8)

    # The asking price comes from the Buy It Now listings alone, by the valuation's rule.
    buy_it_now_only = {**BLADE_RUNNER, "itemSummaries": BLADE_RUNNER["itemSummaries"][:192]}
    expected = valuation_from(
        await estimate_price(
            FakeEbay({"Blade Runner 2049 Blu-ray": buy_it_now_only}),
            film_title="Blade Runner 2049",
            format_code="blu_ray",
        ),
        "blu_ray",
    )
    assert result.asking is not None
    assert result.asking.price == str(expected.price)
    assert result.asking.sampleSize == expected.sample_size


async def test_two_auctions_with_bids_are_not_a_price() -> None:
    payload = {**BLADE_RUNNER, "itemSummaries": BLADE_RUNNER["itemSummaries"][:198] + AUCTIONS[:2]}

    result = judge_search(payload, film=_sampled(), marketplace_id="EBAY_GB", now=NOW)

    assert result.bids is not None
    assert (result.bids.counted, result.bids.price) == (2, None)


# ---------------------------------------------------------------------------
# The report's figures
# ---------------------------------------------------------------------------


def _judged(
    title: str,
    format_code: str,
    *,
    copies: int,
    stored: str,
    asking: str | None,
    bids: list[str],
    ending_soon: int = 0,
    total: int | None = None,
    auction_only: int = 0,
) -> Any:
    """A film's result without a search: the figures are what the summary is tested on."""
    film = _sampled(title, format_code, copies=copies, stored=stored, stored_sample=10)
    entries = [
        _auction(index, bids=1, bid=bid, ends_in=timedelta(hours=2 if index < ending_soon else 72))
        for index, bid in enumerate(bids)
    ]
    for entry in entries:
        entry["title"] = f"{title} {'DVD' if format_code == 'dvd' else 'Blu-ray'}"
    buy_it_now = []
    if asking is not None:
        for index in range(5):
            listing = copy.deepcopy(REAL_AUCTION)
            listing.update(
                itemId=f"v1|9{index}|0",
                title=f"{title} {'DVD' if format_code == 'dvd' else 'Blu-ray'}",
                buyingOptions=["FIXED_PRICE"],
                price={"value": asking, "currency": "GBP"},
            )
            buy_it_now.append(listing)
    filler = [
        {
            **copy.deepcopy(REAL_AUCTION),
            "itemId": f"v1|8{index}|0",
            "buyingOptions": ["AUCTION"],
            "bidCount": 0,
            "title": "Something Else Entirely Blu-ray",
        }
        for index in range(auction_only - len(entries))
    ]
    listings = buy_it_now + entries + filler
    payload = {"total": total if total is not None else len(listings), "itemSummaries": listings}
    return judge_search(payload, film=film, marketplace_id="EBAY_GB", now=NOW)


async def test_the_totals_on_each_basis_count_every_copy_and_say_how_many_discs() -> None:
    films = [
        # Two copies; bids at £6, asking £10: bids are 60% of asking.
        _judged(
            "Heat",
            "blu_ray",
            copies=2,
            stored="12.00",
            asking="10.00",
            bids=["5.00", "6.00", "7.00"],
            ending_soon=3,
        ),
        # No auctions with bids: asking only.
        _judged("Alien", "blu_ray", copies=1, stored="8.00", asking="9.00", bids=[]),
        # Too few Buy It Now listings now, but bids: bids only and the blend have it.
        _judged(
            "Kes",
            "dvd",
            copies=1,
            stored="4.00",
            asking=None,
            bids=["2.00", "3.00", "4.00", "5.00"],
            total=300,
            auction_only=200,
        ),
    ]
    failed = films[0].model_copy(
        update={"title": "Jaws", "results": None, "asking": None, "bids": None, "error": "HTTP 500"}
    )

    overall = summarise_trial([*films, failed], None)

    assert (overall.films, overall.withBids, overall.withBidsEndingSoon) == (3, 2, 1)
    assert (overall.auctionsCounted, overall.endingSoon) == (7, 3)
    # Heat 6.00/10.00; Kes has no asking price to compare with.
    assert (overall.compared, overall.bidToAskingPercent) == (1, 60)
    assert (overall.stored.total, overall.stored.discs) == ("36.00", 4)
    assert (overall.asking.total, overall.asking.discs) == ("29.00", 3)
    assert (overall.bids.total, overall.bids.discs) == ("15.50", 3)
    blend = overall.blend
    assert (blend.total, blend.discs, blend.fromBids, blend.fromAsking) == ("24.50", 4, 3, 1)
    # Kes's 300 results stopped at 200, and auctions with no Buy It Now held 200 places.
    assert (overall.cut, overall.auctionOnlyPlaces, overall.askingLost) == (1, 200, 1)
    assert (overall.askingSample, overall.storedSample) == (10, 30)

    dvd = summarise_trial(films, "dvd")
    assert (dvd.formatCode, dvd.films, dvd.withBids, dvd.bids.total) == ("dvd", 1, 1, "3.50")
    nothing = summarise_trial(films, "4k_uhd")
    assert (nothing.films, nothing.stored.total, nothing.bidToAskingPercent) == (0, "0.00", None)


# ---------------------------------------------------------------------------
# The sample
# ---------------------------------------------------------------------------


async def test_a_third_each_and_what_one_format_cannot_fill_goes_to_the_others() -> None:
    plenty = {"4k_uhd": 500, "blu_ray": 900, "dvd": 300}
    assert quotas(plenty, SAMPLE_SIZE) == {"4k_uhd": 34, "blu_ray": 33, "dvd": 33}
    assert quotas({"4k_uhd": 500, "blu_ray": 900, "dvd": 10}, 100) == {
        "4k_uhd": 45,
        "blu_ray": 45,
        "dvd": 10,
    }
    assert quotas({"blu_ray": 7}, 100) == {"4k_uhd": 0, "blu_ray": 7, "dvd": 0}
    assert quotas({}, 100) == {"4k_uhd": 0, "blu_ray": 0, "dvd": 0}


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        assert await available_films(session) == {}, "priced discs leaked into the test DB"
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


async def _film(db: AsyncSession, title: str) -> Movie:
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=990_000_000 + uuid.uuid4().int % 1_000_000,
        title=title,
        original_title=title,
        media_type="film",
    )
    db.add(film)
    await db.flush()
    return film


async def _disc(
    db: AsyncSession, film: Movie, *formats: str, listing_status: str = "in_collection"
) -> None:
    db.add(
        CollectionItem(
            id=uuid.uuid4(), movie_id=film.id, formats=list(formats), listing_status=listing_status
        )
    )
    await db.flush()


async def _price(db: AsyncSession, film: Movie, format_code: str, price: str | None) -> None:
    db.add(
        DiscValuation(
            id=uuid.uuid4(),
            movie_id=film.id,
            format_code=format_code,
            status="priced" if price is not None else "not_priced",
            price=Decimal(price) if price is not None else None,
            currency="GBP",
            sample_size=12 if price is not None else 1,
            matched=12,
            considered=200,
            basis="current asking prices",
            search_query=f"{film.title} {format_code}",
            checked_utc=NOW - timedelta(days=5),
        )
    )
    await db.flush()


async def _priced(
    db: AsyncSession, title: str, format_code: str, price: str, copies: int = 1
) -> Movie:
    film = await _film(db, title)
    for _ in range(copies):
        await _disc(db, film, format_code)
    await _price(db, film, format_code, price)
    return film


async def test_the_sample_is_owned_films_with_a_stored_price(db: AsyncSession) -> None:
    heat = await _priced(db, "Heat", "blu_ray", "9.99", copies=2)
    await _priced(db, "Alien", "4k_uhd", "24.00")
    await _priced(db, "Kes", "dvd", "3.50")
    unpriced = await _film(db, "Too Rare")
    await _disc(db, unpriced, "blu_ray")
    await _price(db, unpriced, "blu_ray", None)
    sold = await _film(db, "Sold On")
    await _disc(db, sold, "blu_ray", listing_status="sold")
    await _price(db, sold, "blu_ray", "5.00")
    boxed = await _film(db, "Boxed")
    await _disc(db, boxed, "4k_uhd", "blu_ray")  # valued as its 4K
    await _price(db, boxed, "blu_ray", "6.00")  # a Blu-ray price no owned disc stands behind

    sample = await sample_films(db)

    assert {(film.title, film.format_code, film.copies) for film in sample} == {
        ("Heat", "blu_ray", 2),
        ("Alien", "4k_uhd", 1),
        ("Kes", "dvd", 1),
    }
    assert next(film for film in sample if film.movie_id == heat.id).stored_price == Decimal("9.99")


async def test_the_sample_takes_its_shares_at_random_within_each_format(db: AsyncSession) -> None:
    for index in range(3):
        await _priced(db, f"Four K {index}", "4k_uhd", "20.00")
        await _priced(db, f"Blu {index}", "blu_ray", "10.00")
    await _priced(db, "Only DVD", "dvd", "3.00")

    sample = await sample_films(db, size=6)

    counts = {
        code: sum(1 for film in sample if film.format_code == code)
        for code in ("4k_uhd", "blu_ray", "dvd")
    }
    assert counts == {"4k_uhd": 3, "blu_ray": 2, "dvd": 1}


# ---------------------------------------------------------------------------
# A trial
# ---------------------------------------------------------------------------


async def _snapshot(db: AsyncSession) -> list[tuple[Any, ...]]:
    rows = await db.execute(
        select(
            DiscValuation.id,
            DiscValuation.price,
            DiscValuation.sample_size,
            DiscValuation.checked_utc,
            DiscValuation.run_id,
        ).order_by(DiscValuation.id)
    )
    return [tuple(row) for row in rows]


async def _trial_now(db: AsyncSession, ebay: FakeEbay, *, now: datetime = NOW) -> ValuationRun:
    outcome = await start_trial(db, started_by=None, now=now)
    assert outcome.reason == "started", outcome
    assert outcome.run is not None
    return await work_trial(db, ebay, outcome.run.id, clock=lambda: now)


async def test_a_trial_searches_each_film_once_for_both_and_saves_no_prices(
    db: AsyncSession,
) -> None:
    await _priced(db, "Blade Runner 2049", "blu_ray", "11.50", copies=2)
    await _priced(db, "Jaws", "blu_ray", "7.00")
    await _priced(db, "Heat", "dvd", "3.00")
    before = await _snapshot(db)
    ebay = FakeEbay({"Blade Runner 2049 Blu-ray": WITH_AUCTIONS, "Jaws Blu-ray": JAWS})

    run = await _trial_now(db, ebay)

    assert sorted(ebay.searches) == [
        ("Blade Runner 2049 Blu-ray", BUY_IT_NOW_AND_AUCTIONS),
        ("Heat DVD", BUY_IT_NOW_AND_AUCTIONS),
        ("Jaws Blu-ray", BUY_IT_NOW_AND_AUCTIONS),
    ]
    assert await _snapshot(db) == before, "a trial must not save a price"
    assert (run.trigger, run.status, run.calls, run.failed, run.remaining) == (
        "trial",
        "finished",
        3,
        0,
        0,
    )
    # Blade Runner has a bid price; Jaws and Heat do not.
    assert (run.priced, run.not_priced) == (1, 2)

    report = BidTrialReport.model_validate(run.report)
    assert report.sampled == 3
    assert [film.title for film in report.films if film.bids and film.bids.price] == [
        "Blade Runner 2049"
    ]
    assert (report.overall.films, report.overall.withBids) == (3, 1)
    assert (report.overall.blend.fromBids, report.overall.stored.discs) == (2, 4)
    assert [summary.formatCode for summary in report.formats] == ["4k_uhd", "blu_ray", "dvd"]
    # Its calls came out of the day's share.
    assert await budget_left(db, now=NOW) == DAILY_SHARE - 3


async def test_a_trial_stops_at_its_budget_and_keeps_what_it_found(db: AsyncSession) -> None:
    for index in range(6):
        await _priced(db, f"Film {index}", "blu_ray", "10.00")
    db.add(
        ValuationRun(
            id=uuid.uuid4(),
            trigger="job",
            status="budget_spent",
            started_utc=NOW - timedelta(minutes=30),
            heartbeat_utc=NOW - timedelta(minutes=5),
            finished_utc=NOW - timedelta(minutes=5),
            budget=DAILY_SHARE,
            calls=DAILY_SHARE - 4,
        )
    )
    await db.flush()

    run = await _trial_now(db, FakeEbay())

    assert (run.status, run.budget, run.calls, run.remaining) == ("budget_spent", 4, 4, 2)
    report = BidTrialReport.model_validate(run.report)
    assert (report.sampled, len(report.films)) == (6, 4)
    assert await budget_left(db, now=NOW) == 0


async def test_no_trial_starts_without_a_share_left_or_a_priced_film(db: AsyncSession) -> None:
    nothing = await start_trial(db, started_by=None, now=NOW)
    assert (nothing.reason, nothing.run, nothing.sampled) == ("nothing_to_sample", None, 0)

    await _priced(db, "Heat", "blu_ray", "9.99")
    db.add(
        ValuationRun(
            id=uuid.uuid4(),
            trigger="job",
            status="budget_spent",
            started_utc=NOW - timedelta(minutes=30),
            heartbeat_utc=NOW,
            budget=DAILY_SHARE,
            calls=DAILY_SHARE,
        )
    )
    await db.flush()
    spent = await start_trial(db, started_by=None, now=NOW)
    assert (spent.reason, spent.run, spent.sampled, spent.budget_left) == (
        "budget_spent",
        None,
        1,
        0,
    )


async def test_a_trial_and_a_valuation_run_never_spend_the_share_at_once(
    db: AsyncSession,
) -> None:
    film = await _film(db, "Due Film")
    await _disc(db, film, "blu_ray")  # never priced: due a valuation
    await _priced(db, "Heat", "blu_ray", "9.99")

    valuation = await start_run(db, trigger="job", now=NOW)
    assert valuation.reason == "started" and valuation.run is not None
    blocked = await start_trial(db, started_by=None, now=NOW)
    assert (blocked.reason, blocked.run) == ("running", None)

    valuation.run.status = "finished"
    await db.commit()
    trial = await start_trial(db, started_by=None, now=NOW)
    assert trial.reason == "started"
    assert (await start_run(db, trigger="job", now=NOW)).reason == "running"


async def test_a_failed_search_is_reported_and_too_many_requests_stops_the_trial(
    db: AsyncSession,
) -> None:
    await _priced(db, "Blade Runner 2049", "blu_ray", "11.50")
    await _priced(db, "Heat", "4k_uhd", "20.00")
    ebay = FakeEbay({"Heat 4K": EbayError("eBay search failed (HTTP 500)", 500)})
    ebay.default = WITH_AUCTIONS

    run = await _trial_now(db, ebay)

    assert (run.status, run.failed, run.calls) == ("finished", 1, 2)
    report = BidTrialReport.model_validate(run.report)
    failed = next(film for film in report.films if film.title == "Heat")
    assert (failed.error, failed.results, failed.bids) == (
        "eBay search failed (HTTP 500)",
        None,
        None,
    )
    assert report.overall.films == 1

    await _priced(db, "Jaws", "dvd", "4.00")
    refused = FakeEbay()
    refused.default = EbayError("eBay search failed (HTTP 429)", 429)
    stopped = await _trial_now(db, refused, now=NOW + timedelta(hours=1))
    assert (stopped.status, stopped.calls, stopped.failed) == ("stopped", 1, 1)
    assert stopped.remaining == 2


async def test_the_values_last_run_is_never_a_trial(db: AsyncSession) -> None:
    await _priced(db, "Heat", "blu_ray", "9.99")
    db.add(
        ValuationRun(
            id=uuid.uuid4(),
            trigger="job",
            status="finished",
            started_utc=NOW - timedelta(days=5),
            heartbeat_utc=NOW - timedelta(days=5),
            budget=DAILY_SHARE,
            calls=1,
        )
    )
    await db.flush()
    await _trial_now(db, FakeEbay())

    value = await collection_value(db, now=NOW)

    assert value.latest_run is not None
    assert value.latest_run.trigger == "job"


# ---------------------------------------------------------------------------
# The routes
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
def background(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    import src.routers.valuation as valuation_router

    started: list[uuid.UUID] = []

    async def record(run_id: uuid.UUID) -> None:
        started.append(run_id)

    monkeypatch.setattr(valuation_router, "continue_trial_in_background", record)
    return started


async def test_only_an_admin_can_start_or_read_a_trial(
    db: AsyncSession, ebay_keys: None, background: list[uuid.UUID]
) -> None:
    mark = await _person(db, UserRole.viewer)
    await _priced(db, "Heat", "blu_ray", "9.99")

    async with _as(db, mark) as client:
        started = await client.post("/api/v1/collection/value/bid-trial")
        read = await client.get("/api/v1/collection/value/bid-trial")

    assert (started.status_code, read.status_code) == (403, 403)
    assert background == []


async def test_the_button_claims_a_trial_and_carries_it_on_after_the_response(
    db: AsyncSession, ebay_keys: None, background: list[uuid.UUID]
) -> None:
    craig = await _person(db, UserRole.admin)
    await _priced(db, "Heat", "blu_ray", "9.99")

    async with _as(db, craig) as client:
        before = await client.get("/api/v1/collection/value/bid-trial")
        response = await client.post("/api/v1/collection/value/bid-trial")
        again = await client.post("/api/v1/collection/value/bid-trial")

    assert before.status_code == 200 and before.json() is None
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["outcome"], body["sampled"]) == ("started", 1)
    trial = body["trial"]
    assert (trial["status"], trial["sampleSize"], trial["minSample"]) == ("running", 100, 3)
    assert (trial["endingWindowHours"], trial["dailyShare"]) == (24, DAILY_SHARE)
    assert trial["report"]["sampled"] == 1 and trial["report"]["films"] == []
    run = await db.get(ValuationRun, uuid.UUID(trial["id"]))
    assert run is not None
    assert (run.trigger, run.started_by) == ("trial", craig.id)
    assert background == [run.id]
    assert again.json()["outcome"] == "running"
    assert len(background) == 1


async def test_the_button_says_so_when_ebay_is_not_configured(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, background: list[uuid.UUID]
) -> None:
    monkeypatch.setattr(settings, "ebay_client_id", "")
    monkeypatch.setattr(settings, "ebay_client_secret", "")
    craig = await _person(db, UserRole.admin)
    await _priced(db, "Heat", "blu_ray", "9.99")

    async with _as(db, craig) as client:
        response = await client.post("/api/v1/collection/value/bid-trial")

    assert response.status_code == 503
    assert await db.scalar(select(func.count()).select_from(ValuationRun)) == 0
    assert background == []


async def test_the_report_is_kept_for_reading_later(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    await _priced(db, "Blade Runner 2049", "blu_ray", "11.50")
    # The route reads the real clock, so the trial is dated from it.
    now = utcnow()
    run = await _trial_now(
        db, FakeEbay({"Blade Runner 2049 Blu-ray": _with_auctions(now)}), now=now
    )

    async with _as(db, craig) as client:
        response = await client.get("/api/v1/collection/value/bid-trial")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["status"], body["calls"]) == (str(run.id), "finished", 1)
    film = body["report"]["films"][0]
    assert film["bids"] == {
        "counted": 3,
        "withoutBids": 2,
        "rejected": 4,
        "price": "6.00",
        "endingSoon": 1,
    }
    assert body["report"]["overall"]["blend"]["fromBids"] == 1


async def test_reading_the_trial_closes_one_nobody_has_heard_from(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    await _priced(db, "Heat", "blu_ray", "9.99")
    an_hour_ago = utcnow() - timedelta(hours=1)
    outcome = await start_trial(db, started_by=craig.id, now=an_hour_ago)
    assert outcome.run is not None

    async with _as(db, craig) as client:
        response = await client.get("/api/v1/collection/value/bid-trial")

    assert response.json()["status"] == "abandoned"


# ---------------------------------------------------------------------------
# The migration
# ---------------------------------------------------------------------------


def _load_migration(revision_prefix: str) -> ModuleType:
    versions_dir = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    (path,) = versions_dir.glob(f"{revision_prefix}_*.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(step: Callable[[], None]) -> Callable[[Connection], None]:
    def run(sync_conn: Connection) -> None:
        with Operations.context(MigrationContext.configure(sync_conn)):
            step()

    return run


async def test_the_downgrade_keeps_a_trials_calls_and_the_upgrade_restores_it(
    db_conn: AsyncConnection,
) -> None:
    """The round trip CI's empty schema cannot make, inside the test's own transaction."""
    migration_043 = _load_migration("043")
    trial = uuid.uuid4()
    await db_conn.execute(
        text(
            "INSERT INTO valuation_runs (id, trigger, status, started_utc, heartbeat_utc, budget, "
            "calls, report) VALUES (:id, 'trial', 'finished', :now, :now, 750, 104, "
            "CAST(:report AS jsonb))"
        ),
        {"id": trial, "now": NOW, "report": json.dumps({"sampled": 100})},
    )

    await db_conn.run_sync(_run(migration_043.downgrade))

    trigger, calls = (
        await db_conn.execute(
            text("SELECT trigger, calls FROM valuation_runs WHERE id = :id"), {"id": trial}
        )
    ).one()
    assert (trigger, calls) == ("admin", 104)
    columns = (
        await db_conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'valuation_runs' AND column_name = 'report'"
            )
        )
    ).all()
    assert columns == []
    savepoint = await db_conn.begin_nested()
    with pytest.raises(IntegrityError):
        await db_conn.execute(
            text("UPDATE valuation_runs SET trigger = 'trial' WHERE id = :id"), {"id": trial}
        )
    await savepoint.rollback()

    await db_conn.run_sync(_run(migration_043.upgrade))
    await db_conn.execute(
        text("UPDATE valuation_runs SET trigger = 'trial' WHERE id = :id"), {"id": trial}
    )
    report = (
        await db_conn.execute(
            text("SELECT report FROM valuation_runs WHERE id = :id"), {"id": trial}
        )
    ).scalar_one()
    assert report is None
