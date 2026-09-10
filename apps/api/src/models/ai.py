"""The AI assistant's usage log and per-person caps — §9.1, §9.7."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin


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
        DateTime(timezone=False), nullable=False, server_default=func.now()
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
