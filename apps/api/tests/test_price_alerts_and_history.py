"""Batch 20 — price-drop alerts (§5.6), the run record (§5.5) and the roll-up (§5.8).

**What these prove and what they cannot.** The scrape runs against `httpx.MockTransport`
and the push transport is stubbed, so what is proved is that a price at or below its
threshold produces exactly one alert per person, that the run writes down the numbers
§5.5's corrected criterion is stated in, and that a backdated check aggregates and is
deleted. What is **not** proved is 5.6's acceptance as written — *"triggers a push on test
device"* — which needs a real device, and 5.5's *"first overnight run completes"*, which
needs the Railway cron that `DECISIONS.md` #60 keeps as an owner action.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.movie import Movie
from src.models.notification import Notification, NotificationPreference, PushSubscription
from src.models.price_check import PriceCheck
from src.models.price_history import PriceHistoryDaily, ScrapeRun
from src.models.profile import Profile, UserRole
from src.models.wanted import Retailer, WantedItem
from src.services.notifications import DeliveryOutcome, DeliveryResult
from src.services.scraping.aggregate import aggregate_old_checks
from src.services.scraping.alerts import AlertCandidate, queue_price_drop_alerts
from src.services.scraping.daily import run_daily_scrape

pytestmark = pytest.mark.asyncio


class StubSender:
    """Records instead of pushing. Batch 11's tests carry the transport's own coverage."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, subscription: PushSubscription, payload: bytes) -> DeliveryResult:
        self.sent.append(subscription.endpoint)
        return DeliveryResult(DeliveryOutcome.delivered, 201)


SHOP_PAGE = """
<html><body>
  <div class="result">
    <h3><a class="title" href="https://93.184.216.34/product/heat-4k">Heat [4K UHD]</a></h3>
    <span class="price">£19.99</span>
  </div>
</body></html>
"""

#: A **card-shaped** page listing real products, none of which is the film.
#:
#: Card-shaped on purpose. `DECISIONS.md` #107's not-stocked detection is read from
#: `titled_cards` / `matching_cards`, which `extract` only counts when the page is parsed
#: card by card — a whole-page read leaves both at 0, which Batch 19 documents as "the
#: conservative reading" and reports as a failure instead. Every enabled retailer is a
#: card-based built-in, so that is the path the nightly job actually takes.
NOT_STOCKED_PAGE = "".join(
    f"""
    <div class="product-card" data-testid="product-item">
      <a href="/p/{slug}/" data-testid="product-title">{title}</a>
      <div data-testid="product-price">
        <span class="product-variant-price">{price}</span>
      </div>
    </div>
    """
    for slug, title, price in (
        ("cold-prey", "Cold Prey Trilogy Limited Edition Blu-ray Boxset", "£45.00"),
        ("bruiser", "BRUISER - 4K UHD LE", "£30.00"),
    )
)

#: The film **is** listed and its price cannot be read — a real scraper failure.
#:
#: Distinct from `NOT_STOCKED_PAGE` (the shop has other films) and from an empty page (the
#: shop returned nothing, which `DECISIONS.md` #125 makes `no_results` rather than a
#: failure). This is the case §5.5 means by "failures logged with retailer + reason": the
#: listing is right there and the selector cannot read a number off it.
UNREADABLE_PRICE_PAGE = """
    <div class="product-card" data-testid="product-item">
      <a href="/p/heat/" data-testid="product-title">Heat [4K UHD]</a>
      <div data-testid="product-price"><span class="product-variant-price">Sold out</span></div>
    </div>
"""

#: The selectors the built-in shops actually use.
CARD_CONFIG = {
    "item": "[data-testid='product-item']",
    "title": "[data-testid='product-title']",
    "price": "[data-testid='product-price'] .product-variant-price",
    "url": "[data-testid='product-title']",
}


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _profile(db: AsyncSession, role: UserRole = UserRole.admin) -> Profile:
    profile = Profile(
        id=uuid.uuid4(), display_name=f"{role.value} {uuid.uuid4().hex[:8]}", role=role
    )
    db.add(profile)
    await db.flush()
    return profile


async def _movie(db: AsyncSession, title: str = "Heat") -> Movie:
    movie = Movie(
        id=uuid.uuid4(), tmdb_id=None, title=title, original_title=title, media_type="film"
    )
    db.add(movie)
    await db.flush()
    return movie


