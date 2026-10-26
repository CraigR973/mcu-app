"""Four-state loan flow (AA11); existing loans stay untouched.

Revision ID: 069
Revises: 068
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "069"
down_revision: str | None = "068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("loans", "lent_date", existing_type=sa.Date(), nullable=True)
    op.add_column("loans", sa.Column("state", sa.String(20), nullable=True))
    op.add_column("loans", sa.Column("needed_by_date", sa.Date(), nullable=True))
    op.add_column(
        "loans", sa.Column("returned_by_profile_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("loans", sa.Column("shelved_at_utc", sa.DateTime(timezone=False), nullable=True))
    op.create_foreign_key(
        "fk_loans_returned_by",
        "loans",
        "profiles",
        ["returned_by_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_loans_state", "loans", "state IS NULL OR state IN ('asked_for','out','back','shelved')"
    )
    op.create_check_constraint(
        "ck_loans_state_dates",
        "loans",
        "state IS NULL OR (state = 'asked_for' AND lent_date IS NULL "
        "AND needed_by_date IS NOT NULL AND returned_date IS NULL AND shelved_at_utc IS NULL) "
        "OR (state = 'out' AND lent_date IS NOT NULL "
        "AND returned_date IS NULL AND shelved_at_utc IS NULL) "
        "OR (state = 'back' AND lent_date IS NOT NULL "
        "AND returned_date IS NOT NULL AND shelved_at_utc IS NULL) "
        "OR (state = 'shelved' AND lent_date IS NOT NULL "
        "AND returned_date IS NOT NULL AND shelved_at_utc IS NOT NULL)",
    )
    for role in ("mcu_readonly", "mcu_backup"):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN "
            "GRANT SELECT (state, needed_by_date, returned_by_profile_id, shelved_at_utc) "
            f"ON loans TO {role}; END IF; END $$"
        )


def downgrade() -> None:
    # Never invent a lent date or delete a pending request to satisfy the old NOT NULL.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM loans WHERE lent_date IS NULL) THEN "
        "RAISE EXCEPTION 'Resolve requested loans before downgrading 069'; END IF; END $$"
    )
    op.drop_constraint("ck_loans_state_dates", "loans", type_="check")
    op.drop_constraint("ck_loans_state", "loans", type_="check")
    op.drop_constraint("fk_loans_returned_by", "loans", type_="foreignkey")
    for column in ("shelved_at_utc", "returned_by_profile_id", "needed_by_date", "state"):
        op.drop_column("loans", column)
    op.alter_column("loans", "lent_date", existing_type=sa.Date(), nullable=False)
