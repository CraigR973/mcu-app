"""create movies table

Revision ID: 0001
Revises:
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reusable trigger function — placed in migration 0001 so it exists before any
    # table needs it; later migrations just attach triggers.
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), primary_key=True),  # TMDB movie ID
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("original_title", sa.Text()),
        sa.Column("overview", sa.Text()),
        sa.Column("release_date", sa.Date()),
        sa.Column("runtime", sa.Integer()),
        sa.Column("popularity", sa.Numeric(10, 3)),
        sa.Column("vote_average", sa.Numeric(4, 2)),
        sa.Column("vote_count", sa.Integer(), server_default="0"),
        sa.Column("poster_path", sa.Text()),
        sa.Column("backdrop_path", sa.Text()),
        sa.Column("genre_ids", ARRAY(sa.Integer())),
        sa.Column("status", sa.Text()),
        sa.Column("tagline", sa.Text()),
        sa.Column("budget", sa.BigInteger(), server_default="0"),
        sa.Column("revenue", sa.BigInteger(), server_default="0"),
        sa.Column("imdb_id", sa.Text()),
        sa.Column("homepage", sa.Text()),
        sa.Column("adult", sa.Boolean(), server_default="false"),
        sa.Column("search_vector", TSVECTOR()),
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

    # GIN index for full-text search
    op.create_index(
        "idx_movies_search_vector",
        "movies",
        ["search_vector"],
        postgresql_using="gin",
    )
    # GIN index for genre_ids array membership queries
    op.create_index(
        "idx_movies_genre_ids",
        "movies",
        ["genre_ids"],
        postgresql_using="gin",
    )
    op.create_index("idx_movies_release_date", "movies", ["release_date"])
    op.create_index(
        "idx_movies_popularity",
        "movies",
        [sa.text("popularity DESC")],
        postgresql_using="btree",
    )

    # Trigger: keep updated_at current on every UPDATE
    op.execute("""
        CREATE TRIGGER movies_set_updated_at
        BEFORE UPDATE ON movies
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS movies_set_updated_at ON movies;")
    op.drop_index("idx_movies_popularity", table_name="movies")
    op.drop_index("idx_movies_release_date", table_name="movies")
    op.drop_index("idx_movies_genre_ids", table_name="movies")
    op.drop_index("idx_movies_search_vector", table_name="movies")
    op.drop_table("movies")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at;")