async def _want(
    db: AsyncSession, movie: Movie, *, max_price: str | None = "25.00", fmt: str | None = "4k_uhd"
) -> WantedItem:
    want = WantedItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        preferred_format=fmt,
        max_price=Decimal(max_price) if max_price is not None else None,
        currency="GBP",
        is_active=True,
    )
    db.add(want)
    await db.flush()
    return want


async def _retailer(
    db: AsyncSession, name: str = "Test Shop", *, config: dict[str, str] | None = None
) -> Retailer:
    retailer = Retailer(
        id=uuid.uuid4(),
        name=name,
        base_url="https://93.184.216.34",
        search_url_template="https://93.184.216.34/search?q={query}",
        scraper_config=config or {"title": "a.title", "price": ".price", "url": "a.title"},
        scraper_type="generic_css",
        scrape_frequency="daily",
        enabled=True,
        currency="GBP",
        region="GB",
        consecutive_failures=0,
    )
    db.add(retailer)
    await db.flush()
    return retailer


async def _check(
    db: AsyncSession,
    want: WantedItem,
    retailer: Retailer,
    *,
    price: str,
    when: datetime,
    notified: bool = False,
    url: str | None = None,
) -> PriceCheck:
    check = PriceCheck(
        id=uuid.uuid4(),
        wanted_id=want.id,
        retailer_id=retailer.id,
        retailer_name_snapshot=retailer.name,
        price=Decimal(price),
        currency="GBP",
        title_snapshot="Heat [4K UHD]",
        url=url or f"https://93.184.216.34/p/{uuid.uuid4().hex}",
        notification_sent=notified,
        checked_at=when,
    )
    db.add(check)
    await db.flush()
    return check


async def _deals_notifications(db: AsyncSession) -> list[Notification]:
    return list(
        (await db.execute(select(Notification).where(Notification.category == "deals")))
        .scalars()
        .all()
    )


