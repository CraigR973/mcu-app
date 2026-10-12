"""eBay price alerts and the deal scan, without a database — Batch T8a.

**What this proves:** listing numbers are read from the addresses people copy, and a short
link is refused; the captured listing and search payloads (26 Sep 2026) are read as eBay
sends them, postage included; a new listing is named as a catalogue film only when the
film's title opens it, a studio's name before it is allowed, and two films of one title
make no match; a deal is 30% or more under the usual price, compared within the listing's
condition when enough listings stand behind it; a listing target meets its target on the
Buy It Now price with postage, or on the current bid alone, and says so in words; a saved
search finds the cheapest matching UK Buy It Now copy; the newest-first reader stops where
the last pass did.

**What it does not:** a live eBay call, or anything stored. ``test_ebay_watch.py`` runs the
passes against Postgres.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.ebay.estimate import search_query, sold_listings_url
from src.ebay.matching import Listing, MatchVerdict
from src.ebay.pricing import summarise
from src.models.ebay_watch import EbayPriceRef, EbayTarget, EbayWatchRun
from src.models.movie import Movie
from src.scripts.ebay_watch import report
from src.services.ebay_watch.catalogue import Catalogue, CatalogueFilm
from src.services.ebay_watch.links import legacy_item_id, listing_url
from src.services.ebay_watch.listings import item_state, scan_listing
from src.services.ebay_watch.refs import USED_POOL, Yardstick, _values, yardstick
from src.services.ebay_watch.runs import StartOutcome, deal_alert
from src.services.ebay_watch.scan import Find, is_deal, read_new_listings
from src.services.ebay_watch.targets import check_listing, check_search
from src.services.ebay_watch.usual import ShopPrice, UsualPrice

FIXTURES = Path(__file__).parent / "fixtures"
ITEM = json.loads((FIXTURES / "ebay_item_auction_with_buy_now.json").read_text())
NEWEST = json.loads((FIXTURES / "ebay_newest_bluray_4k_gb.json").read_text())
NOW = datetime(2026, 9, 26, 10, 0)


def _used_listing(price: str, condition_id: str) -> Listing:
    return Listing(
        item_id=f"v1|{price}|0",
        title="Heat 4K Ultra HD",
        price=Decimal(price),
        currency="GBP",
        condition_id=condition_id,
        web_url="https://www.ebay.co.uk/itm/1",
        leaf_category_ids=("617",),
        country="GB",
        item_group_type=None,
    )


def _ok_4k() -> MatchVerdict:
    return MatchVerdict(ok=True, format_code="4k_uhd", edition="standard")


def _summary(title_start: str) -> dict[str, Any]:
    return next(item for item in NEWEST["itemSummaries"] if item["title"].startswith(title_start))


class FakeEbay:
    """A scripted Browse: one listing by number, and search pages in order."""

    marketplace_id = "EBAY_GB"
    attempts_per_search = 1

    def __init__(
        self,
        *,
        item: dict[str, Any] | None = None,
        pages: list[dict[str, Any]] | None = None,
    ) -> None:
        self.item = item
        self.pages = list(pages or [])
        self.search_calls = 0
        self.searched: list[dict[str, Any]] = []

    async def search(self, query: str, **params: Any) -> dict[str, Any]:
        self.search_calls += 1
        self.searched.append({"q": query, **params})
        return self.pages.pop(0) if self.pages else {"itemSummaries": []}

    async def get_item_by_legacy_id(self, legacy_item_id: str) -> dict[str, Any] | None:
        self.search_calls += 1
        return self.item


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "https://www.ebay.co.uk/itm/168722516953",
        "https://www.ebay.co.uk/itm/168722516953?hash=item274861:g:OywAAeSwqchqt4tc",
        "www.ebay.co.uk/itm/The-Brazen-Bull-DVD/168722516953",
        "https://www.ebay.com/itm/168722516953/",
        "https://cgi.ebay.co.uk/ws/eBayISAPI.dll?ViewItem&item=168722516953",
        " 168722516953 ",
    ],
)
async def test_the_listing_number_is_read_from_the_addresses_people_copy(address: str) -> None:
    assert legacy_item_id(address) == "168722516953"


@pytest.mark.parametrize(
    "address",
    [
        "https://ebay.us/m/AbCdEf",  # a short link: the number is not in it
        "https://www.amazon.co.uk/itm/168722516953",
        "https://www.ebay.co.uk/sch/i.html?_nkw=blade+runner",
        "not a link",
        "",
    ],
)
async def test_anything_else_is_not_a_listing(address: str) -> None:
    assert legacy_item_id(address) is None


async def test_the_plain_address_drops_a_searchs_tracking() -> None:
    assert listing_url("168722516953") == "https://www.ebay.co.uk/itm/168722516953"


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


async def test_an_auction_with_buy_it_now_is_read_as_both() -> None:
    state = item_state(ITEM)
    assert state is not None
    assert (state.legacy_id, state.buy_now, state.current_bid, state.postage) == (
        "168722516953",
        Decimal("6.99"),
        Decimal("4.99"),
        Decimal("0.00"),
    )
    assert state.ends_at == datetime(2026, 10, 3, 9, 6, 39)
    assert state.available and not state.is_auction_only
    assert state.url == "https://www.ebay.co.uk/itm/168722516953"


async def test_an_auction_alone_has_no_buy_it_now() -> None:
    payload = deepcopy(ITEM)
    payload["buyingOptions"] = ["AUCTION"]
    payload["price"] = {"value": "4.99", "currency": "GBP"}
    state = item_state(payload)
    assert state is not None
    assert (state.buy_now, state.current_bid, state.is_auction_only) == (
        None,
        Decimal("4.99"),
        True,
    )


async def test_a_sold_out_listing_is_not_available() -> None:
    payload = deepcopy(ITEM)
    payload["estimatedAvailabilities"] = [{"estimatedAvailabilityStatus": "OUT_OF_STOCK"}]
    state = item_state(payload)
    assert state is not None and not state.available


async def test_a_new_listing_is_read_with_its_postage_and_when_it_was_listed() -> None:
    found = scan_listing(_summary("Tinker Tailor"))
    assert found is not None
    assert (found.listing.price, found.postage, found.total) == (
        Decimal("3.00"),
        Decimal("2.70"),
        Decimal("5.70"),
    )
    assert found.listed_at == datetime(2026, 9, 26, 9, 2, 43)
    assert found.buy_now
    assert found.url == f"https://www.ebay.co.uk/itm/{found.legacy_id}"


# ---------------------------------------------------------------------------
# Which film a listing is
# ---------------------------------------------------------------------------


def _film(
    title: str, *, wanted: bool = False, best_owned: int | None = None, year: int | None = None
) -> CatalogueFilm:
    return CatalogueFilm(
        movie_id=uuid.uuid4(),
        tmdb_id=1,
        title=title,
        year=year,
        wanted=wanted,
        preferred_format=None,
        best_owned=best_owned,
    )


def _catalogue(*films: CatalogueFilm) -> Catalogue:
    catalogue = Catalogue()
    for film in films:
        catalogue.add(film)
    return catalogue


def _listing(title_start: str) -> Listing:
    found = scan_listing(_summary(title_start))
    assert found is not None
    return found.listing


async def test_a_listing_that_opens_with_the_films_title_is_that_film() -> None:
    last_jedi = _film("Star Wars: The Last Jedi", best_owned=1)
    named = _catalogue(last_jedi).named_in(_listing("Star Wars the Last Jedi"))
    assert named == (last_jedi, "4k_uhd")
    assert last_jedi.upgraded_by("4k_uhd") and not last_jedi.upgraded_by("blu_ray")


async def test_a_studio_before_the_title_is_allowed() -> None:
    expendables = _film("The Expendables 3", best_owned=2)
    assert _catalogue(expendables).named_in(_listing("Lionsgate The Expendables 3")) == (
        expendables,
        "blu_ray",
    )


async def test_a_title_further_in_is_not_the_film() -> None:
    """ "Schwarzenegger TRUE LIES … SLIPCOVER ONLY": a name first, and not a disc."""
    true_lies = _film("True Lies", best_owned=1)
    assert _catalogue(true_lies).named_in(_listing("Schwarzenegger TRUE LIES")) is None


async def test_a_box_set_is_not_the_film() -> None:
    alien = _film("Alien", best_owned=2)
    assert _catalogue(alien).named_in(_listing("Alien Anthology Box Set")) is None


async def test_a_year_and_certificate_after_the_title_are_still_the_film() -> None:
    snatch = _film("Snatch", best_owned=2)
    assert _catalogue(snatch).named_in(_listing("Snatch (2000)")) == (snatch, "blu_ray")


async def test_a_leading_article_may_be_dropped_by_the_seller() -> None:
    matrix = _film("The Matrix", best_owned=1)
    listing = Listing(
        item_id="v1|1|0",
        title="Matrix (1999) 4K Ultra HD Blu-ray New & Sealed",
        price=Decimal("9.99"),
        currency="GBP",
        condition_id="1000",
        web_url="https://www.ebay.co.uk/itm/1",
        leaf_category_ids=("617",),
        country="GB",
        item_group_type=None,
    )
    assert _catalogue(matrix).named_in(listing) == (matrix, "4k_uhd")


async def test_two_films_of_one_title_make_no_match() -> None:
    first, second = _film("World War Z", best_owned=2), _film("World War Z", best_owned=2)
    assert _catalogue(first, second).named_in(_listing("World War Z")) is None


async def test_the_longer_title_wins_over_the_shorter() -> None:
    wars = _film("Star Wars", best_owned=2)
    force = _film("Star Wars: The Force Awakens", best_owned=2)
    assert _catalogue(wars, force).named_in(_listing("Star Wars: The Force Awakens")) == (
        force,
        "blu_ray",
    )


# ---------------------------------------------------------------------------
# What counts as a deal
# ---------------------------------------------------------------------------


def _ref(**fields: Any) -> EbayPriceRef:
    values: dict[str, Any] = {
        "movie_id": uuid.uuid4(),
        "format_code": "4k_uhd",
        "status": "priced",
        "median": Decimal("20.00"),
        "sample_size": 12,
        "by_condition": {
            "1000": {"median": "24.00", "n": 9},
            "3000": {"median": "15.00", "n": 2},
            "used": {"median": "14.00", "n": 5},
        },
        "checked_utc": NOW,
    }
    values.update(fields)
    return EbayPriceRef(**values)


async def test_a_listing_is_compared_within_its_condition_when_enough_stand_behind_it() -> None:
    assert yardstick(_ref(), "1000") == Yardstick(Decimal("24.00"), 9)
    # Two used listings are one seller's asking price: every used listing pooled stands in.
    assert yardstick(_ref(), "3000") == Yardstick(Decimal("14.00"), 5)


async def test_a_used_listing_never_meets_the_new_median() -> None:
    """X1's guard (MK47-02): 227 of 265 finds were judged against New's median."""
    thin = {"1000": {"median": "24.00", "n": 9}, "4000": {"median": "15.00", "n": 2}}
    # Too few used listings, alone or pooled: no yardstick at all, never the New headline.
    assert (
        yardstick(_ref(by_condition={**thin, "used": {"median": "15.00", "n": 2}}), "4000") is None
    )
    assert yardstick(_ref(by_condition={**thin, "used": {"median": None, "n": 0}}), "4000") is None
    # A used group dearer than New is passed over for the pool, and a dearer pool for nothing.
    odd = {
        "1000": {"median": "24.00", "n": 9},
        "2750": {"median": "30.00", "n": 4},
        "used": {"median": "18.00", "n": 7},
    }
    assert yardstick(_ref(by_condition=odd), "2750") == Yardstick(Decimal("18.00"), 7)
    dearer = {**odd, "used": {"median": "26.00", "n": 7}}
    assert yardstick(_ref(by_condition=dearer), "2750") is None
    # With no New group to compare with, a used group of three is enough.
    alone = {"5000": {"median": "8.00", "n": 3}, "used": {"median": "9.00", "n": 5}}
    assert yardstick(_ref(by_condition=alone), "5000") == Yardstick(Decimal("8.00"), 3)


async def test_a_usual_price_stored_before_x1_is_searched_again() -> None:
    """Without the used pool, a stored usual cannot judge a used listing, so it is stale."""

    estimate = summarise(
        [(_used_listing(price, "4000"), _ok_4k()) for price in ("6.00", "8.00", "10.00")]
        + [(_used_listing("12.00", "5000"), _ok_4k())],
        film_title="Heat",
        format_code="4k_uhd",
        marketplace_id="EBAY_GB",
    )
    stored = _values(estimate, "4k_uhd")["by_condition"]
    assert isinstance(stored, dict)
    # 6, 8, 10 and 12 pooled: the median of the four prices, not of the two medians.
    assert stored[USED_POOL] == {"median": "9.00", "n": 4}


async def test_no_yardstick_without_three_listings() -> None:
    assert (
        yardstick(_ref(status="not_priced", median=None, sample_size=2, by_condition={}), "1000")
        is None
    )


async def test_a_deal_is_thirty_percent_or_more_under_the_usual_price() -> None:
    # The usual price itself since Batch V8, which may average in the shops' prices.
    usual = Decimal("20.00")
    assert is_deal(Decimal("14.00"), usual)
    assert not is_deal(Decimal("14.01"), usual)


async def test_a_shop_price_is_a_ceiling_never_a_lift() -> None:
    """Batch X1 (MK47-06, #239 amended): eBay's figure, lowered to the cheapest shop's."""
    ebay = Yardstick(Decimal("16.00"), 20)
    assert UsualPrice(ebay).amount == Decimal("16.00")

    dearer = UsualPrice(ebay, (ShopPrice("Zavvi", Decimal("20.00")),))
    assert dearer.amount == Decimal("16.00")
    assert dearer.sources() == [
        {"source": "eBay", "price": "16.00"},
        {"source": "Zavvi", "price": "20.00"},
    ]

    cheaper = UsualPrice(
        ebay, (ShopPrice("Arrow Video", Decimal("13.99")), ShopPrice("Zavvi", Decimal("19.99")))
    )
    assert cheaper.amount == Decimal("13.99")


async def test_a_deal_is_judged_against_the_lowered_price() -> None:
    """The 70% rule compares with the usual after the ceiling, not eBay's alone."""
    figure = UsualPrice(Yardstick(Decimal("16.00"), 20), (ShopPrice("Zavvi", Decimal("13.00")),))
    assert figure.amount == Decimal("13.00")
    # Under eBay's £16.00 × 70% = £11.20, but not under £13.00 × 70% = £9.10.
    assert is_deal(Decimal("11.00"), Decimal("16.00"))
    assert not is_deal(Decimal("11.00"), figure.amount)


async def test_the_sold_listings_link_searches_as_the_estimator_does() -> None:
    """V8: eBay's own sold listings for the film and format, which only a signed-in
    person can read (#16, #126), with the words the asking prices were searched with."""
    assert sold_listings_url(search_query("Heat", "blu_ray")) == (
        "https://www.ebay.co.uk/sch/i.html?_nkw=Heat+Blu-ray&_sacat=617&LH_Sold=1&LH_Complete=1"
    )


async def test_a_deal_push_says_why_it_matters() -> None:
    found = scan_listing(_summary("Star Wars the Last Jedi"))
    assert found is not None
    film = _film("Star Wars: The Last Jedi", best_owned=1)
    person = uuid.uuid4()
    alert = deal_alert(
        Find(film, "4k_uhd", found, Yardstick(Decimal("16.00"), 20), False, 70), person
    )
    # Batch X1: the listing's own title and condition, then what "usual" stands on.
    assert alert.title == "Star Wars the Last Jedi 4K Ultra HD Blu-ray New Sealed"
    assert alert.body.startswith("New, £4.75 with postage on eBay: 70% under the usual £16.00")
    assert "(asking prices, 20 listings)" in alert.body
    assert "Filed as Star Wars: The Last Jedi on 4K." in alert.body
    assert "upgrade" in alert.body
    assert alert.url == found.url
    assert alert.dedupe_key == f"ebay-deal:{found.legacy_id}:{person}"


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


def _target(**fields: Any) -> EbayTarget:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "kind": "listing",
        "legacy_item_id": "168722516953",
        "target_price": Decimal("7.00"),
        "currency": "GBP",
        "title": "THE BRAZEN BULL (NICTOPHOBIA) - Dvd  -",
        "status": "watching",
    }
    values.update(fields)
    return EbayTarget(**values)


