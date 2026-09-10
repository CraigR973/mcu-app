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
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.clock import utcnow
from src.config import settings
from src.database import AsyncSessionLocal
from src.models.ai import AiConversation, AiMessage, AiToolCall, AiUsageLogEntry
from src.models.profile import Profile
from src.routers.movies import Database
from src.schemas.ai import (
    AiSettingsResponse,
    AiSettingsUpdateRequest,
    AiStatusResponse,
    AskRequest,
    AskResponse,
    ChatMessageResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    PendingToolCallResponse,
    ToolCallResolveRequest,
    ToolListResponse,
    ToolSummary,
    UsageResponse,
)
from src.services.ai.caps import UsageToday, get_or_create_settings, usage_today
from src.services.ai.chat import (
    ChatEvent,
    pending_calls,
    resolve_tool_call,
    resume_after_confirmation,
    run_turn,
)
from src.services.ai.client import ClaudeClient
from src.services.ai.tools import is_write_tool, tools_for

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


# ---------------------------------------------------------------------------
# Conversations, streaming chat and the confirmation boundary — §9.2, §9.3, §9.4
# ---------------------------------------------------------------------------

#: How a streaming handler gets a session.
#:
#: **Not the request's own.** FastAPI closes a `yield` dependency *before* a streaming
#: response body is consumed, so a generator holding the request session would find it
#: closed the moment it tried to read the conversation. This opens its own, and the tests
#: replace it with one bound to their rolled-back transaction.
_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = AsyncSessionLocal


def set_session_factory(
    factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None,
) -> None:
    """Substitute the streaming session factory. Used by tests."""
    global _session_factory
    _session_factory = factory or AsyncSessionLocal