class TestPriceDropAlerts:
    """§5.6 — *"if price ≤ max_price and not notified, queue push"*."""

    async def test_a_price_below_the_threshold_alerts(self, db: AsyncSession) -> None:
        person = await _profile(db)
        want = await _want(db, await _movie(db), max_price="25.00")
        retailer = await _retailer(db)
        check = await _check(db, want, retailer, price="19.99", when=datetime(2026, 4, 1, 3, 0))

        queued = await queue_price_drop_alerts(
            db, [AlertCandidate(check=check, wanted=want)], now=datetime(2026, 4, 1, 3, 0)
        )

        assert queued >= 1
        alerts = await _deals_notifications(db)
        mine = [a for a in alerts if a.user_id == person.id]
        assert len(mine) == 1
        assert mine[0].title == "Heat is £19.99"
        assert "Test Shop" in mine[0].body
        assert check.notification_sent is True

    async def test_a_price_exactly_at_the_threshold_alerts(self, db: AsyncSession) -> None:
        """The boundary the owner actually chose.

        `max_price` is `Numeric`, never a float, precisely so £25.00 compares equal to
        £25.00 at the point somebody cared about — a value round-tripped through a float
        would miss its own threshold.
        """
        await _profile(db)
        want = await _want(db, await _movie(db), max_price="25.00")
        retailer = await _retailer(db)
        check = await _check(db, want, retailer, price="25.00", when=datetime(2026, 4, 1, 3, 0))

        queued = await queue_price_drop_alerts(db, [AlertCandidate(check=check, wanted=want)])

        assert queued >= 1

    async def test_a_price_above_the_threshold_does_not_alert(self, db: AsyncSession) -> None:
        await _profile(db)
        want = await _want(db, await _movie(db), max_price="15.00")
        retailer = await _retailer(db)
        check = await _check(db, want, retailer, price="19.99", when=datetime(2026, 4, 1, 3, 0))

        queued = await queue_price_drop_alerts(db, [AlertCandidate(check=check, wanted=want)])

        assert queued == 0
        assert check.notification_sent is False

    async def test_a_want_with_no_threshold_never_alerts(self, db: AsyncSession) -> None:
        """`max_price` is nullable: "I want this" is not "tell me when it is cheap"."""
        await _profile(db)
        want = await _want(db, await _movie(db), max_price=None)
        retailer = await _retailer(db)
        check = await _check(db, want, retailer, price="0.99", when=datetime(2026, 4, 1, 3, 0))

        assert await queue_price_drop_alerts(db, [AlertCandidate(check=check, wanted=want)]) == 0

    async def test_a_second_night_at_the_same_low_price_does_not_alert_again(
        self, db: AsyncSession
    ) -> None:
        """**The reason the rule is a transition, not a condition.**

        "Price ≤ max_price" stays true for as long as the disc is cheap, so alerting on the
        condition would send the same message every night until it was bought.
        """
        await _profile(db)
        want = await _want(db, await _movie(db), max_price="25.00")
        retailer = await _retailer(db)
        first = await _check(db, want, retailer, price="19.99", when=datetime(2026, 4, 1, 3, 0))
        await queue_price_drop_alerts(db, [AlertCandidate(check=first, wanted=want)])
        before = len(await _deals_notifications(db))

        second = await _check(db, want, retailer, price="19.99", when=datetime(2026, 4, 2, 3, 0))
        queued = await queue_price_drop_alerts(db, [AlertCandidate(check=second, wanted=want)])

        assert queued == 0
        assert len(await _deals_notifications(db)) == before
        assert second.notification_sent is True, "still cheap, and marked as already told"

    async def test_a_price_that_recovers_and_drops_again_alerts_again(
        self, db: AsyncSession
    ) -> None:
        """The re-arm. A second drop is news again precisely because it went back up."""
        person = await _profile(db)
        want = await _want(db, await _movie(db), max_price="25.00")
        retailer = await _retailer(db)

        first = await _check(db, want, retailer, price="19.99", when=datetime(2026, 4, 1, 3, 0))
        await queue_price_drop_alerts(db, [AlertCandidate(check=first, wanted=want)])
        recovered = await _check(db, want, retailer, price="29.99", when=datetime(2026, 4, 2, 3, 0))
        await queue_price_drop_alerts(db, [AlertCandidate(check=recovered, wanted=want)])
        again = await _check(db, want, retailer, price="18.00", when=datetime(2026, 4, 3, 3, 0))
        await queue_price_drop_alerts(db, [AlertCandidate(check=again, wanted=want)])

        mine = [a for a in await _deals_notifications(db) if a.user_id == person.id]
        assert len(mine) == 2
        assert {a.title for a in mine} == {"Heat is £19.99", "Heat is £18.00"}

    async def test_a_drop_at_one_shop_is_not_silenced_by_a_drop_at_another(
        self, db: AsyncSession
    ) -> None:
        """Two shops are two offers on two pages. Either is worth hearing about."""
        person = await _profile(db)
        want = await _want(db, await _movie(db), max_price="25.00")
        one = await _retailer(db, "Shop One")
        two = await _retailer(db, "Shop Two")

        first = await _check(db, want, one, price="19.99", when=datetime(2026, 4, 1, 3, 0))
        await queue_price_drop_alerts(db, [AlertCandidate(check=first, wanted=want)])
        second = await _check(db, want, two, price="18.50", when=datetime(2026, 4, 1, 3, 5))
        await queue_price_drop_alerts(db, [AlertCandidate(check=second, wanted=want)])

        mine = [a for a in await _deals_notifications(db) if a.user_id == person.id]
        assert len(mine) == 2

    async def test_a_substituted_format_alerts_but_says_so(self, db: AsyncSession) -> None:
        """`DECISIONS.md` #105: a want for 4K is a want for 4K.

        Suppressing the alert would hide a real find; sending it silently would let
        "Heat is £19.99" mean the Blu-ray when the want was the 4K.
        """
        person = await _profile(db)
        want = await _want(db, await _movie(db), max_price="25.00")
        retailer = await _retailer(db)
        check = await _check(db, want, retailer, price="19.99", when=datetime(2026, 4, 1, 3, 0))

        await queue_price_drop_alerts(
            db,
            [AlertCandidate(check=check, wanted=want, substituted_format="Blu-ray")],
        )

        mine = [a for a in await _deals_notifications(db) if a.user_id == person.id]
        assert "Blu-ray" in mine[0].body
        assert "not the format you wanted" in mine[0].body

    async def test_a_different_edition_alerts_but_says_so(self, db: AsyncSession) -> None:
        person = await _profile(db)
        want = await _want(db, await _movie(db), max_price="25.00")
        want.preferred_edition = "Limited Edition"
        retailer = await _retailer(db)
        check = await _check(db, want, retailer, price="19.99", when=datetime(2026, 4, 1, 3, 0))

        await queue_price_drop_alerts(
            db, [AlertCandidate(check=check, wanted=want, edition_matched=False)]
        )

        mine = [a for a in await _deals_notifications(db) if a.user_id == person.id]
        assert "different edition" in mine[0].body
        assert "Limited Edition" in mine[0].body

    async def test_turning_deals_off_suppresses_the_alert(self, db: AsyncSession) -> None:
        """§6.1 × §5.6 — the acceptance criterion Batch 11 shipped, with its real sender.

        The notification is still written, `suppressed`, naming the category. What must not
        happen is a delivery.
        """
        person = await _profile(db)
        db.add(
            NotificationPreference(
                id=uuid.uuid4(), user_id=person.id, deals_enabled=False, digest_mode=False
            )
        )
        await db.flush()
        want = await _want(db, await _movie(db), max_price="25.00")
        retailer = await _retailer(db)
        check = await _check(db, want, retailer, price="19.99", when=datetime(2026, 4, 1, 3, 0))

        await queue_price_drop_alerts(db, [AlertCandidate(check=check, wanted=want)])

        mine = [a for a in await _deals_notifications(db) if a.user_id == person.id]
        assert len(mine) == 1
        assert mine[0].status == "suppressed"
        assert mine[0].suppressed_reason == "category_disabled"