async def test_buy_it_now_with_postage_under_the_target_is_met() -> None:
    target = _target(target_price=Decimal("7.00"))
    alert = await check_listing(FakeEbay(item=ITEM), target, now=NOW)
    assert alert is not None
    assert target.status == "met" and target.met_at_utc == NOW
    assert "Buy It Now at £6.99 with postage" in alert.body
    assert alert.url == "https://www.ebay.co.uk/itm/168722516953"
    assert alert.dedupe_key == f"ebay-target:{target.id}:168722516953:7.00"


async def test_a_current_bid_under_the_target_offers_it_as_a_maximum_bid() -> None:
    target = _target(target_price=Decimal("5.50"))
    alert = await check_listing(FakeEbay(item=ITEM), target, now=NOW)
    assert alert is not None
    assert alert.title.endswith("bidding at £4.99")
    assert "Set £5.50 as your maximum bid on eBay" in alert.body
    assert "Sat 03 Oct at 09:06" in alert.body


async def test_above_the_target_nothing_is_said_but_the_price_is_kept() -> None:
    target = _target(target_price=Decimal("4.00"))
    assert await check_listing(FakeEbay(item=ITEM), target, now=NOW) is None
    assert (target.status, target.current_price, target.last_checked_utc) == (
        "watching",
        Decimal("6.99"),
        NOW,
    )