async def _conversation_for(
    db: AsyncSession, conversation_id: uuid.UUID, user: Profile
) -> AiConversation:
    """One of the caller's own conversations, or a 404.

    Scoped to the caller rather than checked for ownership afterwards: with two profiles,
    "read the other person's chat" is not an administrative capability.
    """
    conversation = (
        await db.execute(
            select(AiConversation).where(
                AiConversation.id == conversation_id,
                AiConversation.user_id == user.id,
                AiConversation.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.get("/ai/tools", response_model=ToolListResponse)
async def list_tools(user: CurrentUser) -> ToolListResponse:
    """§9.2's acceptance — *"the tool list differs correctly between admin and viewer"*.

    An endpoint rather than an internal detail, because that criterion is a statement about
    what a given person can do and the only honest way to check it is to ask as them.
    """
    available = tools_for(user.role)
    return ToolListResponse(
        role=user.role.value,
        items=[
            ToolSummary(
                name=str(tool["name"]),
                description=str(tool.get("description", "")),
                writes=is_write_tool(str(tool["name"])),
            )
            for tool in available
        ],
        total=len(available),
    )


@router.get("/ai/conversations", response_model=ConversationListResponse)
async def list_conversations(user: CurrentUser, db: Database) -> ConversationListResponse:
    """§9.3's "conversation list"."""
    rows = list(
        (
            await db.execute(
                select(AiConversation)
                .where(AiConversation.user_id == user.id, AiConversation.deleted_at.is_(None))
                .order_by(AiConversation.updated_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return ConversationListResponse(
        items=[
            ConversationResponse(
                id=row.id, title=row.title, createdAt=row.created_at, updatedAt=row.updated_at
            )
            for row in rows
        ],
        total=len(rows),
    )


@router.post(
    "/ai/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(user: CurrentUser, db: Database) -> ConversationResponse:
    """Start a chat. The title arrives with the first question."""
    conversation = AiConversation(id=uuid.uuid4(), user_id=user.id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        createdAt=conversation.created_at,
        updatedAt=conversation.updated_at,
    )


@router.get("/ai/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def read_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: Database
) -> ConversationDetailResponse:
    """§9.3's "conversation detail", plus anything still waiting to be confirmed.

    The pending calls are part of the detail because a person can close the tab on a
    confirmation prompt and come back — the row outlives the stream that raised it.
    """
    conversation = await _conversation_for(db, conversation_id, user)
    messages = list(
        (
            await db.execute(
                select(AiMessage)
                .where(AiMessage.conversation_id == conversation.id)
                .order_by(AiMessage.sequence.asc())
            )
        )
        .scalars()
        .all()
    )
    waiting = await pending_calls(db, conversation)
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        createdAt=conversation.created_at,
        updatedAt=conversation.updated_at,
        messages=[
            ChatMessageResponse(
                id=message.id,
                role=message.role,
                text=message.text,
                sequence=message.sequence,
                createdAt=message.created_at_utc,
            )
            # A `tool_result` has nothing a person would want to read, and rendering it as
            # something they said would be a lie about who is in the conversation.
            for message in messages
            if message.role != "tool_result"
        ],
        pendingToolCalls=[
            PendingToolCallResponse(id=call.id, toolName=call.tool_name, input=call.tool_input)
            for call in waiting
        ],
    )


@router.delete("/ai/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: uuid.UUID, user: CurrentUser, db: Database) -> None:
    """Soft-delete a chat. The usage log is a separate table and survives it."""
    conversation = await _conversation_for(db, conversation_id, user)
    conversation.deleted_at = utcnow()
    await db.commit()


async def _stream(
    conversation_id: uuid.UUID,
    user: Profile,
    *,
    prompt: str | None = None,
    resume: bool = False,
) -> AsyncIterator[str]:
    """Drive one turn and render it as Server-Sent Events.

    Its own session, for the reason `_session_factory` explains. It commits at the end
    rather than per event, so a stream that dies halfway leaves the conversation as it was
    rather than half a turn that cannot be replayed.
    """
    async with _session_factory() as db:
        conversation = (
            await db.execute(
                select(AiConversation).where(
                    AiConversation.id == conversation_id,
                    AiConversation.user_id == user.id,
                    AiConversation.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if conversation is None:
            yield ChatEvent(kind="error", text="That conversation is gone.").to_sse()
            return

        if not resume:
            usage = await usage_today(db, user.id)
            if usage.blocked:
                # The same ceiling Batch 30 enforces, at the same point: before the call.
                yield ChatEvent(
                    kind="error",
                    text=usage.refusal_message() or "Today's limit has been reached.",
                ).to_sse()
                await db.commit()
                return

        client = ai_client()
        events = (
            resume_after_confirmation(db, conversation=conversation, user=user, client=client)
            if resume
            else run_turn(db, conversation=conversation, user=user, client=client, prompt=prompt)
        )
        try:
            async for event in events:
                yield event.to_sse()
        finally:
            await db.commit()


@router.post("/ai/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID, payload: AskRequest, user: CurrentUser, db: Database
) -> StreamingResponse:
    """§9.3's acceptance — *"user sends message, streamed response renders progressively"*.

    Answers `text/event-stream`. `X-Accel-Buffering: no` is not decoration: a proxy that
    buffers the body delivers the whole answer at once, which looks exactly like streaming
    being broken and is invisible in every test that does not run behind that proxy.
    """
    await _conversation_for(db, conversation_id, user)
    return StreamingResponse(
        _stream(conversation_id, user, prompt=payload.prompt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/ai/tool-calls/{call_id}/resolve")
async def resolve_tool_call_endpoint(
    call_id: uuid.UUID,
    payload: ToolCallResolveRequest,
    user: CurrentUser,
    db: Database,
) -> StreamingResponse:
    """§9.4 — confirm or cancel a pending write, then continue the turn.

    **Nothing has run at this point.** The write executes here if and only if `confirm` is
    true; cancelling records the refusal and tells the model the write did not happen, so
    it cannot go on to report success.
    """
    call = (
        await db.execute(
            select(AiToolCall)
            .join(AiConversation, AiConversation.id == AiToolCall.conversation_id)
            .where(AiToolCall.id == call_id, AiConversation.user_id == user.id)
        )
    ).scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool call not found")
    if call.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That has already been answered"
        )

    conversation = await _conversation_for(db, call.conversation_id, user)
    await resolve_tool_call(
        db, conversation=conversation, call=call, user=user, confirm=payload.confirm
    )
    await db.commit()

    return StreamingResponse(
        _stream(conversation.id, user, resume=True),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
