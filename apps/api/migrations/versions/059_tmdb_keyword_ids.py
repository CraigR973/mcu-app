"""a film's TMDB keywords, for the Archive's Film Noir

Revision ID: 059
Revises: 058
Create Date: 2026-10-16

Batch Y5 (#277). Mark asked for a Film Noir filter on 16 Oct and Craig chose TMDB's keyword
9807 "film noir" (224 of the 1,850 identified owned films carry it). ``movies.tmdb_keyword_ids``
holds every keyword id of the film or series, not a noir flag, so the next keyword asked for
needs no migration. Null is "not fetched yet": every full TMDB fetch fills it from now on, and
``src.scripts.fill_keywords`` fills the films already identified, at Craig's word. An empty
array is "TMDB has none".

GIN-indexed as ``genre_ids`` is, for the same containment filter. Granted to both read-only
roles, guarded so CI's database (which has neither) still migrates. It holds no credential.

The downgrade drops the column: the filter's keyword is unknown again.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "059"
down_revision: str | None = "058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "movies",
        sa.Column("tmdb_keyword_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
    )
    op.create_index(
        "ix_movies_tmdb_keyword_ids",
        "movies",
        ["tmdb_keyword_ids"],
        postgresql_using="gin",
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT (tmdb_keyword_ids) ON movies TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        "GRANT SELECT (tmdb_keyword_ids) ON movies TO mcu_backup; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_index("ix_movies_tmdb_keyword_ids", table_name="movies")
    op.drop_column("movies", "tmdb_keyword_ids")
