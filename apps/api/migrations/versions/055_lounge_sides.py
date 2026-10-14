"""the Lounge cabinet's two sides become its shelves

Revision ID: 055
Revises: 054
Create Date: 2026-10-14

Mark's request, 14 Oct: the Lounge needs a Left / Right picker, as Front and Back have their
shelves. The side goes in ``shelf``, and this revision fills it in for the copies that
already say which side only in their location text (read-only, 14 Oct):

| Location text | Side | Live rows | In the Trash |
|---|---|---|---|
| ``Lounge Cabinet - Right Hand Side`` | ``Right`` | 96 | 95 |
| ``Lounge Cabinet - Left Hand Side`` (+ ``& E:\\Movies``) | ``Left`` | 68 | 65 |

Two stay without a side, which is the truth about them: Nope and Us, both 4K, moved to the
Lounge on 14 Oct by a form that dropped the side Mark typed. He picks it again.

**It has to land with the picker.** ``parse_location`` now reads a side out of Lounge text,
so a Lounge copy still without one would have its text replaced by plain "Lounge" the next
time anything on it was edited (`DECISIONS.md` #266's rule), which is the bug being fixed.

Text naming exactly one side sets it; text naming both or neither sets nothing, as the
parser does. The 160 soft-deleted copies are included, so one restored from the Trash agrees
with its text. No column is added, so neither ``mcu_readonly`` nor ``mcu_backup`` needs a grant.
Each row's ``updated_at`` moves, which is true: a form open on one of them during the deploy
is told the copy changed, as #42 intends.

The downgrade clears every Lounge side, including any picked after this ran; the location
text, which still names the side, is left alone.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "055"
down_revision: str | None = "054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SIDES = (("Left", "left", "right"), ("Right", "right", "left"))


def upgrade() -> None:
    for side, named, other in _SIDES:
        # ``shelf IS NULL`` guards the backfill, as 007's does: a side set by the picker
        # after this was written is never overwritten by a re-run.
        op.execute(
            sa.text(
                "UPDATE collection_items SET shelf = :side "
                "WHERE section = 'Lounge' AND shelf IS NULL "
                "AND location ~* :named AND location !~* :other"
            ).bindparams(side=side, named=rf"\m{named}\M", other=rf"\m{other}\M")
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE collection_items SET shelf = NULL "
            "WHERE section = 'Lounge' AND shelf = ANY(:sides)"
        ).bindparams(sa.bindparam("sides", value=[side for side, _, _ in _SIDES]))
    )
