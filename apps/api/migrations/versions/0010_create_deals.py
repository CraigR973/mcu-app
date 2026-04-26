"""create deals table

Scraped 4K/Blu-ray deals refreshed daily by the background scraper. Each row
represents one deal at one retailer. movie_id is nullable — scraped titles are
matched to the movies table asynchronously.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_FORMAT = ("4k_uhd", "blu_ray", "dvd", "digital", "steelbook", "box_set", "other")


def upgrade() -> None:
    op.create_table(
        "deals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # Nullable — matched asynchronously after scraping
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="SET NULL"),
        ),
        sa.Column("title_raw", sa.String(500), nullable=False),
        sa.Column("format", sa.String(50)),
        sa.Column(
            "retailer_id",
            sa.BigInteger(),
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalised for display without a join
        sa.Column("retailer_name", sa.String(100), nullable=False),
        sa.Column("current_price", sa.Numeric(8, 2)),
        sa.Column("original_price", sa.Numeric(8, 2)),
        # Calculated by scraper: ROUND((original - current) / original * 100)
        sa.Column("discount_percent", sa.Integer()),
        sa.Column("url", sa.Text()),
        sa.Column(
            "already_owned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "dismissed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "found_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_check_constraint(
        "ck_deals_format",
        "deals",
        f"format IS NULL OR format IN {_FORMAT}",
    )
    op.create_check_constraint(
        "ck_deals_prices",
        "deals",
        "current_price IS NULL OR current_price >= 0",
    )
    op.create_check_constraint(
        "ck_deals_discount",
        "deals",
        "discount_percent IS NULL OR (discount_percent >= 0 AND discount_percent <= 100)",
    )

    op.create_index("idx_deals_movie_id", "deals", ["movie_id"])
    op.create_index("idx_deals_retailer_id", "deals", ["retailer_id"])
    op.create_index("idx_deals_found_at", "deals", ["found_at"])
    # Feed queries filter dismissed + already_owned
    op.create_index(
        "idx_deals_active",
        "deals",
        ["dismissed", "already_owned", "found_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_deals_active", table_name="deals")
    op.drop_index("idx_deals_found_at", table_name="deals")
    op.drop_index("idx_deals_retailer_id", table_name="deals")
    op.drop_index("idx_deals_movie_id", table_name="deals")
    op.drop_constraint("ck_deals_discount", "deals", type_="check")
    op.drop_constraint("ck_deals_prices", "deals", type_="check")
    op.drop_constraint("ck_deals_format", "deals", type_="check")
    op.drop_table("deals")
