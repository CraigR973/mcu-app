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
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol

import anthropic
import structlog
from anthropic.types import MessageParam
from anthropic.types.output_config_param import OutputConfigParam
from anthropic.types.thinking_config_adaptive_param import ThinkingConfigAdaptiveParam
from anthropic.types.tool_choice_param import ToolChoiceParam
from anthropic.types.tool_param import ToolParam

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

#: What the assistant is, and what it must not pretend to be. Who is asking and today's date
#: are added per call by :func:`system_prompt` (AI45-02): the model logged "a watch last night"
#: without knowing which night, and wrote to nobody in particular.
BASE_PROMPT = """You are the assistant for Mark's Cinematic Universe, a private film \
collection app used by exactly two people, Craig and Mark. It catalogues their films — 4K \
UHD, Blu-ray and DVD discs, and downloads — along with where each one is kept, a shared \
wanted list, each person's watch history and upcoming releases.

Answer questions about the collection plainly and briefly. These are two people talking \
about their own films, not customers being served: skip the preamble, skip the summary of \
what you are about to do, and give the answer.

Use the tools for anything about the collection. **Never invent a film, a shelf location, a \
price or a watch date.** If no tool result gives you the data, say what you would need rather \
than guessing — a confident wrong answer about which shelf something is on costs somebody a \
trip to the garage.

Every list a tool returns starts with its total. When a result says films were left out, say \
how many, or ask for the next page; never present part of a list as the whole of it.

Two tools write: add_to_wanted and log_watch. **The app shows the person a Yes/No card before \
either one runs**, so when they ask you to add a film or log a watch, call the tool straight \
away. Do not ask them to confirm in words first; the card is the confirmation. If a tool says \
a title matches more than one film, ask which one they mean.

Prices are in pounds. Dates are day-first. The collection is British and region B by \
default."""


def system_prompt(person: str | None = None, today: date | None = None) -> str:
    """The prompt for one call: :data:`BASE_PROMPT`, then who is asking and the date.

    ``today`` is the person's own date (Europe/London), not UTC's: "last night" at 00:30 in
    June is still yesterday in Britain.
    """
    lines = [BASE_PROMPT]
    if person:
        lines.append(f"You are talking to {person}.")
    if today is not None:
        lines.append(f"Today is {today:%A} {today.day} {today:%B %Y}.")
    return "\n\n".join(lines)


#: Kept for callers that ask without a person (none in the app today).
SYSTEM_PROMPT = BASE_PROMPT

#: What a person reads when the fault is one only Craig can fix: a rejected key, a spend limit,
#: a retired model, a request the API refuses (AI45-04). The daily check names the failure to
#: him the next morning (`health_checks.check_assistant`), which is what makes "has been told"
#: true; rephrasing would fail the same way, so the old advice to rephrase is gone.
CRAIG_HAS_BEEN_TOLD = "The assistant isn't working right now; Craig has been told."


class Usage(Protocol):
    """The subset of the SDK's usage object this module reads."""

    input_tokens: int
    output_tokens: int


#: Streaming lifts the HTTP-timeout constraint, so the ceiling can be generous — a turn
#: that calls two tools and then writes a real answer needs the room.
STREAM_MAX_TOKENS = 16000


