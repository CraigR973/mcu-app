"""Durable successful-add receipts; retries retain their original result (AB3)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UUIDPrimaryKeyMixin


class CollectionAddRequest(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "collection_add_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_collection_add_request"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collection_items.id", ondelete="SET NULL"), nullable=True
    )
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )
