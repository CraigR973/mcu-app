"""Segmentation and medians — Batch 28, Phase 4.1.

The central assertion in this file is :func:`test_the_naive_median_is_wildly_higher_than_the
_matched_one`. `DECISIONS.md` #129's whole claim is a **comparison** — a keyword search's
median against the real disc's — so the guard against the match filter quietly stopping is
a test that re-takes that comparison on every run, from the captured payloads.

Without it, a filter that silently degrades to "accept everything" still passes every
segment test: the segments would simply be larger and the prices higher, and nothing would
say so.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.ebay.matching import Listing, listing_from_summary, match
from src.ebay.pricing import ASKING_PRICES, median, naive_median, summarise

FIXTURES = Path(__file__).parent / "fixtures"


def _summaries(name: str) -> list[dict[str, Any]]:
    payload = json.loads((FIXTURES / name).read_text())
    items: list[dict[str, Any]] = payload["itemSummaries"]
    return items


BLADE_RUNNER = _summaries("ebay_browse_blade_runner_2049.json")
JAWS = _summaries("ebay_browse_jaws.json")


def _estimate(summaries: list[dict[str, Any]], film: str, format_code: str | None = "blu_ray"):
    judged = []
    unusable = 0
    for summary in summaries:
        listing = listing_from_summary(summary)
        if listing is None:
            unusable += 1
            continue
        judged.append((listing, match(listing, film_title=film)))
    return summarise(
        judged,
        film_title=film,
        format_code=format_code,
        marketplace_id="EBAY_GB",
        unusable=unusable,
    )


def _listings(*prices: str, condition_id: str = "1000") -> list[Listing]:
    return [
        Listing(
            item_id=f"v1|{index}|0",
            title="Jaws [Blu-ray]",
            price=Decimal(price),
            currency="GBP",
            condition_id=condition_id,
            web_url="https://www.ebay.co.uk/itm/1",
            leaf_category_ids=("617",),
            country="GB",
            item_group_type=None,
        )
        for index, price in enumerate(prices)
    ]


# ---------------------------------------------------------------------------
# The median itself
# ---------------------------------------------------------------------------


def test_an_odd_sample_takes_the_middle_value() -> None:
    assert median([Decimal("3"), Decimal("11"), Decimal("7")]) == Decimal("7.00")


def test_an_even_sample_averages_the_middle_pair_and_rounds_to_a_penny() -> None:
    """£10.00 and £10.05 average to £10.025, which is not an amount of money."""
    assert median([Decimal("10.00"), Decimal("10.05")]) == Decimal("10.03")


def test_the_median_never_becomes_a_float() -> None:
    result = median([Decimal("0.10"), Decimal("0.20"), Decimal("0.30")])
    assert isinstance(result, Decimal)
    assert result == Decimal("0.20")


# ---------------------------------------------------------------------------
# #129's comparison, re-taken on every run
# ---------------------------------------------------------------------------


def test_the_naive_median_is_wildly_higher_than_the_matched_one() -> None:
    """`DECISIONS.md` #129 measured £30.45 against £12.21 — a 149% overstatement.

    The exact figures move with the market, so what is asserted is the *relationship*: the
    median over everything a keyword search returns must be far above the median of the
    plain disc. If this ever fails, the match filter has stopped filtering — which is the
    one failure mode that leaves every other test in this file green.
    """
    for summaries, film in ((BLADE_RUNNER, "Blade Runner 2049"), (JAWS, "Jaws")):
        everything = [
            listing
            for summary in summaries
            if (listing := listing_from_summary(summary)) is not None
        ]
        naive = naive_median(everything)
        estimate = _estimate(summaries, film)
        headline = estimate.headline()

        assert naive is not None
        assert headline is not None
        assert naive > headline.median * 2, f"{film}: naive {naive} vs matched {headline.median}"


def test_the_headline_rests_on_a_sample_worth_having() -> None:
    for summaries, film in ((BLADE_RUNNER, "Blade Runner 2049"), (JAWS, "Jaws")):
        headline = _estimate(summaries, film).headline()
        assert headline is not None
        assert headline.sample_size >= 10, film
        assert headline.edition == "standard"
        assert headline.format_code == "blu_ray"


def test_a_collector_edition_is_never_the_headline() -> None:
    """The £925 FilmArena box is a real listing and a real market. It is not "what this
    disc is worth", and quoting it as one is #129's overstatement wearing a different hat."""
    for summaries, film in ((BLADE_RUNNER, "Blade Runner 2049"), (JAWS, "Jaws")):
        estimate = _estimate(summaries, film)
        headline = estimate.headline()
        assert headline is not None
        assert headline.edition == "standard"

        # Like for like. A one-listing *DVD* collector segment can undercut a Blu-ray
        # headline without saying anything about editions, so the comparison is made
        # within the headline's own format — where the split is what stops the £925
        # FilmArena box from setting the price of a £9 disc.
        same_format = [
            segment
            for segment in estimate.segments
            if segment.edition == "collector" and segment.format_code == headline.format_code
        ]
        assert same_format, f"{film}: no collector segment for {headline.format_code}"
        assert headline.median < min(segment.median for segment in same_format)


# ---------------------------------------------------------------------------
# What the answer has to carry with it
# ---------------------------------------------------------------------------


def test_every_considered_listing_is_accounted_for() -> None:
    """Matched + rejected + unusable = considered. A filter that loses listings silently
    is a filter nobody can audit."""
    for summaries, film in ((BLADE_RUNNER, "Blade Runner 2049"), (JAWS, "Jaws")):
        estimate = _estimate(summaries, film)
        assert estimate.matched + sum(estimate.rejected.values()) + estimate.unusable == (
            estimate.considered
        )
        assert estimate.considered == len(summaries)


def test_the_basis_says_asking_prices_and_not_sold_prices() -> None:
    estimate = _estimate(JAWS, "Jaws")
    assert estimate.basis == ASKING_PRICES == "current asking prices"


def test_segments_are_keyed_on_the_numeric_condition_not_its_display_string() -> None:
    """#129: 16 distinct display strings for about five real conditions, in three
    languages. Keying on the string splits *New* into five samples of a dozen."""
    estimate = _estimate(BLADE_RUNNER, "Blade Runner 2049")
    for segment in estimate.segments:
        assert segment.condition_id.isdigit() or segment.condition_id == "unknown"


def test_a_missing_condition_is_labelled_rather_than_defaulted() -> None:
    judged = [
        (listing, match(listing, film_title="Jaws"))
        for listing in _listings("9.99", "12.99", condition_id="unknown")
    ]
    estimate = summarise(judged, film_title="Jaws", format_code="blu_ray", marketplace_id="EBAY_GB")
    assert [s.condition_label for s in estimate.segments] == ["Not stated"]


def test_segments_are_ordered_largest_sample_first() -> None:
    estimate = _estimate(BLADE_RUNNER, "Blade Runner 2049")
    sizes = [segment.sample_size for segment in estimate.segments]
    assert sizes == sorted(sizes, reverse=True)


def test_a_headline_can_be_asked_for_by_condition() -> None:
    """What Batch 29's upgrade flow needs: the price for *this* disc's condition."""
    estimate = _estimate(BLADE_RUNNER, "Blade Runner 2049")
    new_only = estimate.headline(condition_id="1000")
    assert new_only is not None
    assert new_only.condition_id == "1000"
    assert new_only.condition_label == "New"


def test_no_segment_means_no_headline_rather_than_a_guess() -> None:
    estimate = summarise(
        [], film_title="A Film Nobody Lists", format_code="blu_ray", marketplace_id="EBAY_GB"
    )
    assert estimate.segments == []
    assert estimate.headline() is None
    assert estimate.matched == 0