async def test_a_listing_eBay_no_longer_has_has_ended() -> None:
    target = _target()
    assert await check_listing(FakeEbay(item=None), target, now=NOW) is None
    assert target.status == "ended"


async def test_a_listing_past_its_end_is_not_asked_about() -> None:
    target = _target(ends_at_utc=datetime(2026, 9, 25, 9, 0))
    client = FakeEbay(item=ITEM)
    assert await check_listing(client, target, now=NOW) is None
    assert (target.status, client.search_calls) == ("ended", 0)


async def test_a_saved_search_finds_the_cheapest_matching_uk_copy() -> None:
    movie = Movie(
        id=uuid.uuid4(), tmdb_id=181808, title="Star Wars: The Last Jedi", media_type="film"
    )
    target = _target(
        kind="search",
        legacy_item_id=None,
        movie_id=movie.id,
        format_code="4k_uhd",
        target_price=Decimal("5.00"),
        title=movie.title,
    )
    client = FakeEbay(pages=[NEWEST])
    alert = await check_search(client, target, movie, now=NOW)
    assert client.searched[0]["q"] == "Star Wars: The Last Jedi 4K"
    assert alert is not None
    assert alert.title == "Star Wars: The Last Jedi on 4K: £4.75"
    assert "New, Buy It Now at £4.75 with postage" in alert.body
    assert (target.status, target.current_price, target.current_postage) == (
        "watching",
        Decimal("3.84"),
        Decimal("0.91"),
    )


