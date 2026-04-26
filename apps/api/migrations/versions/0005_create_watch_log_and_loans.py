"""create watch_log and loans tables

watch_log — personal viewing history with ratings; soft-deletes supported.
loans — tracks discs lent to friends/family with optional due-date reminders.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # watch_log — one row per viewing event; soft-deletable
    # -------------------------------------------------------------------------
    op.create_table(
        "watch_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("watched_at", sa.Date(), nullable=False),
        sa.Column(
            "is_rewatch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        # 0.5–5.0 in 0.5 steps; NULL = unrated
        sa.Column("personal_rating", sa.Numeric(2, 1)),
        sa.Column("review", sa.Text()),
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
        "ck_watch_log_personal_rating",
        "watch_log",
        "personal_rating IS NULL OR (personal_rating >= 0.5 AND personal_rating <= 5.0"
        " AND personal_rating * 2 = FLOOR(personal_rating * 2))",
    )

    op.create_index("idx_watch_log_movie_id", "watch_log", ["movie_id"])
    op.create_index("idx_watch_log_user_id", "watch_log", ["user_id"])
    op.create_index("idx_watch_log_watched_at", "watch_log", ["watched_at"])
    op.create_index("idx_watch_log_deleted_at", "watch_log", ["deleted_at"])
    # "On this day" feature queries by month/day
    op.create_index(
        "idx_watch_log_user_watched",
        "watch_log",
        ["user_id", "watched_at"],
    )

    op.execute("""
        CREATE TRIGGER watch_log_set_updated_at
        BEFORE UPDATE ON watch_log
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    op.execute("""
        CREATE TRIGGER watch_log_soft_delete
        BEFORE DELETE ON watch_log
        FOR EACH ROW EXECUTE FUNCTION soft_delete();
    """)

    # -------------------------------------------------------------------------
    # loans — disc lending tracker with overdue-reminder support
    # -------------------------------------------------------------------------
    op.create_table(
        "loans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "collection_item_id",
            sa.BigInteger(),
            sa.ForeignKey("collection_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("borrower_name", sa.String(255), nullable=False),
        sa.Column("lent_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("returned_date", sa.Date()),
        sa.Column(
            "reminder_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("notes", sa.Text()),
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
        "ck_loans_dates",
        "loans",
        "returned_date IS NULL OR returned_date >= lent_date",
    )
    op.create_check_constraint(
        "ck_loans_due_date",
        "loans",
        "due_date IS NULL OR due_date >= lent_date",
    )

    op.create_index("idx_loans_collection_item_id", "loans", ["collection_item_id"])
    # Active loans query (returned_date IS NULL)
    op.create_index("idx_loans_returned_date", "loans", ["returned_date"])
    op.create_index("idx_loans_due_date", "loans", ["due_date"])

    op.execute("""
        CREATE TRIGGER loans_set_updated_at
        BEFORE UPDATE ON loans
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS loans_set_updated_at ON loans;")
    op.drop_index("idx_loans_due_date", table_name="loans")
    op.drop_index("idx_loans_returned_date", table_name="loans")
    op.drop_index("idx_loans_collection_item_id", table_name="loans")
    op.drop_constraint("ck_loans_due_date", "loans", type_="check")
    op.drop_constraint("ck_loans_dates", "loans", type_="check")
    op.drop_table("loans")

    op.execute("DROP TRIGGER IF EXISTS watch_log_soft_delete ON watch_log;")
    op.execute("DROP TRIGGER IF EXISTS watch_log_set_updated_at ON watch_log;")
    op.drop_index("idx_watch_log_user_watched", table_name="watch_log")
    op.drop_index("idx_watch_log_deleted_at", table_name="watch_log")
    op.drop_index("idx_watch_log_watched_at", table_name="watch_log")
    op.drop_index("idx_watch_log_user_id", table_name="watch_log")
    op.drop_index("idx_watch_log_movie_id", table_name="watch_log")
    op.drop_constraint("ck_watch_log_personal_rating", "watch_log", type_="check")
    op.drop_table("watch_log")
