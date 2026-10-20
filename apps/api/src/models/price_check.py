"""Prices found by the scrapers — roadmap §3.6.

**§3.6's notification trigger is not implemented here.** It describes a Postgres trigger
that queues a push when a price falls below `wanted_list.max_price`; push is **Batch 11**
(blocked on a credential checkpoint) and the alerting is **Batch 20**. `notification_sent`
exists for that batch and nothing writes it.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UUIDPrimaryKeyMixin

CONDITIONS = ("new", "used", "refurbished", "unknown")
LISTING_TYPES = ("buy_it_now", "auction", "fixed_price", "unknown")


class PriceCheck(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "price_checks"

    #: Both ``SET NULL``: a price check is a historical fact — "£12.99 at HMV on the
    #: 9th" — and stays true after the wanted entry is removed or the retailer edited.
    wanted_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wanted_list.id", ondelete="SET NULL"), nullable=True
    )
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retailers.id", ondelete="SET NULL"), nullable=True
    )

    #: §3.6's own column, and the reason the row is still readable once the FK is null.
    retailer_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")
    condition: Mapped[str] = mapped_column(String(50), nullable=False, server_default="unknown")
    listing_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="unknown")

    #: What the page called it. Kept so a wrong-page match is diagnosable afterwards
    #: rather than only at the moment it happened.
    title_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    url: Mapped[str] = mapped_column(Text, nullable=False)

    notification_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PriceCheck {self.retailer_name_snapshot} {self.price} {self.currency}>"
