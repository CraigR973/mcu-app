"""create completion_sets and retailers tables

completion_sets — cached reference lists (director filmographies, franchise members,
award winners) used for fast "10 of 20 owned" completion queries. Refreshed weekly.

retailers — configurable list of online retailers for deal scraping and price checks.
Seeded with HMV, Zavvi, Amazon UK, Blu-ray.com, Arrow Video, Criterion. Admin can
add/edit/disable via the Settings UI.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_SET_TYPE = ("director", "actor", "franchise", "box_set", "award", "curated_list")
_SCRAPER_TYPE = ("built_in", "generic_css", "custom")
_SCRAPE_FREQ = ("daily", "weekly", "manual")
_SCRAPE_STATUS = ("success", "error", "blocked")


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # completion_sets — read-heavy; no soft delete; refreshed by background job
    # -------------------------------------------------------------------------
    op.create_table(
        "completion_sets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("set_type", sa.String(50), nullable=False),
        # Stable identifier: tmdb_person_id, franchise slug, award name, etc.
        sa.Column("set_key", sa.String(255), nullable=False),
        sa.Column("set_name", sa.String(255), nullable=False),
        # Array of TMDB movie IDs; intersected with movies table at query time
        sa.Column("member_tmdb_ids", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("metadata", JSONB(), server_default=sa.text("'{}'")),
        sa.Column("last_refreshed", sa.TIMESTAMP(timezone=True)),
    )

    op.create_check_constraint(
        "ck_completion_sets_set_type",
        "completion_sets",
        f"set_type IN {_SET_TYPE}",
    )

    # Unique (type, key) so background job can upsert safely
    op.create_unique_constraint(
        "uq_completion_sets_type_key",
        "completion_sets",
        ["set_type", "set_key"],
    )

    op.create_index("idx_completion_sets_set_type", "completion_sets", ["set_type"])
    op.create_index("idx_completion_sets_set_key", "completion_sets", ["set_key"])

    # -------------------------------------------------------------------------
    # retailers — configurable scraper registry; seeded via seed script
    # -------------------------------------------------------------------------
    op.create_table(
        "retailers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.Text()),
        sa.Column("deals_url", sa.Text()),
        # {query} placeholder expanded at runtime
        sa.Column("search_url_template", sa.Text()),
        sa.Column(
            "scraper_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'generic_css'"),
        ),
        # CSS selector config consumed by generic_css scraper
        sa.Column("scraper_config", JSONB(), server_default=sa.text("'{}'")),
        sa.Column(
            "scrape_frequency",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'daily'"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default=sa.text("'GBP'"),
        ),
        sa.Column(
            "region",
            sa.String(2),
            nullable=False,
            server_default=sa.text("'GB'"),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "added_by",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_scraped_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_scrape_status", sa.String(50)),
        sa.Column("last_scrape_error", sa.Text()),
    )

    op.create_check_constraint(
        "ck_retailers_scraper_type",
        "retailers",
        f"scraper_type IN {_SCRAPER_TYPE}",
    )
    op.create_check_constraint(
        "ck_retailers_scrape_frequency",
        "retailers",
        f"scrape_frequency IN {_SCRAPE_FREQ}",
    )
    op.create_check_constraint(
        "ck_retailers_last_scrape_status",
        "retailers",
        f"last_scrape_status IS NULL OR last_scrape_status IN {_SCRAPE_STATUS}",
    )

    op.create_unique_constraint("uq_retailers_name", "retailers", ["name"])
    op.create_index("idx_retailers_enabled", "retailers", ["enabled"])


def downgrade() -> None:
    op.drop_index("idx_retailers_enabled", table_name="retailers")
    op.drop_constraint("uq_retailers_name", "retailers", type_="unique")
    op.drop_constraint("ck_retailers_last_scrape_status", "retailers", type_="check")
    op.drop_constraint("ck_retailers_scrape_frequency", "retailers", type_="check")
    op.drop_constraint("ck_retailers_scraper_type", "retailers", type_="check")
    op.drop_table("retailers")

    op.drop_index("idx_completion_sets_set_key", table_name="completion_sets")
    op.drop_index("idx_completion_sets_set_type", table_name="completion_sets")
    op.drop_constraint("uq_completion_sets_type_key", "completion_sets", type_="unique")
    op.drop_constraint("ck_completion_sets_set_type", "completion_sets", type_="check")
    op.drop_table("completion_sets")
