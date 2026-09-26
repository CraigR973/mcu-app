"""ebay watch — price targets, the scheduled passes, usual prices, and eBay deals that expire

Revision ID: 040
Revises: 039
Create Date: 2026-09-26

Batch T8a (`DECISIONS.md` #203, #216). Three tables and two changes to ``deals``:

- ``ebay_targets``: a price someone wants to hear about, on one listing or on a film and
  format. One live target per person per listing, and per person per film and format.
- ``ebay_watch_runs``: one scheduled pass, with its share of the day's eBay calls. One runs
  at a time.
- ``ebay_price_refs``: what a film on a format usually asks, kept for a fortnight.
- ``deals.expires_at_utc``: an eBay find leaves the feed when it expires, because nothing
  scrapes it again the way a retailer's sale page is.
- ``uq_deals_ebay_url``: an eBay deal has no retailer row, so the existing
  ``(retailer_id, url)`` constraint never fires for it (NULLs are distinct). This one does,
  for rows named eBay only, so a retailer's deal orphaned by a deleted retailer is untouched.

The downgrade drops the targets people set. The scheduled passes and usual prices are
rebuilt by the next run; the targets are not, and the audit keeps nothing of them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "040"
down_revision: str | None = "039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ebay_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("format_code", sa.String(20), nullable=True),
        sa.Column("legacy_item_id", sa.Text(), nullable=True),
        sa.Column("target_price", sa.Numeric(8, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("is_auction", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("current_price", sa.Numeric(8, 2), nullable=True),
        sa.Column("current_postage", sa.Numeric(8, 2), nullable=True),
        sa.Column("current_item_id", sa.Text(), nullable=True),
        sa.Column("current_url", sa.Text(), nullable=True),
        sa.Column("ends_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="watching"),
        sa.Column("last_checked_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("met_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.CheckConstraint("kind IN ('listing', 'search')", name="ck_ebay_targets_kind"),
        sa.CheckConstraint("status IN ('watching', 'met', 'ended')", name="ck_ebay_targets_status"),
        sa.CheckConstraint("target_price > 0", name="ck_ebay_targets_price"),
        sa.CheckConstraint(
            "format_code IS NULL OR format_code IN ('4k_uhd', 'blu_ray', 'dvd')",
            name="ck_ebay_targets_format",
        ),
        sa.CheckConstraint(
            "(kind = 'listing') = (legacy_item_id IS NOT NULL)", name="ck_ebay_targets_listing"
        ),
        sa.CheckConstraint(
            "kind = 'listing' OR (movie_id IS NOT NULL AND format_code IS NOT NULL)",
            name="ck_ebay_targets_search",
        ),
    )
    op.create_index(
        "uq_ebay_targets_listing",
        "ebay_targets",
        ["owner_id", "legacy_item_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND kind = 'listing'"),
    )
    op.create_index(
        "uq_ebay_targets_search",
        "ebay_targets",
        ["owner_id", "movie_id", "format_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND kind = 'search'"),
    )
    op.create_index("ix_ebay_targets_checked", "ebay_targets", ["status", "last_checked_utc"])

    op.create_table(
        "ebay_watch_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
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
        sa.Column("targets_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_alerts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("listings_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refs_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deals_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deals_pushed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("newest_listing_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("trigger IN ('job', 'admin')", name="ck_ebay_watch_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running', 'finished', 'budget_spent', 'stopped', 'abandoned')",
            name="ck_ebay_watch_runs_status",
        ),
        sa.CheckConstraint("budget >= 0 AND calls >= 0", name="ck_ebay_watch_runs_counts"),
    )
    op.create_index("ix_ebay_watch_runs_started_utc", "ebay_watch_runs", ["started_utc"])
    op.create_index(
        "uq_ebay_watch_runs_one_running",
        "ebay_watch_runs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "ebay_price_refs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format_code", sa.String(20), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("median", sa.Numeric(8, 2), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "by_condition",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("checked_utc", sa.DateTime(timezone=False), nullable=False),
        sa.UniqueConstraint("movie_id", "format_code", name="uq_ebay_price_refs_movie_format"),
        sa.CheckConstraint(
            "format_code IN ('4k_uhd', 'blu_ray', 'dvd')", name="ck_ebay_price_refs_format"
        ),
        sa.CheckConstraint("status IN ('priced', 'not_priced')", name="ck_ebay_price_refs_status"),
        sa.CheckConstraint(
            "(status = 'priced') = (median IS NOT NULL)", name="ck_ebay_price_refs_priced"
        ),
    )

    op.add_column("deals", sa.Column("expires_at_utc", sa.DateTime(timezone=False), nullable=True))
    op.create_index(
        "uq_deals_ebay_url",
        "deals",
        ["url"],
        unique=True,
        postgresql_where=sa.text("retailer_id IS NULL AND retailer_name_snapshot = 'eBay'"),
    )


def downgrade() -> None:
    op.drop_index("uq_deals_ebay_url", table_name="deals")
    op.drop_column("deals", "expires_at_utc")
    op.drop_table("ebay_price_refs")
    op.drop_index("uq_ebay_watch_runs_one_running", table_name="ebay_watch_runs")
    op.drop_index("ix_ebay_watch_runs_started_utc", table_name="ebay_watch_runs")
    op.drop_table("ebay_watch_runs")
    op.drop_index("ix_ebay_targets_checked", table_name="ebay_targets")
    op.drop_index("uq_ebay_targets_search", table_name="ebay_targets")
    op.drop_index("uq_ebay_targets_listing", table_name="ebay_targets")
    op.drop_table("ebay_targets")
