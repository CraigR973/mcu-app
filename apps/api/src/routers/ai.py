"""The AI assistant's endpoints — Batch 30, §9.1 and §9.7.

Everything is caller-scoped: a person's questions, their usage and their caps are theirs.
There is no admin view of the other person's conversations, which with two profiles would
be a surveillance feature rather than an administrative one.

**Batch 31 owns conversations, tools and the chat UI.** This batch deliberately ships a
single-turn endpoint: `DECISIONS.md` #12 warned that the assistant is the second consumer
that would reopen the response-envelope question, and the way it does not is by calling
the same endpoints the web app calls through the same schemas — which is a decision that
belongs with the tools, in 31, not here.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import select

from src.auth import CurrentUser
from src.clock import utcnow
from src.config import settings
from src.models.ai import AiUsageLogEntry
from src.routers.movies import Database
from src.schemas.ai import (
    AiSettingsResponse,
    AiSettingsUpdateRequest,
    AiStatusResponse,
    AskRequest,
    AskResponse,
    UsageResponse,
)
from src.services.ai.caps import UsageToday, get_or_create_settings, usage_today
from src.services.ai.client import ClaudeClient

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ai"])

#: Overridden by the tests, which must never reach the real API — every call spends the
#: owner's money. Production leaves it `None` and builds a client per request.
_client_override: ClaudeClient | None = None


def set_ai_client(client: ClaudeClient | None) -> None:
    """Substitute the Claude client. Used by tests; never called in production."""
    global _client_override
    _client_override = client


def ai_client() -> ClaudeClient:
    return _client_override or ClaudeClient()


def _usage_response(usage: UsageToday) -> UsageResponse:
    return UsageResponse(
        messages=usage.messages,
        messageCap=usage.message_cap,
        messagesRemaining=usage.messages_remaining,
        costUsd=f"{usage.cost_usd:.6f}",
        costCapUsd=f"{usage.cost_cap_usd:.2f}",
        blocked=usage.blocked,
        limitMessage=usage.refusal_message(),
        resetsAt=usage.resets_at_utc,
    )


@router.get("/ai/status", response_model=AiStatusResponse)
async def ai_status(_user: CurrentUser) -> AiStatusResponse:
    """Can this deployment answer a question at all?"""
    return AiStatusResponse(configured=ai_client().configured, model=settings.ai_model)


@router.get("/ai/usage", response_model=UsageResponse)
async def read_usage(user: CurrentUser, db: Database) -> UsageResponse:
    """§9.7's counters for today."""
    usage = await usage_today(db, user.id)
    await db.commit()
    return _usage_response(usage)


@router.get("/ai/settings", response_model=AiSettingsResponse)
async def read_settings(user: CurrentUser, db: Database) -> AiSettingsResponse:
    """The caps, seeded from config on first read."""
    limits = await get_or_create_settings(db, user.id)
    await db.commit()
    return AiSettingsResponse(
        dailyMessageCap=limits.daily_message_cap,
        dailyCostCapUsd=f"{limits.daily_cost_cap_usd:.2f}",
    )


@router.put("/ai/settings", response_model=AiSettingsResponse)
async def update_settings(
    payload: AiSettingsUpdateRequest, user: CurrentUser, db: Database
) -> AiSettingsResponse:
    """§9.7's "editable in the app afterwards"."""
    limits = await get_or_create_settings(db, user.id)
    if payload.dailyMessageCap is not None:
        limits.daily_message_cap = payload.dailyMessageCap
    if payload.dailyCostCapUsd is not None:
        limits.daily_cost_cap_usd = Decimal(str(payload.dailyCostCapUsd))
    await db.commit()
    await db.refresh(limits)
    return AiSettingsResponse(
        dailyMessageCap=limits.daily_message_cap,
        dailyCostCapUsd=f"{limits.daily_cost_cap_usd:.2f}",
    )


@router.post("/ai/ask", response_model=AskResponse)
async def ask(payload: AskRequest, user: CurrentUser, db: Database) -> AskResponse:
    """§9.1 — ask one question. §9.7 — refuse gracefully once the cap is reached.

    **The cap is checked before the call, not after.** Checking afterwards would still
    have spent the money, which is the only thing the cap exists to prevent.

    **A refusal is a 200, not a 429.** §9.7 asks for a "graceful limit reached message" and
    the person needs to read it in the chat where they asked; an error status hands the
    front end an exception to render instead of an answer. The body says `blocked` and
    carries the sentence.
    """
    usage = await usage_today(db, user.id)
    if usage.blocked:
        message = usage.refusal_message() or "Today's limit has been reached."
        logger.info("ai_capped", user_id=str(user.id), messages=usage.messages)
        await db.commit()
        return AskResponse(
            id=uuid.uuid4(),
            text=message,
            model=settings.ai_model,
            inputTokens=0,
            outputTokens=0,
            cacheReadTokens=0,
            cacheWriteTokens=0,
            costUsd="0.000000",
            stopReason="cap_reached",
            latencyMs=0,
            error=None,
        )

    reply = await ai_client().ask(payload.prompt)

    # Logged whether or not it worked. A usage log holding only successes cannot explain
    # an outage — and a failed call still consumed input tokens.
    entry = AiUsageLogEntry(
        id=uuid.uuid4(),
        user_id=user.id,
        model=reply.model,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        cache_read_tokens=reply.cache_read_tokens,
        cache_write_tokens=reply.cache_write_tokens,
        cost_usd=reply.cost_usd,
        stop_reason=reply.stop_reason,
        latency_ms=reply.latency_ms,
        error=reply.error,
        created_at_utc=utcnow(),
    )
    db.add(entry)
    await db.commit()

    return AskResponse(
        id=entry.id,
        text=reply.text,
        model=reply.model,
        inputTokens=reply.input_tokens,
        outputTokens=reply.output_tokens,
        cacheReadTokens=reply.cache_read_tokens,
        cacheWriteTokens=reply.cache_write_tokens,
        costUsd=f"{reply.cost_usd:.6f}",
        stopReason=reply.stop_reason,
        latencyMs=reply.latency_ms,
        error=reply.error,
    )


@router.get("/ai/history", response_model=list[AskResponse])
async def usage_history(
    user: CurrentUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AskResponse]:
    """The caller's own usage log — what was asked of the model and what it cost.

    Not the transcript: the prompts and answers are not stored here, only the accounting.
    Batch 31 adds conversations, and keeping them apart is what lets this survive one
    being deleted.
    """
    rows = list(
        (
            await db.execute(
                select(AiUsageLogEntry)
                .where(AiUsageLogEntry.user_id == user.id)
                .order_by(AiUsageLogEntry.created_at_utc.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        AskResponse(
            id=row.id,
            text="",
            model=row.model,
            inputTokens=row.input_tokens,
            outputTokens=row.output_tokens,
            cacheReadTokens=row.cache_read_tokens,
            cacheWriteTokens=row.cache_write_tokens,
            costUsd=f"{row.cost_usd:.6f}",
            stopReason=row.stop_reason,
            latencyMs=row.latency_ms or 0,
            error=row.error,
        )
        for row in rows
    ]
