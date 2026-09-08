"""widen the section vocabulary to the four cabinets and backfill

Revision ID: 007
Revises: 006
Create Date: 2026-09-08

§3.4 named five sections. 124 of the 1,857 imported rows named somewhere else, so they
kept their raw ``location`` text and were left with ``section IS NULL`` — invisible to
the section filter Batch 6 exists to build. `STATUS.md` recorded settling that as this
batch's job.

They are not scattered. 122 of the 124 are four named cabinets, and this revision adds
them to the vocabulary and backfills the rows (`DECISIONS.md` #34):

| Location text | Section | Rows |
|---|---|---|
| ``Top Big Cabinet`` (+ ``& E:\\Movies``) | ``Top Big Cabinet`` | 38 |
| ``Top Small Cabinet`` / ``Top small cabinet`` (+ variants) | ``Top Small Cabinet`` | 38 |
| ``Left Hand Side Small Cabinet Fish Room`` | ``Fish Room Cabinet`` | 26 |
| ``Black Box next to cabinet`` | ``Black Box`` | 20 |

Two rows stay unsectioned and that is the right answer for them: ``(In with The
Killing)``, which names another disc rather than a place, and one row with no location at
all.

**It also clears four wrong shelf values.** ``parse_location`` used to read any bare
digit as a shelf, so ``Top small cabinet (Arrow 4 Film Noir Classics Vol 2)`` parsed to
shelf ``4th``. Those four rows would have surfaced under a "4th shelf" filter — the very
filter this batch ships — so the parser fix and the data fix land together. Cabinets have
no shelves.

**This revision writes to live rows**, which is why Batch 6's close-out stops for
sign-off instead of deploying itself (`AGENTS.md`, close-out protocol). The write is
derived entirely from ``location``, which is never modified, so it is reproducible and
fully reversible.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Prefix → section, mirroring ``_SECTION_PREFIXES`` in the spreadsheet parser. Matched
#: with ``ILIKE`` so the two spellings of "Top small cabinet" need one entry.
#:
#: The pattern is a bound parameter, never interpolated: a literal ``%`` in SQL passed
#: through psycopg2 is read as a parameter placeholder, which cost a session during
#: Batch 5's close-out.
_CABINETS: list[tuple[str, str]] = [
    ("top big cabinet%", "Top Big Cabinet"),
    ("top small cabinet%", "Top Small Cabinet"),
    ("left hand side small cabinet fish room%", "Fish Room Cabinet"),
    ("black box next to cabinet%", "Black Box"),
]

_SECTIONS_V1 = ("Front", "Back", "Lounge", "Garage", "Digital")
_SECTIONS_V2 = (
    *_SECTIONS_V1,
    "Top Big Cabinet",
    "Top Small Cabinet",
    "Fish Room Cabinet",
    "Black Box",
)


def _check_clause(sections: tuple[str, ...]) -> str:
    values = ", ".join(f"'{name}'" for name in sections)
    return f"section IS NULL OR section IN ({values})"


def upgrade() -> None:
    # Widen the constraint before the backfill, or every UPDATE below violates it.
    op.drop_constraint("ck_collection_items_section", "collection_items", type_="check")
    op.create_check_constraint(
        "ck_collection_items_section",
        "collection_items",
        _check_clause(_SECTIONS_V2),
    )

    for pattern, section in _CABINETS:
        # ``section IS NULL`` guards the backfill: a section set by hand after this
        # migration was written must not be overwritten by a re-run.
        op.execute(
            sa.text(
                "UPDATE collection_items SET section = :section "
                "WHERE section IS NULL AND location ILIKE :pattern"
            ).bindparams(section=section, pattern=pattern)
        )

    # Cabinets have no shelves. The only rows this touches are the four that the old
    # bare-digit ordinal match mislabelled.
    op.execute(
        sa.text(
            "UPDATE collection_items SET shelf = NULL "
            "WHERE shelf IS NOT NULL AND section = ANY(:cabinets)"
        ).bindparams(sa.bindparam("cabinets", value=[s for _, s in _CABINETS]))
    )


def downgrade() -> None:
    # Restore the shelf the old parser produced, before clearing the sections that
    # identify which rows to restore it on. This reinstates a value we know to be
    # wrong, which is what reversing means: a downgrade that quietly kept the
    # improvement would hide that it had run.
    op.execute(
        sa.text(
            "UPDATE collection_items SET shelf = '4th' "
            "WHERE section = 'Top Small Cabinet' AND location ILIKE :pattern"
        ).bindparams(pattern="top small cabinet (arrow 4 film noir%")
    )

    op.execute(
        sa.text(
            "UPDATE collection_items SET section = NULL WHERE section = ANY(:cabinets)"
        ).bindparams(sa.bindparam("cabinets", value=[s for _, s in _CABINETS]))
    )

    op.drop_constraint("ck_collection_items_section", "collection_items", type_="check")
    op.create_check_constraint(
        "ck_collection_items_section",
        "collection_items",
        _check_clause(_SECTIONS_V1),
    )
