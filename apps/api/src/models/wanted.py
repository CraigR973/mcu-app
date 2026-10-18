"""The wanted list and the retailers watched for it — roadmap §3.5 and §3.16.

**Four earlier batches deferred work to this table.** Batch 13's "bulk add missing to
wanted list", Batch 15's `wanted_list` trash tab, Batch 16's third ownership state, and
Batch 17's `release_calendar.is_wishlist_match` were all left undone because §3.5 had no
implementation. That is what makes this the table to get right rather than the quick half
of the batch.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

WANTED_LIST_TABLE = "wanted_list"
RETAILERS_TABLE = "retailers"

SCRAPER_TYPES = ("built_in", "generic_css", "custom")
SCRAPE_FREQUENCIES = ("daily", "weekly", "manual")
SCRAPE_STATUSES = ("success", "error", "blocked")

#: §3.16's original six plus permitted UK replacements selected after the live Batch 19
#: acceptance checks (`DECISIONS.md` #91).
#:
#: **Seeded with no selectors.** `scraper_config` is deliberately empty for every one of
#: them: the CSS a retailer's page needs is Batch 19's problem, and inventing selectors
#: here that nobody has run against a live page would be worse than none — a scraper
#: configured with a plausible wrong selector *does not error*, it persists a wrong number
#: (the risk note the ledger carries for Batch 19). An empty config is visibly unconfigured.
DEFAULT_RETAILERS: tuple[dict[str, str], ...] = (
    {"name": "HMV", "base_url": "https://store.hmv.com", "deals_url": "https://store.hmv.com/sale"},
    {
        "name": "Zavvi",
        "base_url": "https://www.zavvi.com",
        # Batch 22b: `/sale.list` 404s. The same address as the built-in's sale page.
        "deals_url": "https://www.zavvi.com/c/offers/2-for-30-4k/",
    },
    {"name": "Amazon UK", "base_url": "https://www.amazon.co.uk"},
    {"name": "Blu-ray.com", "base_url": "https://www.blu-ray.com"},
    {"name": "Arrow Video", "base_url": "https://www.arrowfilms.com"},
    {"name": "Criterion", "base_url": "https://www.criterion.com"},
    {"name": "101 Films", "base_url": "https://101-films-store.com"},
    {"name": "Second Sight", "base_url": "https://secondsightfilms.co.uk"},
    {"name": "Powerhouse Films", "base_url": "https://www.powerhousefilms.co.uk"},
)


class WantedItem(Base, UUIDPrimaryKeyMixin):
    """A film someone is looking to buy — §3.5."""

    __tablename__ = "wanted_list"

    #: ``RESTRICT``, matching ``collection_items.movie_id``: wanting a film is a decision
    #: a person made, not a fact about the film row, and must not be swept away by tidying.
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="RESTRICT"), nullable=False
    )

    preferred_format: Mapped[str | None] = mapped_column(String(50), nullable=True)

    #: Which *edition* within that format — "Arte Originale Slipcover", "Steelbook". Free
    #: text because boutique edition names are invented per release (`DECISIONS.md` #104).
    #: It never narrows the search, only which listing on the page gets priced.
    preferred_edition: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: ``Numeric``, never a float. The threshold Batch 20's alerts compare against, and a
    #: price that has round-tripped through a float compares wrongly at exactly the
    #: boundary the person cared about.
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")

    #: §3.5's "whether still looking". **Not** the same as ``deleted_at``: "I stopped
    #: looking for this" is a decision worth keeping, and "I removed it by mistake" is an
    #: accident worth undoing. Only the second belongs in a bin.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<WantedItem {self.movie_id} {self.preferred_format}>"


class Retailer(Base, UUIDPrimaryKeyMixin):
    """A shop to watch — §3.16."""

    __tablename__ = "retailers"

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    #: Fetched by a background job, so the scheme is constrained to http/https in the
    #: database as well as at the API. A `file:` URL here would be a request the scraper
    #: makes on the server's behalf.
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    deals_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_url_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    scraper_type: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="generic_css"
    )

    #: The CSS selectors Batch 19's generic scraper reads. A CHECK keeps it an object,
    #: so a wrong shape fails when an admin saves it rather than inside an unattended job.
    scraper_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    scrape_frequency: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="weekly"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")
    region: Mapped[str] = mapped_column(String(2), nullable=False, server_default="GB")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    last_scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    last_scrape_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_scrape_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Batch 19's "auto-disable after 3 fails" counts here. Created now so that batch adds
    #: behaviour rather than a migration.
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    #: Batch X11 (MK47-05): how many scheduled checks in a row this shop refused at least
    #: half of its requests, twice each. At seven the scheduled check asks it weekly rather
    #: than nightly (:func:`src.services.scraping.runner.is_resting`); any night it refuses
    #: less sets it back to zero. Migration 060.
    refused_nights: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Retailer {self.name!r} enabled={self.enabled}>"
