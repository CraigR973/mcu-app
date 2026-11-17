"""Explicit personal review work (AD1, #351), separate from derived loans/trips.

Target IDs deliberately have no foreign keys: an answer must outlive a target's deletion,
as the audit log does. Reads revalidate targets; assignments cannot block existing repairs.

**AG5 (amends #351): any want can ask "which film?".** A ``wanted_identity`` row carries its
own ``wording``, written when it is assigned from the years its shop listings name, and its
answer is one of those years. The other two kinds keep their fixed words in
``services/assigned_reviews.py``.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin


class AssignedReview(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "assigned_reviews"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('titanic_disc', 'wanted_identity', 'shetland_series')",
            name="ck_assigned_review_kind",
        ),
        CheckConstraint("revision >= 1", name="ck_assigned_review_revision"),
        CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="ck_assigned_review_snapshot"),
        CheckConstraint(
            "answer IS NULL OR answer = 'unsure' OR "
            "(kind = 'titanic_disc' AND answer IN ('1953', '1997')) OR "
            "(kind = 'wanted_identity' AND answer ~ '^(19|20)[0-9]{2}$') OR "
            "(kind = 'shetland_series' AND answer IN ('use_series', 'keep_separate'))",
            name="ck_assigned_review_answer",
        ),
        CheckConstraint(
            "(kind = 'wanted_identity') = (wording IS NOT NULL) "
            "AND (wording IS NULL OR jsonb_typeof(wording) = 'object')",
            name="ck_assigned_review_wording",
        ),
        Index(
            "uq_assigned_review_target",
            "kind",
            "target_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_assigned_reviews_person", "assigned_to"),
    )

    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    answer: Mapped[str | None] = mapped_column(String(30), nullable=True)
    #: AG5: a want question's own words, ``{"title", "question", "evidence", "choices":
    #: [{"value", "label"}]}``; null for the other kinds, whose words are fixed in code.
    wording: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    answered_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
