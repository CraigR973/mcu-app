"""create wanted_list and retailers

Revision ID: 016
Revises: 015
Create Date: 2026-09-09

Roadmap §3.5 and §3.16 — Batch 18's phases 5.1 and 5.2.

**Four earlier batches deferred work to this table**, which is a fair summary of how
central it is:

- Batch 13 dropped §11.2's "bulk add missing to wanted list" button.
- Batch 15 made the trash **refuse** the name `wanted_list` rather than answer an empty
  page for a table that did not exist.
- Batch 16 shipped a two-state ownership enum where §7.2 asked for three, because
  "wanted" had nothing behind it.
- Batch 17 created `release_calendar.is_wishlist_match` and wrote nothing to it.

This migration creates the table each of those was waiting for. Wiring them up is this
batch's job for the first three; the calendar flag is left to whichever batch next has
reason to touch ingestion.

Two shapes differ from §3.5 and §3.16 as drawn:

**`wanted_list.deleted_at`.** §3.5 has `is_active` and no soft delete, but §6.30 lists
"wanted entries" among the things that go to Trash, and Batch 15's trash was built to
widen to exactly this table. `is_active` and `deleted_at` are **not** the same thing:
"I stopped looking for this" is a decision, "I removed it by mistake" is an accident, and
only the second should be undoable from a bin.

**`retailers.scraper_config` gets a CHECK that it is an object.** It holds CSS selectors
that Batch 19's generic scraper will read; an array or a scalar there would fail at scrape
time, in a job nobody is watching, rather than at the moment an admin saved it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORMATS = ("4k_uhd", "blu_ray", "dvd", "download")
SCRAPER_TYPES = ("built_in", "generic_css", "custom")
FREQUENCIES = ("daily", "weekly", "manual")
SCRAPE_STATUSES = ("success", "error", "blocked")


def _in_list(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(chr(39) + v + chr(39) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "wanted_list",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preferred_format", sa.String(50), nullable=True),
        sa.Column("max_price", sa.Numeric(8, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        # RESTRICT, matching `collection_items.movie_id`: a wanted entry is a decision a
        # person made, not a fact about a film row, and must not be swept away by tidying.
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="RESTRICT"),
        # SET NULL: the entry outlives whoever added it, exactly as a disc does.
        sa.ForeignKeyConstraint(["added_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "preferred_format IS NULL OR " + _in_list("preferred_format", FORMATS),
            name="ck_wanted_list_format",
        ),
        sa.CheckConstraint(
            "max_price IS NULL OR max_price > 0", name="ck_wanted_list_max_price_positive"
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_wanted_list_currency"),
    )
    op.create_index("ix_wanted_list_movie_id", "wanted_list", ["movie_id"])
    op.create_index("ix_wanted_list_deleted_at", "wanted_list", ["deleted_at"])
    # One live entry per film. Wanting the same film twice is a mistake, not a plan — and
    # the price alerts of Batch 20 would fire twice for it.
    op.create_index(
        "uq_wanted_list_live_movie",
        "wanted_list",
        ["movie_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "retailers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("deals_url", sa.Text(), nullable=True),
        sa.Column("search_url_template", sa.Text(), nullable=True),
        sa.Column("scraper_type", sa.String(50), nullable=False, server_default="generic_css"),
        sa.Column(
            "scraper_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("scrape_frequency", sa.String(20), nullable=False, server_default="weekly"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("region", sa.String(2), nullable=False, server_default="GB"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_scraped_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_scrape_status", sa.String(50), nullable=True),
        sa.Column("last_scrape_error", sa.Text(), nullable=True),
        # Batch 19's "auto-disable after 3 fails" needs somewhere to count. Created here
        # so that batch adds behaviour rather than a migration.
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["added_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            _in_list("scraper_type", SCRAPER_TYPES), name="ck_retailers_scraper_type"
        ),
        sa.CheckConstraint(
            _in_list("scrape_frequency", FREQUENCIES), name="ck_retailers_frequency"
        ),
        sa.CheckConstraint(
            "last_scrape_status IS NULL OR " + _in_list("last_scrape_status", SCRAPE_STATUSES),
            name="ck_retailers_scrape_status",
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_retailers_currency"),
        sa.CheckConstraint("region ~ '^[A-Z]{2}$'", name="ck_retailers_region"),
        # The selectors Batch 19's generic scraper reads. An array or a scalar here would
        # fail at scrape time — in an unattended job — rather than when it was saved.
        sa.CheckConstraint(
            "jsonb_typeof(scraper_config) = 'object'", name="ck_retailers_config_object"
        ),
        # http/https only. `base_url` is fetched by a background job, so a `file:` or
        # `gopher:` value would be a request the scraper makes on someone's behalf.
        sa.CheckConstraint("base_url ~* '^https?://'", name="ck_retailers_base_url_scheme"),
        sa.CheckConstraint(
            "deals_url IS NULL OR deals_url ~* '^https?://'",
            name="ck_retailers_deals_url_scheme",
        ),
        sa.CheckConstraint(
            "search_url_template IS NULL OR search_url_template ~* '^https?://'",
            name="ck_retailers_search_url_scheme",
        ),
    )
    op.create_index("ix_retailers_deleted_at", "retailers", ["deleted_at"])
    op.create_index(
        "uq_retailers_live_name",
        "retailers",
        [sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    for table in ("wanted_list", "retailers"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )
        # Both are soft-deleting, so both join §13.5's trash — which means both need the
        # trigger that turns a DELETE into a tombstone, and which `013` made skippable
        # for the permanent-delete path.
        op.execute(
            f"""
            CREATE TRIGGER {table}_soft_delete
            BEFORE DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION soft_delete();
            """
        )


def downgrade() -> None:
    for table in ("wanted_list", "retailers"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_soft_delete ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_set_updated_at ON {table};")
    op.drop_index("uq_retailers_live_name", table_name="retailers")
    op.drop_index("ix_retailers_deleted_at", table_name="retailers")
    op.drop_table("retailers")
    op.drop_index("uq_wanted_list_live_movie", table_name="wanted_list")
    op.drop_index("ix_wanted_list_deleted_at", table_name="wanted_list")
    op.drop_index("ix_wanted_list_movie_id", table_name="wanted_list")
    op.drop_table("wanted_list")
