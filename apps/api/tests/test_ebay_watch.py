"""eBay price alerts and the deal scan against Postgres — Batch T8a. These run in CI.

**What this proves:** each person sets and sees only their own alerts, on a listing by its
address or on a film and format, and cannot set the same one twice; a listing already under
its target is saved as met, without a push; a pass checks every watching target and tells
only its owner; the deal scan puts a find on the Deals page as eBay with its usual price,
pushes it to both people, and the next pass neither reads the same listings again nor
pushes twice; deal pushes stop at five a person a day; an expired eBay deal leaves the
feed, its count and the menu's badge; a pass starts only inside the day's share and one at
a time; a merge carries saved searches to the kept film, dropping a duplicate.

**What it does not:** a live eBay call. eBay is a scripted client answering with the
payloads captured on 26 Sep 2026.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.deal import Deal
from src.models.ebay_watch import EbayPriceRef, EbayTarget, EbayWatchRun
from src.models.movie import Movie
from src.models.notification import Notification
from src.models.price_check import PriceCheck
from src.models.profile import Profile, UserRole
from src.models.wanted import WantedItem
from src.routers.ebay_watch import get_ebay_client_factory
from src.services.ebay_watch.runs import DAILY_SHARE, clear_ended_finds, start_run, work_run
from src.services.identification import _move_back, move_references

FIXTURES = Path(__file__).parent / "fixtures"
ITEM = json.loads((FIXTURES / "ebay_item_auction_with_buy_now.json").read_text())
NEWEST = json.loads((FIXTURES / "ebay_newest_bluray_4k_gb.json").read_text())
# An hour after the newest captured listing, so the first pass's three hours cover them all.
NOW = datetime(2026, 9, 26, 10, 0)
LAST_JEDI_4K = "https://www.ebay.co.uk/itm/298708357566"
LAST_JEDI_TITLE = "Star Wars the Last Jedi 4K Ultra HD Blu-ray New Sealed"


def _for_sale(legacy_id: str, *, available: bool = True) -> dict[str, Any]:
    """An item call's answer for a find still for sale, or sold out (Batch X1's re-check)."""
    return {
        "legacyItemId": legacy_id,
        "title": "A listing",
        "price": {"value": "3.84", "currency": "GBP"},
        "buyingOptions": ["FIXED_PRICE"],
        "estimatedAvailabilities": [
            {"estimatedAvailabilityStatus": "IN_STOCK" if available else "OUT_OF_STOCK"}
        ],
    }


#: Every find in the captured page, still for sale when the pass re-checks it.
ON_SALE = {"298708357566": _for_sale("298708357566")}


class FakeEbay:
    """A scripted Browse: one listing by number, and search pages in order."""

    marketplace_id = "EBAY_GB"
    attempts_per_search = 1

    def __init__(
        self,
        *,
        item: dict[str, Any] | None = None,
        pages: list[dict[str, Any]] | None = None,
        items: dict[str, dict[str, Any] | None] | None = None,
    ) -> None:
        self.item = item
        #: Answers by listing number, before ``item``: the re-check before a deal's push.
        self.items = dict(ON_SALE if items is None else items)
        self.pages = list(pages or [])
        self.search_calls = 0
        self.searched: list[dict[str, Any]] = []
        self.looked_up: list[str] = []

    async def search(self, query: str, **params: Any) -> dict[str, Any]:
        self.search_calls += 1
        self.searched.append({"q": query, **params})
        return self.pages.pop(0) if self.pages else {"itemSummaries": []}

    async def get_item_by_legacy_id(self, legacy_item_id: str) -> dict[str, Any] | None:
        self.search_calls += 1
        self.looked_up.append(legacy_item_id)
        if legacy_item_id in self.items:
            return self.items[legacy_item_id]
        return self.item


class _Opened:
    def __init__(self, fake: FakeEbay) -> None:
        self.fake = fake

    async def __aenter__(self) -> FakeEbay:
        return self.fake

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _routes_read_the_capture_time(monkeypatch: pytest.MonkeyPatch) -> None:
    # ITEM is a real listing, and it ended at 09:06 UTC on 3 Oct 2026. Routes reading the
    # wall clock saw it as ended from then on, and two tests failed on every branch. The
    # routes read NOW instead, the capture's time, as every pass here already does.
    monkeypatch.setattr("src.routers.ebay_watch.utcnow", lambda: NOW)


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


def _as(db: AsyncSession, person_id: uuid.UUID, ebay: FakeEbay | None = None) -> AsyncClient:
    # By id, and the profile read again on each request, as a real request does: a refused
    # request rolls the shared session back, which expires every object in it, and reading
    # an expired one outside a request is IO the test cannot do (T9 met this first).

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        fresh = await db.get(Profile, person_id)
        assert fresh is not None
        return fresh

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    if ebay is not None:
        app.dependency_overrides[get_ebay_client_factory] = lambda: lambda: _Opened(ebay)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _film(
    db: AsyncSession, title: str, *, tmdb_id: int | None, owned: list[str] | None = None
) -> Movie:
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=2017,
        media_type="film",
    )
    db.add(film)
    await db.flush()
    if owned is not None:
        db.add(CollectionItem(id=uuid.uuid4(), movie_id=film.id, formats=owned))
        await db.flush()
    return film


def _listing_target(owner: Profile, *, price: str) -> EbayTarget:
    return EbayTarget(
        id=uuid.uuid4(),
        owner_id=owner.id,
        kind="listing",
        legacy_item_id="168722516953",
        target_price=Decimal(price),
        currency="GBP",
        title="THE BRAZEN BULL (NICTOPHOBIA) - Dvd  -",
        status="watching",
        created_at_utc=NOW - timedelta(days=1),
    )


def _search_target(owner: Profile, film: Movie, *, price: str) -> EbayTarget:
    return EbayTarget(
        id=uuid.uuid4(),
        owner_id=owner.id,
        kind="search",
        movie_id=film.id,
        format_code="4k_uhd",
        target_price=Decimal(price),
        currency="GBP",
        title=film.title,
        status="watching",
        created_at_utc=NOW - timedelta(days=1),
    )


async def _notes(db: AsyncSession, person: Profile, prefix: str) -> list[Notification]:
    return list(
        (
            await db.scalars(
                select(Notification).where(
                    Notification.user_id == person.id, Notification.dedupe_key.like(f"{prefix}%")
                )
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Setting alerts
# ---------------------------------------------------------------------------


async def test_a_person_sets_a_listing_alert_and_only_they_see_it(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    mark = await _person(db, UserRole.viewer)
    craig_id, mark_id = craig.id, mark.id
    address = "https://www.ebay.co.uk/itm/168722516953?hash=item274861:g:OywAAeSwqchqt4tc"

    async with _as(db, mark_id, FakeEbay(item=ITEM)) as client:
        made = await client.post(
            "/api/v1/ebay/targets/listing", json={"address": address, "targetPrice": "4.00"}
        )
        assert made.status_code == 201, made.text
        body = made.json()
        assert (body["kind"], body["status"], body["currentPrice"], body["isAuction"]) == (
            "listing",
            "watching",
            "6.99",
            False,
        )
        assert body["url"] == "https://www.ebay.co.uk/itm/168722516953"
        again = await client.post(
            "/api/v1/ebay/targets/listing", json={"address": address, "targetPrice": "3.00"}
        )
        assert again.status_code == 422
        assert "already" in again.json()["detail"]
        mine = await client.get("/api/v1/ebay/targets")
        assert [item["id"] for item in mine.json()["items"]] == [body["id"]]
        assert mine.json()["lastRun"] is None

    async with _as(db, craig_id) as client:
        assert (await client.get("/api/v1/ebay/targets")).json()["items"] == []
        refused = await client.delete(f"/api/v1/ebay/targets/{body['id']}")
        assert refused.status_code == 404

    async with _as(db, mark_id) as client:
        changed = await client.patch(
            f"/api/v1/ebay/targets/{body['id']}", json={"targetPrice": "6.50"}
        )
        assert changed.json()["targetPrice"] == "6.50"
        assert (await client.delete(f"/api/v1/ebay/targets/{body['id']}")).status_code == 204
        assert (await client.get("/api/v1/ebay/targets")).json()["items"] == []


async def test_a_listing_already_under_its_target_is_saved_as_met_without_a_push(
    db: AsyncSession,
) -> None:
    mark = await _person(db, UserRole.viewer)
    mark_id = mark.id
    async with _as(db, mark_id, FakeEbay(item=ITEM)) as client:
        made = await client.post(
            "/api/v1/ebay/targets/listing",
            json={"address": "168722516953", "targetPrice": "10.00"},
        )
    assert made.json()["status"] == "met"
    assert await _notes(db, mark, "ebay-target:") == []


async def test_an_address_that_is_not_a_listing_is_refused_before_eBay_is_asked(
    db: AsyncSession,
) -> None:
    mark = await _person(db, UserRole.viewer)
    mark_id = mark.id
    ebay = FakeEbay(item=ITEM)
    async with _as(db, mark_id, ebay) as client:
        refused = await client.post(
            "/api/v1/ebay/targets/listing",
            json={"address": "https://ebay.us/m/AbCdEf", "targetPrice": "5.00"},
        )
    assert refused.status_code == 422
    assert "/itm/" in refused.json()["detail"]
    assert ebay.search_calls == 0


async def test_a_saved_search_needs_an_identified_film_and_one_per_format(
    db: AsyncSession,
) -> None:
    mark = await _person(db, UserRole.viewer)
    mark_id = mark.id
    film = await _film(db, "Star Wars: The Last Jedi", tmdb_id=990_181_808)
    unmatched = await _film(db, "Star Wars Ep VIII", tmdb_id=None)
    # Taken before a refused request rolls the session back and expires both films.
    film_id, unmatched_id = str(film.id), str(unmatched.id)
    async with _as(db, mark_id) as client:
        made = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": film_id, "formatCode": "4k_uhd", "targetPrice": "12"},
        )
        assert made.status_code == 201, made.text
        assert (made.json()["kind"], made.json()["formatCode"], made.json()["targetPrice"]) == (
            "search",
            "4k_uhd",
            "12.00",
        )
        twice = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": film_id, "formatCode": "4k_uhd", "targetPrice": "10"},
        )
        assert twice.status_code == 422
        other_format = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": film_id, "formatCode": "blu_ray", "targetPrice": "6"},
        )
        assert other_format.status_code == 201
        unidentified = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": unmatched_id, "formatCode": "4k_uhd", "targetPrice": "6"},
        )
        assert unidentified.status_code == 422
        missing = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": str(uuid.uuid4()), "formatCode": "4k_uhd", "targetPrice": "6"},
        )
        assert missing.status_code == 404
        by_film = await client.get(f"/api/v1/ebay/targets?movieId={film_id}")
        assert len(by_film.json()["items"]) == 2


# ---------------------------------------------------------------------------
# A pass
# ---------------------------------------------------------------------------


async def _pass(db: AsyncSession, ebay: FakeEbay, *, now: datetime = NOW) -> EbayWatchRun:
    outcome = await start_run(db, trigger="job", now=now)
    assert outcome.reason == "started", outcome
    assert outcome.run is not None
    result = await work_run(db, ebay, outcome.run.id, clock=lambda: now)
    return result.run


async def _last_jedi_owned_on_blu_ray(db: AsyncSession) -> Movie:
    """Owned on Blu-ray, so a 4K is an upgrade, with a usual 4K price of £16.00."""
    film = await _film(db, "Star Wars: The Last Jedi", tmdb_id=990_181_808, owned=["blu_ray"])
    db.add(
        EbayPriceRef(
            id=uuid.uuid4(),
            movie_id=film.id,
            format_code="4k_uhd",
            status="priced",
            median=Decimal("16.00"),
            sample_size=20,
            by_condition={"1000": {"median": "16.00", "n": 14}, "used": {"median": None, "n": 0}},
            checked_utc=NOW - timedelta(days=2),
        )
    )
    await db.commit()
    return film


async def test_a_pass_checks_targets_finds_a_deal_and_tells_the_right_people(
    db: AsyncSession,
) -> None:
    craig = await _person(db, UserRole.admin)
    mark = await _person(db, UserRole.viewer)
    film = await _last_jedi_owned_on_blu_ray(db)
    listing_target = _listing_target(mark, price="7.00")
    search_target = _search_target(craig, film, price="5.00")
    db.add_all([listing_target, search_target])
    await db.commit()
    # The saved search's own search, then the scan's page of newest listings.
    ebay = FakeEbay(item=ITEM, pages=[NEWEST, NEWEST])

    run = await _pass(db, ebay)

    assert (run.status, run.targets_checked, run.target_alerts) == ("finished", 2, 2)
    assert (run.pages, run.listings_seen, run.candidates, run.refs_fetched) == (1, 14, 1, 0)
    # The target's item and search, the scan's page, and the deal's re-check before its push.
    assert (run.deals_found, run.deals_pushed, run.calls) == (1, 1, 4)
    # Batch X1: the next pass starts ten minutes before this one did, not at a listing.
    assert run.newest_listing_utc == NOW - timedelta(minutes=10)

    await db.refresh(listing_target)
    await db.refresh(search_target)
    assert (listing_target.status, listing_target.met_at_utc) == ("met", NOW)
    assert (search_target.status, search_target.current_url) == ("watching", LAST_JEDI_4K)

    # Each target tells its owner, and only its owner.
    mark_targets = await _notes(db, mark, "ebay-target:")
    craig_targets = await _notes(db, craig, "ebay-target:")
    assert [note.url for note in mark_targets] == ["https://www.ebay.co.uk/itm/168722516953"]
    assert [note.url for note in craig_targets] == [LAST_JEDI_4K]
    assert "Buy It Now at £6.99 with postage" in mark_targets[0].body

    # The deal is on the Deals page as eBay, and both people hear of it.
    deal = await db.scalar(select(Deal).where(Deal.url == LAST_JEDI_4K))
    assert deal is not None
    assert (deal.retailer_name_snapshot, deal.price, deal.was_price, deal.discount_percent) == (
        "eBay",
        Decimal("4.75"),
        Decimal("16.00"),
        70,
    )
    assert (deal.movie_id, deal.format_code, deal.expires_at_utc) == (
        film.id,
        "4k_uhd",
        NOW + timedelta(days=3),
    )
    assert (deal.title_snapshot, deal.listing_condition, deal.usual_listings) == (
        LAST_JEDI_TITLE,
        "New",
        14,
    )
    for person in (craig, mark):
        notes = await _notes(db, person, "ebay-deal:")
        assert [note.url for note in notes] == [LAST_JEDI_4K]
        # Batch X1: the listing's own title and condition, and what "usual" is.
        assert notes[0].title == LAST_JEDI_TITLE
        assert notes[0].body.startswith("New, £4.75 with postage on eBay: 70% under the usual")
        assert "(asking prices, 14 listings)" in notes[0].body
        assert "Filed as Star Wars: The Last Jedi (2017) on 4K." in notes[0].body


async def test_the_next_pass_reads_no_listing_twice_and_pushes_nothing_twice(
    db: AsyncSession,
) -> None:
    craig = await _person(db, UserRole.admin)
    film = await _last_jedi_owned_on_blu_ray(db)
    db.add(_search_target(craig, film, price="5.00"))
    await db.commit()
    await _pass(db, FakeEbay(pages=[NEWEST, NEWEST]))

    second = await _pass(db, FakeEbay(pages=[NEWEST, NEWEST]), now=NOW + timedelta(hours=2))

    # The same listings are older than where the first pass got to.
    assert (second.listings_seen, second.deals_found, second.deals_pushed) == (0, 0, 0)
    # The saved search finds the same listing, and its push is not sent again.
    assert (second.targets_checked, second.target_alerts) == (1, 0)
    assert len(await _notes(db, craig, "ebay-target:")) == 1
    assert len(await _notes(db, craig, "ebay-deal:")) == 1


async def test_a_stored_mark_in_the_future_never_blinds_the_next_pass(db: AsyncSession) -> None:
    """X1's guard (CR43-01), on read: production's row says 21 Oct 16:35, stored on 9 Oct
    by a listing dated 12 days ahead. A pass ignores any mark later than its own start."""
    await _person(db, UserRole.admin)
    await _last_jedi_owned_on_blu_ray(db)
    for mark in (NOW + timedelta(days=12), NOW - timedelta(hours=2)):
        db.add(
            EbayWatchRun(
                id=uuid.uuid4(),
                trigger="job",
                status="finished",
                started_utc=NOW - timedelta(days=1),
                heartbeat_utc=NOW - timedelta(days=1),
                finished_utc=NOW - timedelta(days=1),
                budget=DAILY_SHARE,
                calls=0,
                newest_listing_utc=mark,
            )
        )
    await db.commit()

    run = await _pass(db, FakeEbay(pages=[NEWEST]))

    # Read from two hours ago, so the whole captured page: before X1, nothing.
    assert (run.listings_seen, run.deals_found) == (14, 1)
    assert run.newest_listing_utc == NOW - timedelta(minutes=10)


async def test_a_find_that_has_sold_out_is_not_pushed_and_leaves_the_page(
    db: AsyncSession,
) -> None:
    """X1 (MK47-04's bound, #254): one item call before the push."""
    craig = await _person(db, UserRole.admin)
    await _last_jedi_owned_on_blu_ray(db)
    ebay = FakeEbay(
        pages=[NEWEST], items={"298708357566": _for_sale("298708357566", available=False)}
    )

    run = await _pass(db, ebay)

    assert (run.deals_found, run.deals_pushed) == (1, 0)
    assert ebay.looked_up == ["298708357566"]
    assert await _notes(db, craig, "ebay-deal:") == []
    deal = await db.scalar(select(Deal).where(Deal.url == LAST_JEDI_4K))
    assert deal is not None
    # Off the page now, and with the listing's own words gone (licence §8.1.2).
    assert deal.expires_at_utc == NOW
    assert (deal.title_snapshot, deal.image_url, deal.listing_condition) == (
        "Star Wars: The Last Jedi",
        None,
        None,
    )
    assert (deal.price, deal.movie_id) == (Decimal("4.75"), deal.movie_id)


async def test_a_find_that_ended_is_not_pushed(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    await _last_jedi_owned_on_blu_ray(db)

    run = await _pass(db, FakeEbay(pages=[NEWEST], items={"298708357566": None}))

    assert (run.deals_found, run.deals_pushed) == (1, 0)
    assert await _notes(db, craig, "ebay-deal:") == []


async def test_the_first_pass_after_x1_searches_each_wanted_film_once(db: AsyncSession) -> None:
    """X1: about ten calls, once, to recover what the blind days of 9–12 Oct hid."""
    await _person(db, UserRole.admin)
    film = await _last_jedi_owned_on_blu_ray(db)
    db.add(WantedItem(id=uuid.uuid4(), movie_id=film.id, preferred_format=None, currency="GBP"))
    other = await _film(db, "Heat", tmdb_id=949)
    db.add(WantedItem(id=uuid.uuid4(), movie_id=other.id, preferred_format=None, currency="GBP"))
    await db.commit()
    # A quiet newest-listings page; the Last Jedi listing comes back from its own search.
    ebay = FakeEbay(pages=[{"itemSummaries": []}, NEWEST, {"itemSummaries": []}])

    first = await _pass(db, ebay)

    assert first.wanted_searched == 2
    queries = sorted(search["q"] for search in ebay.searched[1:])
    assert queries == [
        "Heat (blu-ray,bluray,4k,uhd)",
        "Star Wars: The Last Jedi (blu-ray,bluray,4k,uhd)",
    ]
    assert first.deals_found == 1
    # The same matcher and checks: the Last Jedi's listing, and nothing else on the page.
    assert first.candidates == 1

    later = FakeEbay(pages=[{"itemSummaries": []}])
    second = await _pass(db, later, now=NOW + timedelta(hours=2))
    assert second.wanted_searched is None
    assert len(later.searched) == 1


async def test_deal_pushes_stop_at_five_a_person_a_day(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    mark = await _person(db, UserRole.viewer)
    await _last_jedi_owned_on_blu_ray(db)
    for index in range(5):
        db.add(
            Notification(
                id=uuid.uuid4(),
                user_id=craig.id,
                category="deals",
                status="sent",
                sent_at_utc=NOW - timedelta(hours=1),
                delivered_count=1,
                title="An earlier deal",
                body="",
                dedupe_key=f"ebay-deal:earlier-{index}:{craig.id}",
                created_at_utc=NOW - timedelta(hours=1),
            )
        )
    await db.commit()

    run = await _pass(db, FakeEbay(pages=[NEWEST]))

    assert run.deals_found == 1
    assert len(await _notes(db, craig, "ebay-deal:")) == 5
    assert len(await _notes(db, mark, "ebay-deal:")) == 1


async def test_a_pass_starts_only_inside_the_days_share_and_one_at_a_time(
    db: AsyncSession,
) -> None:
    db.add(
        EbayWatchRun(
            id=uuid.uuid4(),
            trigger="job",
            status="running",
            started_utc=NOW - timedelta(minutes=5),
            heartbeat_utc=NOW - timedelta(minutes=5),
            budget=DAILY_SHARE,
            calls=DAILY_SHARE - 40,
        )
    )
    await db.commit()
    assert (await start_run(db, trigger="job", now=NOW)).reason == "running"

    # Silent for half an hour: abandoned, and the next may start with what is left.
    later = NOW + timedelta(minutes=40)
    outcome = await start_run(db, trigger="job", now=later)
    assert outcome.reason == "started"
    assert outcome.run is not None and outcome.run.budget == 40
    abandoned = await db.scalar(
        select(func.count(EbayWatchRun.id)).where(EbayWatchRun.status == "abandoned")
    )
    assert abandoned == 1
    outcome.run.status = "finished"
    outcome.run.calls = 40
    await db.commit()
    assert (await start_run(db, trigger="job", now=later)).reason == "budget_spent"


# ---------------------------------------------------------------------------
# The Deals page
# ---------------------------------------------------------------------------


async def test_an_expired_ebay_deal_leaves_the_feed_its_count_and_the_badge(
    db: AsyncSession,
) -> None:
    mark_id = (await _person(db, UserRole.viewer)).id
    for suffix, expires in (("1", datetime(2020, 1, 1)), ("2", datetime(2099, 1, 1))):
        db.add(
            Deal(
                id=uuid.uuid4(),
                retailer_id=None,
                retailer_name_snapshot="eBay",
                title_snapshot=f"An eBay find {suffix}",
                url=f"https://www.ebay.co.uk/itm/99000000000{suffix}",
                price=Decimal("4.75"),
                was_price=Decimal("16.00"),
                currency="GBP",
                discount_percent=70,
                expires_at_utc=expires,
            )
        )
    await db.commit()
    async with _as(db, mark_id) as client:
        feed = (await client.get("/api/v1/deals")).json()
        count = (await client.get("/api/v1/deals/count")).json()
        badge = (await client.get("/api/v1/nav/sections")).json()
    titles = [item["title"] for item in feed["items"] if item["retailer"] == "eBay"]
    assert titles == ["An eBay find 2"]
    assert count["count"] == feed["total"]
    assert badge["deals"] == feed["total"]


async def test_a_shops_deal_leaves_the_page_two_days_after_it_was_last_seen(
    db: AsyncSession,
) -> None:
    """X1: the six Zavvi deals last seen on 30 Sep were still on the page on 12 Oct."""
    mark_id = (await _person(db, UserRole.viewer)).id
    now = datetime.now(UTC).replace(tzinfo=None)
    for name, seen in (
        ("stale", now - timedelta(days=2, minutes=1)),
        ("fresh", now - timedelta(days=1)),
    ):
        db.add(
            Deal(
                id=uuid.uuid4(),
                retailer_id=None,
                retailer_name_snapshot="Zavvi",
                title_snapshot=f"A {name} Zavvi deal",
                url=f"https://www.zavvi.com/p/x1-{name}",
                price=Decimal("10.00"),
                was_price=Decimal("20.00"),
                currency="GBP",
                discount_percent=50,
                first_seen_at_utc=seen,
                last_seen_at_utc=seen,
            )
        )
    await db.commit()
    async with _as(db, mark_id) as client:
        feed = (await client.get("/api/v1/deals")).json()
        count = (await client.get("/api/v1/deals/count")).json()
    titles = [item["title"] for item in feed["items"] if item["retailer"] == "Zavvi"]
    assert titles == ["A fresh Zavvi deal"]
    assert count["count"] == feed["total"]
    # Every card carries when its price was last seen.
    assert all(item["lastSeenAt"] for item in feed["items"])


async def test_an_expired_ebay_find_keeps_its_price_and_film_and_loses_the_listing(
    db: AsyncSession,
) -> None:
    """X1 (eBay API licence §8.1.2, §3.1(b)): run at the start and end of every pass."""
    film = await _film(db, "Heat", tmdb_id=949)
    expired = Deal(
        id=uuid.uuid4(),
        retailer_id=None,
        retailer_name_snapshot="eBay",
        movie_id=film.id,
        title_snapshot="HEAT 4K UHD Pacino De Niro mint",
        url="https://www.ebay.co.uk/itm/990000000077",
        image_url="https://i.ebayimg.com/heat.jpg",
        listing_condition="Like new",
        format_code="4k_uhd",
        price=Decimal("6.00"),
        was_price=Decimal("15.00"),
        currency="GBP",
        discount_percent=60,
        first_seen_at_utc=NOW - timedelta(days=4),
        last_seen_at_utc=NOW - timedelta(days=4),
        expires_at_utc=NOW - timedelta(days=1),
    )
    live = Deal(
        id=uuid.uuid4(),
        retailer_id=None,
        retailer_name_snapshot="eBay",
        movie_id=film.id,
        title_snapshot="Heat 4K UHD new",
        url="https://www.ebay.co.uk/itm/990000000078",
        image_url="https://i.ebayimg.com/heat2.jpg",
        listing_condition="New",
        price=Decimal("7.00"),
        currency="GBP",
        expires_at_utc=NOW + timedelta(days=1),
    )
    db.add_all([expired, live])
    await db.commit()

    await clear_ended_finds(db, now=NOW)

    await db.refresh(expired)
    await db.refresh(live)
    assert (expired.title_snapshot, expired.image_url, expired.listing_condition) == (
        "Heat",
        None,
        None,
    )
    assert (expired.price, expired.was_price, expired.movie_id, expired.first_seen_at_utc) == (
        Decimal("6.00"),
        Decimal("15.00"),
        film.id,
        NOW - timedelta(days=4),
    )
    assert (live.title_snapshot, live.image_url) == (
        "Heat 4K UHD new",
        "https://i.ebayimg.com/heat2.jpg",
    )


# ---------------------------------------------------------------------------
# Batch V8, amended by X1 — a shop's price can lower a New listing's usual, never raise it
# ---------------------------------------------------------------------------


async def _wanted_with_shop_prices(db: AsyncSession, film: Movie, *, zavvi: str) -> None:
    """The film wanted on 4K, and what the nightly check found at the shops this week."""
    want = WantedItem(id=uuid.uuid4(), movie_id=film.id, preferred_format="4k_uhd", currency="GBP")
    db.add(want)
    await db.flush()
    checks = [
        # Zavvi's latest standard 4K: the one shop price that counts.
        ("Zavvi", zavvi, "Star Wars: The Last Jedi 4K Ultra HD", timedelta(days=1)),
        # Zavvi's earlier price: only each shop's latest counts.
        ("Zavvi", "25.00", "Star Wars: The Last Jedi 4K Ultra HD", timedelta(days=3)),
        # A limited edition is not what eBay's figure measures.
        ("Second Sight", "45.00", "The Last Jedi Limited Edition 4K Ultra HD", timedelta(days=1)),
        # Not the find's format.
        ("Arrow Video", "9.00", "Star Wars: The Last Jedi Blu-ray", timedelta(days=1)),
        # Older than the nightly check's last week.
        ("HMV", "5.00", "Star Wars: The Last Jedi 4K Ultra HD", timedelta(days=8)),
    ]
    for index, (shop, price, title, age) in enumerate(checks):
        db.add(
            PriceCheck(
                id=uuid.uuid4(),
                wanted_id=want.id,
                retailer_id=None,
                retailer_name_snapshot=shop,
                price=Decimal(price),
                currency="GBP",
                title_snapshot=title,
                url=f"https://shop.test/last-jedi/{index}",
                checked_at=NOW - age,
            )
        )
    await db.commit()


async def test_a_cheaper_shop_lowers_a_new_listings_usual_like_for_like(
    db: AsyncSession,
) -> None:
    craig = await _person(db, UserRole.admin)
    film = await _last_jedi_owned_on_blu_ray(db)
    await _wanted_with_shop_prices(db, film, zavvi="14.00")

    run = await _pass(db, FakeEbay(pages=[NEWEST]))

    assert run.deals_found == 1
    deal = await db.scalar(select(Deal).where(Deal.url == LAST_JEDI_4K))
    assert deal is not None
    # Zavvi's £14.00 is under eBay's £16.00, so it is the ceiling. The limited edition, the
    # Blu-ray, Zavvi's earlier price and HMV's of eight days ago are left out.
    assert deal.was_price == Decimal("14.00")
    assert deal.usual_sources == [
        {"source": "eBay", "price": "16.00"},
        {"source": "Zavvi", "price": "14.00"},
    ]
    # (£14.00 - £4.75) / £14.00 = 66.1%.
    assert deal.discount_percent == 66
    (note,) = await _notes(db, craig, "ebay-deal:")
    assert "66% under the usual £14.00" in note.body

    # The pass ran on the test's clock, so its three days ended long ago; the feed is read now.
    deal.expires_at_utc = datetime(2099, 1, 1)
    await db.commit()
    async with _as(db, craig.id) as client:
        feed = (await client.get("/api/v1/deals")).json()
    (item,) = [item for item in feed["items"] if item["retailer"] == "eBay"]
    assert (item["wasPrice"], item["condition"], item["usualListings"]) == ("14.00", "New", 14)
    assert item["usualSources"] == [
        {"source": "eBay", "price": "16.00"},
        {"source": "Zavvi", "price": "14.00"},
    ]
    assert item["soldListingsUrl"] == (
        "https://www.ebay.co.uk/sch/i.html"
        "?_nkw=Star+Wars%3A+The+Last+Jedi+4K&_sacat=617&LH_Sold=1&LH_Complete=1"
    )


async def test_a_dearer_shop_never_raises_the_usual(db: AsyncSession) -> None:
    """MK47-06: averaged, Zavvi's £20.00 made eBay's £16.00 an £18.00 usual."""
    await _person(db, UserRole.admin)
    film = await _last_jedi_owned_on_blu_ray(db)
    await _wanted_with_shop_prices(db, film, zavvi="20.00")

    await _pass(db, FakeEbay(pages=[NEWEST]))

    deal = await db.scalar(select(Deal).where(Deal.url == LAST_JEDI_4K))
    assert deal is not None
    assert (deal.was_price, deal.discount_percent) == (Decimal("16.00"), 70)


async def test_an_earlier_find_reads_as_ebay_alone_and_a_shops_deal_has_no_parts(
    db: AsyncSession,
) -> None:
    """A find stored before V8 kept eBay's figure in ``was_price`` and recorded no parts."""
    mark_id = (await _person(db, UserRole.viewer)).id
    db.add_all(
        [
            Deal(
                id=uuid.uuid4(),
                retailer_id=None,
                retailer_name_snapshot="eBay",
                title_snapshot="An earlier eBay find",
                url="https://www.ebay.co.uk/itm/990000000009",
                price=Decimal("4.75"),
                was_price=Decimal("16.00"),
                currency="GBP",
                discount_percent=70,
                expires_at_utc=datetime(2099, 1, 1),
            ),
            Deal(
                id=uuid.uuid4(),
                retailer_id=None,
                retailer_name_snapshot="Zavvi",
                title_snapshot="A disc in Zavvi's sale",
                url="https://www.zavvi.com/p/v8-test",
                price=Decimal("10.00"),
                was_price=Decimal("20.00"),
                currency="GBP",
                discount_percent=50,
            ),
        ]
    )
    await db.commit()

    async with _as(db, mark_id) as client:
        feed = (await client.get("/api/v1/deals")).json()

    by_title = {item["title"]: item for item in feed["items"]}
    earlier = by_title["An earlier eBay find"]
    assert earlier["usualSources"] == [{"source": "eBay", "price": "16.00"}]
    # Matched to no film, so there is no film and format to search sold listings for.
    assert earlier["soldListingsUrl"] is None
    sale = by_title["A disc in Zavvi's sale"]
    assert (sale["usualSources"], sale["soldListingsUrl"]) == (None, None)


# ---------------------------------------------------------------------------
# A merge
# ---------------------------------------------------------------------------


async def test_a_merge_carries_saved_searches_to_the_kept_film(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    mark = await _person(db, UserRole.viewer)
    kept = await _film(db, "Star Wars: The Last Jedi", tmdb_id=990_181_808)
    merged = await _film(db, "Star Wars Ep VIII", tmdb_id=None)
    marks = _search_target(mark, merged, price="8.00")
    craigs = _search_target(craig, merged, price="9.00")
    craigs_kept = _search_target(craig, kept, price="7.00")
    db.add_all([marks, craigs, craigs_kept])
    await db.flush()

    merge = await move_references(db, merged.id, kept.id)

    assert set(merge.moved["ebay_targets"]) == {str(marks.id), str(craigs.id)}
    assert merge.dropped["ebay_targets"] == [{"id": str(craigs.id)}]
    await db.refresh(marks)
    await db.refresh(craigs)
    assert (marks.movie_id, marks.deleted_at) == (kept.id, None)
    assert craigs.movie_id == kept.id and craigs.deleted_at is not None

    await _move_back(db, merge.moved, source_id=merged.id, target_id=kept.id)
    await db.refresh(marks)
    assert marks.movie_id == merged.id
