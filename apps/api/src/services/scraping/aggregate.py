"""Rolling raw price checks into daily history — §5.8.

*"Nightly job rolls price_checks > 90 days old into price_history_daily."* The raw rows are
deleted afterwards, which is the point: Batch 21's chart wants a point per day, not every
individual check from four months ago.

**Aggregate and delete in one transaction.** Doing them separately has two failure modes and
both are bad — aggregate-then-crash double-counts the day on the next run, delete-then-crash
loses the history outright. Inside one transaction the pair is atomic, which also makes the
unique index below a belt rather than the only brace.

**Written in Python rather than as one big `INSERT … SELECT … GROUP BY`.** Not for
performance — the volume is a few thousand rows a year — but because `wanted_id` and
`retailer_id` are both nullable (a deleted want leaves the check standing, by design), and
`ON CONFLICT` cannot match a NULL key. Grouping here means the null cases are handled
explicitly and visibly instead of silently escaping the deduplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.price_check import PriceCheck
from src.models.price_history import RETENTION_DAYS, PriceHistoryDaily

logger = structlog.get_logger(__name__)


@dataclass
class AggregationResult:
    """What one roll-up did — read back by the endpoint and asserted on."""

    days_aggregated: int = 0
    rows_written: int = 0
    rows_merged: int = 0
    raw_rows_removed: int = 0


def _round_money(value: Decimal) -> Decimal:
    """Two decimal places, half-up — how money rounds, and what the column holds."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def aggregate_old_checks(
    db: AsyncSession,
    *,
    older_than_days: int = RETENTION_DAYS,
    now: datetime | None = None,
) -> AggregationResult:
    """Roll every check older than the cutoff into `price_history_daily`, then delete it.

    ``older_than_days`` is a parameter rather than a constant so §5.8's acceptance —
    *"after backdating test data, rows > 90 days are aggregated and raw rows removed"* —
    can be driven without a fixture that has to invent a date four months ago and then
    rely on the clock agreeing with it.
    """
    now = now or utcnow()
    cutoff = now - timedelta(days=older_than_days)
    result = AggregationResult()

    day = func.date(PriceCheck.checked_at).label("day")
    groups = (
        await db.execute(
            select(
                PriceCheck.wanted_id,
                PriceCheck.retailer_id,
                day,
                func.min(PriceCheck.price).label("min_price"),
                func.max(PriceCheck.price).label("max_price"),
                func.avg(PriceCheck.price).label("avg_price"),
                func.count().label("check_count"),
                # A group is one want at one shop on one day, so these are constant
                # within it; `min` is just a way to select the value under a GROUP BY.
                func.min(PriceCheck.retailer_name_snapshot).label("retailer_name"),
                func.min(PriceCheck.currency).label("currency"),
            )
            .where(PriceCheck.checked_at < cutoff)
            .group_by(PriceCheck.wanted_id, PriceCheck.retailer_id, day)
        )
    ).all()

    for group in groups:
        result.days_aggregated += 1
        existing = (
            await db.execute(
                select(PriceHistoryDaily).where(
                    PriceHistoryDaily.wanted_id.is_(None)
                    if group.wanted_id is None
                    else PriceHistoryDaily.wanted_id == group.wanted_id,
                    PriceHistoryDaily.retailer_id.is_(None)
                    if group.retailer_id is None
                    else PriceHistoryDaily.retailer_id == group.retailer_id,
                    PriceHistoryDaily.date == group.day,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(
                PriceHistoryDaily(
                    wanted_id=group.wanted_id,
                    retailer_id=group.retailer_id,
                    retailer_name_snapshot=group.retailer_name,
                    date=group.day,
                    min_price=_round_money(group.min_price),
                    max_price=_round_money(group.max_price),
                    avg_price=_round_money(Decimal(group.avg_price)),
                    currency=group.currency,
                    check_count=group.check_count,
                )
            )
            result.rows_written += 1
            continue

        # A day already rolled up, being rolled up again — only reachable if an earlier
        # run aggregated and then failed before deleting. Merge rather than replace: the
        # average is re-weighted by both counts, because a plain mean of two means is
        # wrong whenever the counts differ.
        total = existing.check_count + group.check_count
        existing.avg_price = _round_money(
            (
                existing.avg_price * existing.check_count
                + Decimal(group.avg_price) * group.check_count
            )
            / total
        )
        existing.min_price = min(existing.min_price, _round_money(group.min_price))
        existing.max_price = max(existing.max_price, _round_money(group.max_price))
        existing.check_count = total
        result.rows_merged += 1

    if result.days_aggregated:
        # The rows about to be deleted are exactly the ones just counted into the groups,
        # so the total is already known — no second query, and no reliance on `rowcount`,
        # which SQLAlchemy exposes only on the untyped cursor result.
        result.raw_rows_removed = sum(group.check_count for group in groups)
        await db.execute(delete(PriceCheck).where(PriceCheck.checked_at < cutoff))

    logger.info(
        "price_checks_aggregated",
        cutoff=cutoff.isoformat(),
        days=result.days_aggregated,
        written=result.rows_written,
        merged=result.rows_merged,
        removed=result.raw_rows_removed,
    )
    return result
