"""A line from one person to Craig — Batch X12a (UX48-05's "Tell Craig")."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base

#: Long enough for "the shelf says Back 2nd but the disc is in the Lounge", short enough to
#: read in Home's row without opening anything.
NOTE_MAX_LENGTH = 300


class CraigNote(Base):
    """What a person typed on the You page, held in Home's "Needs attention" until cleared."""

    __tablename__ = "craig_notes"
    __table_args__ = (
        CheckConstraint(
            f"char_length(body) BETWEEN 1 AND {NOTE_MAX_LENGTH}", name="ck_craig_notes_body_length"
        ),
        Index("ix_craig_notes_open", "created_utc", postgresql_where=text("cleared_utc IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    cleared_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
