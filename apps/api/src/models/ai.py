"""The AI assistant — usage and caps (§9.1, §9.7), conversations and tool calls (§9.2–9.4)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UpdatedAtMixin, UUIDPrimaryKeyMixin


class AiUsageLogEntry(Base, UUIDPrimaryKeyMixin):
    """One call to the model — §9.1's "token + cost logging per message".

    Deliberately **not** the chat transcript. Batch 31 owns conversations and messages;
    this survives them, so "what did I spend last month" stays answerable after a
    conversation is deleted.
    """

    __tablename__ = "ai_usage_log"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: The id actually used, not the one config holds now.
    model: Mapped[str] = mapped_column(String(60), nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Six decimal places. A short question costs a fraction of a penny, and rounding to
    #: cents per call would record every one as zero.
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0"))

    stop_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Set when the call failed. The row still exists — a log that holds only successes
    #: cannot explain an outage.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AiUsageLogEntry {self.model} in={self.input_tokens} out={self.output_tokens}>"


class AiSettings(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """§9.7's per-user caps, editable in the app.

    Two ceilings, because a message count alone does not bound spend: one question asked
    over a long conversation costs many times a short one, and the whole point of the cap
    is that a runaway loop cannot quietly empty the owner's account.
    """

    __tablename__ = "ai_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    #: Zero is meaningful — "no AI for me" — which is why the constraint floors at 0.
    daily_message_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    daily_cost_cap_usd: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("2.00")
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AiSettings {self.user_id} cap={self.daily_message_cap}>"


#: What a stored message is. `tool_result` is a *user*-role message on the wire — the
#: results of a turn's tool calls go back as one user message — but it is a different kind
#: of thing from something a person typed, and the chat must not render it as one.
MESSAGE_ROLES = ("user", "assistant", "tool_result")

#: §9.4's lifecycle. `pending` only ever applies to a write tool.
TOOL_CALL_STATUSES = ("pending", "confirmed", "cancelled", "failed")


class AiConversation(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """One chat — §9.3's "conversation list and detail"."""

    __tablename__ = "ai_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: Derived from the first question. Nobody titles a chat before having it.
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New conversation")

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AiConversation {self.title!r}>"


class AiMessage(Base, UUIDPrimaryKeyMixin):
    """One turn's worth of content blocks.

    **`content` is the blocks, not the text.** The API is stateless and every turn re-sends
    the whole conversation; a turn that used a tool is three messages, and replaying only
    the rendered text would make Claude answer as though the tool call never happened —
    quietly, with no error anywhere.
    """

    __tablename__ = "ai_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    #: What the chat renders. Empty for a `tool_result`, which has nothing to show.
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    #: Monotonic within a conversation. `created_at` cannot order these: several rows are
    #: written in one transaction and `NOW()` is the transaction's start time, so they
    #: would share a timestamp (gotcha 24).
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AiMessage {self.role} #{self.sequence}>"


class AiToolCall(Base, UUIDPrimaryKeyMixin):
    """A tool Claude asked to call — §9.4's confirmation boundary.

    **This is a row rather than an in-memory future because the confirmation crosses an
    HTTP boundary.** Claude asks, the browser prompts, and the answer arrives in a later
    request; the agent loop is therefore suspended rather than blocked. An in-process
    future would lose every pending confirmation on the next deploy.
    """

    __tablename__ = "ai_tool_calls"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )

    #: The API's own id. The `tool_result` must quote it back exactly or the next turn is
    #: rejected outright.
    tool_use_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AiToolCall {self.tool_name} {self.status}>"
