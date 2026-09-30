"""add "Craig's house" to the section vocabulary

Revision ID: 042
Revises: 041
Create Date: 2026-09-30

Batch V4 (`DECISIONS.md` #228): "Craig's house is fine". One place with no shelves, counted
like any other disc. The CHECK on ``collection_items.section`` names every section, so the
new one has to be added to it before a disc can be filed there.

**It is the first name with an apostrophe.** Migration 007 built its clause by pasting each
name inside quotes, which would write ``'Craig's house'`` and end the SQL string after
``Craig``. Here each name is escaped the SQL way, ``'Craig''s house'``, and
``test_craigs_house.py`` checks both the clause and the constraint Postgres ends up holding.

**The upgrade writes no rows.** No disc is in Craig's house until someone moves one there.
The downgrade clears ``section`` on any disc that is, before narrowing the CHECK back, and
leaves ``location`` alone, as 007's does: the typed text still says where the disc is.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: str | None = "041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CRAIGS_HOUSE = "Craig's house"

#: The vocabulary as 007 left it, and with the new name. Spelled out rather than imported
#: from the model: a migration describes the schema at its own revision, not today's.
_SECTIONS_V2 = (
    "Front",
    "Back",
    "Lounge",
    "Garage",
    "Digital",
    "Top Big Cabinet",
    "Top Small Cabinet",
    "Fish Room Cabinet",
    "Black Box",
)
_SECTIONS_V3 = (*_SECTIONS_V2, CRAIGS_HOUSE)


def _literal(name: str) -> str:
    """A SQL string literal: quotes doubled, so an apostrophe stays inside the string."""
    return "'" + name.replace("'", "''") + "'"


def _check_clause(sections: tuple[str, ...]) -> str:
    values = ", ".join(_literal(name) for name in sections)
    return f"section IS NULL OR section IN ({values})"


def upgrade() -> None:
    op.drop_constraint("ck_collection_items_section", "collection_items", type_="check")
    op.create_check_constraint(
        "ck_collection_items_section",
        "collection_items",
        _check_clause(_SECTIONS_V3),
    )


def downgrade() -> None:
    # A disc filed in Craig's house would break the narrower CHECK, so its section goes
    # first. Its `location` is left as typed.
    op.execute(
        sa.text("UPDATE collection_items SET section = NULL WHERE section = :name").bindparams(
            name=CRAIGS_HOUSE
        )
    )
    op.drop_constraint("ck_collection_items_section", "collection_items", type_="check")
    op.create_check_constraint(
        "ck_collection_items_section",
        "collection_items",
        _check_clause(_SECTIONS_V2),
    )
