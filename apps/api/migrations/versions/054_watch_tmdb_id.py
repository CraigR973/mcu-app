"""a watch keeps the TMDB film it was of

Revision ID: 054
Revises: 053
Create Date: 2026-10-14

Batch X5, "Watch history: films not owned, the backfill, the year rule" (CT46-02). One
nullable column, ``watch_log.tmdb_id``: the film Letterboxd's feed names for each viewing (or
the one the diary backfill identified), kept beside ``movie_id``, the row the watch hangs on.

**Nothing to backfill:** the 1,566 imported watches came from a file with no TMDB id, and the
four the feed wrote on 11 Oct can be read again from it. **Both roles' grants on
``watch_log`` are table-level**, so ``mcu_readonly`` and ``mcu_backup`` read the new column
with no grant of their own; it is not a credential.

The downgrade drops the column; the watches stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "054"
down_revision: str | None = "053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("watch_log", sa.Column("tmdb_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("watch_log", "tmdb_id")
