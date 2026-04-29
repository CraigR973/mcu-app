"""Add pg_trgm GIN index on movie_credits.person_name for fast ILIKE search.

Revision ID: 0016
Revises: 0015
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_movie_credits_person_name_trgm "
        "ON movie_credits USING gin (lower(person_name) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_movie_credits_person_name_trgm")
