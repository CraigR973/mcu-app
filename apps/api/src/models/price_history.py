"""Rolled-up price history and the record of each scrape run — §3.18, §5.5, §5.8."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

#: §5.8's threshold — raw checks older than this are rolled up and deleted.
RETENTION_DAYS = 90

#: What started a run. `cron` is the Railway schedule; `manual` is a person or an agent.
SCRAPE_TRIGGERS = ("cron", "manual")


class PriceHistoryDaily(Base, UUIDPrimaryKeyMixin):
    """One day's prices for one want at one retailer, after the raw rows are gone.

    §3.18 as designed. The point is Batch 21's charts: a trend line does not need every
    individual check from four months ago, it needs a point per day — so 90 days of raw
    rows collapse to a fraction of the space and the chart is unchanged.
    """

    __tablename__ = "price_history_daily"

    wanted_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wanted_list.id", ondelete="SET NULL"), nullable=True
    )
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retailers.id", ondelete="SET NULL"), nullable=True
    )

    #: Kept for the same reason `price_checks` keeps it, and more so: by the time a row is
    #: aggregated it is at least 90 days old, so the retailer being gone is likely.
    retailer_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)
    min_price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    max_price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    check_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PriceHistoryDaily {self.retailer_name_snapshot} {self.date} {self.avg_price}>"


class ScrapeRun(Base, UUIDPrimaryKeyMixin):
    """What one scrape run did — §5.5's acceptance, made answerable the morning after.

    **This table exists because a number nobody wrote down cannot be checked.** The
    corrected §5.5 criterion (`DECISIONS.md` #112) is stated in counts — attempted,
    not-stocked, written — and until now those lived only inside one HTTP response.
    On 2026-09-09 a scraper "test" showed results on screen while saving nothing, and
    afterwards there was no way to tell. A run that records itself is the answer to that
    class of question, and the only way *"first overnight run completes"* is checkable
    at breakfast.
    """

    __tablename__ = "scrape_runs"

    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    #: ``NULL`` while in flight — so a run that died halfway is visible as a run that died
    #: halfway, rather than as no row at all.
    finished_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    #: Pairs the shops were actually asked about — neither skipped nor answered "not
    #: stocked". The left-hand side of #112's corrected criterion.
    attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_stocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Wants whose shop answered with an empty results page — neither a failure nor a
    #: claim that the shop has not got it (`DECISIONS.md` #125). Recorded so the run's
    #: numbers add up: before this column existed these were counted in `failed`.
    no_results: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alerts_queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: §5.5's "failures logged with retailer + reason", as
    #: ``[{"retailer": ..., "reason": ...}]``.
    failures: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    #: Batch 20b, second half: each refused request that was retried, as ``{"retailer",
    #: "wanted", "asked", "waited", "note", "retry"}``: what the shop asked for, the wait it
    #: was given, and whether the retry got through. Migration 045.
    refusals: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    disabled_retailers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    #: Set when the run itself blew up, as opposed to individual scrapes failing.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ScrapeRun {self.started_at_utc} written={self.written}>"
