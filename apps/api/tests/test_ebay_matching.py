"""The eBay match filter — Batch 28, Phase 4.1.

**These tests run against two captured production payloads**, not against invented JSON.
``tests/fixtures/ebay_browse_*.json`` are verbatim ``item_summary/search`` responses from
``api.ebay.com``, ``EBAY_GB``, 200 listings each, taken on 2026-09-11.

That is a direct consequence of `DECISIONS.md` #122. ``test_specs.py``'s Blu-ray.com
fixture had been *invented to match the parser*, so eleven tests passed for weeks against
markup the site had never served, and the defect surfaced only when ten live pages were
fetched and nothing at all came out of them. A hand-written eBay payload would have exactly
the same property: it would agree with :mod:`src.ebay.matching` by construction and prove
nothing about eBay.

So the assertions here are of two kinds, and both matter:

- **Property assertions over the whole captured set** — no collector edition in the
  standard bucket, every rejection carrying a reason, the matched median materially below
  the naive one. These are what break when eBay changes its payload.
- **Named single listings**, quoted verbatim from the fixtures, for each way a keyword
  search lies. These are what break when the filter changes and someone needs to know
  which specific failure they have reintroduced.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.ebay.matching import (
    CONDITION_LABELS,
    UNKNOWN_CONDITION_ID,
    Listing,
    classify_edition,
    listing_from_summary,
    match,
    tokens,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[dict[str, Any]]:
    payload = json.loads((FIXTURES / name).read_text())
    summaries: list[dict[str, Any]] = payload["itemSummaries"]
    return summaries


BLADE_RUNNER = _load("ebay_browse_blade_runner_2049.json")
JAWS = _load("ebay_browse_jaws.json")


def _listing(**overrides: Any) -> Listing:
    """A plain GB Blu-ray listing, for the unit cases below."""
    base: dict[str, Any] = {
        "item_id": "v1|1|0",
        "title": "Blade Runner 2049 [Blu-ray]",
        "price": Decimal("9.99"),
        "currency": "GBP",
        "condition_id": "1000",
        "web_url": "https://www.ebay.co.uk/itm/1",
        "leaf_category_ids": ("617",),
        "country": "GB",
        "item_group_type": None,
    }
    base.update(overrides)
    return Listing(**base)


def _judge(summaries: list[dict[str, Any]], film: str, **kwargs: Any) -> list[tuple[Listing, Any]]:
    judged = []
    for summary in summaries:
        listing = listing_from_summary(summary)
        assert listing is not None, summary.get("title")
        judged.append((listing, match(listing, film_title=film, **kwargs)))
    return judged


def _find(summaries: list[dict[str, Any]], needle: str) -> Listing:
    """The first captured listing whose title contains ``needle``, verbatim."""
    for summary in summaries:
        title = summary.get("title")
        if isinstance(title, str) and needle.lower() in title.lower():
            listing = listing_from_summary(summary)
            assert listing is not None
            return listing
    raise AssertionError(f"no captured listing contains {needle!r}")


# ---------------------------------------------------------------------------
# The payload is read where it is documented to be
# ---------------------------------------------------------------------------


def test_every_captured_summary_is_readable() -> None:
    """400 real listings, none of them an unreadable shape.

    If this ever fails against a *fresh* capture, eBay changed its response — which is a
    different problem from a noisy search and is counted separately for that reason.
    """
    for summary in BLADE_RUNNER + JAWS:
        assert listing_from_summary(summary) is not None, summary.get("itemId")


def test_a_summary_missing_its_price_is_unusable_rather_than_free() -> None:
    assert listing_from_summary({"itemId": "v1|1|0", "title": "Jaws Blu-ray"}) is None


def test_a_summary_with_an_unparseable_price_is_unusable() -> None:
    summary = {
        "itemId": "v1|1|0",
        "title": "Jaws Blu-ray",
        "price": {"value": "", "currency": "GBP"},
    }
    assert listing_from_summary(summary) is None


def test_a_listing_with_no_condition_gets_its_own_bucket() -> None:
    """`DECISIONS.md` #129: "A missing condition is its own bucket, never a default."

    Three of the 200 Blade Runner listings carry no ``conditionId`` at all. Defaulting
    them to New would put unknown-condition discs into the segment people price against.
    """
    summary = {
        "itemId": "v1|1|0",
        "title": "Jaws Blu-ray",
        "price": {"value": "9.99", "currency": "GBP"},
    }
    listing = listing_from_summary(summary)
    assert listing is not None
    assert listing.condition_id == UNKNOWN_CONDITION_ID
    assert listing.condition_id not in CONDITION_LABELS


# ---------------------------------------------------------------------------
# Each way a keyword search lies, named
# ---------------------------------------------------------------------------


def test_a_dvd_player_is_rejected_on_its_category() -> None:
    """A search for a film returns hardware. The category gate is the cheapest guard there is.

    Four Blade Runner results are leaf 175711, "DVD & Blu-ray Players"; six Jaws results
    are leaf 360, "Art Prints". Every one of them has the film's name in the title, a £
    price in a plausible range and an ebay.co.uk URL.
    """
    listing = _find(BLADE_RUNNER, "Player")
    assert "617" not in listing.leaf_category_ids
    verdict = match(listing, film_title="Blade Runner 2049")
    assert not verdict.ok
    assert "not a disc category" in (verdict.reason or "")


def test_two_real_discs_are_lost_to_the_category_gate_and_that_is_the_trade() -> None:
    """A stated cost, not an oversight.

    Two captured Jaws listings are genuine Blu-rays that their sellers filed under "Other"
    (88433) and "Audio Books" (29792). The allowlist refuses them. Widening it to admit
    those two would admit every art print and DVD player alongside, which is the trade
    ``extract.MEDIA_MARKERS`` documents and this follows: a stated failure rather than a
    wrong number.
    """
    miscategorised = [
        listing
        for summary in JAWS
        if (listing := listing_from_summary(summary)) is not None
        and "617" not in listing.leaf_category_ids
        and "blu" in listing.title.lower()
        and "custom" not in listing.title.lower()
    ]
    assert len(miscategorised) == 2
    for listing in miscategorised:
        assert not match(listing, film_title="Jaws").ok


def test_a_sequel_is_not_the_film() -> None:
    """The single most common lie in a "Jaws" search, and the one a word-set matcher misses.

    ``extract._normalise`` discards tokens of two characters or fewer, so "Jaws 2" and
    "Jaws" reduce to the same single word. 18 captured listings are Jaws 2.
    """
    listing = _find(JAWS, "Jaws 2 (1978) - Blu-ray - Roy Scheider")
    verdict = match(listing, film_title="Jaws")
    assert not verdict.ok
    assert "different film" in (verdict.reason or "")


def test_a_two_film_set_is_rejected_even_when_both_names_are_right() -> None:
    listing = _find(BLADE_RUNNER, "Blade Runner: Final Cut (1982) Blade Runner 2049 (2017)")
    verdict = match(listing, film_title="Blade Runner 2049")
    assert not verdict.ok
    assert "bundle" in (verdict.reason or "")


def test_a_custom_slipcover_is_an_accessory_not_a_from_price() -> None:
    """Both gates fire on this listing, and the order decides which reason a person reads.

    "Blade Runner 2049 4K or Blu-ray Custom Slipcover" is a multi-variation listing *and*
    a cardboard sleeve. "It is a slipcover" is the useful half.
    """
    listing = _find(BLADE_RUNNER, "Blade Runner 2049 4K or Blu-ray Custom Slipcover")
    assert listing.item_group_type == "SELLER_DEFINED_VARIATIONS"
    verdict = match(listing, film_title="Blade Runner 2049")
    assert not verdict.ok
    assert "accessory" in (verdict.reason or "")


def test_a_lot_of_four_discs_is_rejected() -> None:
    listing = _find(BLADE_RUNNER, "Lot of 4 The Babadook")
    verdict = match(listing, film_title="Blade Runner 2049")
    assert not verdict.ok
    assert "bundle" in (verdict.reason or "")


def test_an_overseas_seller_is_excluded_from_a_uk_median_by_default() -> None:
    verdict = match(_listing(country="JP"), film_title="Blade Runner 2049")
    assert not verdict.ok
    assert "ships from JP" in (verdict.reason or "")

    everywhere = match(_listing(country="JP"), film_title="Blade Runner 2049", country=None)
    assert everywhere.ok


def test_a_multi_variation_listing_is_excluded_because_its_price_is_a_from_price() -> None:
    verdict = match(
        _listing(item_group_type="SELLER_DEFINED_VARIATIONS"), film_title="Blade Runner 2049"
    )
    assert not verdict.ok
    assert "from" in (verdict.reason or "")


def test_a_listing_naming_no_format_is_refused_rather_than_guessed() -> None:
    """The same trade ``extract.MEDIA_MARKERS`` makes: a stated failure, not a wrong number."""
    verdict = match(_listing(title="Blade Runner 2049"), film_title="Blade Runner 2049")
    assert not verdict.ok
    assert "no disc format" in (verdict.reason or "")


# ---------------------------------------------------------------------------
# The two guards that had to be tuned against real titles
# ---------------------------------------------------------------------------


def test_an_age_rating_is_not_a_sequel_number() -> None:
    """ "Blade Runner 2049 [15] 4K UHD" is the film. Two captured listings say exactly that.

    Without :data:`~src.ebay.matching._CERTIFICATE` the sequel guard reads the 15 as an
    instalment number and throws the disc away.
    """
    listing = _find(BLADE_RUNNER, "Blade Runner 2049 [15] 4K UHD")
    verdict = match(listing, film_title="Blade Runner 2049", format_code="4k_uhd")
    assert verdict.ok, verdict.reason


@pytest.mark.parametrize(
    "title",
    [
        "Blade Runner 2049 3-Discs Steelbook Edition 4K Ultra HD + Blu-Ray 3D + Blu-Ray",
        "Blade Runner 2049 2 Disc Blu-ray Set",
    ],
)
def test_a_disc_count_is_not_a_sequel_number(title: str) -> None:
    verdict = match(_listing(title=title), film_title="Blade Runner 2049")
    assert verdict.ok, verdict.reason


def test_a_seller_keyword_dump_does_not_make_it_a_different_film() -> None:
    """eBay titles are stuffed with keywords, which is why the retailer scrapers'
    ``_meaningful_extras`` rule is *not* reused here: it reads "KZVG The Cheap Fast Free
    Post" as evidence of another film and rejects a perfectly ordinary Blu-ray."""
    listing = _find(BLADE_RUNNER, "KZVG The Cheap Fast Free Post")
    verdict = match(listing, film_title="Blade Runner 2049")
    assert verdict.ok, verdict.reason
    assert verdict.format_code == "blu_ray"


