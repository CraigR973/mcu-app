"""Cost arithmetic and model configuration — Batch 30, §9.1.

No database and no network: these are the parts of the assistant that can be checked on
this machine, which matters because everything DB-backed skips locally (gotcha 15) and
every *real* call spends the owner's money.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.config import Settings
from src.services.ai.pricing import (
    DEFAULT_MODEL,
    MODEL_PRICING,
    SUPPORTED_MODELS,
    estimate_cost_usd,
)


def test_the_default_model_is_priced() -> None:
    """A model with no price logs every call as costing nothing.

    That is worse than a wrong id, which fails loudly: an unpriced model *works*, and
    silently makes §9.7's cost cap unenforceable.
    """
    assert DEFAULT_MODEL in MODEL_PRICING


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_no_model_id_carries_a_date_suffix(model: str) -> None:
    """The ids are complete as written.

    Appending a date to one is a 404 at request time, and `docs/phase-batches.md` is
    explicit that the April spec's model names predate the current lineup by two
    generations — so this guards the exact failure a half-remembered id would cause.
    """
    assert not model[-1].isdigit() or "-2" not in model[-9:], model


def test_output_tokens_cost_more_than_input_tokens() -> None:
    """True of every Claude model, and the thing a transposed multiplication breaks."""
    for model, pricing in MODEL_PRICING.items():
        assert pricing.output_per_mtok > pricing.input_per_mtok, model
        assert pricing.cache_read_per_mtok < pricing.input_per_mtok, model


def test_a_known_call_costs_what_the_published_rate_says() -> None:
    """Sonnet 5 at $2/$10 per million: 1,000 in and 500 out."""
    cost = estimate_cost_usd("claude-sonnet-5", input_tokens=1000, output_tokens=500)

    # (1000 × 2 + 500 × 10) / 1_000_000 = 0.007
    assert cost == Decimal("0.007000")


def test_cached_reads_are_charged_at_the_cache_rate() -> None:
    """A conversation reusing a cached system prompt must not be billed as fresh input."""
    fresh = estimate_cost_usd("claude-sonnet-5", input_tokens=10000, output_tokens=0)
    cached = estimate_cost_usd(
        "claude-sonnet-5", input_tokens=0, output_tokens=0, cache_read_tokens=10000
    )

    assert cached < fresh
    assert cached == Decimal("0.002000")


def test_a_short_question_does_not_round_to_zero() -> None:
    """**Why the column is six decimal places.**

    Rounding each call to the nearest cent would record every ordinary question as free,
    and a cost cap counting zeros never triggers.
    """
    cost = estimate_cost_usd("claude-sonnet-5", input_tokens=50, output_tokens=20)

    assert cost > 0
    assert cost < Decimal("0.01")


def test_an_unknown_model_costs_zero_rather_than_raising() -> None:
    """Bookkeeping must never be the reason somebody's question fails.

    The token counts are still recorded, so the row can be repriced by hand.
    """
    assert estimate_cost_usd("some-future-model", input_tokens=100, output_tokens=100) == 0


class TestModelConfiguration:
    def test_the_configured_model_defaults_to_the_ledgers_choice(self) -> None:
        # `docs/phase-batches.md`: "Sonnet 5 is the sensible default for an assistant
        # answering questions about a film collection."
        assert Settings().ai_model == "claude-sonnet-5"

    def test_an_unknown_model_id_is_refused_at_load(self) -> None:
        """A typo fails at boot, not in front of the first person to ask a question."""
        with pytest.raises(ValueError, match="ai_model must be one of"):
            Settings(ai_model="claude-sonnet-5-20260101")

    def test_every_supported_model_is_accepted(self) -> None:
        for model in SUPPORTED_MODELS:
            assert Settings(ai_model=model).ai_model == model

    def test_the_default_cap_is_the_owners_fifty(self) -> None:
        # Owner, 2026-09-09. A starting value, not a commitment.
        assert Settings().ai_daily_message_cap == 50
