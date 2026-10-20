"""A discounted disc on a retailer's sale page — Batch 22, Phase 5.9."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, and_, or_
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement

from src.models.base import UTC_NOW, Base, UUIDPrimaryKeyMixin

DEALS_TABLE = "deals"

#: How long a shop's deal stays on the page after the scrape last saw it (Batch X1).
SHOP_DEAL_FRESH_FOR = timedelta(days=2)


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
    #: Batch V8. An eBay find's ``was_price`` is its usual price, the average of eBay's
    #: figure and the shops' recent prices; these are its parts, each
    #: ``{"source": …, "price": …}``, eBay first. Null for a retailer's deal, whose "was"
    #: price is its own, and for eBay finds stored before V8, which were eBay's alone.
    usual_sources: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")
    #: Batch X1, eBay finds only: the listing's own condition ("Very good"), and how many
    #: asking prices stand behind ``was_price``. Null for a shop's deal; the condition is
    #: cleared with the title and image once an eBay find expires (licence §8.1.2).
    listing_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    usual_listings: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: **Derived from the two prices, never read off the page.** The batch's risk note is
    #: that a layout change stores a plausible wrong discount; a number computed from two
    #: figures that each passed a shape check cannot be a "save 70%" badge that happened
    #: to match a selector.
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Two timestamps because a deal persists across runs. "How long has this been on
    #: offer" and "is it still there" are different questions and one column answers
    #: neither.
    first_seen_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )
    last_seen_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )

    #: §5.10: *"dismissed items don't reappear"*. A soft state rather than a delete,
    #: because the next scrape will re-find the same deal and the row has to remember.
    dismissed_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    dismissed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    #: Batch T8a. An eBay find sells or ends within days, and nothing re-checks it, so it
    #: leaves the feed at this time. A retailer's deal has none: its page is scraped
    #: again, and since Batch X1 it leaves the feed :data:`SHOP_DEAL_FRESH_FOR` after the
    #: scrape last saw it, so a shop that stops answering cannot leave a stale price up.
    expires_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Deal {self.retailer_name_snapshot} {self.title_snapshot!r} {self.price}>"


def live_deal(now: datetime) -> ColumnElement[bool]:
    """A deal the feed shows: not dismissed, and not past its expiry or its freshness.

    An eBay find carries its own expiry. A shop's deal has none and leaves two days after
    the scrape last saw it (Batch X1): the six Zavvi deals last seen on 30 Sep were still on
    the page on 12 Oct, every scrape since having been refused. One definition for the feed,
    its count and the menu's badge, so they cannot disagree.
    """
    return and_(
        Deal.dismissed_at_utc.is_(None),
        or_(
            Deal.expires_at_utc > now,
            and_(
                Deal.expires_at_utc.is_(None),
                Deal.last_seen_at_utc > now - SHOP_DEAL_FRESH_FOR,
            ),
        ),
    )
