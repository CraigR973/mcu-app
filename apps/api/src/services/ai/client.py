"""The Claude client — §9.1.

**The official SDK, not raw HTTP.** The request shapes for thinking, effort and tool use
have all moved in the last year; a hand-rolled client against `/v1/messages` is a second
place for that drift to land, and this project has enough of those.

**Three things the April spec could not have known**, and each is load-bearing:

- **The model id.** `docs/phase-batches.md` says *"do not guess a model id"* — the spec
  predates the current lineup by two generations. It lives in config, validated against
  `pricing.SUPPORTED_MODELS` at load, so a typo fails at boot rather than at first use.
- **Thinking is configured, not budgeted.** `budget_tokens` is removed on the Claude 5
  family and returns a `400`. Adaptive thinking plus an `effort` level replaces it.
- **There is no assistant prefill.** A last-turn assistant prefill returns a `400`, so
  response shaping is done in the system prompt.

**Every call is logged, including the ones that fail.** A usage log holding only successes
cannot explain an outage, which is precisely the failure this project keeps meeting: the
TMDB token was missing for an unknown length of time and nothing recorded why calls were
failing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol

import anthropic
import structlog
from anthropic.types import MessageParam
from anthropic.types.output_config_param import OutputConfigParam
from anthropic.types.thinking_config_adaptive_param import ThinkingConfigAdaptiveParam

from src.config import settings
from src.services.ai.pricing import estimate_cost_usd

logger = structlog.get_logger(__name__)

#: Non-streaming ceiling. Large enough that an answer about a film collection is never cut
#: off mid-sentence, small enough to stay well inside the SDK's HTTP timeout — Batch 31's
#: streaming chat is where a bigger number belongs.
MAX_TOKENS = 4096

#: Medium for a question about a catalogue: the work is retrieval and phrasing rather than
#: reasoning, and the effort dial is the first thing that trades cost for depth.
#:
#: Typed as the SDK's own literal so an invented level fails the typechecker rather than
#: the API — the skill's rule about not redefining SDK data structures, applied to a value.
Effort = Literal["low", "medium", "high", "xhigh", "max"]
DEFAULT_EFFORT: Effort = "medium"

#: What the assistant is, and what it must not pretend to be.
SYSTEM_PROMPT = """You are the assistant for Mark's Cinematic Universe, a private film \
collection app used by exactly two people, Craig and Mark. It catalogues around 1,857 \
physical discs — 4K UHD, Blu-ray and DVD — along with where each one is shelved, a wanted \
list, watch history and upcoming releases.

Answer questions about the collection plainly and briefly. These are two people talking \
about their own films, not customers being served: skip the preamble, skip the summary of \
what you are about to do, and give the answer.

You do not have direct access to the catalogue in this conversation unless a tool result \
appears above. **Never invent a film, a shelf location, a price or a watch date.** If you \
have not been given the data, say what you would need rather than guessing — a confident \
wrong answer about which shelf something is on costs somebody a trip to the garage.

Prices are in pounds. Dates are day-first. The collection is British and region-B by \
default."""


class Usage(Protocol):
    """The subset of the SDK's usage object this module reads."""

    input_tokens: int
    output_tokens: int


