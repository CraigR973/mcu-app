"""establish the re-scaffold baseline

Revision ID: 001
Revises:
Create Date: 2026-09-07

Batch 2 intentionally has no domain or authentication tables. Those schemas land with
their owning Batches 3 and 4 instead of recreating the speculative legacy schema.
"""

from collections.abc import Sequence

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Mark a fresh Postgres database as ready for the new migration chain."""


def downgrade() -> None:
    """Return the fresh database to Alembic base."""
