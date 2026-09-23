"""collection valuation — what each disc is being asked for on eBay, and the runs that found out

Revision ID: 036
Revises: 035
Create Date: 2026-09-23

Batch T6, snag 7. Nothing stored a price, so a total needed 1,454 live eBay searches.
Two tables:

- ``disc_valuations``: one row per film and format, because that is what one search
  prices. A row is either ``priced``, with a price, or ``not_priced``, without one. The
  CHECK makes a guessed price unrepresentable rather than merely unwritten.
- ``valuation_runs``: one row per run, with its budget and counts. The partial unique index
  allows one ``running`` row at a time, so a scheduled run and an admin's button cannot
  both spend the day's eBay share.

Both tables hold derived data, so the downgrade drops them and nothing is lost that the
next run cannot rebuild.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036"
down_revision: str | None = "035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "valuation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column(
            "started_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("heartbeat_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("finished_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("not_priced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remaining", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("trigger IN ('job', 'admin')", name="ck_valuation_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running', 'finished', 'budget_spent', 'stopped', 'abandoned')",
            name="ck_valuation_runs_status",
        ),
        sa.CheckConstraint("budget >= 0 AND calls >= 0", name="ck_valuation_runs_counts"),
    )
    op.create_index("ix_valuation_runs_started_utc", "valuation_runs", ["started_utc"])
    op.create_index(
        "uq_valuation_runs_one_running",
        "valuation_runs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "disc_valuations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format_code", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("price", sa.Numeric(8, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("condition_label", sa.String(50), nullable=True),
        sa.Column("matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("considered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("basis", sa.String(50), nullable=False),
        sa.Column("search_query", sa.Text(), nullable=False),
        sa.Column("checked_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("valuation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("movie_id", "format_code", name="uq_disc_valuations_movie_format"),
        sa.CheckConstraint(
            "format_code IN ('4k_uhd', 'blu_ray', 'dvd')", name="ck_disc_valuations_format"
        ),
        sa.CheckConstraint("status IN ('priced', 'not_priced')", name="ck_disc_valuations_status"),
        sa.CheckConstraint(
            "(status = 'priced') = (price IS NOT NULL)",
            name="ck_disc_valuations_price_only_when_priced",
        ),
    )
    op.create_index("ix_disc_valuations_checked_utc", "disc_valuations", ["checked_utc"])


def downgrade() -> None:
    op.drop_index("ix_disc_valuations_checked_utc", table_name="disc_valuations")
    op.drop_table("disc_valuations")
    op.drop_index("uq_valuation_runs_one_running", table_name="valuation_runs")
    op.drop_index("ix_valuation_runs_started_utc", table_name="valuation_runs")
    op.drop_table("valuation_runs")
