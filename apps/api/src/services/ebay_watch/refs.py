"""Cached eBay price references for deal and shop checks.

One search uses the film page's estimator (`src/ebay/estimate.py`). AA10b stores the disc's
used figure in ``usedFigure`` and judges every eBay listing against it, including New ones.
The earlier condition medians remain for shop alerts; ``yardstick`` still reads them there.
References last a fortnight, and an older row without ``usedFigure`` is fetched again.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ebay.estimate import EbaySearch, estimate_price
from src.ebay.pricing import (
    MIN_SAMPLE,
    NEW_CONDITION_ID,
    USED_CONDITION_IDS,
    PriceEstimate,
    used_value,
)
from src.matching.engine import searchable_title
from src.models.ebay_watch import EbayPriceRef

#: How long a usual price stands before it is searched again.
FRESH_FOR = timedelta(days=14)

#: ``by_condition``'s entry for every used listing pooled (Batch X1). A usual price stored
#: before X1 has none, and is searched again the next time a listing needs it.
USED_POOL = "used"
USED_FIGURE = "usedFigure"


@dataclass(frozen=True)
class Yardstick:
    """The price a listing is compared with, and how many listings stand behind it."""

    median: Decimal
    sample_size: int


@dataclass(frozen=True)
class DealFigure:
    """The one used-disc figure against which every eBay listing is tested."""

    amount: Decimal
    sample_size: int
    basis: str

    def sources(self) -> list[dict[str, str]]:
        if self.basis == "sales":
            name = f"{self.sample_size} observed sales, postage in"
        elif self.basis == "used_quartile":
            name = "Lower quartile of used asks, postage in"
        else:
            name = "New asking median scaled to used"
        return [{"source": name, "price": str(self.amount)}]


def deal_figure(ref: EbayPriceRef) -> DealFigure | None:
    group = (ref.by_condition or {}).get(USED_FIGURE)
    if not isinstance(group, dict) or group.get("price") is None:
        return None
    count = int(group.get("n") or 0)
    basis = group.get("basis")
    if count < MIN_SAMPLE or basis not in {"used_quartile", "new_scaled"}:
        return None
    return DealFigure(Decimal(str(group["price"])), count, basis)


def _group(groups: dict[str, object], key: str) -> Yardstick | None:
    """One stored group's median, if it has enough listings behind it to be one."""
    group = groups.get(key)
    if not isinstance(group, dict) or group.get("median") is None:
        return None
    count = int(group.get("n") or 0)
    if count < MIN_SAMPLE:
        return None
    return Yardstick(Decimal(str(group["median"])), count)


def yardstick(ref: EbayPriceRef, condition_id: str) -> Yardstick | None:
    """What a listing in this condition is judged against, or ``None`` for nothing fair."""
    groups = ref.by_condition or {}
    if condition_id in USED_CONDITION_IDS:
        new = _group(groups, NEW_CONDITION_ID)
        for candidate in (_group(groups, condition_id), _group(groups, USED_POOL)):
            if candidate is not None and (new is None or candidate.median <= new.median):
                return candidate
        return None
    own = _group(groups, condition_id)
    if own is not None:
        return own
    if ref.status == "priced" and ref.median is not None and ref.sample_size >= MIN_SAMPLE:
        return Yardstick(ref.median, ref.sample_size)
    return None


def _values(estimate: PriceEstimate, format_code: str, *, factor: Decimal) -> dict[str, object]:
    headline = estimate.headline(format_code=format_code)
    priced = headline is not None and headline.sample_size >= MIN_SAMPLE
    by_condition: dict[str, dict[str, object]] = {
        segment.condition_id: {"median": str(segment.median), "n": segment.sample_size}
        for segment in estimate.segments
        if segment.edition == "standard" and segment.format_code == format_code
    }
    pooled = estimate.used_pooled.get((format_code, "standard"))
    by_condition[USED_POOL] = (
        {"median": str(pooled.median), "n": pooled.count} if pooled else {"median": None, "n": 0}
    )
    used = used_value(estimate, format_code, factor=factor)
    by_condition[USED_FIGURE] = (
        {"price": str(used.price), "n": used.sample_size, "basis": used.basis}
        if used is not None
        else {"price": None, "n": 0, "basis": None}
    )
    return {
        "status": "priced" if priced else "not_priced",
        "median": headline.median if priced and headline else None,
        "sample_size": headline.sample_size if headline else 0,
        "by_condition": by_condition,
    }


async def stored_ref(
    db: AsyncSession,
    *,
    movie_id: uuid.UUID,
    format_code: str,
    now: datetime,
    require_used_figure: bool = False,
) -> EbayPriceRef | None:
    """A fresh reference, with the figure required by the caller."""
    ref = await db.scalar(
        select(EbayPriceRef).where(
            EbayPriceRef.movie_id == movie_id, EbayPriceRef.format_code == format_code
        )
    )
    if (
        ref is not None
        and ref.checked_utc >= now - FRESH_FOR
        and (USED_FIGURE if require_used_figure else USED_POOL) in (ref.by_condition or {})
    ):
        return ref
    return None


async def fetch_ref(
    db: AsyncSession,
    client: EbaySearch,
    *,
    movie_id: uuid.UUID,
    title: str,
    format_code: str,
    now: datetime,
    year: int | None = None,
) -> EbayPriceRef:
    """One search for the film on the format, stored as its usual price. Raises what the
    client raises."""
    estimate = await estimate_price(
        client,
        film_title=searchable_title(title, identified=True),
        format_code=format_code,
        film_year=year,
    )
    # The sparse-used fallback uses the same measured format factor as a valuation.
    from src.services.valuation import used_factors

    factors = await used_factors(db)
    values = {
        **_values(estimate, format_code, factor=factors[format_code].factor),
        "checked_utc": now,
    }
    await db.execute(
        insert(EbayPriceRef)
        .values(id=uuid.uuid4(), movie_id=movie_id, format_code=format_code, **values)
        .on_conflict_do_update(constraint="uq_ebay_price_refs_movie_format", set_=values)
    )
    fresh = await db.scalar(
        select(EbayPriceRef)
        .where(EbayPriceRef.movie_id == movie_id, EbayPriceRef.format_code == format_code)
        .execution_options(populate_existing=True)
    )
    if fresh is None:  # pragma: no cover - written by the statement above
        raise RuntimeError("the usual price was not stored")
    return fresh
