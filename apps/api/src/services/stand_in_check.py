"""AA10c: does the stand-in read what discs sell for? (`DECISIONS.md` #290, #394).

AA10b values a disc with fewer than three recorded sales at a **stand-in**: the lower quartile
of current used Buy It Now asks, postage in. #290 left one question open until AA10a had about
four weeks of recorded sales: would today's used median (the rule before AA10b, the median of
used asks with postage left out) be closer? This answers it, read-only, from what is stored.

**How a disc is judged (the owner's word, 22 Nov, #394).** For every disc with recorded
sales whose value is the lower-quartile stand-in, each figure's error is ``(figure − sales
median) / sales median``, with the sales median taken as the valuation takes it: one sold
listing counts once, postage in, over the last 90 days (#291). Only discs with
:data:`MIN_SALES` or more sales count; below that one sale is the whole "median". The closer
figure is the one with the smaller **median absolute error** across those discs, the typical
miss on one disc. A tie keeps the lower quartile, the figure already in place. The bias (the
median signed error), its middle half and the ratio of the summed figures to the summed sales
are reported beside it, so a reader can see how the two differ, not only which won.

**What it reads.** :func:`discs_query` and :func:`deals_query` are ordinary selects over the
app's own tables, and :func:`gather` runs them on a session. ``src.scripts.stand_in_check``
sends the same selects to the live database through the read-only role, so the live report and
the tests cannot disagree about which rows count. It writes nothing.

**The deals check (MK53-04, wave 2, #383).** Of the live eBay deals whose film and format have
recorded sales, how many cost, postage in, at or above that disc's sales median: a deal that
is no saving on what copies actually sell for. 16 Nov's review measured a fifth to a third.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final, Literal

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ebay.pricing import MIN_SAMPLE, median
from src.models.deal import Deal, live_deal
from src.models.ebay_sold import EbayUsedListing
from src.models.valuation import DiscValuation
from src.services.ebay_sold import RETENTION

#: Fewer sales than this and a disc's "median" is one or two sales: the valuation's own bar for
#: "based on N sales" (`pricing.MIN_SAMPLE`), the owner's choice on 22 Nov.
MIN_SALES = MIN_SAMPLE

LOWER_QUARTILE: Final = "lower_quartile"
USED_MEDIAN: Final = "used_median"
Figure = Literal["lower_quartile", "used_median"]

#: Why a disc with recorded sales is left out of the comparison, in the order they are tried.
NO_VALUE = "no stored value (an eBay-tracked film not owned)"
NOT_PRICED = "not priced"
NEW_SCALED = "valued from New, so no lower-quartile stand-in"
OTHER_BASIS = "valued by an older rule"
NO_USED_MEDIAN = "no used median stored"
TOO_FEW_SALES = "fewer sales than the minimum"

_RATIO = Decimal("0.0001")


@dataclass(frozen=True)
class DiscEvidence:
    """One film and format with recorded sales, and the figures stored for it."""

    movie_id: uuid.UUID
    format_code: str
    #: Each sold listing's last price with postage, once (#291).
    sales: tuple[Decimal, ...]
    #: Null when no value row exists for the pair.
    status: str | None
    value_basis: str | None
    #: The stored value: the lower-quartile stand-in when ``value_basis`` is ``used_quartile``.
    price: Decimal | None
    used_median: Decimal | None


@dataclass(frozen=True)
class Errors:
    """How far one figure sits from the sales medians, as fractions (0.05 is 5% high)."""

    #: The bias: the median signed error.
    median: Decimal
    #: The middle half of the signed errors.
    p25: Decimal
    p75: Decimal
    #: The typical miss on one disc, which decides the closer figure.
    median_absolute: Decimal
    #: The figures summed over the summed sales medians, which is what a total feels.
    total_ratio: Decimal


@dataclass(frozen=True)
class Comparison:
    min_sales: int
    #: Discs with at least one recorded sale, and the sales behind them.
    discs_with_sales: int
    sales_recorded: int
    #: Discs compared and the sales behind those.
    compared: int
    sales_used: int
    excluded: dict[str, int] = field(default_factory=dict)
    lower_quartile: Errors | None = None
    used_median: Errors | None = None
    #: Discs on which each figure is strictly the nearer; the rest are level.
    lower_quartile_closer: int = 0
    used_median_closer: int = 0
    keep: Figure = LOWER_QUARTILE


@dataclass(frozen=True)
class DealEvidence:
    price: Decimal
    sales: tuple[Decimal, ...]


@dataclass(frozen=True)
class DealCheck:
    live: int
    #: Live deals whose film and format have at least one recorded sale.
    checkable: int
    #: Of those, priced at or above the disc's sales median.
    at_or_above: int
    #: The same, for discs with :data:`MIN_SALES` or more sales.
    checkable_min: int
    at_or_above_min: int


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------


def relative_error(figure: Decimal, sales_median: Decimal) -> Decimal:
    """``(figure − sales median) / sales median``; positive when the figure reads high."""
    if sales_median <= 0:
        raise ValueError("a sales median must be positive")
    return (figure - sales_median) / sales_median


def quantile(values: Sequence[Decimal], q: Decimal) -> Decimal:
    """Linear between the nearest zero-based ranks, as `pricing.lower_quartile` takes it."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    rank = Decimal(len(ordered) - 1) * q
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def _ratio(value: Decimal) -> Decimal:
    return value.quantize(_RATIO, rounding=ROUND_HALF_UP)


def errors(figures: Sequence[Decimal], sales_medians: Sequence[Decimal]) -> Errors:
    signed = [
        relative_error(figure, sold) for figure, sold in zip(figures, sales_medians, strict=True)
    ]
    return Errors(
        median=_ratio(quantile(signed, Decimal("0.5"))),
        p25=_ratio(quantile(signed, Decimal("0.25"))),
        p75=_ratio(quantile(signed, Decimal("0.75"))),
        median_absolute=_ratio(quantile([abs(error) for error in signed], Decimal("0.5"))),
        total_ratio=_ratio(sum(figures, Decimal(0)) / sum(sales_medians, Decimal(0))),
    )


def exclusion(disc: DiscEvidence, *, min_sales: int = MIN_SALES) -> str | None:
    """Why ``disc`` is not compared, or ``None`` when it is."""
    if disc.status is None:
        return NO_VALUE
    if disc.status != "priced" or disc.price is None:
        return NOT_PRICED
    if disc.value_basis == "new_scaled":
        return NEW_SCALED
    if disc.value_basis != "used_quartile":
        return OTHER_BASIS
    if disc.used_median is None:
        return NO_USED_MEDIAN
    if len(disc.sales) < min_sales:
        return TOO_FEW_SALES
    return None


def compare(discs: Iterable[DiscEvidence], *, min_sales: int = MIN_SALES) -> Comparison:
    """Both figures against the sales, and which to keep as the stand-in."""
    discs = [disc for disc in discs if disc.sales]
    excluded: dict[str, int] = {}
    kept: list[tuple[DiscEvidence, Decimal]] = []
    for disc in discs:
        reason = exclusion(disc, min_sales=min_sales)
        if reason is None:
            kept.append((disc, median(list(disc.sales))))
        else:
            excluded[reason] = excluded.get(reason, 0) + 1
    base = Comparison(
        min_sales=min_sales,
        discs_with_sales=len(discs),
        sales_recorded=sum(len(disc.sales) for disc in discs),
        compared=len(kept),
        sales_used=sum(len(disc.sales) for disc, _ in kept),
        excluded=excluded,
    )
    if not kept:
        return base
    sold = [sales_median for _, sales_median in kept]
    quartiles = [disc.price for disc, _ in kept if disc.price is not None]
    medians = [disc.used_median for disc, _ in kept if disc.used_median is not None]
    quartile_errors = errors(quartiles, sold)
    median_errors = errors(medians, sold)
    misses = [
        (abs(relative_error(q, s)), abs(relative_error(m, s)))
        for q, m, s in zip(quartiles, medians, sold, strict=True)
    ]
    keep: Figure = (
        USED_MEDIAN
        if median_errors.median_absolute < quartile_errors.median_absolute
        else LOWER_QUARTILE
    )
    return Comparison(
        **{
            **base.__dict__,
            "lower_quartile": quartile_errors,
            "used_median": median_errors,
            "lower_quartile_closer": sum(1 for q, m in misses if q < m),
            "used_median_closer": sum(1 for q, m in misses if m < q),
            "keep": keep,
        }
    )


