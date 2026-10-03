"""film reviews — Blu-ray.com's and AVForums' reviews of a film, and the runs that find them

Revision ID: 046
Revises: 045
Create Date: 2026-10-03

Batch V9, snag 8 (`DECISIONS.md` #228, #241). Two tables:

- ``film_reviews``: one per film, site and format: the review's page address, Brave's title
  and one-line description of it, and, for Blu-ray.com, the review's scores under the
  site's own headings with when they were read. ``status`` says how far it got: ``none``
  (searched, nothing kept), ``found`` (a page to read; AVForums' rows stay here, links
  only), ``scored``, ``no_review`` (the page and the editions it links have no review of
  this format), ``mismatch`` (the page is another year's film) or ``failed``. Every row
  names its source, so everything derived from a site can be found and removed (#110).
- ``review_runs``: one per batch of searches and page reads, with the Brave searches it
  sent, so they count towards the month's total (#202). One nightly batch runs at a time.

Both are granted to the read-only role, guarded so CI's database (which has none) still
migrates (`AGENTS.md`, "Cloud sessions"). Neither holds a credential.

The downgrade drops both: the next batch would search and read again.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "046"
down_revision: str | None = "045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: #110's release-page predicate, as `bluray_com.canonical_release_url` writes it.
BLURAY_COM_PAGE = r"^https://www\.blu-ray\.com/movies/[^/]+/[0-9]+/$"
#: An AVForums review page: `/reviews/<slug>.<id>/`.
AVFORUMS_PAGE = r"^https://www\.avforums\.com/reviews/[^/]+\.[0-9]+/$"


def upgrade() -> None:
    op.create_table(
        "review_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("started_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("heartbeat_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("finished_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("searches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_review", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("trigger IN ('job', 'want_added')", name="ck_review_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running', 'finished', 'stopped', 'halted', 'abandoned')",
            name="ck_review_runs_status",
        ),
        sa.CheckConstraint(
            "searches >= 0 AND found >= 0 AND fetched >= 0 AND scored >= 0 AND no_review >= 0",
            name="ck_review_runs_counts",
        ),
    )
    op.create_index("ix_review_runs_started_utc", "review_runs", ["started_utc"])
    op.create_index(
        "uq_review_runs_one_nightly",
        "review_runs",
        ["trigger"],
        unique=True,
        postgresql_where=sa.text("status = 'running' AND trigger = 'job'"),
    )

    op.create_table(
        "film_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site", sa.Text(), nullable=False),
        sa.Column("format_code", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("found_via", sa.Text(), nullable=False),
        sa.Column("found_url", sa.Text(), nullable=True),
        sa.Column("search_query", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("overall", sa.Numeric(3, 1), nullable=True),
        sa.Column("out_of", sa.SmallInteger(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("found_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("checked_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("scores_read_utc", sa.DateTime(timezone=False), nullable=True),
        sa.CheckConstraint("site IN ('bluray_com', 'avforums')", name="ck_film_reviews_site"),
        sa.CheckConstraint(
            "format_code IS NULL OR format_code IN ('4k_uhd', 'blu_ray', 'dvd')",
            name="ck_film_reviews_format",
        ),
        sa.CheckConstraint(
            "status IN ('none', 'found', 'scored', 'no_review', 'mismatch', 'failed')",
            name="ck_film_reviews_status",
        ),
        sa.CheckConstraint("found_via IN ('brave', 'spec_page')", name="ck_film_reviews_found_via"),
        sa.CheckConstraint(
            "(status = 'none') = (url IS NULL)", name="ck_film_reviews_url_unless_none"
        ),
        sa.CheckConstraint(
            f"url IS NULL OR (site = 'bluray_com' AND url ~ '{BLURAY_COM_PAGE}') "
            f"OR (site = 'avforums' AND url ~ '{AVFORUMS_PAGE}')",
            name="ck_film_reviews_url_shape",
        ),
        sa.CheckConstraint(
            "(status = 'scored') = (scores IS NOT NULL AND overall IS NOT NULL "
            "AND out_of IS NOT NULL AND scores_read_utc IS NOT NULL)",
            name="ck_film_reviews_scored",
        ),
        sa.CheckConstraint(
            "site = 'bluray_com' OR scores IS NULL", name="ck_film_reviews_avforums_unscored"
        ),
        sa.CheckConstraint(
            "overall IS NULL OR (overall > 0 AND overall <= out_of)",
            name="ck_film_reviews_overall",
        ),
        sa.CheckConstraint("out_of IS NULL OR out_of IN (5, 10)", name="ck_film_reviews_out_of"),
        sa.CheckConstraint("attempts >= 0", name="ck_film_reviews_attempts"),
    )
    op.create_index(
        "uq_film_reviews_film_site_format",
        "film_reviews",
        ["movie_id", "site", sa.text("coalesce(format_code, '')")],
        unique=True,
    )
    op.create_index("ix_film_reviews_site_status", "film_reviews", ["site", "status"])

    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT ON film_reviews, review_runs TO mcu_readonly; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_index("ix_film_reviews_site_status", table_name="film_reviews")
    op.drop_index("uq_film_reviews_film_site_format", table_name="film_reviews")
    op.drop_table("film_reviews")
    op.drop_index("uq_review_runs_one_nightly", table_name="review_runs")
    op.drop_index("ix_review_runs_started_utc", table_name="review_runs")
    op.drop_table("review_runs")
