"""The collection's value, the parts that need no database — Batch T6, snag 7.

**What this proves:** which format a disc is valued as, what eBay is asked for an
unidentified film, that a value needs three used listings or three New ones behind it, that
a stored value is exactly the number the film page's own check would show, from the same
captured eBay payloads the estimator's tests use, and how the used-to-New factor is read
from the films that have both (Batch X6).

**What it does not:** the runs themselves, their budget and the totals. Those need Postgres
and are in ``test_valuation_runs.py``, which runs in CI.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.ebay.estimate import estimate_price, search_query
from src.ebay.pricing import ASKING_PRICES, used_value
from src.models.valuation import ValuationRun
from src.scripts.value_collection import report
from src.services.valuation import (
    FALLBACK_FACTOR,
    MAX_FACTOR,
    MIN_FACTOR_PAIRS,
    StartOutcome,
    UsedFactor,
    day_start,
    factors_from,
    search_title,
    valuation_from,
    valued_format,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _payload(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return payload


BLADE_RUNNER = _payload("ebay_browse_blade_runner_2049.json")
JAWS = _payload("ebay_browse_jaws.json")


class Answering:
    """An eBay that returns one captured payload, whatever it is asked."""

    marketplace_id = "EBAY_GB"

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.queries: list[str] = []

    async def search(
        self, query: str, *, limit: int = 200, category_ids: str | None = None
    ) -> dict[str, Any]:
        del limit, category_ids
        self.queries.append(query)
        return self.payload


# ---------------------------------------------------------------------------
# Which disc is valued as what
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("formats", "expected"),
    [
        (["4k_uhd", "blu_ray"], "4k_uhd"),
        (["blu_ray", "download"], "blu_ray"),
        (["blu_ray", "dvd"], "blu_ray"),
        (["dvd"], "dvd"),
        (["download"], None),
        ([], None),
    ],
)
def test_a_disc_is_valued_as_its_best_physical_format(
    formats: list[str], expected: str | None
) -> None:
    assert valued_format(formats) == expected


def test_an_identified_film_is_searched_by_its_tmdb_title() -> None:
    assert search_title("Blade Runner 2049", identified=True) == "Blade Runner 2049"


@pytest.mark.parametrize(
    ("spreadsheet", "searched"),
    [
        ("In The Heat Of The Night (Sidney Poitier)", "In The Heat Of The Night"),
        ("Mummy, The (Brendan Fraser)", "The Mummy"),
        ("Heat (1995)", "Heat"),
    ],
)
def test_an_unidentified_film_is_searched_without_the_spreadsheets_notes(
    spreadsheet: str, searched: str
) -> None:
    """No listing says "(Sidney Poitier)", and a search that insists on it finds nothing."""
    assert search_title(spreadsheet, identified=False) == searched


def test_the_search_names_the_format() -> None:
    assert search_query("Jaws", "4k_uhd") == "Jaws 4K"
    assert search_query("Jaws", "blu_ray") == "Jaws Blu-ray"
    assert search_query("Jaws", "dvd") == "Jaws DVD"


# ---------------------------------------------------------------------------
# A price, or not
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "film", "format_code"),
    [
        (BLADE_RUNNER, "Blade Runner 2049", "blu_ray"),
        (BLADE_RUNNER, "Blade Runner 2049", "4k_uhd"),
        (BLADE_RUNNER, "Blade Runner 2049", "dvd"),
        (JAWS, "Jaws", "blu_ray"),
        (JAWS, "Jaws", "4k_uhd"),
    ],
)
async def test_a_stored_value_is_the_film_pages_used_value(
    payload: dict[str, Any], film: str, format_code: str
) -> None:
    """The valuation and the film page's "What is it worth?" run the same estimator and the
    same rule (Batch X6), so the stored number and the live one agree, down to the penny and
    the listing count."""
    estimate = await estimate_price(Answering(payload), film_title=film, format_code=format_code)
    live = used_value(estimate, format_code, factor=FALLBACK_FACTOR)
    assert live is not None

    valuation = valuation_from(estimate, format_code, factor=FALLBACK_FACTOR)

    assert valuation.status == "priced"
    assert valuation.price == live.price
    assert valuation.sample_size == live.sample_size
    assert valuation.value_basis == live.basis
    assert (valuation.low, valuation.high, valuation.factor) == (live.low, live.high, live.factor)
    assert valuation.condition_label == ("Used" if live.basis == "used" else "New")
    assert estimate.basis == ASKING_PRICES


@pytest.mark.asyncio
async def test_the_captured_prices_are_the_ones_expected() -> None:
    """Pinned, so a change to the estimator shows up here as a changed valuation.

    Before Batch X6 these were £9.99 and £6.73, the largest group's median: New for Blade
    Runner, Very good for Jaws (#209). As used copies (#256), Blade Runner's 24 used listings
    say £5.45 and Jaws's 30 say £6.73; a DVD with one used listing and four New is New's £9.13
    at the factor.
    """
    blade_runner = await estimate_price(
        Answering(BLADE_RUNNER), film_title="Blade Runner 2049", format_code="blu_ray"
    )
    jaws = await estimate_price(Answering(JAWS), film_title="Jaws", format_code="blu_ray")
    dvd = await estimate_price(
        Answering(BLADE_RUNNER), film_title="Blade Runner 2049", format_code="dvd"
    )

    used = valuation_from(blade_runner, "blu_ray", factor=FALLBACK_FACTOR)
    assert (used.price, used.sample_size, used.value_basis) == (Decimal("5.45"), 24, "used")
    assert (used.low, used.high) == (Decimal("3.29"), Decimal("65.99"))
    assert (used.new_median, used.new_count) == (Decimal("9.99"), 29)
    assert valuation_from(jaws, "blu_ray", factor=FALLBACK_FACTOR).price == Decimal("6.73")

    scaled = valuation_from(dvd, "dvd", factor=Decimal("0.60"))
    assert (scaled.price, scaled.value_basis, scaled.factor) == (
        Decimal("5.48"),
        "new_scaled",
        Decimal("0.60"),
    )
    assert (scaled.sample_size, scaled.used_count, scaled.condition_label) == (4, 1, "New")


def _summary(index: int, condition_id: str, price: str = "10.00") -> dict[str, Any]:
    return {
        "itemId": f"v1|{index}|0",
        "title": "Blade Runner 2049 Blu-ray",
        "price": {"value": price, "currency": "GBP"},
        "conditionId": condition_id,
        "leafCategoryIds": ["617"],
        "itemLocation": {"country": "GB"},
    }


def _listings(*, used: int, new: int) -> dict[str, Any]:
    """``used`` Very good listings at £4 and ``new`` New ones at £10."""
    summaries = [_summary(i, "4000", "4.00") for i in range(used)]
    summaries += [_summary(100 + i, "1000", "10.00") for i in range(new)]
    return {"itemSummaries": summaries}


async def _valued(*, used: int, new: int) -> Any:
    estimate = await estimate_price(
        Answering(_listings(used=used, new=new)),
        film_title="Blade Runner 2049",
        format_code="blu_ray",
    )
    return valuation_from(estimate, "blu_ray", factor=Decimal("0.55"))


@pytest.mark.asyncio
async def test_three_used_listings_value_a_disc_whatever_new_says() -> None:
    valuation = await _valued(used=3, new=40)
    assert (valuation.status, valuation.price, valuation.value_basis) == (
        "priced",
        Decimal("4.00"),
        "used",
    )
    assert (valuation.sample_size, valuation.factor) == (3, None)


@pytest.mark.asyncio
async def test_two_used_listings_fall_back_to_new_at_the_factor() -> None:
    """Too few used copies to have a median: New's £10 at a factor of 0.55 is £5.50."""
    valuation = await _valued(used=2, new=3)
    assert (valuation.status, valuation.price, valuation.value_basis) == (
        "priced",
        Decimal("5.50"),
        "new_scaled",
    )
    assert (valuation.sample_size, valuation.factor) == (3, Decimal("0.55"))
    assert (valuation.used_count, valuation.new_count) == (2, 3)


@pytest.mark.asyncio
async def test_two_of_each_are_not_enough_to_price_a_disc() -> None:
    """#129: a median of two is one seller's asking price. Not priced, never a guess."""
    valuation = await _valued(used=2, new=2)
    assert (valuation.status, valuation.price, valuation.value_basis) == ("not_priced", None, None)
    assert (valuation.sample_size, valuation.used_count, valuation.new_count) == (2, 2, 2)


@pytest.mark.asyncio
async def test_open_box_and_unstated_conditions_value_nothing() -> None:
    """Five "Open box" and five with no condition: neither says what a used copy asks."""
    summaries = [_summary(i, "1500") for i in range(5)]
    summaries += [
        {k: v for k, v in _summary(50 + i, "x").items() if k != "conditionId"} for i in range(5)
    ]
    estimate = await estimate_price(
        Answering({"itemSummaries": summaries}),
        film_title="Blade Runner 2049",
        format_code="blu_ray",
    )
    assert valuation_from(estimate, "blu_ray", factor=FALLBACK_FACTOR).status == "not_priced"


@pytest.mark.asyncio
async def test_nothing_matching_is_not_priced() -> None:
    """Jaws has one DVD listing, and it is a collector's edition: nothing to go on."""
    estimate = await estimate_price(Answering(JAWS), film_title="Jaws", format_code="dvd")
    valuation = valuation_from(estimate, "dvd", factor=FALLBACK_FACTOR)
    assert valuation.status == "not_priced"
    assert valuation.price is None
    assert valuation.sample_size == 0
    assert (valuation.used_count, valuation.new_count) == (0, 0)


# ---------------------------------------------------------------------------
# The used-to-New factor (Batch X6)
# ---------------------------------------------------------------------------


def _ratios(*values: str) -> list[Decimal]:
    return [Decimal(value) for value in values]


def test_a_format_with_too_few_films_takes_the_fallback() -> None:
    factors = factors_from({"blu_ray": _ratios(*["0.50"] * (MIN_FACTOR_PAIRS - 1))})
    assert factors["blu_ray"] == UsedFactor(FALLBACK_FACTOR, 0)
    assert not factors["blu_ray"].measured
    assert factors["4k_uhd"] == factors["dvd"] == UsedFactor(FALLBACK_FACTOR, 0)


def test_enough_films_give_their_median_ratio() -> None:
    ratios = _ratios(*["0.50"] * 10, *["0.70"] * 11)
    factors = factors_from({"4k_uhd": ratios})
    assert factors["4k_uhd"] == UsedFactor(Decimal("0.70"), 21)
    assert factors["4k_uhd"].measured


def test_a_used_copy_is_never_valued_above_a_new_one() -> None:
    factors = factors_from({"dvd": _ratios(*["1.30"] * MIN_FACTOR_PAIRS)})
    assert factors["dvd"].factor == MAX_FACTOR


# ---------------------------------------------------------------------------
# The budget's day, and the command's exit code
# ---------------------------------------------------------------------------


def test_the_budget_day_starts_at_midnight_utc() -> None:
    """Not a rolling 24 hours: a job that runs at 03:00 every night would find yesterday's
    run still inside that window, and do nothing."""
    assert day_start(datetime(2026, 9, 24, 3, 0, 7)) == datetime(2026, 9, 24)


def _run(**fields: Any) -> ValuationRun:
    defaults: dict[str, Any] = {
        "trigger": "job",
        "status": "finished",
        "budget": 750,
        "calls": 0,
        "priced": 0,
        "not_priced": 0,
        "failed": 0,
        "remaining": 0,
        "last_error": None,
    }
    return ValuationRun(**{**defaults, **fields})


def test_a_run_that_stopped_having_priced_nothing_fails_the_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    run = _run(status="stopped", failed=5, last_error="eBay search failed (HTTP 500)")
    assert report(StartOutcome("started", run, 10, 750), run) == 1
    assert "HTTP 500" in capsys.readouterr().out


def test_a_run_that_priced_something_succeeds_even_if_it_stopped() -> None:
    run = _run(status="stopped", priced=40, failed=5)
    assert report(StartOutcome("started", run, 10, 750), run) == 0


def test_nothing_to_do_is_not_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    assert report(StartOutcome("nothing_due", None, 0, 750), None) == 0
    assert "nothing was done" in capsys.readouterr().out