class TestAggregation:
    """§5.8 — *"after backdating test data, rows > 90 days are aggregated and raw removed"*."""

    async def test_old_checks_are_rolled_up_and_the_raw_rows_removed(
        self, db: AsyncSession
    ) -> None:
        want = await _want(db, await _movie(db))
        retailer = await _retailer(db)
        now = datetime(2026, 9, 10, 3, 0)
        old_day = now - timedelta(days=120)
        for price in ("10.00", "20.00", "30.00"):
            await _check(db, want, retailer, price=price, when=old_day)

        result = await aggregate_old_checks(db, older_than_days=90, now=now)

        assert result.days_aggregated == 1
        assert result.rows_written == 1
        assert result.raw_rows_removed == 3
        row = (
            (
                await db.execute(
                    select(PriceHistoryDaily).where(PriceHistoryDaily.wanted_id == want.id)
                )
            )
            .scalars()
            .one()
        )
        assert row.min_price == Decimal("10.00")
        assert row.max_price == Decimal("30.00")
        assert row.avg_price == Decimal("20.00")
        assert row.check_count == 3
        assert row.retailer_name_snapshot == "Test Shop"

        remaining = (
            (await db.execute(select(PriceCheck).where(PriceCheck.wanted_id == want.id)))
            .scalars()
            .all()
        )
        assert list(remaining) == [], "the raw rows are gone"

    async def test_recent_checks_are_left_alone(self, db: AsyncSession) -> None:
        want = await _want(db, await _movie(db))
        retailer = await _retailer(db)
        now = datetime(2026, 9, 10, 3, 0)
        await _check(db, want, retailer, price="19.99", when=now - timedelta(days=10))

        result = await aggregate_old_checks(db, older_than_days=90, now=now)

        assert result.days_aggregated == 0
        assert result.raw_rows_removed == 0
        kept = (
            (await db.execute(select(PriceCheck).where(PriceCheck.wanted_id == want.id)))
            .scalars()
            .all()
        )
        assert len(list(kept)) == 1

    async def test_each_day_becomes_its_own_row(self, db: AsyncSession) -> None:
        want = await _want(db, await _movie(db))
        retailer = await _retailer(db)
        now = datetime(2026, 9, 10, 3, 0)
        await _check(db, want, retailer, price="10.00", when=now - timedelta(days=120))
        await _check(db, want, retailer, price="12.00", when=now - timedelta(days=119))

        result = await aggregate_old_checks(db, older_than_days=90, now=now)

        assert result.days_aggregated == 2
        assert result.rows_written == 2

    async def test_re_running_merges_with_a_weighted_average(self, db: AsyncSession) -> None:
        """Only reachable if a run aggregated and then failed before deleting.

        The average must be re-weighted by both counts: a plain mean of two means is wrong
        whenever the counts differ, and this asserts the arithmetic rather than the shape.
        """
        want = await _want(db, await _movie(db))
        retailer = await _retailer(db)
        now = datetime(2026, 9, 10, 3, 0)
        day = now - timedelta(days=120)
        # First roll-up: three checks averaging 20.00.
        for price in ("10.00", "20.00", "30.00"):
            await _check(db, want, retailer, price=price, when=day)
        await aggregate_old_checks(db, older_than_days=90, now=now)

        # A fourth check for the same day appears and is rolled up again.
        await _check(db, want, retailer, price="40.00", when=day)
        result = await aggregate_old_checks(db, older_than_days=90, now=now)

        assert result.rows_merged == 1
        row = (
            (
                await db.execute(
                    select(PriceHistoryDaily).where(PriceHistoryDaily.wanted_id == want.id)
                )
            )
            .scalars()
            .one()
        )
        assert row.check_count == 4
        assert row.min_price == Decimal("10.00")
        assert row.max_price == Decimal("40.00")
        # (20.00 × 3 + 40.00 × 1) / 4 = 25.00 — not (20.00 + 40.00) / 2 = 30.00.
        assert row.avg_price == Decimal("25.00")

    async def test_a_check_whose_want_is_gone_still_aggregates(self, db: AsyncSession) -> None:
        """`price_checks.wanted_id` is nullable by design — the check is a historical fact.

        `ON CONFLICT` cannot match a NULL key, which is why the roll-up groups in Python.
        """
        retailer = await _retailer(db)
        now = datetime(2026, 9, 10, 3, 0)
        orphan = PriceCheck(
            id=uuid.uuid4(),
            wanted_id=None,
            retailer_id=retailer.id,
            retailer_name_snapshot=retailer.name,
            price=Decimal("11.00"),
            currency="GBP",
            url="https://93.184.216.34/p/orphan",
            checked_at=now - timedelta(days=120),
        )
        db.add(orphan)
        await db.flush()

        result = await aggregate_old_checks(db, older_than_days=90, now=now)

        assert result.rows_written == 1
        row = (
            (
                await db.execute(
                    select(PriceHistoryDaily).where(PriceHistoryDaily.wanted_id.is_(None))
                )
            )
            .scalars()
            .one()
        )
        assert row.avg_price == Decimal("11.00")


