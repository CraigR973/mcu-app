"""Record the wants whose shop answered with an empty results page.

Before this column, an empty results page was counted in `failed` — 8 of one real run's
11 "failures" were shops that simply do not carry the film (`DECISIONS.md` #125). The
column exists so a run's numbers add up honestly rather than reading as breakage.

Revision ID: 027
Revises: 026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: str | None = "026"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "scrape_runs",
        sa.Column("no_results", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("scrape_runs", "no_results")