# ---------------------------------------------------------------------------
# Reading the newest listings
# ---------------------------------------------------------------------------


def _run(budget: int = 50) -> EbayWatchRun:
    return EbayWatchRun(
        id=uuid.uuid4(),
        trigger="job",
        status="running",
        started_utc=NOW,
        heartbeat_utc=NOW,
        budget=budget,
        calls=0,
        pages=0,
    )


async def test_the_reader_keeps_only_listings_since_the_last_pass() -> None:
    run = _run()
    client = FakeEbay(pages=[NEWEST])
    listings, stopped = await read_new_listings(client, run, since=datetime(2026, 9, 26, 8, 30))
    assert stopped is None
    # A short page is the last: one call.
    assert (client.search_calls, run.pages) == (1, 1)
    assert all(
        found.listed_at and found.listed_at > datetime(2026, 9, 26, 8, 30) for found in listings
    )
    assert len(listings) == 11
    # Batch X1: the next pass starts ten minutes before this one did, not at a listing.
    assert run.newest_listing_utc == NOW - timedelta(minutes=10)
    first = client.searched[0]
    assert (first["category_ids"], first["sort"], first["filter"]) == (
        "617",
        "newlyListed",
        "itemLocationCountry:GB,buyingOptions:{FIXED_PRICE}",
    )


