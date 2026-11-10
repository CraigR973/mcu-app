"""A film set not to count toward one completion set — AE3 (#355, point 3).

Eastwood's set will never be complete while Piano Blues, a TV documentary episode, counts
against it, nor Kubrick's while his disowned Fear and Desire does. Either person can say a
missing film does not count, **in that set only**: it still counts in every other set it
is in. Saying so is audited in ``admin_actions``, and "Count it again" removes the row.

Keyed on the set's id and the member's TMDB id, because a missing film has no ``movies``
row; that is what missing means. A set the weekly rebuild retires takes its rows with it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UUIDPrimaryKeyMixin


class CompletionExclusion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "completion_exclusions"
    __table_args__ = (UniqueConstraint("set_id", "tmdb_id", name="uq_completion_exclusion"),)

    set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("completion_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: ``SET NULL``: who said so is useful, but losing the profile must not bring a film back.
    excluded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    excluded_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )
