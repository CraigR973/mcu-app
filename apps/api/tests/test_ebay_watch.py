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
from datetime import datetime, timedelta
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
from src.models.profile import Profile, UserRole
from src.routers.ebay_watch import get_ebay_client_factory
from src.services.ebay_watch.runs import DAILY_SHARE, start_run, work_run
from src.services.identification import _move_back, move_references

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent / "fixtures"
ITEM = json.loads((FIXTURES / "ebay_item_auction_with_buy_now.json").read_text())
NEWEST = json.loads((FIXTURES / "ebay_newest_bluray_4k_gb.json").read_text())
# An hour after the newest captured listing, so the first pass's three hours cover them all.
NOW = datetime(2026, 9, 26, 10, 0)
LAST_JEDI_4K = "https://www.ebay.co.uk/itm/298708357566"


class FakeEbay:
    """A scripted Browse: one listing by number, and search pages in order."""

    marketplace_id = "EBAY_GB"
    attempts_per_search = 1

    def __init__(
        self, *, item: dict[str, Any] | None = None, pages: list[dict[str, Any]] | None = None
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


def _as(db: AsyncSession, person: Profile, ebay: FakeEbay | None = None) -> AsyncClient:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return person

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
    address = "https://www.ebay.co.uk/itm/168722516953?hash=item274861:g:OywAAeSwqchqt4tc"

    async with _as(db, mark, FakeEbay(item=ITEM)) as client:
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

    async with _as(db, craig) as client:
        assert (await client.get("/api/v1/ebay/targets")).json()["items"] == []
        refused = await client.delete(f"/api/v1/ebay/targets/{body['id']}")
        assert refused.status_code == 404

    async with _as(db, mark) as client:
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
    async with _as(db, mark, FakeEbay(item=ITEM)) as client:
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
    ebay = FakeEbay(item=ITEM)
    async with _as(db, mark, ebay) as client:
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
    film = await _film(db, "Star Wars: The Last Jedi", tmdb_id=990_181_808)
    unmatched = await _film(db, "Star Wars Ep VIII", tmdb_id=None)
    async with _as(db, mark) as client:
        made = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": str(film.id), "formatCode": "4k_uhd", "targetPrice": "12"},
        )
        assert made.status_code == 201, made.text
        assert (made.json()["kind"], made.json()["formatCode"], made.json()["targetPrice"]) == (
            "search",
            "4k_uhd",
            "12.00",
        )
        twice = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": str(film.id), "formatCode": "4k_uhd", "targetPrice": "10"},
        )
        assert twice.status_code == 422
        other_format = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": str(film.id), "formatCode": "blu_ray", "targetPrice": "6"},
        )
        assert other_format.status_code == 201
        unidentified = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": str(unmatched.id), "formatCode": "4k_uhd", "targetPrice": "6"},
        )
        assert unidentified.status_code == 422
        missing = await client.post(
            "/api/v1/ebay/targets/search",
            json={"movieId": str(uuid.uuid4()), "formatCode": "4k_uhd", "targetPrice": "6"},
        )
        assert missing.status_code == 404
        by_film = await client.get(f"/api/v1/ebay/targets?movieId={film.id}")
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
            by_condition={"1000": {"median": "16.00", "n": 14}},
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
    assert (run.deals_found, run.deals_pushed, run.calls) == (1, 1, 3)
    assert run.newest_listing_utc == datetime(2026, 9, 26, 9, 11, 56)

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
    for person in (craig, mark):
        notes = await _notes(db, person, "ebay-deal:")
        assert [note.url for note in notes] == [LAST_JEDI_4K]
        assert notes[0].title == "Star Wars: The Last Jedi on 4K: £4.75"


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
    mark = await _person(db, UserRole.viewer)
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
    async with _as(db, mark) as client:
        feed = (await client.get("/api/v1/deals")).json()
        count = (await client.get("/api/v1/deals/count")).json()
        badge = (await client.get("/api/v1/nav/sections")).json()
    titles = [item["title"] for item in feed["items"] if item["retailer"] == "eBay"]
    assert titles == ["An eBay find 2"]
    assert count["count"] == feed["total"]
    assert badge["deals"] == feed["total"]


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
