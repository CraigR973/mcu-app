"""create wanted_list, price_checks, price_history_daily tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wanted_list",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("format", sa.Text()),  # NULL = any format acceptable
        sa.Column("max_price", sa.Numeric(10, 2)),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("notes", sa.Text()),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_wanted_list_priority",
        "wanted_list",
        "priority BETWEEN 1 AND 5",
    )
    op.create_check_constraint(
        "ck_wanted_list_format",
        "wanted_list",
        "format IS NULL OR format IN "
        "('4k_bluray', 'bluray', 'dvd', 'digital', 'laserdisc', 'vhs', 'hddvd')",
    )

    op.create_index("idx_wanted_list_movie_id", "wanted_list", ["movie_id"])
    op.create_index("idx_wanted_list_priority", "wanted_list", ["priority"])
    op.create_index("idx_wanted_list_deleted_at", "wanted_list", ["deleted_at"])

    op.execute("""
        CREATE TRIGGER wanted_list_set_updated_at
        BEFORE UPDATE ON wanted_list
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    op.execute("""
        CREATE TRIGGER wanted_list_soft_delete
        BEFORE DELETE ON wanted_list
        FOR EACH ROW EXECUTE FUNCTION soft_delete();
    """)

    # ---------------------------------------------------------------------------
    # price_checks — individual price observations (append-only, no soft delete)
    # ---------------------------------------------------------------------------
    op.create_table(
        "price_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "wanted_list_id",
            sa.BigInteger(),
            sa.ForeignKey("wanted_list.id", ondelete="SET NULL"),
        ),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),  # 'ebay', 'amazon', 'mercari', …
        sa.Column("condition", sa.Text()),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column(
            "checked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_price_checks_price",
        "price_checks",
        "price >= 0",
    )

    op.create_index("idx_price_checks_movie_id", "price_checks", ["movie_id"])
    op.create_index("idx_price_checks_wanted_list_id", "price_checks", ["wanted_list_id"])
    # Composite used for aggregation queries ("all ebay bluray prices for movie X")
    op.create_index(
        "idx_price_checks_movie_format_source",
        "price_checks",
        ["movie_id", "format", "source"],
    )
    op.create_index("idx_price_checks_checked_at", "price_checks", ["checked_at"])

    # ---------------------------------------------------------------------------
    # price_history_daily — daily aggregates rolled up from price_checks
    # ---------------------------------------------------------------------------
    op.create_table(
        "price_history_daily",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("min_price", sa.Numeric(10, 2)),
        sa.Column("max_price", sa.Numeric(10, 2)),
        sa.Column("avg_price", sa.Numeric(10, 2)),
        sa.Column("median_price", sa.Numeric(10, 2)),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_unique_constraint(
        "uq_price_history_daily_movie_format_source_date",
        "price_history_daily",
        ["movie_id", "format", "source", "date"],
    )

    # Timeline queries: all price history for a movie across all formats/sources
    op.create_index(
        "idx_price_history_daily_movie_date",
        "price_history_daily",
        ["movie_id", "date"],
    )
    op.create_index("idx_price_history_daily_date", "price_history_daily", ["date"])


def downgrade() -> None:
    op.drop_index("idx_price_history_daily_date", table_name="price_history_daily")
    op.drop_index("idx_price_history_daily_movie_date", table_name="price_history_daily")
    op.drop_constraint(
        "uq_price_history_daily_movie_format_source_date",
        "price_history_daily",
        type_="unique",
    )
    op.drop_table("price_history_daily")

    op.drop_index("idx_price_checks_checked_at", table_name="price_checks")
    op.drop_index("idx_price_checks_movie_format_source", table_name="price_checks")
    op.drop_index("idx_price_checks_wanted_list_id", table_name="price_checks")
    op.drop_index("idx_price_checks_movie_id", table_name="price_checks")
    op.drop_constraint("ck_price_checks_price", "price_checks", type_="check")
    op.drop_table("price_checks")

    op.execute("DROP TRIGGER IF EXISTS wanted_list_soft_delete ON wanted_list;")
    op.execute("DROP TRIGGER IF EXISTS wanted_list_set_updated_at ON wanted_list;")
    op.drop_index("idx_wanted_list_deleted_at", table_name="wanted_list")
    op.drop_index("idx_wanted_list_priority", table_name="wanted_list")
    op.drop_index("idx_wanted_list_movie_id", table_name="wanted_list")
    op.drop_constraint("ck_wanted_list_format", "wanted_list", type_="check")
    op.drop_constraint("ck_wanted_list_priority", "wanted_list", type_="check")
    op.drop_table("wanted_list")
