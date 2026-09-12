"""A discounted disc on a retailer's sale page — Batch 22, Phase 5.9."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

DEALS_TABLE = "deals"


class Deal(Base, UUIDPrimaryKeyMixin):
    __tablename__ = DEALS_TABLE

    #: ``SET NULL`` with a snapshot beside it, the same shape as ``price_checks``: a deal
    #: is a historical fact and stays readable after the retailer row changes.
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retailers.id", ondelete="SET NULL"), nullable=True
    )
    retailer_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)

    #: Null until the title is matched to a film. An unmatched deal is kept rather than
    #: dropped — it is the evidence that the matcher needs work, and dropping it would
    #: make a broken matcher indistinguishable from a quiet sale page.
    movie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="SET NULL"), nullable=True
    )
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    title_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    format_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    was_price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")

    #: **Derived from the two prices, never read off the page.** The batch's risk note is
    #: that a layout change stores a plausible wrong discount; a number computed from two
    #: figures that each passed a shape check cannot be a "save 70%" badge that happened
    #: to match a selector.
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Two timestamps because a deal persists across runs. "How long has this been on
    #: offer" and "is it still there" are different questions and one column answers
    #: neither.
    first_seen_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    last_seen_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    #: §5.10: *"dismissed items don't reappear"*. A soft state rather than a delete,
    #: because the next scrape will re-find the same deal and the row has to remember.
    dismissed_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    dismissed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Deal {self.retailer_name_snapshot} {self.title_snapshot!r} {self.price}>"
