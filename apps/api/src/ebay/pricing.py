"""Turning matched listings into a price — Batch 28, Phase 4.1.

Phase 4.1's acceptance asks for *"a reasonable UK median price"*. `DECISIONS.md` #129 is
the reason that is not one number:

> the match filter is where the batch's effort goes, not the median function; a result
> failing the match assertion is a **failure, never data**; and the segmentation must key
> on category IDs and ``conditionId`` rather than title regexes.

So this module reports a **table**, not a figure: one row per *(format, edition,
condition)* with its own median, sample size and range, plus the tally of everything that
was rejected and why. A caller that wants a single number asks
:meth:`PriceEstimate.headline` for one and is told how many listings it rests on — which
is the difference between "£12.21 from 56 plain Blu-rays" and "£30.45", the number that
comes out when nothing is segmented at all.

**Everything here is asking prices.** Sold comps are unobtainable — Marketplace Insights
is closed to new applicants and eBay put sold listings behind a login wall in late August
2026 (`DECISIONS.md` #16, re-confirmed by #126) — so every surface that shows one of these
numbers must say "current asking prices". :attr:`PriceEstimate.basis` carries that string
so the UI cannot forget to.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .matching import CONDITION_LABELS, UNKNOWN_CONDITION_ID, Listing, MatchVerdict

#: What every number produced here actually is. Not a sold price, and the UI must say so.
ASKING_PRICES = "current asking prices"

_PENNY = Decimal("0.01")

#: eBay's condition code for a new copy.
NEW_CONDITION_ID = "1000"
#: The codes of a used copy: Like new, Used, Very good, Good, Acceptable. Pooled when one of
#: them alone is too few to have a median (Batch X1, MK47-02).
USED_CONDITION_IDS = frozenset({"2750", "3000", "4000", "5000", "6000"})


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(_PENNY, rounding=ROUND_HALF_UP)


def median(prices: list[Decimal]) -> Decimal:
    """The median, kept in :class:`~decimal.Decimal` throughout.

    The stdlib's ``median`` averages the middle pair for an even-length sample, which for
    money means a half-penny, and it works in floats. Rounded here rather than at the wire,
    so the stored number and the displayed one are the same number.
    """
    ordered = sorted(prices)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return _round(ordered[middle])
    return _round((ordered[middle - 1] + ordered[middle]) / 2)


@dataclass(frozen=True)
class PriceSegment:
    """One comparable group of listings, and what it says.

    A segment is only meaningful alongside :attr:`sample_size`. Two listings have a median
    and it means nothing; the field is mandatory in the API response for that reason.
    """

    format_code: str
    edition: str
    condition_id: str
    condition_label: str
    sample_size: int
    median: Decimal
    low: Decimal
    high: Decimal
    currency: str


@dataclass
class PriceEstimate:
    """Every segment a search produced, plus what it threw away.

    :attr:`rejected` is not diagnostics — it is part of the answer. A search that matched
    four listings out of two hundred is either a rare disc or a broken filter, and the
    tally is what tells the two apart. `DECISIONS.md` #122 is the standing reminder: a
    parser that silently extracted nothing from ten live pages looked exactly like a
    parser that worked.
    """

    film_title: str
    format_code: str | None
    marketplace_id: str
    considered: int
    matched: int
    segments: list[PriceSegment] = field(default_factory=list)
    rejected: dict[str, int] = field(default_factory=dict)
    #: Payload entries that were not the shape the Browse API documents — no title, no
    #: price, an unparseable amount. Counted apart from rejections because a rise here is
    #: eBay changing its response, not a noisy keyword search.
    unusable: int = 0
    basis: str = ASKING_PRICES
    #: Every used listing's median and count together, per ``(format, edition)`` — Batch
    #: X1. A median of medians would not be a median, so it is taken from the prices here.
    used_pooled: dict[tuple[str, str], tuple[Decimal, int]] = field(default_factory=dict)

    def headline(
        self, *, format_code: str | None = None, condition_id: str | None = None
    ) -> PriceSegment | None:
        """The one segment a caller should show, or ``None`` if there isn't one.

        Standard editions only — a collector steelbook is a different product at a
        different price, and quoting one as "what this disc is worth" is `DECISIONS.md`
        #129's 149% overstatement wearing a different hat. Among the candidates the
        **largest sample** wins rather than the cheapest or the newest, because the
        question this answers is "what is the going rate", and the going rate is where the
        listings are.
        """
        wanted_format = format_code or self.format_code
        candidates = [
            segment
            for segment in self.segments
            if segment.edition == "standard"
            and (wanted_format is None or segment.format_code == wanted_format)
            and (condition_id is None or segment.condition_id == condition_id)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda segment: (segment.sample_size, -segment.median))


def summarise(
    judged: list[tuple[Listing, MatchVerdict]],
    *,
    film_title: str,
    format_code: str | None,
    marketplace_id: str,
    unusable: int = 0,
) -> PriceEstimate:
    """Group judged listings into segments and count the rejections.

    Segmenting on ``(format, edition, conditionId)`` and nothing else is deliberate.
    ``condition`` — the display string — is never a key: #129 found 16 distinct values for
    about five real conditions in a single result set, across three languages, so keying on
    it would split *New* into five segments of a dozen and call each one a sample.
    """
    grouped: dict[tuple[str, str, str], list[Listing]] = {}
    rejected: Counter[str] = Counter()

    for listing, verdict in judged:
        if not verdict.ok or verdict.format_code is None:
            rejected[verdict.reason or "rejected"] += 1
            continue
        key = (verdict.format_code, verdict.edition, listing.condition_id)
        grouped.setdefault(key, []).append(listing)

    segments: list[PriceSegment] = []
    for (found_format, edition, condition_id), listings in grouped.items():
        prices = [listing.price for listing in listings]
        segments.append(
            PriceSegment(
                format_code=found_format,
                edition=edition,
                condition_id=condition_id,
                condition_label=CONDITION_LABELS.get(
                    condition_id, "Not stated" if condition_id == UNKNOWN_CONDITION_ID else "Other"
                ),
                sample_size=len(prices),
                median=median(prices),
                low=_round(min(prices)),
                high=_round(max(prices)),
                currency=listings[0].currency,
            )
        )

    segments.sort(key=lambda segment: (-segment.sample_size, segment.format_code, segment.edition))

    used: dict[tuple[str, str], list[Decimal]] = {}
    for (found_format, edition, condition_id), listings in grouped.items():
        if condition_id in USED_CONDITION_IDS:
            used.setdefault((found_format, edition), []).extend(
                listing.price for listing in listings
            )

    return PriceEstimate(
        film_title=film_title,
        format_code=format_code,
        marketplace_id=marketplace_id,
        considered=len(judged) + unusable,
        matched=sum(segment.sample_size for segment in segments),
        segments=segments,
        rejected=dict(rejected.most_common()),
        unusable=unusable,
        used_pooled={key: (median(prices), len(prices)) for key, prices in used.items()},
    )


def naive_median(listings: list[Listing]) -> Decimal | None:
    """The median over *everything* a keyword search returned — the number not to use.

    Kept because `DECISIONS.md` #129's central claim is a comparison, and a comparison
    needs both halves. ``tests/test_ebay_pricing.py`` asserts against the captured
    fixtures that this is materially higher than the matched median, so the day the match
    filter quietly stops filtering, a test fails instead of a price silently inflating.
    """
    if not listings:
        return None
    return median([listing.price for listing in listings])
