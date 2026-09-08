"""profiles.onboarding_completed_at_utc

Revision ID: 010
Revises: 009
Create Date: 2026-09-08

The wizard's completion flag, which this app has never had on the new spine.

Phase 2.8's wizard shipped in April against a Supabase column, and Batch 3 removed the
wizard entirely rather than port a flow whose "I have finished" would save nowhere
(`DECISIONS.md` #27). Rebuilding it means creating the column it needs — the schema doc
never designed one, so this defines it.

A **nullable timestamp rather than a boolean**: it answers "has this person finished?" and
"when?" for the price of one column, follows the `*_utc` convention every other domain
timestamp here uses, and cannot end up in the "true but we do not know when" state a
boolean plus a later audit question would produce.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("onboarding_completed_at_utc", sa.DateTime(timezone=False), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "onboarding_completed_at_utc")
