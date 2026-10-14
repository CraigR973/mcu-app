"""a disc's value as a used copy: how it was reached, its range, and both groups

Revision ID: 052
Revises: 051
Create Date: 2026-10-14

Batch X6, "Value the shelf as used copies" (MK47-03, #256 amending #209). Eight nullable
columns on ``disc_valuations`` and two checks:

- ``value_basis``: ``used`` (the median of three or more used listings) or ``new_scaled`` (New's
  median times the format's used-to-New factor). Null when not priced.
- ``factor``: what a ``new_scaled`` value was multiplied by, and only on one.
- ``low``, ``high``: the range of the listings the value rests on, for Home's most valuable.
- ``used_median``, ``used_count``, ``new_median``, ``new_count``: both groups, priced or not,
  which the factor is measured from.

**Nothing to backfill, deliberately.** A value stored before X6 is the largest condition
group's median, a new copy's price for 965 of the 1,300 priced discs; it cannot be turned into
a used copy's value without the listings. Its ``used_count`` stays null, which makes it due at
the next valuation run and leaves it out of every total and list until then. The read-only
role's grant on the table is table-level, so it covers the new columns; none is a credential.

The downgrade drops the checks and the columns. The values stored since stay, and read as
they did before X6.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: str | None = "051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("disc_valuations", sa.Column("value_basis", sa.String(20), nullable=True))
    op.add_column("disc_valuations", sa.Column("factor", sa.Numeric(4, 2), nullable=True))
    op.add_column("disc_valuations", sa.Column("low", sa.Numeric(8, 2), nullable=True))
    op.add_column("disc_valuations", sa.Column("high", sa.Numeric(8, 2), nullable=True))
    op.add_column("disc_valuations", sa.Column("used_median", sa.Numeric(8, 2), nullable=True))
    op.add_column("disc_valuations", sa.Column("used_count", sa.Integer(), nullable=True))
    op.add_column("disc_valuations", sa.Column("new_median", sa.Numeric(8, 2), nullable=True))
    op.add_column("disc_valuations", sa.Column("new_count", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_disc_valuations_value_basis",
        "disc_valuations",
        "value_basis IS NULL OR value_basis IN ('used', 'new_scaled')",
    )
    op.create_check_constraint(
        "ck_disc_valuations_factor_only_when_scaled",
        "disc_valuations",
        "value_basis IS NULL OR (value_basis = 'new_scaled') = (factor IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_disc_valuations_factor_only_when_scaled", "disc_valuations", type_="check"
    )
    op.drop_constraint("ck_disc_valuations_value_basis", "disc_valuations", type_="check")
    for column in (
        "new_count",
        "new_median",
        "used_count",
        "used_median",
        "high",
        "low",
        "factor",
        "value_basis",
    ):
        op.drop_column("disc_valuations", column)
