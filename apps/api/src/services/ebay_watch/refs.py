"""What a film on a format usually asks on eBay UK — Batch T8a's yardstick for a deal.

One search with the film page's estimator (`src/ebay/estimate.py`), so "usually" means the
same number "What is it worth?" would show. It is kept for a fortnight: the scan meets the
same film again within days, and asking prices do not move that fast.

**A used copy is compared with used copies.** The estimator splits listings by eBay's
condition code. When the listing's condition has three or more standard-edition listings
behind it, that group's median is the yardstick; otherwise the headline (the largest
group) is. Fewer than three listings in any group, and there is no yardstick at all:
a median of two is one seller's asking price (#129).
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
from src.ebay.pricing import PriceEstimate
from src.matching.engine import searchable_title
from src.models.ebay_watch import EbayPriceRef
from src.services.valuation import MIN_SAMPLE

#: How long a usual price stands before it is searched again.
FRESH_FOR = timedelta(days=14)


@dataclass(frozen=True)
class Yardstick:
    """The price a listing is compared with, and how many listings stand behind it."""

    median: Decimal
    sample_size: int


def yardstick(ref: EbayPriceRef, condition_id: str) -> Yardstick | None:
    """The listing's condition group's median if it has enough listings, else the headline."""
    group = (ref.by_condition or {}).get(condition_id)
    if isinstance(group, dict) and int(group.get("n") or 0) >= MIN_SAMPLE:
        return Yardstick(Decimal(str(group["median"])), int(group["n"]))
    if ref.status == "priced" and ref.median is not None and ref.sample_size >= MIN_SAMPLE:
        return Yardstick(ref.median, ref.sample_size)
    return None


def _values(estimate: PriceEstimate, format_code: str) -> dict[str, object]:
    headline = estimate.headline(format_code=format_code)
    priced = headline is not None and headline.sample_size >= MIN_SAMPLE
    by_condition = {
        segment.condition_id: {"median": str(segment.median), "n": segment.sample_size}
        for segment in estimate.segments
        if segment.edition == "standard" and segment.format_code == format_code
    }
    return {
        "status": "priced" if priced else "not_priced",
        "median": headline.median if priced and headline else None,
        "sample_size": headline.sample_size if headline else 0,
        "by_condition": by_condition,
    }


async def stored_ref(
    db: AsyncSession, *, movie_id: uuid.UUID, format_code: str, now: datetime
) -> EbayPriceRef | None:
    """The stored usual price, if it is still fresh."""
    ref = await db.scalar(
        select(EbayPriceRef).where(
            EbayPriceRef.movie_id == movie_id, EbayPriceRef.format_code == format_code
        )
    )
    if ref is not None and ref.checked_utc >= now - FRESH_FOR:
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
) -> EbayPriceRef:
    """One search for the film on the format, stored as its usual price. Raises what the
    client raises."""
    estimate = await estimate_price(
        client, film_title=searchable_title(title, identified=True), format_code=format_code
    )
    values = {**_values(estimate, format_code), "checked_utc": now}
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
