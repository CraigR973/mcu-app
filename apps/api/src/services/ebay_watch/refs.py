"""What a film on a format usually asks on eBay UK — Batch T8a's yardstick for a deal.

One search with the film page's estimator (`src/ebay/estimate.py`), so "usually" means the
same number "What is it worth?" would show. It is kept for a fortnight: the scan meets the
same film again within days, and asking prices do not move that fast.

**A used copy is compared only with used copies** (Batch X1, MK47-02; #239 amended). The
estimator splits listings by eBay's condition code. A used listing (Like new, Used, Very good,
Good, Acceptable) is judged against its own condition's median when that has three or more
standard-edition listings behind it, else against every used listing pooled when they have
three or more, else not at all. Never against New's median: 227 of the 265 finds of 26 Sep–
9 Oct were, whatever their condition, so a used disc at a used price read as a deal. And
never against a used group whose median is above New's, which says the group is thin or odd.

Any other listing, New among them, keeps T8a's rule: its own condition's median with three
or more behind it, otherwise the headline (the largest group). A median of two is one
seller's asking price (#129).
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
from src.ebay.pricing import MIN_SAMPLE, NEW_CONDITION_ID, USED_CONDITION_IDS, PriceEstimate
from src.matching.engine import searchable_title
from src.models.ebay_watch import EbayPriceRef

#: How long a usual price stands before it is searched again.
FRESH_FOR = timedelta(days=14)

#: ``by_condition``'s entry for every used listing pooled (Batch X1). A usual price stored
#: before X1 has none, and is searched again the next time a listing needs it.
USED_POOL = "used"


@dataclass(frozen=True)
class Yardstick:
    """The price a listing is compared with, and how many listings stand behind it."""

    median: Decimal
    sample_size: int


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


def _values(estimate: PriceEstimate, format_code: str) -> dict[str, object]:
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
    return {
        "status": "priced" if priced else "not_priced",
        "median": headline.median if priced and headline else None,
        "sample_size": headline.sample_size if headline else 0,
        "by_condition": by_condition,
    }


async def stored_ref(
    db: AsyncSession, *, movie_id: uuid.UUID, format_code: str, now: datetime
) -> EbayPriceRef | None:
    """The stored usual price, if it is still fresh and has the used listings pooled."""
    ref = await db.scalar(
        select(EbayPriceRef).where(
            EbayPriceRef.movie_id == movie_id, EbayPriceRef.format_code == format_code
        )
    )
    if (
        ref is not None
        and ref.checked_utc >= now - FRESH_FOR
        and USED_POOL in (ref.by_condition or {})
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
