"""create movie_credits table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movie_credits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("person_name", sa.Text(), nullable=False),
        sa.Column("credit_type", sa.Text(), nullable=False),  # 'cast' | 'crew'
        sa.Column("character", sa.Text()),
        sa.Column("department", sa.Text()),
        sa.Column("job", sa.Text()),
        sa.Column("credit_order", sa.Integer()),
        sa.Column("profile_path", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_movie_credits_credit_type",
        "movie_credits",
        "credit_type IN ('cast', 'crew')",
    )

    op.create_index("idx_movie_credits_movie_id", "movie_credits", ["movie_id"])
    op.create_index("idx_movie_credits_person_id", "movie_credits", ["person_id"])
    # Composite index for the common "all cast for a movie, ordered" query
    op.create_index(
        "idx_movie_credits_movie_type_order",
        "movie_credits",
        ["movie_id", "credit_type", "credit_order"],
    )


def downgrade() -> None:
    op.drop_index("idx_movie_credits_movie_type_order", table_name="movie_credits")
    op.drop_index("idx_movie_credits_person_id", table_name="movie_credits")
    op.drop_index("idx_movie_credits_movie_id", table_name="movie_credits")
    op.drop_constraint("ck_movie_credits_credit_type", "movie_credits", type_="check")
    op.drop_table("movie_credits")
