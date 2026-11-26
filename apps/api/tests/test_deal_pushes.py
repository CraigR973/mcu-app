"""AG6: deals — the right disc, a fair figure, sensible pushes (MK53-01, -04, -05, -06; #383).

Pushes as both people agreed on 24 Nov: Wanted-list finds and finds of 40% or more at once,
the other finds in one summary after 18:00 in the person's own time, quiet hours 22:00–07:00 by
default, and a per-person Wanted-only choice. A percentage only on a figure of 5 or more asks
or 3 or more sales. An ended find's pushes lose the listing's words.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.ebay.matching import Listing, name_key
from src.models.deal import Deal
from src.models.movie import Movie, MovieCredit
from src.models.notification import Notification, NotificationPreference
from src.models.profile import Profile, UserRole
from src.models.wanted import WantedItem
from src.routers.deals import _to_response
from src.scripts.deal_pushes_owner_step import apply, counts
from src.services.ebay_watch.catalogue import CatalogueFilm, load_catalogue, load_people
from src.services.ebay_watch.links import listing_url
from src.services.ebay_watch.listings import ScanListing
from src.services.ebay_watch.refs import DealFigure, basis_of_source, figure_backed
from src.services.ebay_watch.runs import (
    clear_ended_finds,
    deal_alert,
    pushed_at_once,
    queue_deal_pushes,
    queue_upgrade_summaries,
    summary_due,
)
from src.services.ebay_watch.scan import Find, deal_backed

#: Midday GMT on 25 Nov: no one's quiet hours.
NOW = datetime(2026, 11, 25, 12, 0)
#: The first pass after 18:00 in London in winter (passes run at twenty past every second hour).
EVENING = datetime(2026, 11, 25, 18, 20)
LONDON = ZoneInfo("Europe/London")


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _person(db: AsyncSession, *, wanted_only: bool = False) -> Profile:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"person {uuid.uuid4().hex[:6]}",
        role=UserRole.admin,
        pin_hash="test-pin-hash",
    )
    db.add(person)
    await db.flush()
    db.add(
        NotificationPreference(id=uuid.uuid4(), user_id=person.id, deals_wanted_only=wanted_only)
    )
    await db.flush()
    return person


async def _movie(db: AsyncSession, title: str, year: int = 1995) -> Movie:
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=900000 + int(uuid.uuid4().int % 99999),
        title=title,
        original_title=title,
        year=year,
        media_type="film",
    )
    db.add(film)
    await db.flush()
    return film


def _film(movie_id: uuid.UUID, title: str, *, wanted: bool) -> CatalogueFilm:
    return CatalogueFilm(
        movie_id=movie_id,
        tmdb_id=1,
        title=title,
        year=1995,
        wanted=wanted,
        preferred_format=None,
        best_owned=None if wanted else 2,
    )


def _find(
    title: str,
    legacy_id: str,
    *,
    wanted: bool = False,
    percent: int,
    asks: int,
    movie_id: uuid.UUID | None = None,
) -> Find:
    listing = ScanListing(
        listing=Listing(
            item_id=f"v1|{legacy_id}|0",
            title=f"{title} 4K UHD Blu-ray",
            price=Decimal("6.00"),
            currency="GBP",
            condition_id="1000",
            web_url=listing_url(legacy_id),
            leaf_category_ids=("617",),
            country="GB",
            item_group_type=None,
        ),
        legacy_id=legacy_id,
        listed_at=NOW,
        postage=Decimal("0"),
        image_url=None,
        buy_now=True,
    )
    return Find(
        film=_film(movie_id or uuid.uuid4(), title, wanted=wanted),
        format_code="4k_uhd",
        listing=listing,
        usual=DealFigure(Decimal("15.00"), asks, "used_quartile"),
        wanted=wanted,
        discount_percent=percent,
    )


async def _always_for_sale(_legacy_id: str) -> bool | None:
    return True


async def _pushes(db: AsyncSession, person: Profile) -> list[Notification]:
    return list(
        (await db.scalars(select(Notification).where(Notification.user_id == person.id))).all()
    )


# ---------------------------------------------------------------------------
# A fair figure (MK53-04)
# ---------------------------------------------------------------------------


def test_a_percentage_needs_five_asks_or_three_sales() -> None:
    assert not figure_backed("used_quartile", 4)
    assert figure_backed("used_quartile", 5)
    assert not figure_backed("new_scaled", 3)
    assert figure_backed("new_scaled", 5)
    assert not figure_backed("sales", 2)
    assert figure_backed("sales", 3)
    assert basis_of_source("3 observed sales, postage in") == "sales"
    assert basis_of_source("Lower quartile of used asks, postage in") == "asks"
    assert basis_of_source(None) == "asks"


def test_a_thin_figure_is_pushed_without_a_percentage() -> None:
    thin = deal_alert(_find("Heat", "111111111111", wanted=True, percent=45, asks=3), uuid.uuid4())
    assert "45%" not in thin.body
    assert "under the few asks seen, £15.00 (lower quartile of used asks" in thin.body
    firm = deal_alert(_find("Heat", "111111111112", wanted=True, percent=45, asks=5), uuid.uuid4())
    assert "45% under £15.00 (lower quartile of used asks" in firm.body


def test_the_deals_page_shows_a_percentage_only_when_backed() -> None:
    def ebay(listings: int, source: str) -> Deal:
        return Deal(
            id=uuid.uuid4(),
            retailer_id=None,
            retailer_name_snapshot="eBay",
            title_snapshot="Heat",
            url=listing_url("222222222222"),
            price=Decimal("6.00"),
            was_price=Decimal("15.00"),
            currency="GBP",
            discount_percent=60,
            usual_sources=[{"source": source, "price": "15.00"}],
            usual_listings=listings,
            first_seen_at_utc=NOW,
            last_seen_at_utc=NOW,
        )

    asks = "Lower quartile of used asks, postage in"
    assert not _to_response(ebay(3, asks), None).discountBacked
    assert _to_response(ebay(5, asks), None).discountBacked
    assert _to_response(ebay(3, "3 observed sales, postage in"), None).discountBacked
    shop = ebay(1, asks)
    shop.retailer_id, shop.retailer_name_snapshot = uuid.uuid4(), "HMV"
    assert deal_backed(shop)


# ---------------------------------------------------------------------------
# Sensible pushes (MK53-05, #383)
# ---------------------------------------------------------------------------


def test_what_is_pushed_at_once() -> None:
    assert pushed_at_once(_find("A", "1", wanted=True, percent=12, asks=3))
    assert pushed_at_once(_find("B", "2", percent=40, asks=5))
    assert not pushed_at_once(_find("C", "3", percent=39, asks=20))
    # 45% on three asks is the overstatement MK53-04 found: it waits for the summary.
    assert not pushed_at_once(_find("D", "4", percent=45, asks=3))


def test_the_summary_is_due_from_18_00_in_the_persons_own_time() -> None:
    assert summary_due(LONDON, datetime(2026, 11, 25, 17, 59)) is None
    assert summary_due(LONDON, datetime(2026, 11, 25, 18, 20)) == EVENING.date()
    # British Summer Time: 17:20 UTC is 18:20 there; 16:20 UTC is 17:20, not yet.
    assert summary_due(LONDON, datetime(2027, 7, 1, 16, 20)) is None
    assert summary_due(LONDON, datetime(2027, 7, 1, 17, 20)) == datetime(2027, 7, 1).date()


async def test_only_wanted_and_big_finds_push_at_once_and_wanted_only_means_wanted(
    db: AsyncSession,
) -> None:
    craig = await _person(db)
    mark = await _person(db, wanted_only=True)
    wanted = _find("Wanted", "300000000001", wanted=True, percent=15, asks=3)
    big = _find("Big", "300000000002", percent=45, asks=8)
    thin_big = _find("ThinBig", "300000000003", percent=45, asks=3)
    small = _find("Small", "300000000004", percent=39, asks=8)

    pushed = await queue_deal_pushes(
        db, [small, thin_big, big, wanted], now=NOW, recheck=_always_for_sale
    )

    assert pushed == 2
    assert sorted(n.url for n in await _pushes(db, craig)) == sorted(
        [wanted.listing.url, big.listing.url]
    )
    assert [n.url for n in await _pushes(db, mark)] == [wanted.listing.url]


async def _deal(
    db: AsyncSession,
    film: Movie,
    legacy_id: str,
    *,
    percent: int,
    listings: int = 8,
    seen: datetime = NOW,
    expires: datetime | None = None,
    dismissed: bool = False,
) -> Deal:
    deal = Deal(
        id=uuid.uuid4(),
        retailer_id=None,
        retailer_name_snapshot="eBay",
        movie_id=film.id,
        title_snapshot=f"{film.title.upper()} 4K UHD mint",
        url=listing_url(legacy_id),
        image_url="https://i.ebayimg.com/x.jpg",
        listing_condition="Like new",
        format_code="4k_uhd",
        price=Decimal("6.00"),
        was_price=Decimal("15.00"),
        usual_sources=[{"source": "Lower quartile of used asks, postage in", "price": "15.00"}],
        usual_listings=listings,
        currency="GBP",
        discount_percent=percent,
        first_seen_at_utc=seen,
        last_seen_at_utc=seen,
        expires_at_utc=expires or seen + timedelta(days=3),
        dismissed_at_utc=NOW if dismissed else None,
    )
    db.add(deal)
    await db.flush()
    return deal


async def test_the_days_other_finds_come_as_one_summary_after_18_00(db: AsyncSession) -> None:
    craig = await _person(db)
    mark = await _person(db, wanted_only=True)
    films = {name: await _movie(db, name) for name in "ABCDEFGPQRS"}
    await _deal(db, films["A"], "400000000001", percent=60)
    await _deal(db, films["B"], "400000000002", percent=30)
    await _deal(db, films["C"], "400000000003", percent=50, listings=3)  # thin: last
    ended = await _deal(db, films["D"], "400000000004", percent=45)  # sold since
    await _deal(db, films["E"], "400000000005", percent=25)
    await _deal(db, films["F"], "400000000006", percent=20)
    await _deal(db, films["G"], "400000000007", percent=15)
    told = await _deal(db, films["P"], "400000000008", percent=70)  # pushed at once
    await _deal(db, films["Q"], "400000000009", percent=65, dismissed=True)
    await _deal(db, films["R"], "400000000010", percent=64, expires=NOW)
    await _deal(db, films["S"], "400000000011", percent=63, seen=NOW - timedelta(days=1))
    db.add(
        Notification(
            id=uuid.uuid4(),
            user_id=craig.id,
            category="deals",
            status="sent",
            sent_at_utc=NOW,
            delivered_count=1,
            title="P",
            body="",
            url=told.url,
            dedupe_key=f"ebay-deal:400000000008:{craig.id}",
            created_at_utc=NOW,
        )
    )
    await db.flush()
    asked: list[str] = []

    async def recheck(legacy_id: str) -> bool | None:
        asked.append(legacy_id)
        return legacy_id != "400000000004"

    assert (
        await queue_upgrade_summaries(db, now=EVENING - timedelta(hours=2), recheck=recheck)
        == set()
    )

    told_people = await queue_upgrade_summaries(db, now=EVENING, recheck=recheck)

    # Only these two people's rows are read: the database may hold other profiles.
    assert craig.id in told_people and mark.id not in told_people
    [summary] = [n for n in await _pushes(db, craig) if n.dedupe_key.startswith("ebay-summary:")]
    assert summary.dedupe_key == f"ebay-summary:2026-11-25:{craig.id}"
    assert summary.title == "Today's eBay finds: 6"
    assert summary.url == "/deals"
    assert summary.body.split("\n") == [
        "• A (1995) on 4K: £6.00, 60% under",
        "• B (1995) on 4K: £6.00, 30% under",
        "• E (1995) on 4K: £6.00, 25% under",
        "• F (1995) on 4K: £6.00, 20% under",
        "• G (1995) on 4K: £6.00, 15% under",
        "…and 1 more on the Deals page.",
    ]
    # A summary names films, never a listing's own words.
    assert "MINT" not in summary.body and "Like new" not in summary.body
    # The one that sold leaves the Deals page.
    await db.refresh(ended)
    assert ended.expires_at_utc == EVENING
    # Wanted-only: nothing on the Wanted list, so no summary.
    assert await _pushes(db, mark) == []
    # One a day.
    later = await queue_upgrade_summaries(db, now=EVENING + timedelta(hours=2), recheck=recheck)
    assert craig.id not in later


async def test_wanted_only_summary_names_only_wanted_films(db: AsyncSession) -> None:
    mark = await _person(db, wanted_only=True)
    wanted_film = await _movie(db, "Sorcerer", 1977)
    other = await _movie(db, "Heat")
    db.add(WantedItem(id=uuid.uuid4(), movie_id=wanted_film.id, currency="GBP", is_active=True))
    await _deal(db, wanted_film, "500000000001", percent=20)
    await _deal(db, other, "500000000002", percent=55)
    await db.flush()

    assert mark.id in await queue_upgrade_summaries(db, now=EVENING, recheck=_always_for_sale)
    [summary] = await _pushes(db, mark)
    assert summary.body == "• Sorcerer (1977) on 4K: £6.00, 20% under"


# ---------------------------------------------------------------------------
# Ended finds' pushes (MK53-06)
# ---------------------------------------------------------------------------


async def _push(db: AsyncSession, person: Profile, deal: Deal, *, status: str) -> Notification:
    legacy_id = deal.url.rsplit("/", 1)[-1]
    push = Notification(
        id=uuid.uuid4(),
        user_id=person.id,
        category="deals",
        status=status,
        title=deal.title_snapshot,
        body="Like new, £6.00 with postage on eBay: 60% under £15.00. Filed as Heat (1995) on 4K.",
        url=deal.url,
        dedupe_key=f"ebay-deal:{legacy_id}:{person.id}",
        deliver_after_utc=NOW + timedelta(hours=8) if status == "queued" else None,
        sent_at_utc=NOW - timedelta(days=3) if status == "sent" else None,
        delivered_count=1 if status == "sent" else 0,
        created_at_utc=NOW - timedelta(days=3),
    )
    db.add(push)
    await db.flush()
    return push


async def test_an_ended_finds_pushes_lose_the_listings_words(db: AsyncSession) -> None:
    craig = await _person(db)
    mark = await _person(db)
    heat = await _movie(db, "Heat")
    ending = await _deal(db, heat, "600000000001", percent=60, seen=NOW - timedelta(days=3))
    sent = await _push(db, craig, ending, status="sent")
    waiting = await _push(db, mark, ending, status="queued")
    # A find cleared before AG6, its push stored then: the pass does not reach it.
    old = await _deal(db, heat, "600000000002", percent=50, seen=NOW - timedelta(days=30))
    old_push = await _push(db, craig, old, status="sent")
    old.title_snapshot, old.image_url, old.listing_condition = "Heat", None, None
    await db.commit()

    await clear_ended_finds(db, now=NOW)

    for push in (sent, waiting, old_push):
        await db.refresh(push)
    assert sent.title == "Heat (1995) on 4K, on eBay"
    assert sent.body == (
        "An eBay find that has ended: £6.00 with postage, filed as Heat (1995) on 4K. "
        "The listing's own words are not kept once it ends."
    )
    assert "MINT" not in sent.title and "Like new" not in sent.body
    assert (sent.status, waiting.status, waiting.suppressed_reason) == (
        "sent",
        "suppressed",
        "deal_ended",
    )
    assert waiting.title == sent.title
    assert old_push.title == "HEAT 4K UHD mint"


async def test_the_owner_step_rewrites_stored_pushes_and_sets_quiet_hours(
    db: AsyncSession,
) -> None:
    craig = await _person(db)
    mark = await _person(db)
    quiet = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == mark.id)
    )
    assert quiet is not None
    quiet.quiet_hours_start, quiet.quiet_hours_end = time(23, 0), time(6, 0)
    nobody = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == craig.id)
    )
    assert nobody is not None
    nobody.quiet_hours_start = nobody.quiet_hours_end = None
    heat = await _movie(db, "Heat")
    old = await _deal(db, heat, "700000000001", percent=50, seen=NOW - timedelta(days=30))
    old.title_snapshot, old.image_url, old.listing_condition = "Heat", None, None
    push = await _push(db, craig, old, status="sent")
    live = await _deal(db, heat, "700000000002", percent=50, seen=NOW)
    live_push = await _push(db, craig, live, status="sent")
    await db.flush()

    pushes, finds, people = await counts(db)
    assert (pushes, finds) == (1, 1)
    assert people >= 1  # this person, and any other preference row the database holds

    assert await apply(db, expect_pushes=2, expect_people=people) is not None
    assert await apply(db, expect_pushes=1, expect_people=people) is None

    await db.refresh(push)
    await db.refresh(live_push)
    await db.refresh(nobody)
    await db.refresh(quiet)
    assert push.title == "Heat (1995) on 4K, on eBay"
    assert live_push.title == "HEAT 4K UHD mint"
    assert (nobody.quiet_hours_start, nobody.quiet_hours_end) == (time(22, 0), time(7, 0))
    assert (quiet.quiet_hours_start, quiet.quiet_hours_end) == (time(23, 0), time(6, 0))
    assert await counts(db) == (0, 1, 0)


# ---------------------------------------------------------------------------
# The right disc (MK53-01): the people the scan reads
# ---------------------------------------------------------------------------


async def test_the_scan_reads_cast_but_not_writers_and_each_films_own_credits(
    db: AsyncSession,
) -> None:
    craig = await _person(db)
    del craig
    film = await _movie(db, "The Invisible Man", 1933)
    db.add(WantedItem(id=uuid.uuid4(), movie_id=film.id, currency="GBP", is_active=True))
    other = await _movie(db, "Upgrade", 2018)
    for movie, name, role in (
        (film, "Claude Rains", "cast"),
        (other, "Michael Dorman", "cast"),
        (other, "Stephen Kingsworth", "cast"),
        (other, "Stephen Kingsworth", "writer"),
    ):
        db.add(MovieCredit(id=uuid.uuid4(), movie_id=movie.id, person_name=name, role=role))
    await db.flush()

    people = await load_people(db)
    assert name_key("Michael Dorman") in people.by_first["michael"]
    assert name_key("Stephen Kingsworth") not in people.by_first.get("stephen", ())

    catalogue = await load_catalogue(db)
    [filed] = [f for f in catalogue.films if f.movie_id == film.id]
    assert filed.people == frozenset({name_key("Claude Rains")})

    def listing(title: str) -> Listing:
        return Listing(
            item_id="v1|1|0",
            title=title,
            price=Decimal("5.00"),
            currency="GBP",
            condition_id="1000",
            web_url=listing_url("800000000001"),
            leaf_category_ids=("617",),
            country="GB",
            item_group_type=None,
        )

    assert catalogue.named_in(listing("The Invisible Man 4K UHD Michael Dorman")) is None
    assert catalogue.named_in(listing("The Invisible Man 4K UHD Claude Rains")) is not None
    assert catalogue.named_in(listing("The Invisible Man 4K UHD Stephen Kingsworth")) is not None
