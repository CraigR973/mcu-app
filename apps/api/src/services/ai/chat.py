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

**What is stored is what the API accepts back** (Batch X7, AI45-01). Each answer used to be
stored as the SDK's full dump of the response, and a streamed text block carries the SDK-only
`parsed_output`; replayed next turn, the API refused it with a 400, so no conversation got
past its first answer from 10 Sep to 13 Oct. :func:`request_block` keeps only the fields the
SDK's request type for that block declares, on write and again on read, so the stored chats
continue as they are.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from anthropic.types import (
    MessageParam,
    RedactedThinkingBlockParam,
    TextBlockParam,
    ThinkingBlockParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.config import settings
from src.models.ai import AiConversation, AiMessage, AiToolCall, AiUsageLogEntry
from src.models.profile import Profile
from src.services.ai.caps import person_today, reserve_call
from src.services.ai.client import ClaudeClient, TurnEvent, system_prompt
from src.services.ai.tools import execute_tool, is_write_tool, prepare_write, tools_for

logger = structlog.get_logger(__name__)

#: How many tool round trips one question may take before the loop gives up. Not a
#: performance guard — a model that has decided to search the collection over and over is
#: spending the owner's money in a loop, and the cap is what stops one question doing it.
MAX_TOOL_ROUNDS = 5

#: How many tools one round may run (AI45-05: a round could ask for any number). The rest
#: are answered "not run", so the model asks for them in its next round.
MAX_TOOL_CALLS_PER_ROUND = 4

#: Longest title derived from a first message.
TITLE_LENGTH = 80

#: Each content block type the loop stores, and the fields the API accepts back for it: the
#: SDK's own request types, so a field the SDK adds or removes moves this with it.
_REQUEST_FIELDS: dict[str, frozenset[str]] = {
    block_type: frozenset(param.__required_keys__ | param.__optional_keys__)
    for block_type, param in (
        ("text", TextBlockParam),
        ("tool_use", ToolUseBlockParam),
        ("thinking", ThinkingBlockParam),
        ("redacted_thinking", RedactedThinkingBlockParam),
        ("tool_result", ToolResultBlockParam),
    )
}


def request_block(block: dict[str, Any]) -> dict[str, Any]:
    """One stored block as the API will take it back: its request fields, no nulls.

    A block type outside the table keeps its fields bar the nulls; none reaches the loop
    today (no server tools are offered).
    """
    allowed = _REQUEST_FIELDS.get(str(block.get("type")))
    return {
        key: value
        for key, value in block.items()
        if value is not None and (allowed is None or key in allowed)
    }


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
        content=[request_block(block) for block in content],
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
            # Cleaned on read as well as on write: the answers stored before X7 carry
            # `parsed_output`, and this is what lets those six conversations continue.
            content=[request_block(block) for block in row.content],  # type: ignore[misc]
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


async def _record_failure(
    db: AsyncSession, user: Profile, event: TurnEvent, *, now: datetime
) -> None:
    """A failed call leaves a usage row, with its status and error type (AI45-04).

    The chat used to write a row only when a call succeeded, so a failure left one log line
    that Railway did not keep. The row costs nothing and does not count against the
    allowance (`caps.usage_today` skips errors); the daily check counts these rows.
    """
    logger.warning(
        "ai_chat_failed",
        user_id=str(user.id),
        status=event.status,
        error_type=event.error_type,
    )
    db.add(
        AiUsageLogEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            model=settings.ai_model,
            stop_reason="error",
            error=(event.error or event.text or "unknown error")[:1000],
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

    **The allowance is checked before every model call** (`caps.reserve_call`), a resumed
    turn's included, and before a new message is stored, so a refused question leaves no
    orphan behind.
    """
    now = now or utcnow()

    usage = await reserve_call(db, user.id, now=now)
    if usage.blocked:
        yield ChatEvent(
            kind="error", text=usage.refusal_message() or "Today's limit has been reached."
        )
        return

    if prompt is not None:
        # A card still waiting is closed as declined first (AI45-02): its tool call would
        # otherwise sit unanswered in front of the new message, which the API refuses.
        await close_waiting_calls(db, conversation)
        await append_message(
            db, conversation, role="user", content=[{"type": "text", "text": prompt}], text=prompt
        )
        if conversation.title == "New conversation":
            conversation.title = derive_title(prompt)
        await db.flush()

    today = await person_today(db, user.id, now=now)
    system = system_prompt(user.display_name, today)
    tools = tools_for(user.role)

    for round_number in range(MAX_TOOL_ROUNDS):
        if round_number > 0:
            usage = await reserve_call(db, user.id)
            if usage.blocked:
                yield ChatEvent(
                    kind="error",
                    text=usage.refusal_message() or "Today's limit has been reached.",
                )
                return
        last_round = round_number == MAX_TOOL_ROUNDS - 1
        history = await history_for(db, conversation)
        final: Any = None
        assistant_text: list[str] = []

        async for event in client.stream_turn(
            history,
            tools=tools,
            system=system,
            # The last round must answer with what it has (AI45-05, Part D's D3).
            tool_choice={"type": "none"} if last_round else None,
        ):
            if event.kind == "text":
                assistant_text.append(event.text)
                yield ChatEvent(kind="text", text=event.text)
            elif event.kind == "error":
                await _record_failure(db, user, event, now=utcnow())
                yield ChatEvent(kind="error", text=event.text)
                return
            else:
                final = event.message
                await _record_usage(db, user, event, now=utcnow())

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
        for index, block in enumerate(tool_uses):
            call = AiToolCall(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                tool_use_id=str(block["id"]),
                tool_name=str(block["name"]),
                tool_input=block.get("input") or {},
                created_at_utc=utcnow(),
            )
            db.add(call)
            if index >= MAX_TOOL_CALLS_PER_ROUND:
                _settle(
                    call,
                    "failed",
                    f"Not run: at most {MAX_TOOL_CALLS_PER_ROUND} tools run at once. Ask for "
                    "this one again in your next step if it is still needed.",
                )
            elif is_write_tool(call.tool_name):
                proposal = await prepare_write(
                    call.tool_name, call.tool_input, user=user, db=db, today=today
                )
                if proposal.input is None:
                    # Nothing to confirm: the model reads why and asks the person.
                    _settle(call, "failed", proposal.refusal or "That could not be done.")
                else:
                    call.tool_input = proposal.input
                    needs_confirmation.append(call)
            else:
                outcome = await execute_tool(
                    call.tool_name, call.tool_input, user=user, db=db, today=today
                )
                _settle(call, "confirmed" if outcome.ok else "failed", outcome.text)
        await db.flush()

        if needs_confirmation:
            # **The suspension.** Nothing is executed, nothing is appended, and the turn
            # ends here until a person answers.
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


def _settle(call: AiToolCall, status: str, result: str) -> None:
    call.status = status
    call.result = result
    call.resolved_at_utc = utcnow()


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
            # A cancelled or failed call is an error result: it tells the model the write
            # did not happen, which is what stops it reporting success in the next sentence.
            **({"is_error": True} if call.status in {"cancelled", "failed"} else {}),
        }
        for call in calls
    ]
    await append_message(db, conversation, role="tool_result", content=content, text="")


async def _claim(db: AsyncSession, call: AiToolCall, status: str) -> bool:
    """Move a call out of `pending` in one guarded update; false if someone else already did.

    **One confirmation writes once** (AI45-06). Two taps on Yes, or Yes on two phones, each
    read `pending` and each wrote: two watch rows in 5 of 5 trials. The update takes the row's
    lock, so the second waits for the first to commit, finds the status moved on, and claims
    nothing.
    """
    claimed = (
        await db.execute(
            update(AiToolCall)
            .where(AiToolCall.id == call.id, AiToolCall.status == "pending")
            .values(status=status, resolved_at_utc=utcnow())
            .returning(AiToolCall.id)
            .execution_options(synchronize_session=False)
        )
    ).scalar_one_or_none()
    await db.refresh(call)
    return claimed is not None


async def resolve_tool_call(
    db: AsyncSession,
    *,
    conversation: AiConversation,
    call: AiToolCall,
    user: Profile,
    confirm: bool,
    now: datetime | None = None,
) -> bool:
    """§9.4 — execute a confirmed write, or record that it was refused.

    Returns whether this request was the one that answered the call; a second answer to
    the same call does nothing and returns false.

    **Cancelling leaves nothing behind**, which is the acceptance criterion. The row is
    kept, marked `cancelled`, with a result the model reads as a refusal — deleting it
    would make "did that actually run?" unanswerable afterwards. A write that fails is
    marked `failed`, not `confirmed`.
    """
    if not await _claim(db, call, "confirmed" if confirm else "cancelled"):
        return False

    if confirm:
        today = await person_today(db, user.id, now=now)
        outcome = await execute_tool(call.tool_name, call.tool_input, user=user, db=db, today=today)
        _settle(call, "confirmed" if outcome.ok else "failed", outcome.text)
    else:
        _settle(
            call, "cancelled", "The person declined to run this. Do not try it again unless asked."
        )
    await db.flush()

    logger.info(
        "ai_tool_resolved",
        tool=call.tool_name,
        status=call.status,
        conversation_id=str(conversation.id),
    )
    return True


async def close_waiting_calls(db: AsyncSession, conversation: AiConversation) -> None:
    """Close any card still waiting as declined, and answer its turn, before a new message.

    The person typed instead of tapping: they moved on, so the write does not run, and the
    model is told so in the `tool_result` the API requires straight after its call.
    """
    waiting = await pending_calls(db, conversation)
    if not waiting:
        return
    for call in waiting:
        if await _claim(db, call, "cancelled"):
            _settle(
                call,
                "cancelled",
                "Not run: the person sent a new message instead of answering the card. Do "
                "not try it again unless they ask.",
            )
    await db.flush()
    await _answer_last_turn(db, conversation)


async def _answer_last_turn(db: AsyncSession, conversation: AiConversation) -> bool:
    """Append the results for the last assistant message's tool calls. False if none."""
    last_assistant = (
        await db.execute(
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation.id, AiMessage.role == "assistant")
            .order_by(AiMessage.sequence.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_assistant is None:
        return False
    tool_use_ids = [
        str(block["id"]) for block in last_assistant.content if block.get("type") == "tool_use"
    ]
    await _append_tool_results(db, conversation, tool_use_ids)
    return True


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
    if not await _answer_last_turn(db, conversation):  # pragma: no cover - implied by a call
        yield ChatEvent(kind="error", text="There is nothing to continue.")
        return

    async for event in run_turn(db, conversation=conversation, user=user, client=client):
        yield event
