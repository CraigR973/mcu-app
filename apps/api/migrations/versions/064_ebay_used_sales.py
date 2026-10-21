"""Store observed used eBay listings and bounded weekly passes (AA10a).

Revision ID: 064
Revises: 063
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "064"
down_revision: str | None = "063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ebay_used_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legacy_item_id", sa.Text(), nullable=False),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format_code", sa.String(20), nullable=False),
        sa.Column("price", sa.Numeric(8, 2), nullable=False),
        sa.Column("postage", sa.Numeric(8, 2), nullable=False),
        sa.Column("condition_code", sa.String(10), nullable=False),
        sa.Column("first_seen_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("last_seen_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("ended_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("sold_count", sa.Integer(), nullable=True),
        sa.Column("missing_checked_utc", sa.DateTime(timezone=False), nullable=True),
        sa.UniqueConstraint("legacy_item_id", name="uq_ebay_used_listings_item"),
        sa.CheckConstraint(
            "status IN ('active', 'sold', 'ended')", name="ck_ebay_used_listings_status"
        ),
        sa.CheckConstraint(
            "sold_count IS NULL OR sold_count >= 0", name="ck_ebay_used_listings_sold_count"
        ),
    )
    op.create_index(
        "ix_ebay_used_listings_movie_format", "ebay_used_listings", ["movie_id", "format_code"]
    )
    op.create_index(
        "ix_ebay_used_listings_retention", "ebay_used_listings", ["status", "ended_at_utc"]
    )

    op.create_table(
        "ebay_used_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format_code", sa.String(20), nullable=False),
        sa.Column("checked_utc", sa.DateTime(timezone=False), nullable=False),
        sa.UniqueConstraint("movie_id", "format_code", name="uq_ebay_used_scans_movie_format"),
    )
    op.create_index("ix_ebay_used_scans_checked", "ebay_used_scans", ["checked_utc"])

    op.create_table(
        "ebay_used_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trigger", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("heartbeat_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("finished_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("searched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ended", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("trigger IN ('admin', 'job')", name="ck_ebay_used_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running', 'finished', 'budget_spent', 'stopped', 'abandoned')",
            name="ck_ebay_used_runs_status",
        ),
        sa.CheckConstraint("budget >= 0 AND calls >= 0", name="ck_ebay_used_runs_budget"),
    )
    op.create_index("ix_ebay_used_runs_started", "ebay_used_runs", ["started_utc"])
    op.create_index(
        "uq_ebay_used_runs_running",
        "ebay_used_runs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.add_column("disc_valuations", sa.Column("sales_price", sa.Numeric(8, 2), nullable=True))
    op.add_column(
        "disc_valuations",
        sa.Column("sales_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("disc_valuations", sa.Column("sales_low", sa.Numeric(8, 2), nullable=True))
    op.add_column("disc_valuations", sa.Column("sales_high", sa.Numeric(8, 2), nullable=True))
    op.add_column(
        "disc_valuations",
        sa.Column("sales_checked_utc", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_check_constraint(
        "ck_disc_valuations_sales_count", "disc_valuations", "sales_count >= 0"
    )

    # Neither table holds credentials. CI's Postgres has neither role.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT ON ebay_used_listings, ebay_used_scans, ebay_used_runs TO mcu_readonly; "
        "GRANT SELECT (sales_price, sales_count, sales_low, sales_high, "
        "sales_checked_utc) ON disc_valuations TO mcu_readonly; "
        "END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        "GRANT SELECT ON ebay_used_listings, ebay_used_scans, ebay_used_runs TO mcu_backup; "
        "GRANT SELECT (sales_price, sales_count, sales_low, sales_high, "
        "sales_checked_utc) ON disc_valuations TO mcu_backup; "
        "END IF; END $$"
    )


def downgrade() -> None:
    op.drop_constraint("ck_disc_valuations_sales_count", "disc_valuations")
    for column in ("sales_checked_utc", "sales_high", "sales_low", "sales_count", "sales_price"):
        op.drop_column("disc_valuations", column)
    op.drop_index("uq_ebay_used_runs_running", table_name="ebay_used_runs")
    op.drop_index("ix_ebay_used_runs_started", table_name="ebay_used_runs")
    op.drop_table("ebay_used_runs")
    op.drop_index("ix_ebay_used_scans_checked", table_name="ebay_used_scans")
    op.drop_table("ebay_used_scans")
    op.drop_index("ix_ebay_used_listings_retention", table_name="ebay_used_listings")
    op.drop_index("ix_ebay_used_listings_movie_format", table_name="ebay_used_listings")
    op.drop_table("ebay_used_listings")
