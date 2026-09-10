"""The conversation loop — §9.3's chat and §9.4's confirmation boundary.

**A manual loop, not the SDK's tool runner.** The runner drives the whole agentic cycle in
one process, and §9.4 requires the opposite: when Claude asks to call a write tool the loop
has to **stop**, hand the request to a browser, and resume on a later HTTP request when a
person has said yes. That is a suspension across a network boundary, which is exactly the
control the runner does not expose.

**How a turn actually runs.**

1. The person's message is stored, and the whole conversation is replayed to the model —
   the API is stateless, so history is re-sent every time.
2. Text streams back to the browser as it arrives.
3. If the turn ends in `tool_use`, a row is written for **every** call it asked for. Read
   tools run immediately; write tools stay `pending`.
4. If nothing is pending, the results go back as one `tool_result` message and the loop
   goes round again. If anything is pending, the turn **suspends** — and the browser is
   told what is waiting.
5. Confirming or cancelling resolves the pending rows and resumes from step 4.

**Why every call in a turn gets a row, including the reads.** The API requires that one
`tool_result` message answers *all* of an assistant message's `tool_use` blocks. A turn
that asks to search the collection and add something to the wanted list cannot send half
an answer while it waits — so the read is executed, its result is held on its row, and both
go back together once the write is resolved.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from anthropic.types import MessageParam
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.ai import AiConversation, AiMessage, AiToolCall, AiUsageLogEntry
from src.models.profile import Profile
from src.services.ai.client import ClaudeClient, TurnEvent
from src.services.ai.tools import execute_tool, is_write_tool, tools_for

logger = structlog.get_logger(__name__)

#: How many tool round trips one question may take before the loop gives up. Not a
#: performance guard — a model that has decided to search the collection over and over is
#: spending the owner's money in a loop, and the cap is what stops one question doing it.
MAX_TOOL_ROUNDS = 5

#: Longest title derived from a first message.
TITLE_LENGTH = 80


@dataclass
class ChatEvent:
    """What the browser is told, as it happens.

    ``text`` many times, then exactly one terminal event: ``done``, ``confirm`` (a write
    tool is waiting) or ``error``.
    """

    kind: str
    text: str = ""
    payload: dict[str, Any] | None = None

    def to_sse(self) -> str:
        """One Server-Sent Event.

        The double newline is the record separator and its absence is the classic bug: the
        browser holds the last event in its buffer for ever and the answer appears to stop
        one chunk short.
        """
        body = {"kind": self.kind, "text": self.text, **(self.payload or {})}
        return f"data: {json.dumps(body)}\n\n"


async def _next_sequence(db: AsyncSession, conversation_id: uuid.UUID) -> int:
    current = (
        await db.execute(
            select(func.coalesce(func.max(AiMessage.sequence), 0)).where(
                AiMessage.conversation_id == conversation_id
            )
        )
    ).scalar_one()
    return int(current) + 1


async def append_message(
    db: AsyncSession,
    conversation: AiConversation,
    *,
    role: str,
    content: list[dict[str, Any]],
    text: str = "",
) -> AiMessage:
    """Store one message and return it."""
    message = AiMessage(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=role,
        content=content,
        text=text,
        sequence=await _next_sequence(db, conversation.id),
        created_at_utc=utcnow(),
    )
    db.add(message)
    await db.flush()
    return message


async def history_for(db: AsyncSession, conversation: AiConversation) -> list[MessageParam]:
    """The conversation as the API wants it back.

    A stored `tool_result` row is a **user**-role message on the wire: the results of a
    turn's tool calls go back as one user message. It is stored under its own role so the
    chat can decline to render it as something a person said.
    """
    rows = list(
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
    return [
        MessageParam(
            role="assistant" if row.role == "assistant" else "user",
            content=row.content,  # type: ignore[typeddict-item]
        )
        for row in rows
    ]


def derive_title(prompt: str) -> str:
    """A conversation's name, from its first question. Nobody titles a chat."""
    cleaned = " ".join(prompt.split())
    if len(cleaned) <= TITLE_LENGTH:
        return cleaned or "New conversation"
    return cleaned[: TITLE_LENGTH - 1].rstrip() + "…"


async def _record_usage(
    db: AsyncSession, user: Profile, event: TurnEvent, *, now: datetime
) -> None:
    """One row per model call, exactly as Batch 30's single-turn endpoint writes."""
    reply = event.reply
    if reply is None:  # pragma: no cover - `done` always carries one
        return
    db.add(
        AiUsageLogEntry(
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
            created_at_utc=now,
        )
    )
    await db.flush()


async def pending_calls(db: AsyncSession, conversation: AiConversation) -> list[AiToolCall]:
    """Write tools waiting on a person — §9.4's queue."""
    return list(
        (
            await db.execute(
                select(AiToolCall)
                .where(
                    AiToolCall.conversation_id == conversation.id,
                    AiToolCall.status == "pending",
                )
                .order_by(AiToolCall.created_at_utc.asc())
            )
        )
        .scalars()
        .all()
    )