async def test_a_quiet_night_still_moves_the_mark_to_its_own_start() -> None:
    run = _run()
    since = datetime(2026, 9, 26, 9, 30)
    listings, _ = await read_new_listings(FakeEbay(pages=[NEWEST]), run, since=since)
    assert listings == []
    assert run.newest_listing_utc == NOW - timedelta(minutes=10)


async def test_a_listing_dated_in_the_future_is_read_but_never_moves_the_mark() -> None:
    """X1's guard (CR43-01): on 9 Oct one listing dated 12 days ahead set the mark to
    21 Oct 16:35, and every pass after read nothing. It is judged like any other."""
    page = deepcopy(NEWEST)
    page["itemSummaries"][0]["itemCreationDate"] = "2026-10-08T16:35:01.000Z"
    run = _run()
    listings, stopped = await read_new_listings(
        FakeEbay(pages=[page]), run, since=datetime(2026, 9, 26, 8, 30)
    )
    assert stopped is None
    assert datetime(2026, 10, 8, 16, 35, 1) in {found.listed_at for found in listings}
    assert run.newest_listing_utc == NOW - timedelta(minutes=10)


async def test_the_reader_stops_at_the_budget() -> None:
    run = _run(budget=0)
    client = FakeEbay(pages=[NEWEST])
    listings, stopped = await read_new_listings(client, run, since=datetime(2026, 9, 26, 8, 0))
    assert (listings, stopped, client.search_calls) == ([], "budget", 0)
    # A read cut short leaves no mark, so the next pass reads from the last one that finished.
    assert run.newest_listing_utc is None


# ---------------------------------------------------------------------------
# The job's report
# ---------------------------------------------------------------------------


async def test_the_job_reports_what_it_did_and_fails_when_stopped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    run = _run()
    run.status, run.calls, run.targets_checked, run.target_alerts = "finished", 3, 2, 1
    run.listings_seen, run.candidates, run.refs_fetched = 14, 1, 0
    run.deals_found, run.deals_pushed = 1, 1
    assert report(StartOutcome("started", run, 500), run) == 0
    out = capsys.readouterr().out
    assert "eBay calls:      3 of 50" in out
    assert "deals:           1 found, 1 pushed" in out
    run.status, run.last_error = "stopped", "eBay: eBay search failed (HTTP 429)"
    assert report(StartOutcome("started", run, 500), run) == 1
    assert "HTTP 429" in capsys.readouterr().out


async def test_a_spent_share_is_not_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    assert report(StartOutcome("budget_spent", None, 0), None) == 0
    assert "share of eBay calls is spent" in capsys.readouterr().out
