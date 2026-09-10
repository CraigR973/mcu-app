"""What a Claude call costs, and which models this app will talk to — §9.1.

**The April spec predates the current lineup by two generations**, so the roadmap's model
names are not usable and `docs/phase-batches.md` says so explicitly: *"Do not guess a model
id."* The ids here are the Claude 5 family, written out exactly — they are complete as-is
and a date suffix appended to one is a 404 at request time, not a warning.

**Prices are per million tokens and are a snapshot.** They are here so a cost can be
recorded next to the tokens that produced it rather than reconstructed later from a rate
nobody wrote down. A price that moves makes historic rows describe what was actually
charged at the time, which is the useful thing for them to say — so this table is never
back-applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

#: The assistant's default. `docs/phase-batches.md`: *"Sonnet 5 is the sensible default for
#: an assistant answering questions about a film collection."* Overridable in config, which
#: is where the id belongs — not scattered through the code.
DEFAULT_MODEL = "claude-sonnet-5"


@dataclass(frozen=True)
class ModelPricing:
    """Dollars per million tokens, as published."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    #: Cache reads are about a tenth of the input rate; writes about 1.25×. Both are
    #: carried because §9.1 asks for cost per message and a conversation that reuses a
    #: cached system prompt would otherwise be billed at the wrong rate in our own log.
    cache_read_per_mtok: Decimal
    cache_write_per_mtok: Decimal


#: Snapshot taken 2026-09-10. Only the models this app can be configured to use.
MODEL_PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-5": ModelPricing(
        input_per_mtok=Decimal("2.00"),
        output_per_mtok=Decimal("10.00"),
        cache_read_per_mtok=Decimal("0.20"),
        cache_write_per_mtok=Decimal("2.50"),
    ),
    "claude-opus-5": ModelPricing(
        input_per_mtok=Decimal("5.00"),
        output_per_mtok=Decimal("25.00"),
        cache_read_per_mtok=Decimal("0.50"),
        cache_write_per_mtok=Decimal("6.25"),
    ),
    "claude-haiku-4-5": ModelPricing(
        input_per_mtok=Decimal("1.00"),
        output_per_mtok=Decimal("5.00"),
        cache_read_per_mtok=Decimal("0.10"),
        cache_write_per_mtok=Decimal("1.25"),
    ),
    "claude-fable-5-1": ModelPricing(
        input_per_mtok=Decimal("10.00"),
        output_per_mtok=Decimal("50.00"),
        cache_read_per_mtok=Decimal("1.00"),
        cache_write_per_mtok=Decimal("12.50"),
    ),
}

#: Every model this app will accept in config. A typo becomes a startup-visible error
#: instead of a 404 on the first person to open the assistant.
SUPPORTED_MODELS = tuple(MODEL_PRICING)

_MILLION = Decimal("1000000")


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    """Dollars for one call, to six decimal places.

    Six, not two: a single short question costs a fraction of a penny, and rounding each
    call to the nearest cent would record every one of them as zero and make §9.7's cost
    cap unenforceable. Rounding happens when a total is displayed, not when it is stored.

    An unknown model returns ``0`` rather than raising. A cost is bookkeeping and must
    never be the reason a person's question fails — the token counts are still recorded,
    so the row can be repriced by hand if it ever matters.
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return Decimal("0")

    total = (
        Decimal(input_tokens) * pricing.input_per_mtok
        + Decimal(output_tokens) * pricing.output_per_mtok
        + Decimal(cache_read_tokens) * pricing.cache_read_per_mtok
        + Decimal(cache_write_tokens) * pricing.cache_write_per_mtok
    ) / _MILLION
    return total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
