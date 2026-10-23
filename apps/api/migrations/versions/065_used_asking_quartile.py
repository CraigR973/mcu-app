"""Allow postage-in used asking quartiles for AA10b values.

Revision ID: 065
Revises: 064
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "065"
down_revision: str | None = "064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_disc_valuations_value_basis", "disc_valuations")
    op.create_check_constraint(
        "ck_disc_valuations_value_basis",
        "disc_valuations",
        "value_basis IS NULL OR value_basis IN ('used', 'used_quartile', 'new_scaled')",
    )


def downgrade() -> None:
    # Refuse to mislabel live quartile prices as the old used median.
    rows = (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM disc_valuations WHERE value_basis = 'used_quartile'")
        )
        .scalar_one()
    )
    if rows:
        raise RuntimeError("Re-price or remove used_quartile values before downgrading")
    op.drop_constraint("ck_disc_valuations_value_basis", "disc_valuations")
    op.create_check_constraint(
        "ck_disc_valuations_value_basis",
        "disc_valuations",
        "value_basis IS NULL OR value_basis IN ('used', 'new_scaled')",
    )
