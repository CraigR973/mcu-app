"""copy edition — which edition a disc is, as free text

Revision ID: 041
Revises: 040
Create Date: 2026-09-26

Batch U2 (`DECISIONS.md` #220). ``collection_items.edition``: "SteelBook", "Masters of
Cinema", "Zavvi Exclusive SteelBook". Nullable and free text, like the Wanted list's
``preferred_edition``, and the same length. Nothing is written here: the column starts
empty, and is filled only where a disc's Blu-ray.com page is certainly the copy, by the
spec batch and by a one-off script that writes blanks only.

The downgrade drops the column, and with it any edition typed by hand.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "041"
down_revision: str | None = "040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("collection_items", sa.Column("edition", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("collection_items", "edition")