def check_deals(deals: Iterable[DealEvidence], *, min_sales: int = MIN_SALES) -> DealCheck:
    deals = list(deals)
    checkable = [(deal, median(list(deal.sales))) for deal in deals if deal.sales]
    at_or_above = [(deal, sold) for deal, sold in checkable if deal.price >= sold]
    return DealCheck(
        live=len(deals),
        checkable=len(checkable),
        at_or_above=len(at_or_above),
        checkable_min=sum(1 for deal, _ in checkable if len(deal.sales) >= min_sales),
        at_or_above_min=sum(1 for deal, _ in at_or_above if len(deal.sales) >= min_sales),
    )


# ---------------------------------------------------------------------------
# What it reads
# ---------------------------------------------------------------------------


def _sales(now: datetime) -> Any:
    """Each film and format's recorded sales, postage in, as the valuation counts them."""
    return (
        select(
            EbayUsedListing.movie_id.label("movie_id"),
            EbayUsedListing.format_code.label("format_code"),
            func.array_agg(EbayUsedListing.price + EbayUsedListing.postage).label("sales"),
        )
        .where(
            EbayUsedListing.status == "sold",
            EbayUsedListing.sold_count > 0,
            EbayUsedListing.ended_at_utc >= now - RETENTION,
        )
        .group_by(EbayUsedListing.movie_id, EbayUsedListing.format_code)
        .subquery()
    )


def discs_query(now: datetime) -> Select[Any]:
    sales = _sales(now)
    return (
        select(
            sales.c.movie_id,
            sales.c.format_code,
            sales.c.sales,
            DiscValuation.status,
            DiscValuation.value_basis,
            DiscValuation.price,
            DiscValuation.used_median,
        )
        .select_from(sales)
        .outerjoin(
            DiscValuation,
            and_(
                DiscValuation.movie_id == sales.c.movie_id,
                DiscValuation.format_code == sales.c.format_code,
            ),
        )
        .order_by(sales.c.movie_id, sales.c.format_code)
    )


def deals_query(now: datetime) -> Select[Any]:
    """Live eBay deals for a known film and format, with that disc's recorded sales."""
    sales = _sales(now)
    return (
        select(Deal.price, sales.c.sales)
        .select_from(Deal)
        .outerjoin(
            sales,
            and_(sales.c.movie_id == Deal.movie_id, sales.c.format_code == Deal.format_code),
        )
        .where(
            Deal.retailer_name_snapshot == "eBay",
            Deal.retailer_id.is_(None),
            Deal.movie_id.is_not(None),
            Deal.format_code.is_not(None),
            live_deal(now),
        )
        .order_by(Deal.first_seen_at_utc)
    )


def _decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _amounts(value: object) -> tuple[Decimal, ...]:
    """An array of amounts, from a driver (a list) or from Postgres's text form (``{1.5,2}``)."""
    if value is None:
        return ()
    if isinstance(value, str):
        body = value.strip().removeprefix("{").removesuffix("}")
        return tuple(sorted(Decimal(item) for item in body.split(",") if item))
    if isinstance(value, Iterable):
        return tuple(sorted(Decimal(str(item)) for item in value))
    raise TypeError(f"not an array of amounts: {value!r}")


def discs_from_rows(rows: Iterable[Mapping[Any, Any]]) -> list[DiscEvidence]:
    return [
        DiscEvidence(
            movie_id=uuid.UUID(str(row["movie_id"])),
            format_code=str(row["format_code"]),
            sales=_amounts(row["sales"]),
            status=None if row["status"] is None else str(row["status"]),
            value_basis=None if row["value_basis"] is None else str(row["value_basis"]),
            price=_decimal(row["price"]),
            used_median=_decimal(row["used_median"]),
        )
        for row in rows
    ]


def deals_from_rows(rows: Iterable[Mapping[Any, Any]]) -> list[DealEvidence]:
    return [
        DealEvidence(price=Decimal(str(row["price"])), sales=_amounts(row["sales"])) for row in rows
    ]


async def gather(
    db: AsyncSession, *, now: datetime
) -> tuple[list[DiscEvidence], list[DealEvidence]]:
    discs = (await db.execute(discs_query(now))).mappings().all()
    deals = (await db.execute(deals_query(now))).mappings().all()
    return discs_from_rows(discs), deals_from_rows(deals)
