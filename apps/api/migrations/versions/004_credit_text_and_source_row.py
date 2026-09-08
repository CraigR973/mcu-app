"""widen movie_credits.character_name; add collection_items.import_source_row

Revision ID: 004
Revises: 003
Create Date: 2026-09-07

Two defects the first live import surfaced, neither visible before real data went in.

**1. ``character_name`` at ``VARCHAR(255)`` is too narrow.** Roadmap §3.3 sizes it that
way; TMDB exceeds it. Dan Castellaneta's credit on *The Simpsons Movie* is a
300-character role list — "Homer Simpson / Itchy / Barney / Abe Simpson / Stage Manager /
Krusty the Clown / …" — and Hank Azaria's is 270. Any film where one performer voices
many parts does the same. Because the importer writes each item in one transaction, the
overflow rolled back the film, its credits *and* its collection item: the disc vanished
from the catalogue over a cast-list field. ``TEXT`` rather than a larger ``VARCHAR``,
since no fixed length is safe for a slash-separated list and Postgres treats the two
identically. Binary-coercible, so no rows are rewritten.

**2. Idempotency keyed on ``(movie_id, location, formats)`` collapses distinct discs.**
Two spreadsheet rows that resolve to the same TMDB film, on the same shelf, in the same
format, became one row. Three pairs did in the real sheet. Two were genuine duplicate
entries — but the third was "French Connection" and "French Connection 2", which the
matcher resolved to the same film, so an owned disc was silently absent.

``import_source_row`` records which spreadsheet line produced an item, and the importer
keys re-run safety on it instead. Two different source rows can then never collapse into
one, whatever TMDB says about them, and a genuine duplicate line in the sheet stays two
items — which is what the sheet says. It is also the provenance the 764-row review queue
needs: an item can be traced back to the line it came from.

Nullable and unique-where-present: an item added by hand through the Batch 7 UI has no
source row, and Postgres treats each NULL as distinct so any number of those coexist.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "movie_credits",
        "character_name",
        existing_type=sa.String(255),
        type_=sa.Text(),
        existing_nullable=True,
    )

    op.add_column(
        "collection_items",
        sa.Column("import_source_row", sa.Integer(), nullable=True),
    )
    op.create_index(
        "uq_collection_items_import_source_row",
        "collection_items",
        ["import_source_row"],
        unique=True,
        postgresql_where=sa.text("import_source_row IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_collection_items_import_source_row", table_name="collection_items")
    op.drop_column("collection_items", "import_source_row")

    # Truncate on the way down: a value past 255 cannot fit the narrower column, and
    # without this the downgrade fails on exactly the rows that motivated the widening.
    # CI runs `downgrade base` on every push, so this path is exercised.
    op.execute("UPDATE movie_credits SET character_name = left(character_name, 255)")
    op.alter_column(
        "movie_credits",
        "character_name",
        existing_type=sa.Text(),
        type_=sa.String(255),
        existing_nullable=True,
    )
