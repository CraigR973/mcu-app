"""Used eBay listings observed for sale-price evidence (AA10a)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin


class EbayUsedListing(Base, UUIDPrimaryKeyMixin):
    """One standard-edition used Buy It Now listing, without eBay's title or image."""

    __tablename__ = "ebay_used_listings"
    __table_args__ = (
        UniqueConstraint("legacy_item_id", name="uq_ebay_used_listings_item"),
        CheckConstraint(
            "status IN ('active', 'sold', 'ended')", name="ck_ebay_used_listings_status"
        ),
        CheckConstraint(
            "sold_count IS NULL OR sold_count >= 0", name="ck_ebay_used_listings_sold_count"
        ),
        Index("ix_ebay_used_listings_movie_format", "movie_id", "format_code"),
        Index("ix_ebay_used_listings_retention", "status", "ended_at_utc"),
    )

    legacy_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    format_code: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    postage: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    condition_code: Mapped[str] = mapped_column(String(10), nullable=False)
    first_seen_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    last_seen_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    ended_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    sold_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: One check per successful weekly search while an item remains absent.
    missing_checked_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )


class EbayUsedScan(Base, UUIDPrimaryKeyMixin):
    """Last successful weekly search for one tracked film and format."""

    __tablename__ = "ebay_used_scans"
    __table_args__ = (
        UniqueConstraint("movie_id", "format_code", name="uq_ebay_used_scans_movie_format"),
        Index("ix_ebay_used_scans_checked", "checked_utc"),
    )

    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    format_code: Mapped[str] = mapped_column(String(20), nullable=False)
    checked_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class EbayUsedRun(Base, UUIDPrimaryKeyMixin):
    """A bounded pass; the first admin pass enables later scheduled passes."""

    __tablename__ = "ebay_used_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('admin', 'job')", name="ck_ebay_used_runs_trigger"),
        CheckConstraint(
            "status IN ('running', 'finished', 'budget_spent', 'stopped', 'abandoned')",
            name="ck_ebay_used_runs_status",
        ),
        CheckConstraint("budget >= 0 AND calls >= 0", name="ck_ebay_used_runs_budget"),
        Index("ix_ebay_used_runs_started", "started_utc"),
        Index(
            "uq_ebay_used_runs_running",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    trigger: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    heartbeat_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    finished_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    searched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ended: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
