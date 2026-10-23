"""What each disc is being asked for on eBay, and the runs that found out — Batch T6.

Snag 7 asked what the collection is worth. eBay's sold prices are closed to apps
(`DECISIONS.md` #16, #126), so the answer is the one the film page's check already gives,
**current asking prices**, for every physical disc. It is stored so that a total is a sum
over rows rather than 1,454 live searches.

- :class:`DiscValuation`: one row per **film and format**, because one eBay search prices
  exactly that. Two Blu-rays of *Heat* are one search and one price, counted twice in the
  total, because they are two discs.
- :class:`ValuationRun`: one row per run, with its budget and counts, so "did last night's
  run finish?" is a query. ``scrape_runs`` is the precedent. Batch V6's bid trial claims one
  too (trigger ``trial``), so its eBay calls come out of the same day's share.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

#: The formats a valuation prices, best first. Downloads are left out: they cannot be
#: resold, so they are worth nothing to anyone but their owner.
VALUED_FORMATS = ("4k_uhd", "blu_ray", "dvd")

#: ``priced`` carries a price. ``not_priced`` means too few matching listings to say, and
#: carries none. There is no third state that guesses.
VALUATION_STATUSES = ("priced", "not_priced")

#: How a priced disc's value was reached since Batch X6 (#256): ``used``, the median of its
#: used listings; ``new_scaled``, New's median times the format's used-to-New factor. Null on
#: a value from before X6, which was the largest condition group's median (#209).
VALUE_BASES = ("used", "used_quartile", "new_scaled")

#: ``job`` is the scheduled command; ``admin`` is the button on Home. ``trial`` is Home's "Try
#: bid prices" (Batch V6): it spends the same share and saves no prices.
RUN_TRIGGERS = ("job", "admin", "trial")

#: ``budget_spent`` and ``stopped`` both leave films still to price, and the next run
#: carries on from them. ``abandoned`` is a run whose process died: nothing heard from it
#: for :data:`src.services.valuation.RUN_STALE_AFTER`.
RUN_STATUSES = ("running", "finished", "budget_spent", "stopped", "abandoned")


class ValuationRun(Base, UUIDPrimaryKeyMixin):
    """One pass over the films due a price, within a share of eBay's daily allowance."""

    __tablename__ = "valuation_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('job', 'admin', 'trial')", name="ck_valuation_runs_trigger"),
        CheckConstraint(
            "status IN ('running', 'finished', 'budget_spent', 'stopped', 'abandoned')",
            name="ck_valuation_runs_status",
        ),
        CheckConstraint("budget >= 0 AND calls >= 0", name="ck_valuation_runs_counts"),
        Index("ix_valuation_runs_started_utc", "started_utc"),
        # One running row at a time: the claim that stops a scheduled run and the Home
        # button from spending the same day's share twice.
        Index(
            "uq_valuation_runs_one_running",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    started_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    #: Moved on after every film. A running row whose heartbeat has stopped belongs to a
    #: process that died, and is marked abandoned so the next run can start.
    heartbeat_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    finished_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    #: The eBay calls this run was allowed: the daily share less what the last 24 hours'
    #: runs already spent.
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Browse calls actually made, retries included, because eBay counts those too.
    calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: For a trial: films with three or more auctions with bids, and films searched without.
    priced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_priced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Films eBay did not answer for. Their old price, if any, is kept.
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Films still due a price when the run ended. Zero means it finished the job. For a
    #: trial: films in its sample it did not search.
    remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: A trial's report, or an AA10b admin re-price marker that enables later scheduled
    #: valuation runs. Null on older runs and scheduled runs before the re-price starts.
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class DiscValuation(Base, UUIDPrimaryKeyMixin):
    """What one film on one format is being asked for on eBay UK, as of ``checked_utc``."""

    __tablename__ = "disc_valuations"
    __table_args__ = (
        UniqueConstraint("movie_id", "format_code", name="uq_disc_valuations_movie_format"),
        CheckConstraint(
            "format_code IN ('4k_uhd', 'blu_ray', 'dvd')", name="ck_disc_valuations_format"
        ),
        CheckConstraint("status IN ('priced', 'not_priced')", name="ck_disc_valuations_status"),
        # A priced row has a price and a not-priced row has none, so a guess cannot be
        # stored even by a bug.
        CheckConstraint(
            "(status = 'priced') = (price IS NOT NULL)",
            name="ck_disc_valuations_price_only_when_priced",
        ),
        CheckConstraint(
            "value_basis IS NULL OR value_basis IN ('used', 'used_quartile', 'new_scaled')",
            name="ck_disc_valuations_value_basis",
        ),
        # A factor is the mark of a New-based value, and only of one.
        CheckConstraint(
            "value_basis IS NULL OR (value_basis = 'new_scaled') = (factor IS NOT NULL)",
            name="ck_disc_valuations_factor_only_when_scaled",
        ),
        Index("ix_disc_valuations_checked_utc", "checked_utc"),
    )

    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    format_code: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    #: The disc's value as a used copy (Batch X6), exactly as the film page's check reports
    #: it; before X6, the median of the largest condition group. Null when not priced.
    price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    #: Listings behind the price, or the most a not-priced film could muster.
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: "Used" or "New" since Batch X6: which group of listings the price came from.
    condition_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    #: ``used`` or ``new_scaled`` (:data:`VALUE_BASES`); null when not priced, or from before X6.
    value_basis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: The used-to-New factor a ``new_scaled`` value was multiplied by.
    factor: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    #: The cheapest and dearest of the listings the value rests on, before any factor.
    low: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    #: Both groups, priced or not: the standard edition's used listings pooled, and its New
    #: ones. What the factor is measured from. ``used_count`` is null only on a value from
    #: before X6, which is how such a value is told apart and made due.
    used_median: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    used_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_median: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    new_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: AA10a keeps the monthly asking-value intact as a fallback. Three distinct observed
    #: sold listings in the last 90 days make this the effective value instead.
    sales_price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    sales_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sales_low: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    sales_high: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    sales_checked_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: How many listings matched the disc at all, and how many the search returned.
    matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    considered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Always "current asking prices". Stored so no reader can present it as anything else.
    basis: Mapped[str] = mapped_column(String(50), nullable=False)
    #: The words sent to eBay, so a surprising price can be checked by hand.
    search_query: Mapped[str] = mapped_column(Text, nullable=False)
    checked_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("valuation_runs.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def sales_backed(self) -> bool:
        return self.sales_count >= 3 and self.sales_price is not None

    @property
    def effective_price(self) -> Decimal | None:
        return self.sales_price if self.sales_backed else self.price