@dataclass
class AiReply:
    """One answer, with what it cost to produce."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    stop_reason: str | None = None
    latency_ms: int = 0
    #: Set when the call failed. `text` is then a sentence a person can read.
    error: str | None = None


def _text_of(message: Any) -> str:
    """Join the text blocks of a response, ignoring thinking and tool blocks.

    `content` is a list of typed blocks and only some of them are text; reading
    `content[0].text` works right up until the first response that starts with a thinking
    block, which is a runtime `AttributeError` in front of a person.
    """
    return "".join(
        block.text
        for block in getattr(message, "content", [])
        if getattr(block, "type", "") == "text"
    ).strip()


def _int_field(usage: Any, name: str) -> int:
    """Read an optional usage counter. Cache fields are absent when nothing was cached."""
    value = getattr(usage, name, None)
    return int(value) if isinstance(value, int) else 0


class ClaudeClient:
    """A thin wrapper that always returns an :class:`AiReply`, never raises.

    Not raising is deliberate. Every caller is answering a person who asked a question, and
    the useful outcomes are "here is the answer" and "here is why there isn't one" — an
    exception crossing this boundary becomes a 500 and tells them neither.
    """

    def __init__(self, client: anthropic.AsyncAnthropic | None = None) -> None:
        self._client = client
        self._model = settings.ai_model

    @property
    def configured(self) -> bool:
        """Whether this deployment can talk to Claude at all.

        Asked by the readiness endpoint. A key that lives only in a Railway variable has
        nothing testing it — the lesson `STATUS.md` records against the TMDB outage.
        """
        return bool(self._client or settings.anthropic_api_key)

    def _resolve(self) -> anthropic.AsyncAnthropic | None:
        if self._client is not None:
            return self._client
        if not settings.anthropic_api_key:
            return None
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def ask(
        self,
        prompt: str,
        *,
        history: list[MessageParam] | None = None,
        system: str | None = None,
        max_tokens: int = MAX_TOKENS,
        effort: Effort = DEFAULT_EFFORT,
    ) -> AiReply:
        """Ask one question and return the answer with its token and cost accounting."""
        client = self._resolve()
        if client is None:
            return AiReply(
                text=(
                    "The assistant is not configured on the server yet, so there is "
                    "nothing to ask. Nothing else in the app is affected."
                ),
                model=self._model,
                error="ANTHROPIC_API_KEY is not set",
            )

        messages: list[MessageParam] = [*(history or []), {"role": "user", "content": prompt}]
        started = time.perf_counter()
        try:
            message = await client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system or SYSTEM_PROMPT,
                # Adaptive is the only on-mode on the Claude 5 family; `budget_tokens`
                # is removed and returns a 400.
                thinking=ThinkingConfigAdaptiveParam(type="adaptive"),
                output_config=OutputConfigParam(effort=effort),
                messages=messages,
            )
        except anthropic.APIStatusError as exc:
            return self._failure(
                f"api error {exc.status_code}", exc, started, friendly=_friendly(exc.status_code)
            )
        except anthropic.APIConnectionError as exc:
            return self._failure(
                "connection error",
                exc,
                started,
                friendly="The assistant could not be reached. Try again in a moment.",
            )

        usage = getattr(message, "usage", None)
        input_tokens = _int_field(usage, "input_tokens")
        output_tokens = _int_field(usage, "output_tokens")
        cache_read = _int_field(usage, "cache_read_input_tokens")
        cache_write = _int_field(usage, "cache_creation_input_tokens")
        model_used = getattr(message, "model", self._model)

        reply = AiReply(
            text=_text_of(message),
            model=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=estimate_cost_usd(
                model_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
            ),
            stop_reason=getattr(message, "stop_reason", None),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

        # A safety decline arrives as a **200** with `stop_reason: "refusal"`, so reading
        # `content` without checking would hand the person an empty answer and no reason.
        if reply.stop_reason == "refusal":
            reply.text = "The assistant declined to answer that one. Try rephrasing the question."
        elif not reply.text:
            reply.text = "The assistant returned an empty answer. Try asking again."

        logger.info(
            "ai_reply",
            model=reply.model,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            cost_usd=str(reply.cost_usd),
            latency_ms=reply.latency_ms,
            stop_reason=reply.stop_reason,
        )
        return reply

    def _failure(self, kind: str, exc: Exception, started: float, *, friendly: str) -> AiReply:
        latency = int((time.perf_counter() - started) * 1000)
        logger.warning("ai_call_failed", kind=kind, error=str(exc)[:300], latency_ms=latency)
        return AiReply(
            text=friendly,
            model=self._model,
            latency_ms=latency,
            error=f"{kind}: {exc}"[:1000],
        )


def _friendly(status_code: int) -> str:
    """What to show a person for an API status. Never the raw error."""
    if status_code == 401:
        return "The assistant's API key was rejected. It needs to be checked on the server."
    if status_code == 429:
        return "The assistant is rate limited right now. Try again in a minute."
    if status_code >= 500:
        return "The assistant is having trouble at the moment. Try again shortly."
    return "The assistant could not answer that. Try rephrasing the question."
