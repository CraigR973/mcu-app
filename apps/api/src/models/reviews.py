"""Reviews of a film on Blu-ray.com and AVForums — Batch V9, `DECISIONS.md` #228, #241.

**Found with Brave, read only where reading is allowed.** Brave proposes each review's page;
finding one sends neither site a request. Blu-ray.com's scores are then read once from an
exact page address, within #110's bounds as #228 widened them. AVForums forbids automated
access (#241), so its rows stay links: an address and Brave's line, never a score.

**Every row names its source** (``url``, and ``found_url`` where it was found), so all that
was derived from a site can be found and removed, as #110 requires.
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
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

REVIEW_SITES = ("bluray_com", "avforums")
REVIEW_FORMATS = ("4k_uhd", "blu_ray", "dvd")
#: ``none``: searched, nothing kept. ``found``: a page to read (AVForums' stay here).
#: ``scored``: its scores are read. ``no_review``: the page, and the editions it links, have
#: no review of this format. ``mismatch``: the page is another year's film. ``failed``: it
#: would not load after :data:`~src.services.reviews.batch.MAX_ATTEMPTS` tries.
REVIEW_STATUSES = ("none", "found", "scored", "no_review", "mismatch", "failed")
REVIEW_FOUND_VIA = ("brave", "spec_page")
REVIEW_RUN_TRIGGERS = ("job", "want_added")
REVIEW_RUN_STATUSES = ("running", "finished", "stopped", "halted", "abandoned")


class FilmReview(Base, UUIDPrimaryKeyMixin):
    """One site's review of one film on one format, or the record that none was found."""

    __tablename__ = "film_reviews"
    __table_args__ = (
        CheckConstraint("site IN ('bluray_com', 'avforums')", name="ck_film_reviews_site"),
        CheckConstraint(
            "format_code IS NULL OR format_code IN ('4k_uhd', 'blu_ray', 'dvd')",
            name="ck_film_reviews_format",
        ),
        CheckConstraint(
            "status IN ('none', 'found', 'scored', 'no_review', 'mismatch', 'failed')",
            name="ck_film_reviews_status",
        ),
        CheckConstraint("found_via IN ('brave', 'spec_page')", name="ck_film_reviews_found_via"),
        Index(
            "uq_film_reviews_film_site_format",
            "movie_id",
            "site",
            text("coalesce(format_code, '')"),
            unique=True,
        ),
        Index("ix_film_reviews_site_status", "site", "status"),
    )

    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    site: Mapped[str] = mapped_column(Text, nullable=False)
    #: The disc format the review is of; ``None`` for a review of the film itself
    #: (AVForums' "Movie Review"), or for a search that asked for any format.
    format_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    #: The review's page: shown as the link, and the source of any score.
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    found_via: Mapped[str] = mapped_column(Text, nullable=False)
    #: Where it was found, when that is not ``url``: the page Brave proposed, or the disc's
    #: spec page, whose link to the reviewed edition was followed (#241).
    found_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Brave's title and one-line description of the page.
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: ``[{"heading": "Movie", "score": 3.5}, ...]``, the site's headings in its order.
    scores: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    overall: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    out_of: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    found_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    checked_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    scores_read_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<FilmReview {self.site} {self.format_code} {self.status}>"


class ReviewRun(Base, UUIDPrimaryKeyMixin):
    """One batch of review searches and page reads, and the Brave searches it sent."""

    __tablename__ = "review_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('job', 'want_added')", name="ck_review_runs_trigger"),
        CheckConstraint(
            "status IN ('running', 'finished', 'stopped', 'halted', 'abandoned')",
            name="ck_review_runs_status",
        ),
        Index("ix_review_runs_started_utc", "started_utc"),
        Index(
            "uq_review_runs_one_nightly",
            "trigger",
            unique=True,
            postgresql_where=text("status = 'running' AND trigger = 'job'"),
        ),
    )

    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    heartbeat_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    finished_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    #: Brave requests sent, retries included: each is billed, and each counts towards the
    #: month's total (#202).
    searches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ReviewRun {self.trigger} {self.status} searches={self.searches}>"
