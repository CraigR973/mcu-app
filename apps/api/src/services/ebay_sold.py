"""AA10a: observe used Buy It Now listings weekly and value discs from sold ones.

The first pass is an admin action. Until it has been started, the existing ``cron-ebay``
job does no sold-listing work; this keeps the first live eBay pass at Craig's checkpoint.
Every later scheduled pass has its own 600-call UTC-day ceiling. Together with the existing
500 watch and 750 valuation shares, the jobs reserve at most 1,850 of 5,000 daily calls.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Literal

import structlog
from sqlalchemy import and_, delete, func, or_, select, union, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.database import AsyncSessionLocal
from src.ebay.client import DEFAULT_MAX_RETRIES, EbayClient, EbayError, EbayNotConfigured
from src.ebay.estimate import search_query
from src.ebay.matching import match
from src.ebay.pricing import USED_CONDITION_IDS, median
from src.models.ebay_sold import EbayUsedListing, EbayUsedRun, EbayUsedScan
from src.models.ebay_watch import EbayPriceRef
from src.models.movie import Movie
from src.models.valuation import DiscValuation
from src.services.ebay_watch.client import WatchClient
from src.services.ebay_watch.listings import OUT_OF_STOCK, parse_utc, scan_listing
from src.services.valuation import REVALUE_AFTER, _film_formats

logger = structlog.get_logger(__name__)

DAILY_SHARE = 600
WEEK = timedelta(days=7)
RETENTION = timedelta(days=90)
STALE_RUN = timedelta(minutes=30)
MIN_CALLS = DEFAULT_MAX_RETRIES + 1
GBP = "GBP"
DISC_CATEGORY = "617"
FIXED_PRICE = "buyingOptions:{FIXED_PRICE}"

StartReason = Literal["started", "inactive", "running", "budget_spent"]


@dataclass(frozen=True)
class TrackedDisc:
    movie_id: uuid.UUID
    format_code: str
    title: str
    identified: bool
    year: int | None
    is_tv: bool


@dataclass(frozen=True)
class ObservedListing:
    legacy_item_id: str
    price: Decimal
    postage: Decimal
    condition_code: str


@dataclass(frozen=True)
class EndVerdict:
    status: Literal["active", "sold", "ended"]
    sold_count: int | None
    ended_at: datetime | None


def observed(summary: dict[str, object], disc: TrackedDisc) -> ObservedListing | None:
    """Only comparable UK, standard-edition, used fixed-price discs with stated postage."""
    item = scan_listing(summary)
    if item is None or not item.buy_now or item.postage is None:
        return None
    if item.listing.currency != GBP or item.listing.condition_id not in USED_CONDITION_IDS:
        return None
    verdict = match(
        item.listing,
        film_title=disc.title,
        format_code=disc.format_code,
        country="GB",
        film_year=disc.year,
        is_series=disc.is_tv,
    )
    if not verdict.ok or verdict.edition != "standard":
        return None
    return ObservedListing(
        legacy_item_id=item.legacy_id,
        price=item.listing.price,
        postage=item.postage,
        condition_code=item.listing.condition_id,
    )


def end_verdict(payload: dict[str, object] | None, *, now: datetime) -> EndVerdict:
    """A 404 is ended, never evidence of a sale; an explicit sold count is required."""
    if payload is None:
        return EndVerdict("ended", None, now)
    raw = payload.get("estimatedAvailabilities")
    availability = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], dict) else {}
    status = availability.get("estimatedAvailabilityStatus")
    sold = availability.get("estimatedSoldQuantity")
    sold_count = (
        sold if isinstance(sold, int) and not isinstance(sold, bool) and sold >= 0 else None
    )
    ended = parse_utc(payload.get("itemEndDate"))
    if status == OUT_OF_STOCK and sold_count is not None and sold_count > 0:
        return EndVerdict("sold", sold_count, ended if ended and ended <= now else now)
    if status == OUT_OF_STOCK or (ended is not None and ended <= now):
        return EndVerdict("ended", sold_count, ended if ended and ended <= now else now)
    return EndVerdict("active", sold_count, None)


async def tracked_discs(db: AsyncSession, *, now: datetime, limit: int) -> list[TrackedDisc]:
    """Owned and deal-tracked film/format pairs due a weekly search."""
    owned = _film_formats()
    pairs = union(
        select(owned.c.movie_id, owned.c.format_code),
        select(EbayPriceRef.movie_id, EbayPriceRef.format_code),
    ).subquery()
    rows = await db.execute(
        select(
            pairs.c.movie_id,
            pairs.c.format_code,
            Movie.title,
            Movie.tmdb_id,
            Movie.year,
            Movie.is_tv,
        )
        .join(Movie, Movie.id == pairs.c.movie_id)
        .outerjoin(
            EbayUsedScan,
            and_(
                EbayUsedScan.movie_id == pairs.c.movie_id,
                EbayUsedScan.format_code == pairs.c.format_code,
            ),
        )
        .where(
            Movie.deleted_at.is_(None),
            or_(EbayUsedScan.id.is_(None), EbayUsedScan.checked_utc <= now - WEEK),
        )
        .order_by(EbayUsedScan.checked_utc.asc().nulls_first(), Movie.title, pairs.c.format_code)
        .limit(limit)
    )
    return [
        TrackedDisc(movie_id, code, title, tmdb_id is not None, year, bool(is_tv))
        for movie_id, code, title, tmdb_id, year, is_tv in rows
    ]


async def _record_search(
    db: AsyncSession, disc: TrackedDisc, items: list[ObservedListing], *, now: datetime
) -> None:
    """A successful search advances the weekly clock; an error leaves it due."""
    ids = {item.legacy_item_id for item in items}
    previous = (
        (
            await db.scalars(select(EbayUsedListing).where(EbayUsedListing.legacy_item_id.in_(ids)))
        ).all()
        if ids
        else []
    )
    existing_by_id = {listing.legacy_item_id: listing for listing in previous}
    relisted_sold = False
    for item in items:
        existing = existing_by_id.get(item.legacy_item_id)
        if existing is None:
            existing = EbayUsedListing(
                id=uuid.uuid4(),
                legacy_item_id=item.legacy_item_id,
                movie_id=disc.movie_id,
                format_code=disc.format_code,
                price=item.price,
                postage=item.postage,
                condition_code=item.condition_code,
                first_seen_utc=now,
                last_seen_utc=now,
                status="active",
                ended_at_utc=None,
                sold_count=None,
                missing_checked_utc=None,
            )
            db.add(existing)
            existing_by_id[item.legacy_item_id] = existing
        elif existing.movie_id == disc.movie_id and existing.format_code == disc.format_code:
            relisted_sold |= existing.status == "sold"
            existing.price = item.price
            existing.postage = item.postage
            existing.condition_code = item.condition_code
            existing.last_seen_utc = now
            existing.status = "active"
            existing.ended_at_utc = None
            existing.sold_count = None
            existing.missing_checked_utc = None
    if relisted_sold:
        await db.flush()
        await refresh_sales_value(db, disc.movie_id, disc.format_code, now=now)
    await db.execute(
        insert(EbayUsedScan)
        .values(
            id=uuid.uuid4(), movie_id=disc.movie_id, format_code=disc.format_code, checked_utc=now
        )
        .on_conflict_do_update(
            constraint="uq_ebay_used_scans_movie_format", set_={"checked_utc": now}
        )
    )
    await db.commit()


async def pending_missing(db: AsyncSession, *, limit: int) -> list[EbayUsedListing]:
    """Items absent from a successful search and not checked in this disappearance episode."""
    rows = await db.scalars(
        select(EbayUsedListing)
        .join(
            EbayUsedScan,
            and_(
                EbayUsedScan.movie_id == EbayUsedListing.movie_id,
                EbayUsedScan.format_code == EbayUsedListing.format_code,
            ),
        )
        .where(
            EbayUsedListing.status == "active",
            EbayUsedListing.missing_checked_utc.is_(None),
            EbayUsedListing.last_seen_utc < EbayUsedScan.checked_utc,
        )
        .order_by(EbayUsedListing.last_seen_utc)
        .limit(limit)
    )
    return list(rows)


async def refresh_sales_value(
    db: AsyncSession, movie_id: uuid.UUID, format_code: str, *, now: datetime
) -> None:
    """One sold listing counts once; its count is retained but older unit sales are unknown."""
    rows = await db.execute(
        select(EbayUsedListing.price, EbayUsedListing.postage).where(
            EbayUsedListing.movie_id == movie_id,
            EbayUsedListing.format_code == format_code,
            EbayUsedListing.status == "sold",
            EbayUsedListing.sold_count > 0,
            EbayUsedListing.ended_at_utc >= now - RETENTION,
        )
    )
    totals = sorted(Decimal(price) + Decimal(postage) for price, postage in rows)
    values = {
        "sales_count": len(totals),
        "sales_price": median(totals) if len(totals) >= 3 else None,
        "sales_low": totals[0] if totals else None,
        "sales_high": totals[-1] if totals else None,
        "sales_checked_utc": now,
    }
    result = await db.execute(
        update(DiscValuation)
        .where(DiscValuation.movie_id == movie_id, DiscValuation.format_code == format_code)
        .values(**values)
        .returning(DiscValuation.id)
    )
    if result.first() is None and len(totals) >= 3:
        # A recently added disc need not wait for the monthly asking-price pass to have a
        # sales-backed value. The old asking columns remain empty and due for that pass.
        movie = await db.get(Movie, movie_id)
        assert movie is not None
        db.add(
            DiscValuation(
                id=uuid.uuid4(),
                movie_id=movie_id,
                format_code=format_code,
                status="not_priced",
                price=None,
                currency=GBP,
                sample_size=0,
                condition_label=None,
                value_basis=None,
                factor=None,
                low=None,
                high=None,
                used_median=None,
                used_count=0,
                new_median=None,
                new_count=0,
                matched=0,
                considered=0,
                basis="current asking prices",
                search_query=search_query(movie.title, format_code),
                checked_utc=now - REVALUE_AFTER - timedelta(days=1),
                run_id=None,
                **values,
            )
        )


async def _check_missing(
    db: AsyncSession, client: WatchClient, listing: EbayUsedListing, *, now: datetime
) -> EndVerdict:
    payload = await client.get_item_by_legacy_id(listing.legacy_item_id)
    verdict = end_verdict(payload, now=now)
    listing.missing_checked_utc = now
    listing.sold_count = verdict.sold_count
    if verdict.status != "active":
        listing.status = verdict.status
        listing.ended_at_utc = verdict.ended_at
        if verdict.status == "sold":
            await db.flush()
            await refresh_sales_value(db, listing.movie_id, listing.format_code, now=now)
    await db.commit()
    return verdict


async def purge_ended(db: AsyncSession, *, now: datetime) -> int:
    """Remove ended content 90 days after its end, and drop expired sales from values."""
    old = (
        await db.execute(
            select(EbayUsedListing.movie_id, EbayUsedListing.format_code)
            .where(
                EbayUsedListing.status != "active", EbayUsedListing.ended_at_utc < now - RETENTION
            )
            .distinct()
        )
    ).all()
    result = await db.execute(
        delete(EbayUsedListing)
        .where(EbayUsedListing.status != "active", EbayUsedListing.ended_at_utc < now - RETENTION)
        .returning(EbayUsedListing.id)
    )
    count = len(result.all())
    for movie_id, format_code in old:
        await refresh_sales_value(db, movie_id, format_code, now=now)
    await db.commit()
    return count


def _day_start(now: datetime) -> datetime:
    return datetime.combine(now.date(), time.min)


async def budget_left(db: AsyncSession, *, now: datetime) -> int:
    spent = await db.scalar(
        select(func.coalesce(func.sum(EbayUsedRun.calls), 0)).where(
            EbayUsedRun.started_utc >= _day_start(now)
        )
    )
    left = DAILY_SHARE - int(spent or 0)
    return left if left >= MIN_CALLS else 0


async def latest_run(db: AsyncSession) -> EbayUsedRun | None:
    rows = await db.scalars(select(EbayUsedRun).order_by(EbayUsedRun.started_utc.desc()).limit(1))
    return rows.first()


async def start_run(
    db: AsyncSession, *, trigger: Literal["admin", "job"], now: datetime | None = None
) -> tuple[StartReason, EbayUsedRun | None]:
    now = now or utcnow()
    if trigger == "job" and not await db.scalar(
        select(EbayUsedRun.id)
        .where(EbayUsedRun.trigger == "admin", EbayUsedRun.status.in_(("finished", "budget_spent")))
        .limit(1)
    ):
        return "inactive", None
    await db.execute(
        update(EbayUsedRun)
        .where(EbayUsedRun.status == "running", EbayUsedRun.heartbeat_utc < now - STALE_RUN)
        .values(status="abandoned", finished_utc=now, last_error="No heartbeat for 30 minutes")
    )
    await db.commit()
    if await db.scalar(select(EbayUsedRun.id).where(EbayUsedRun.status == "running")):
        return "running", None
    left = await budget_left(db, now=now)
    if not left:
        return "budget_spent", None
    run = EbayUsedRun(
        id=uuid.uuid4(),
        trigger=trigger,
        status="running",
        started_utc=now,
        heartbeat_utc=now,
        finished_utc=None,
        budget=left,
        calls=0,
        searched=0,
        checked=0,
        sold=0,
        ended=0,
        last_error=None,
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return "running", None
    return "started", run


async def work_run(
    db: AsyncSession,
    client: WatchClient,
    run_id: uuid.UUID,
    *,
    clock: Callable[[], datetime] = utcnow,
) -> EbayUsedRun:
    run = await db.get(EbayUsedRun, run_id)
    if run is None or run.status != "running":
        raise ValueError(f"used-listing run {run_id} is not running")
    baseline = client.search_calls
    budget_cap = run.budget

    def room() -> bool:
        return client.search_calls - baseline + client.attempts_per_search <= budget_cap

    try:
        await purge_ended(db, now=clock())
        # Pending checks first, so a call-limited run does not strand vanished listings.
        for listing in await pending_missing(db, limit=run.budget):
            if not room():
                break
            verdict = await _check_missing(db, client, listing, now=clock())
            run.checked += 1
            run.sold += verdict.status == "sold"
            run.ended += verdict.status == "ended"
            run.calls = client.search_calls - baseline
            run.heartbeat_utc = clock()
            await db.commit()

        for disc in await tracked_discs(db, now=clock(), limit=run.budget):
            if not room():
                break
            try:
                payload = await client.search(
                    search_query(disc.title, disc.format_code),
                    category_ids=DISC_CATEGORY,
                    filter=FIXED_PRICE,
                )
            except EbayError as exc:
                run.last_error = f"{disc.title} ({disc.format_code}): {exc}"
                run.calls = client.search_calls - baseline
                run.heartbeat_utc = clock()
                await db.commit()
                if exc.status_code == 429:
                    break
                continue
            seen = [
                item
                for raw in payload.get("itemSummaries") or []
                if isinstance(raw, dict)
                if (item := observed(raw, disc)) is not None
            ]
            await _record_search(db, disc, seen, now=clock())
            run.searched += 1
            run.calls = client.search_calls - baseline
            run.heartbeat_utc = clock()
            await db.commit()
            # Check vanished items now, but never exceed this run's retry-safe budget.
            for listing in await pending_missing(db, limit=run.budget):
                if not room():
                    break
                verdict = await _check_missing(db, client, listing, now=clock())
                run.checked += 1
                run.sold += verdict.status == "sold"
                run.ended += verdict.status == "ended"
                run.calls = client.search_calls - baseline
                run.heartbeat_utc = clock()
                await db.commit()
        run.status = "budget_spent" if not room() else "finished"
    except (EbayNotConfigured, EbayError) as exc:
        await db.rollback()
        run = await db.get(EbayUsedRun, run_id)
        assert run is not None
        run.status = "stopped"
        run.last_error = str(exc)[:500]
    except Exception as exc:
        await db.rollback()
        run = await db.get(EbayUsedRun, run_id)
        assert run is not None
        run.status = "stopped"
        run.last_error = f"{type(exc).__name__}: {exc}"[:500]
        raise
    finally:
        assert run is not None
        run.calls = client.search_calls - baseline
        run.heartbeat_utc = clock()
        run.finished_utc = clock()
        await db.commit()
    logger.info(
        "ebay_used_run_finished",
        status=run.status,
        calls=run.calls,
        searched=run.searched,
        checked=run.checked,
        sold=run.sold,
        ended=run.ended,
    )
    return run


async def continue_admin_run(run_id: uuid.UUID) -> None:
    """The first live pass happens only after the admin explicitly starts it."""
    async with AsyncSessionLocal() as db, EbayClient() as client:
        await work_run(db, client, run_id)
