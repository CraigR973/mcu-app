"""The collection's value, the parts that need no database — Batch T6, snag 7.

**What this proves:** which format a disc is valued as, what eBay is asked for an
unidentified film, that a price needs at least three listings behind it, and that a stored
value is exactly the number the film page's own check would show, from the same captured
eBay payloads the estimator's tests use.

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
from src.ebay.pricing import ASKING_PRICES
from src.models.valuation import ValuationRun
from src.scripts.value_collection import report
from src.services.valuation import (
    MIN_SAMPLE,
    StartOutcome,
    day_start,
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
        (JAWS, "Jaws", "blu_ray"),
    ],
)
async def test_a_stored_value_is_the_film_pages_headline(
    payload: dict[str, Any], film: str, format_code: str
) -> None:
    """The valuation and the film page's "What is it worth?" run the same estimator, so the
    stored number and the live one agree, down to the penny and the listing count."""
    estimate = await estimate_price(Answering(payload), film_title=film, format_code=format_code)
    headline = estimate.headline(format_code=format_code)
    assert headline is not None and headline.sample_size >= MIN_SAMPLE

    valuation = valuation_from(estimate, format_code)

    assert valuation.status == "priced"
    assert valuation.price == headline.median
    assert valuation.sample_size == headline.sample_size
    assert valuation.condition_label == headline.condition_label
    assert estimate.basis == ASKING_PRICES


@pytest.mark.asyncio
async def test_the_captured_prices_are_the_ones_expected() -> None:
    """Pinned, so a change to the estimator shows up here as a changed valuation."""
    blade_runner = await estimate_price(
        Answering(BLADE_RUNNER), film_title="Blade Runner 2049", format_code="blu_ray"
    )
    jaws = await estimate_price(Answering(JAWS), film_title="Jaws", format_code="blu_ray")
    assert valuation_from(blade_runner, "blu_ray").price == Decimal("9.99")
    assert valuation_from(jaws, "blu_ray").price == Decimal("6.73")


def _matching_only(payload: dict[str, Any], keep: int) -> dict[str, Any]:
    """The payload cut down to ``keep`` listings the Blu-ray headline would count."""
    kept = [
        summary
        for summary in payload["itemSummaries"]
        if summary.get("conditionId") == "1000"
        and "4k" not in summary.get("title", "").lower()
        and "steelbook" not in summary.get("title", "").lower()
    ]
    return {"itemSummaries": kept[:keep]}


@pytest.mark.asyncio
async def test_two_listings_are_not_enough_to_price_a_disc() -> None:
    """#129: a median of two is one seller's asking price. Not priced, never a guess."""
    estimate = await estimate_price(
        Answering(_matching_only(BLADE_RUNNER, keep=2)),
        film_title="Blade Runner 2049",
        format_code="blu_ray",
    )
    headline = estimate.headline(format_code="blu_ray")
    assert headline is not None and headline.sample_size == 2

    valuation = valuation_from(estimate, "blu_ray")

    assert valuation.status == "not_priced"
    assert valuation.price is None
    assert valuation.sample_size == 2


@pytest.mark.asyncio
async def test_three_listings_are() -> None:
    estimate = await estimate_price(
        Answering(_matching_only(BLADE_RUNNER, keep=3)),
        film_title="Blade Runner 2049",
        format_code="blu_ray",
    )
    assert valuation_from(estimate, "blu_ray").status == "priced"


@pytest.mark.asyncio
async def test_nothing_matching_is_not_priced() -> None:
    """Jaws has one DVD listing, and it is a collector's edition: nothing to go on."""
    estimate = await estimate_price(Answering(JAWS), film_title="Jaws", format_code="dvd")
    valuation = valuation_from(estimate, "dvd")
    assert valuation.status == "not_priced"
    assert valuation.price is None
    assert valuation.sample_size == 0


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