class TestDailyRun:
    """§5.5 — the nightly pass and the record it leaves."""

    async def _run(
        self, db: AsyncSession, page: str, *, dry_run: bool = False
    ) -> tuple[object, StubSender]:
        sender = StubSender()
        transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            summary = await run_daily_scrape(
                db,
                sender=sender,
                client=client,
                trigger="manual",
                dry_run=dry_run,
                polite_pause=0,
                now=datetime(2026, 4, 1, 3, 0),
            )
        return summary, sender

    async def test_the_run_records_what_it_did(self, db: AsyncSession) -> None:
        await _profile(db)
        await _want(db, await _movie(db))
        await _retailer(db)

        summary, _ = await self._run(db, SHOP_PAGE)

        run = (
            (await db.execute(select(ScrapeRun).where(ScrapeRun.id == uuid.UUID(summary.run_id))))  # type: ignore[attr-defined]
            .scalars()
            .one()
        )
        assert run.finished_at_utc is not None, "a finished run says so"
        assert run.trigger == "manual"
        assert run.attempted >= 1
        assert run.written >= 1
        assert run.error is None

    async def test_written_matches_attempted_minus_not_stocked(self, db: AsyncSession) -> None:
        """**`DECISIONS.md` #112's corrected §5.5 criterion, stated as a test.**

        As originally written it wanted rows ≈ (wants × retailers), which assumes every shop
        stocks every film. The corrected form compares against the pairs that were actually
        answerable, and this is the shape that catches a silent mass failure: if the
        scrapers break, attempted-minus-not-stocked stays high while written collapses.
        """
        await _profile(db)
        await _want(db, await _movie(db))
        await _retailer(db)

        summary, _ = await self._run(db, SHOP_PAGE)

        run = (
            (await db.execute(select(ScrapeRun).where(ScrapeRun.id == uuid.UUID(summary.run_id))))  # type: ignore[attr-defined]
            .scalars()
            .one()
        )
        answerable = run.attempted - 0  # nothing was not-stocked on this page
        assert run.not_stocked == 0
        assert run.written >= answerable * 0.9, "within the ≤10% failure margin"

    async def test_a_shop_that_has_not_got_it_is_not_counted_as_attempted(
        self, db: AsyncSession
    ) -> None:
        """`DECISIONS.md` #107 — a correct "no" is not a failure and not a gap.

        The retailer is card-shaped here, because that is where #107's detection lives and
        what every enabled shop is. A nightly job is exactly the thing that would turn this
        wrong: three correct refusals in a row auto-disable a working scraper.
        """
        await _profile(db)
        await _want(db, await _movie(db))
        await _retailer(db, config=CARD_CONFIG)

        summary, _ = await self._run(db, NOT_STOCKED_PAGE)

        run = (
            (await db.execute(select(ScrapeRun).where(ScrapeRun.id == uuid.UUID(summary.run_id))))  # type: ignore[attr-defined]
            .scalars()
            .one()
        )
        assert run.not_stocked == 1
        assert run.attempted == 0
        assert run.failed == 0, "answering honestly is not failing"

    async def test_failures_are_recorded_with_retailer_and_reason(self, db: AsyncSession) -> None:
        """§5.5's own words — and readable the morning after, not only in a log.

        The page lists the film and its price is unreadable, which is a real failure. It
        used to be an **empty** page, and that is no longer one: `DECISIONS.md` #125 makes
        "the shop returned nothing" `no_results`, because it is equally what a shop
        without the film and a selector that has stopped matching both look like.
        """
        await _profile(db)
        await _want(db, await _movie(db))
        await _retailer(db, config=CARD_CONFIG)

        summary, _ = await self._run(db, UNREADABLE_PRICE_PAGE)

        run = (
            (await db.execute(select(ScrapeRun).where(ScrapeRun.id == uuid.UUID(summary.run_id))))  # type: ignore[attr-defined]
            .scalars()
            .one()
        )
        assert run.failed >= 1
        assert run.no_results == 0, "a listed film with a bad price is a failure, not silence"
        assert run.failures, "the failure is written down"
        assert run.failures[0]["retailer"] == "Test Shop"
        assert run.failures[0]["reason"]

    async def test_an_empty_page_is_recorded_as_no_results_not_a_failure(
        self, db: AsyncSession
    ) -> None:
        """`DECISIONS.md` #125, and the clause of #107 it supersedes.

        #107 decided a page with no titled listing "still takes a strike", so that a site
        redesign would eventually auto-disable the shop. The live run of 2026-09-10
        disproved the premise: **eight of eleven "failures" were shops answering "we have
        not got that"** — Arrow's "Sorry We Couldn't Find Any Results", 101 Films' "0
        results found". Three such nights would have switched a working shop off.
        """
        await _profile(db)
        await _want(db, await _movie(db))
        await _retailer(db, config=CARD_CONFIG)

        summary, _ = await self._run(db, "<html><body>nothing here</body></html>")

        run = (
            (await db.execute(select(ScrapeRun).where(ScrapeRun.id == uuid.UUID(summary.run_id))))  # type: ignore[attr-defined]
            .scalars()
            .one()
        )
        assert run.no_results == 1
        assert run.failed == 0, "an empty page is not the scraper breaking"
        assert run.failures == []

        retailer = (await db.execute(select(Retailer))).scalars().one()
        # Flagged, so a broken selector is visible — and **not** disabled, which is the
        # trade #125 records.
        assert retailer.last_scrape_status == "no_results"
        assert retailer.enabled is True
        assert retailer.consecutive_failures == 0

    async def test_a_dry_run_writes_nothing(self, db: AsyncSession) -> None:
        await _profile(db)
        want = await _want(db, await _movie(db))
        await _retailer(db)

        summary, sender = await self._run(db, SHOP_PAGE, dry_run=True)

        assert summary.scrape.written == 0  # type: ignore[attr-defined]
        assert sender.sent == []
        checks = (
            (await db.execute(select(PriceCheck).where(PriceCheck.wanted_id == want.id)))
            .scalars()
            .all()
        )
        assert list(checks) == []

    async def test_a_run_end_to_end_alerts_and_pushes(self, db: AsyncSession) -> None:
        """The whole §5.6 path: scrape a £19.99 listing against a £25 threshold."""
        person = await _profile(db)
        db.add(
            PushSubscription(
                id=uuid.uuid4(),
                user_id=person.id,
                endpoint="https://fcm.googleapis.com/fcm/send/batch20",
                p256dh="B" + "A" * 86,
                auth="A" * 22,
                device_label="phone",
            )
        )
        await _want(db, await _movie(db), max_price="25.00")
        await _retailer(db)
        await db.flush()

        summary, sender = await self._run(db, SHOP_PAGE)

        assert summary.alerts_queued >= 1  # type: ignore[attr-defined]
        assert summary.pushes_sent >= 1  # type: ignore[attr-defined]
        assert sender.sent, "a price drop reached the device"
