"""eBay price alerts and the deal scan — Batch T8a, `DECISIONS.md` #203 and #216.

Everything here runs on the app's own eBay access. Nobody signs in to eBay and no personal
token is stored; that is T8b's, behind Craig's eBay set-up.

- :class:`EbayTarget`: a price someone wants to hear about. On one listing, found by the
  number in its web address, or on a saved search: a film on a format, meaning any UK Buy
  It Now listing of it.
- :class:`EbayWatchRun`: one scheduled pass, with its share of the day's eBay calls and
  what it did, so "did the 10:20 check run?" is a query. ``valuation_runs`` is the model.
- :class:`EbayPriceRef`: what a film on a format usually asks, from one search, kept for a
  fortnight so the deal scan does not search again for every new listing of it.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UUIDPrimaryKeyMixin

#: ``listing`` watches one eBay listing; ``search`` watches a film on a format.
TARGET_KINDS = ("listing", "search")

#: ``met`` is a listing whose price reached the target; it is not checked again until its
#: target changes. A search stays ``watching``, because the next cheap listing is news too.
#: ``ended`` is a listing eBay no longer has.
TARGET_STATUSES = ("watching", "met", "ended")

#: The disc formats a saved search can name.
TARGET_FORMATS = ("4k_uhd", "blu_ray", "dvd")

WATCH_RUN_STATUSES = ("running", "finished", "budget_spent", "stopped", "abandoned")


class EbayTarget(Base, UUIDPrimaryKeyMixin):
    """One person's price target, on a listing or on a film and format."""

    __tablename__ = "ebay_targets"
    __table_args__ = (
        CheckConstraint("kind IN ('listing', 'search')", name="ck_ebay_targets_kind"),
        CheckConstraint("status IN ('watching', 'met', 'ended')", name="ck_ebay_targets_status"),
        CheckConstraint("target_price > 0", name="ck_ebay_targets_price"),
        CheckConstraint(
            "format_code IS NULL OR format_code IN ('4k_uhd', 'blu_ray', 'dvd')",
            name="ck_ebay_targets_format",
        ),
        # A listing target names its listing, and a search target its film and format.
        CheckConstraint(
            "(kind = 'listing') = (legacy_item_id IS NOT NULL)", name="ck_ebay_targets_listing"
        ),
        CheckConstraint(
            "kind = 'listing' OR (movie_id IS NOT NULL AND format_code IS NOT NULL)",
            name="ck_ebay_targets_search",
        ),
        Index(
            "uq_ebay_targets_listing",
            "owner_id",
            "legacy_item_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND kind = 'listing'"),
        ),
        Index(
            "uq_ebay_targets_search",
            "owner_id",
            "movie_id",
            "format_code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND kind = 'search'"),
        ),
        Index("ix_ebay_targets_checked", "status", "last_checked_utc"),
    )

    #: Who set it, and who is told when it is met.
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    #: The film a search watches. A merge moves it with the film (`DECISIONS.md` #214).
    movie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=True
    )
    format_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: The number in the listing's web address: `ebay.co.uk/itm/<this>`.
    legacy_item_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")
    #: The listing's title, or the film's.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The listing sells by auction alone: its price is the current bid, and an alert
    #: offers the target as a maximum bid for eBay's own bidding (#203).
    is_auction: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    #: What the last check found. For a listing: its price, or its current bid. For a
    #: search: the cheapest matching UK Buy It Now listing, and which one it was.
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    current_postage: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    current_item_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ends_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="watching")
    last_checked_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    met_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class EbayWatchRun(Base, UUIDPrimaryKeyMixin):
    """One scheduled pass: the targets, then the newest UK listings."""

    __tablename__ = "ebay_watch_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('job', 'admin')", name="ck_ebay_watch_runs_trigger"),
        CheckConstraint(
            "status IN ('running', 'finished', 'budget_spent', 'stopped', 'abandoned')",
            name="ck_ebay_watch_runs_status",
        ),
        CheckConstraint("budget >= 0 AND calls >= 0", name="ck_ebay_watch_runs_counts"),
        Index("ix_ebay_watch_runs_started_utc", "started_utc"),
        Index(
            "uq_ebay_watch_runs_one_running",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    started_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    heartbeat_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    finished_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    #: eBay calls this run may make, and made, retries included.
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    targets_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_alerts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: The deal scan: pages of newest listings read, listings new since the last run, the
    #: ones that were a wanted film or an upgrade, usual prices looked up, and deals.
    pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    listings_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refs_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deals_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Finds whose push reached a phone (Batch X3); queued but undelivered ones do not count.
    deals_pushed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Where the next run starts reading. Since Batch X1 the run's own start less
    #: ``scan.MARK_MARGIN``, never a listing's date: one listing dated 12 days ahead, read on
    #: 9 Oct, set it to 21 Oct and blinded every run after. The column keeps its old name.
    newest_listing_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: Batch X1: the Wanted films this run searched one by one. Set by one run only, the
    #: first after X1's deploy, to recover what the blind scan of 9–12 Oct missed.
    wanted_searched: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class EbayPriceRef(Base, UUIDPrimaryKeyMixin):
    """What one film on one format usually asks on eBay UK, from one search."""

    __tablename__ = "ebay_price_refs"
    __table_args__ = (
        UniqueConstraint("movie_id", "format_code", name="uq_ebay_price_refs_movie_format"),
        CheckConstraint(
            "format_code IN ('4k_uhd', 'blu_ray', 'dvd')", name="ck_ebay_price_refs_format"
        ),
        CheckConstraint("status IN ('priced', 'not_priced')", name="ck_ebay_price_refs_status"),
        CheckConstraint(
            "(status = 'priced') = (median IS NOT NULL)", name="ck_ebay_price_refs_priced"
        ),
    )

    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    format_code: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    #: The film page's headline: standard editions, the largest condition group.
    median: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Standard-edition medians by eBay condition code, so a used copy is compared with
    #: used copies: ``{"3000": {"median": "8.50", "n": 6}}``.
    by_condition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    checked_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
