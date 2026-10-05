"""a loan's borrower may be one of the two people

Revision ID: 048
Revises: 047
Create Date: 2026-10-05

Batch W3, "lend and borrow" (`DECISIONS.md` #249). One nullable column on ``loans``:

- ``borrower_profile_id``: set when the borrower is one of the people who use the app, as
  "I'm borrowing it" records; null for a loan to anyone else, as every loan was before.
  ``borrower_name`` still holds the name as text, so a loan reads the same either way.

``ON DELETE SET NULL``: profiles are soft-deleted, so the case should not arise, but a removed
profile must not take a loan's history with it. **Nothing to backfill:** the table held 0 rows
on 5 Oct. The read-only role's grant on ``loans`` is table-level, so it covers the new column
with no grant of its own; nothing in it is a credential.

The downgrade drops the column; the loans themselves, and their borrowers' names, stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "048"
down_revision: str | None = "047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "loans",
        sa.Column(
            "borrower_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL", name="fk_loans_borrower_profile"),
            nullable=True,
        ),
    )
    op.create_index("ix_loans_borrower_profile_id", "loans", ["borrower_profile_id"])


def downgrade() -> None:
    op.drop_index("ix_loans_borrower_profile_id", table_name="loans")
    op.drop_column("loans", "borrower_profile_id")