async def _calls_for_turn(
    db: AsyncSession, conversation: AiConversation, ids: list[str]
) -> list[AiToolCall]:
    if not ids:
        return []
    rows = list(
        (
            await db.execute(
                select(AiToolCall).where(
                    AiToolCall.conversation_id == conversation.id,
                    AiToolCall.tool_use_id.in_(ids),
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {row.tool_use_id: row for row in rows}
    return [by_id[tool_use_id] for tool_use_id in ids if tool_use_id in by_id]


def _confirmation_payload(calls: list[AiToolCall]) -> dict[str, Any]:
    return {
        "toolCalls": [
            {
                "id": str(call.id),
                "toolName": call.tool_name,
                "input": call.tool_input,
            }
            for call in calls
        ]
    }


async def run_turn(
    db: AsyncSession,
    *,
    conversation: AiConversation,
    user: Profile,
    client: ClaudeClient,
    prompt: str | None = None,
    now: datetime | None = None,
) -> AsyncIterator[ChatEvent]:
    """Run a conversation forward until it answers, needs a confirmation, or fails.

    ``prompt`` is ``None`` when resuming after §9.4's confirmation — the history already
    holds everything, including the `tool_result` the resolution just wrote.
    """
    now = now or utcnow()

    if prompt is not None:
        await append_message(
            db, conversation, role="user", content=[{"type": "text", "text": prompt}], text=prompt
        )
        if conversation.title == "New conversation":
            conversation.title = derive_title(prompt)
        await db.flush()

    tools = tools_for(user.role)

    for _ in range(MAX_TOOL_ROUNDS):
        history = await history_for(db, conversation)
        final: Any = None
        assistant_text: list[str] = []

        async for event in client.stream_turn(history, tools=tools):
            if event.kind == "text":
                assistant_text.append(event.text)
                yield ChatEvent(kind="text", text=event.text)
            elif event.kind == "error":
                yield ChatEvent(kind="error", text=event.text)
                return
            else:
                final = event.message
                await _record_usage(db, user, event, now=now)

        if final is None:  # pragma: no cover - `done` or `error` always arrives
            yield ChatEvent(kind="error", text="The assistant stopped unexpectedly.")
            return

        blocks = [block.model_dump() for block in final.content]
        await append_message(
            db,
            conversation,
            role="assistant",
            content=blocks,
            text="".join(assistant_text).strip(),
        )

        tool_uses = [block for block in blocks if block.get("type") == "tool_use"]
        if not tool_uses:
            await db.flush()
            yield ChatEvent(kind="done")
            return

        # A row for every call this turn asked for — see the module docstring on why the
        # reads get one too.
        needs_confirmation: list[AiToolCall] = []
        for block in tool_uses:
            call = AiToolCall(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                tool_use_id=str(block["id"]),
                tool_name=str(block["name"]),
                tool_input=block.get("input") or {},
                created_at_utc=utcnow(),
            )
            db.add(call)
            if is_write_tool(call.tool_name):
                needs_confirmation.append(call)
            else:
                call.result = await execute_tool(call.tool_name, call.tool_input, user=user, db=db)
                call.status = "confirmed"
                call.resolved_at_utc = utcnow()
        await db.flush()

        if needs_confirmation:
            # **The suspension.** Nothing is executed, nothing is appended, and the turn
            # ends here until a person answers.
            await db.flush()
            yield ChatEvent(
                kind="confirm",
                text="",
                payload=_confirmation_payload(needs_confirmation),
            )
            return

        await _append_tool_results(db, conversation, [str(b["id"]) for b in tool_uses])

    yield ChatEvent(
        kind="error",
        text="The assistant went round in circles on that one. Try asking it differently.",
    )


async def _append_tool_results(
    db: AsyncSession, conversation: AiConversation, tool_use_ids: list[str]
) -> None:
    """Send every result for a turn back as one message.

    One message, because the API requires that a turn's `tool_use` blocks are all answered
    together — splitting them is rejected outright.
    """
    calls = await _calls_for_turn(db, conversation, tool_use_ids)
    content = [
        {
            "type": "tool_result",
            "tool_use_id": call.tool_use_id,
            "content": call.result or "",
            # A cancelled call is an error result: it tells the model the write did not
            # happen, which is what stops it reporting success in the next sentence.
            **({"is_error": True} if call.status == "cancelled" else {}),
        }
        for call in calls
    ]
    await append_message(db, conversation, role="tool_result", content=content, text="")


async def resolve_tool_call(
    db: AsyncSession,
    *,
    conversation: AiConversation,
    call: AiToolCall,
    user: Profile,
    confirm: bool,
) -> None:
    """§9.4 — execute a confirmed write, or record that it was refused.

    **Cancelling leaves nothing behind**, which is the acceptance criterion. The row is
    kept, marked `cancelled`, with a result the model reads as a refusal — deleting it
    would make "did that actually run?" unanswerable afterwards.
    """
    if call.status != "pending":
        return

    if confirm:
        call.result = await execute_tool(call.tool_name, call.tool_input, user=user, db=db)
        call.status = "confirmed"
    else:
        call.result = "The person declined to run this. Do not try it again unless asked."
        call.status = "cancelled"
    call.resolved_at_utc = utcnow()
    await db.flush()

    logger.info(
        "ai_tool_resolved",
        tool=call.tool_name,
        status=call.status,
        conversation_id=str(conversation.id),
    )


async def resume_after_confirmation(
    db: AsyncSession,
    *,
    conversation: AiConversation,
    user: Profile,
    client: ClaudeClient,
) -> AsyncIterator[ChatEvent]:
    """Continue a turn whose write tools have all been answered."""
    if await pending_calls(db, conversation):
        yield ChatEvent(kind="error", text="Something is still waiting to be confirmed.")
        return

    # The last assistant message is the one that asked; answer exactly its calls.
    last_assistant = (
        await db.execute(
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation.id, AiMessage.role == "assistant")
            .order_by(AiMessage.sequence.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_assistant is None:  # pragma: no cover - a confirmation implies one exists
        yield ChatEvent(kind="error", text="There is nothing to continue.")
        return

    tool_use_ids = [
        str(block["id"]) for block in last_assistant.content if block.get("type") == "tool_use"
    ]
    await _append_tool_results(db, conversation, tool_use_ids)

    async for event in run_turn(db, conversation=conversation, user=user, client=client):
        yield event
