"""AH2 (#401): a question has a closed state of its own, apart from deletion.

- ``assigned_reviews.closed_at_utc``: when the admin closed the question; null while it is open.
- ``assigned_reviews.closed_by``: who closed it, set null if that profile is ever removed.

Both start null on every row, so no question changes by this migration alone. The two
questions closed by hand on 25 Nov (#400), which reused ``deleted_at``, move to the closed state
only at the owner's word, outside the migration.

Grants are untouched: ``mcu_readonly`` and ``mcu_backup`` hold SELECT on the table, which
covers a new column. The downgrade drops both columns.

Revision ID: 083
Revises: 082
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "083"
down_revision: str | None = "082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assigned_reviews",
        sa.Column("closed_at_utc", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "assigned_reviews",
        sa.Column(
            "closed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL", name="fk_assigned_reviews_closed_by"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("assigned_reviews", "closed_by")
    op.drop_column("assigned_reviews", "closed_at_utc")
