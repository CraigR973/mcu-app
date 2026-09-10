"""Photos of a disc — §3.10.

**Bytes in Postgres.** §3.10 says Supabase Storage; there is no Supabase project and the
owner settled storage as Neon on 2026-09-09. `BYTEA` is TOASTed, so a wide row costs
nothing to the catalogue queries that never select it.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

#: §3.10's "max 5 per item".
MAX_PHOTOS_PER_ITEM = 5

#: What the API will accept and what the CHECK permits.
ALLOWED_CONTENT_TYPES = ("image/jpeg", "image/png", "image/webp")


class ItemPhoto(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "item_photos"
    __table_args__ = (
        UniqueConstraint("collection_item_id", "checksum", name="uq_item_photos_item_checksum"),
    )

    collection_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    #: SHA-256 of the stored bytes. Serves as the `ETag`, so a browser's conditional
    #: request answers 304 and Batch 8's service worker can cache confidently.
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ItemPhoto {self.collection_item_id} {self.byte_size}B>"