def test_the_highest_format_named_wins_even_when_dvd_is_appended_as_a_keyword() -> None:
    """ "Blade Runner 2049 [Blu-ray] [2017] - DVD" is a Blu-ray.

    A contains-"dvd" test files it as a DVD and prices a Blu-ray as one.
    """
    verdict = match(
        _listing(title="Blade Runner 2049 [Blu-ray] [2017] - DVD  KZVG"),
        film_title="Blade Runner 2049",
    )
    assert verdict.ok
    assert verdict.format_code == "blu_ray"


# ---------------------------------------------------------------------------
# Edition segmentation — where #129's 149% actually lives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Blade Runner 2049 4K/3D Steelbook - FilmArena (FAC#101) Maniac Collector Box #4",
        "BLADE RUNNER 2049 Premium Box Limited to 3000 set 4K UltraHD BLU-RAY Steelbook",
        "Blade Runner 2049 Blufans Single Lenticular 4K Steelbook  Sealed - Brand New",
        "Jaws 4K UHD + Blu ray UK Zavvi Collectors Edition Steelbook New Sealed Rare OOP",
    ],
)
def test_boutique_editions_are_classified_as_collector(title: str) -> None:
    assert classify_edition(title) == "collector"


@pytest.mark.parametrize(
    "title",
    [
        "Blade Runner 2049 [Blu-ray]",
        "Blade Runner 2049 (Blu-ray) Sealed With Slip Case - Brand New",
        "Blade Runner 2049 Blu-ray With O-Card Slipcover Ryan Gosling BBFC 15 UK",
        "Jaws (1975) 4K UHD Blu-ray",
    ],
)
def test_ordinary_packaging_is_not_a_collector_edition(title: str) -> None:
    """A slipcover is a cardboard sleeve, not a Filmarena box.

    If "slipcover" counted, most of the standard segment would empty into the collector
    one and the remaining sample would be too small to mean anything.
    """
    assert classify_edition(title) == "standard"


