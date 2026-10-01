"""the bid trial: a valuation run that saves no prices, and its report

Revision ID: 043
Revises: 042
Create Date: 2026-10-01

Batch V6, snag 2's first step (`DECISIONS.md` #228: "trial first"). Home's "Try bid prices"
searches eBay for a sample of priced films with Buy It Now and auctions together, and
reports what bids would say. It spends the same day's eBay share as a valuation run and must
not overlap one, so it claims a ``valuation_runs`` row, with a new trigger, ``trial``, and
keeps its report on that row:

- ``ck_valuation_runs_trigger`` allows ``trial``.
- ``valuation_runs.report`` (JSONB, nullable) holds a trial's report. A valuation run's is
  null.

**The upgrade writes no rows.** The downgrade turns any trial row into an ``admin`` run
rather than deleting it, so the calls it spent still count against that day's share, then
drops the report and narrows the CHECK back.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "043"
down_revision: str | None = "042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_valuation_runs_trigger", "valuation_runs", type_="check")
    op.create_check_constraint(
        "ck_valuation_runs_trigger", "valuation_runs", "trigger IN ('job', 'admin', 'trial')"
    )
    op.add_column("valuation_runs", sa.Column("report", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.execute("UPDATE valuation_runs SET trigger = 'admin' WHERE trigger = 'trial'")
    op.drop_column("valuation_runs", "report")
    op.drop_constraint("ck_valuation_runs_trigger", "valuation_runs", type_="check")
    op.create_check_constraint(
        "ck_valuation_runs_trigger", "valuation_runs", "trigger IN ('job', 'admin')"
    )