@dataclass
class TurnEvent:
    """One thing that happened while a turn streamed.

    `text` arrives many times, then exactly one `done` (carrying the assembled message and
    its accounting) **or** one `error`. The caller forwards the first kind to the browser
    and acts on the second.
    """

    kind: Literal["text", "done", "error"]
    text: str = ""
    message: Any = None
    reply: AiReply | None = None
    error: str | None = None
    #: On `error`: the API's HTTP status (``None`` when it was never reached) and its error
    #: type ("invalid_request_error", "rate_limit_error"…), so a failure is logged as what it was.
    status: int | None = None
    error_type: str | None = None


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
                _describe(exc), exc, started, friendly=_friendly(exc.status_code, _retry_after(exc))
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
            # Priced by the configured id, not the one the response names: an alias can answer
            # under a dated id (Haiku 4.5 does) that the table does not hold, which priced every
            # call at $0 and left the cost cap unable to bind (AI45-08).
            cost_usd=estimate_cost_usd(
                self._model,
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

    async def stream_turn(
        self,
        messages: list[MessageParam],
        *,
        tools: list[ToolParam] | None = None,
        tool_choice: ToolChoiceParam | None = None,
        system: str | None = None,
        max_tokens: int = STREAM_MAX_TOKENS,
        effort: Effort = DEFAULT_EFFORT,
    ) -> AsyncIterator[TurnEvent]:
        """Stream one turn, yielding text as it arrives and the final message at the end.

        **Streaming rather than `create`, because §9.3's acceptance is that the response
        "renders progressively"** — and because a turn that calls tools and then writes a
        long answer is exactly the shape that hits an HTTP timeout without it.

        The final message is *yielded* rather than returned: an async generator cannot
        return a value, and the caller needs both halves — the deltas to forward to the
        browser, and the assembled message to persist and inspect for tool calls.
        """
        client = self._resolve()
        if client is None:
            yield TurnEvent(
                kind="error",
                text=(
                    "The assistant is not configured on the server yet. Nothing else in "
                    "the app is affected."
                ),
                error="ANTHROPIC_API_KEY is not set",
            )
            return

        started = time.perf_counter()
        try:
            async with client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                system=system or SYSTEM_PROMPT,
                thinking=ThinkingConfigAdaptiveParam(type="adaptive"),
                output_config=OutputConfigParam(effort=effort),
                tools=tools or [],
                # `{"type": "none"}` on a question's last round makes the model answer with
                # what it has rather than ask for another tool it will never get (AI45-05).
                tool_choice=tool_choice if tool_choice is not None else anthropic.omit,
                messages=messages,
            ) as stream:
                async for chunk in stream.text_stream:
                    yield TurnEvent(kind="text", text=chunk)
                final = await stream.get_final_message()
        except anthropic.APIStatusError as exc:
            error_type = _error_type(exc)
            logger.warning(
                "ai_stream_failed",
                status=exc.status_code,
                error_type=error_type,
                error=str(exc)[:300],
            )
            yield TurnEvent(
                kind="error",
                text=_friendly(exc.status_code, _retry_after(exc)),
                error=_describe(exc),
                status=exc.status_code,
                error_type=error_type,
            )
            return
        except anthropic.APIConnectionError as exc:
            logger.warning("ai_stream_unreachable", error=str(exc)[:300])
            yield TurnEvent(
                kind="error",
                text="The assistant could not be reached. Try again in a moment.",
                error=f"connection error: {exc}"[:1000],
                error_type=type(exc).__name__,
            )
            return

        usage = getattr(final, "usage", None)
        input_tokens = _int_field(usage, "input_tokens")
        output_tokens = _int_field(usage, "output_tokens")
        cache_read = _int_field(usage, "cache_read_input_tokens")
        cache_write = _int_field(usage, "cache_creation_input_tokens")
        model_used = getattr(final, "model", self._model)

        yield TurnEvent(
            kind="done",
            message=final,
            reply=AiReply(
                text=_text_of(final),
                model=model_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
                # By the configured id, as `ask` prices (AI45-08).
                cost_usd=estimate_cost_usd(
                    self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                ),
                stop_reason=getattr(final, "stop_reason", None),
                latency_ms=int((time.perf_counter() - started) * 1000),
            ),
        )

    def _failure(self, kind: str, exc: Exception, started: float, *, friendly: str) -> AiReply:
        latency = int((time.perf_counter() - started) * 1000)
        logger.warning("ai_call_failed", kind=kind, error=str(exc)[:300], latency_ms=latency)
        return AiReply(
            text=friendly,
            model=self._model,
            latency_ms=latency,
            error=f"{kind}: {exc}"[:1000],
        )


def _error_type(exc: anthropic.APIStatusError) -> str:
    """The API's own error type ("invalid_request_error"), or the SDK's class name."""
    body = exc.body
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("type"), str):
            return str(error["type"])
    return type(exc).__name__


def _retry_after(exc: anthropic.APIStatusError) -> str | None:
    return exc.response.headers.get("retry-after") if exc.response is not None else None


def _describe(exc: anthropic.APIStatusError) -> str:
    """What the usage log records: status, type and the API's message, bounded."""
    return f"{exc.status_code} {_error_type(exc)}: {exc}"[:1000]


def _friendly(status_code: int, retry_after: str | None = None) -> str:
    """What to show a person for an API status. Never the raw error (AI45-04).

    A 429 with ``retry-after`` is a passing rate limit; one without is a spend cap, which
    lasts until access resumes, so waiting a minute would not help. 400, 401, 402, 403, 404
    and 413 are faults in the key, the account, the model or the request: rephrasing fails the
    same way every time.
    """
    if status_code == 429 and retry_after:
        return "The assistant is busy right now. Try again in a minute."
    if status_code >= 500:
        return "The assistant is having trouble at the moment. Try again shortly."
    return CRAIG_HAS_BEEN_TOLD