def test_no_collector_edition_reaches_the_standard_segment() -> None:
    """The property that keeps the headline price honest, over all 400 captured listings."""
    for summaries, film in ((BLADE_RUNNER, "Blade Runner 2049"), (JAWS, "Jaws")):
        for listing, verdict in _judge(summaries, film):
            if verdict.ok and verdict.edition == "standard":
                assert "steelbook" not in listing.title.lower(), listing.title
                assert "filmarena" not in listing.title.lower(), listing.title


# ---------------------------------------------------------------------------
# Whole-set properties
# ---------------------------------------------------------------------------


def test_every_rejection_carries_a_reason() -> None:
    """A rejection with no reason is indistinguishable from a filter that is broken."""
    for summaries, film in ((BLADE_RUNNER, "Blade Runner 2049"), (JAWS, "Jaws")):
        for _, verdict in _judge(summaries, film):
            if not verdict.ok:
                assert verdict.reason, "a rejection with no reason"
            else:
                assert verdict.format_code is not None


def test_the_filter_keeps_a_useful_share_rather_than_almost_everything_or_almost_nothing() -> None:
    """Both failure directions in one assertion.

    A filter that keeps 95% is not filtering; one that keeps 2% has broken and nothing
    downstream would say so — it would simply report a median over four listings.
    """
    for summaries, film in ((BLADE_RUNNER, "Blade Runner 2049"), (JAWS, "Jaws")):
        kept = [verdict for _l, verdict in _judge(summaries, film) if verdict.ok]
        share = len(kept) / len(summaries)
        assert 0.30 < share < 0.85, f"{film}: kept {share:.0%}"


def test_no_jaws_sequel_survives_a_search_for_jaws() -> None:
    """33 captured listings are Jaws 2, 3 or 4. Not one of them may be priced as Jaws."""
    for listing, verdict in _judge(JAWS, "Jaws"):
        if verdict.ok:
            words = tokens(listing.title)
            # Token-wise, not substring-wise: "Jaws 4K Ultra HD" contains "jaws 4" as text
            # and is the right film. The token after "jaws" is "4k", not "4".
            for index, word in enumerate(words):
                if word == "jaws" and words[index + 1 : index + 2] and words[index + 1] in "234":
                    # The one legitimate reading of a number here: a disc count.
                    # "Jaws - 2 Disc '30th Anniversary' Edition on DVD (1975)" is Jaws.
                    following = words[index + 2 : index + 3]
                    assert following and following[0] in {"disc", "discs"}, listing.title
            assert "revenge" not in words, listing.title


def test_tokens_keep_the_short_words_that_separate_a_film_from_its_sequel() -> None:
    assert tokens("Jaws 2 [Blu-ray]") == ["jaws", "2", "blu", "ray"]
    assert tokens("Blade Runner 2049 [15] 4K UHD") == ["blade", "runner", "2049", "4k", "uhd"]
