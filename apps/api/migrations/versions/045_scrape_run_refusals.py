"""each refused request's wait, and whether its retry got through

Revision ID: 045
Revises: 044
Create Date: 2026-10-02

Batch 20b, second half. A refused request now waits for the shop's ``Retry-After`` (up to
90 seconds) before its one retry, and the run's record says, for each refusal, what the
shop asked for, the wait, and whether the retry got through: ``scrape_runs.refusals``,
JSONB, a list of ``{"retailer", "wanted", "asked", "waited", "note", "retry"}``.

**The upgrade writes no rows of its own.** Earlier runs read as an empty list: they waited
two seconds and recorded nothing about it, and their refusals are in ``failures``. The
read-only role reads the column through its table-level grant on ``scrape_runs``. The
downgrade drops the column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "045"
down_revision: str | None = "044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scrape_runs",
        sa.Column(
            "refusals",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("scrape_runs", "refusals")
