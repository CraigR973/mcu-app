"""a TV series keeps its own TMDB id

Revision ID: 056
Revises: 055
Create Date: 2026-10-15

Batch Y3, Mark's feedback of 15 Oct: a TV series is identified from TMDB as a film is. TMDB
numbers films and series separately, so a series' id cannot go in ``movies.tmdb_id``: about
40 modules read that as a film's (values, specs, streaming, reviews, Letterboxd), and would
fetch whichever film happens to share the number. ``tmdb_tv_id`` holds it instead, unique as
``tmdb_id`` is, and a row has at most one of the two.

``identify_lookups.media_type`` says which index an identified lookup's ``tmdb_id`` is from,
``film`` for every row so far.

**No grant:** ``mcu_readonly`` (by hand, 1 Oct) and ``mcu_backup`` (053) are granted both
tables whole, so a new column is readable at once, and neither holds a credential.

The downgrade drops both columns; a series identified since is left with its title, poster
and the rest, unidentified.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "056"
down_revision: str | None = "055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("tmdb_tv_id", sa.Integer(), nullable=True))
    op.create_index("uq_movies_tmdb_tv_id", "movies", ["tmdb_tv_id"], unique=True)
    op.add_column(
        "identify_lookups",
        sa.Column("media_type", sa.Text(), nullable=False, server_default="film"),
    )
    op.create_check_constraint(
        "ck_identify_lookups_media_type", "identify_lookups", "media_type IN ('film', 'tv')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_identify_lookups_media_type", "identify_lookups", type_="check")
    op.drop_column("identify_lookups", "media_type")
    op.drop_index("uq_movies_tmdb_tv_id", table_name="movies")
    op.drop_column("movies", "tmdb_tv_id")
