"""Record the wants whose shop answered with an empty results page.

Before this, an empty results page was counted in `failed` — 8 of one real run's 11
"failures" were shops that simply do not carry the film (`DECISIONS.md` #125). Two changes,
because the state has to be expressible in both places it is written:

1. `scrape_runs.no_results`, so a run's numbers add up honestly rather than reading as
   breakage.
2. `retailers.last_scrape_status` gains `no_results`. Batch 16's CHECK constraint allowed
   only `success`, `error` and `blocked` — which is the constraint doing its job: a new
   state has to be declared rather than smuggled in as a string.

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

CONSTRAINT = "ck_retailers_scrape_status"

#: Batch 16's set, plus the third state.
STATUSES_AFTER = ("success", "error", "blocked", "no_results")
STATUSES_BEFORE = ("success", "error", "blocked")


def _check(values: tuple[str, ...]) -> str:
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"last_scrape_status IS NULL OR last_scrape_status IN ({allowed})"


def upgrade() -> None:
    op.add_column(
        "scrape_runs",
        sa.Column("no_results", sa.Integer(), nullable=False, server_default="0"),
    )
    op.drop_constraint(CONSTRAINT, "retailers", type_="check")
    op.create_check_constraint(CONSTRAINT, "retailers", _check(STATUSES_AFTER))


def downgrade() -> None:
    # The value has to go before the constraint that forbids it comes back, or the
    # narrowed constraint cannot be created against rows already holding `no_results`.
    # `NULL` rather than `error`: a shop that answered "nothing found" has not failed, and
    # the whole point of #125 is not to record it as though it had.
    op.execute(
        sa.text(
            "UPDATE retailers SET last_scrape_status = NULL, last_scrape_error = NULL "
            "WHERE last_scrape_status = 'no_results'"
        )
    )
    op.drop_constraint(CONSTRAINT, "retailers", type_="check")
    op.create_check_constraint(CONSTRAINT, "retailers", _check(STATUSES_BEFORE))
    op.drop_column("scrape_runs", "no_results")
