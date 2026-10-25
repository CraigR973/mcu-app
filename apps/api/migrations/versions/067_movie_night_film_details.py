"""IMDb ratings and TMDB-only night metadata (AA5).

Revision ID: 067
Revises: 066
Create Date: 2026-10-25

Nullable caches, no backfill, no changes to copies or watch history.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "067"
down_revision: str | None = "066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("movies", "movie_night_suggestions"):
        op.add_column(table, sa.Column("imdb_ratings_id", sa.String(20), nullable=True))
        op.add_column(table, sa.Column("imdb_rating", sa.Numeric(), nullable=True))
        op.add_column(table, sa.Column("imdb_vote_count", sa.Integer(), nullable=True))
        op.add_column(
            table, sa.Column("imdb_ratings_checked_utc", sa.DateTime(timezone=False), nullable=True)
        )
        op.create_check_constraint(
            f"ck_{table}_imdb_rating", table, "imdb_rating IS NULL OR imdb_rating BETWEEN 0 AND 10"
        )
        op.create_check_constraint(
            f"ck_{table}_imdb_votes", table, "imdb_vote_count IS NULL OR imdb_vote_count >= 0"
        )
    op.add_column(
        "movie_night_suggestions", sa.Column("runtime_minutes", sa.Integer(), nullable=True)
    )
    op.add_column("movie_night_suggestions", sa.Column("imdb_id", sa.String(20), nullable=True))
    op.add_column(
        "movie_night_suggestions",
        sa.Column("metadata_checked_utc", sa.DateTime(timezone=False), nullable=True),
    )
    for table, columns in (
        ("movies", "imdb_ratings_id, imdb_rating, imdb_vote_count, imdb_ratings_checked_utc"),
        (
            "movie_night_suggestions",
            "imdb_ratings_id, imdb_rating, imdb_vote_count, imdb_ratings_checked_utc, "
            "runtime_minutes, imdb_id, metadata_checked_utc",
        ),
    ):
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
            f"GRANT SELECT ({columns}) ON {table} TO mcu_readonly; END IF; "
            "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
            f"GRANT SELECT ({columns}) ON {table} TO mcu_backup; END IF; END $$"
        )


def downgrade() -> None:
    for column in ("metadata_checked_utc", "imdb_id", "runtime_minutes"):
        op.drop_column("movie_night_suggestions", column)
    for table in ("movie_night_suggestions", "movies"):
        op.drop_constraint(f"ck_{table}_imdb_votes", table, type_="check")
        op.drop_constraint(f"ck_{table}_imdb_rating", table, type_="check")
        for column in (
            "imdb_ratings_checked_utc",
            "imdb_vote_count",
            "imdb_rating",
            "imdb_ratings_id",
        ):
            op.drop_column(table, column)
