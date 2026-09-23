"""calendar refresh state — when the release calendar last refreshed, and what it found

Revision ID: 035
Revises: 034
Create Date: 2026-09-23

Batch T5. The release calendar was refreshed only when an admin pressed a button, and
nobody had since 9 Sep, so it went stale without anyone noticing. It now refreshes itself
when it is read and is more than a day old. That needs somewhere to record when the last
refresh started and finished, so two readers cannot start two refreshes, and so the page
can say how fresh it is.

One row, pinned by a CHECK, as `specs_integration_state` is: a state table that can grow
a second row grows one eventually, and then "when did it last run?" has two answers.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: str | None = "034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_refresh_state",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("last_started_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_finished_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_disc_releases", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("id = 1", name="ck_calendar_refresh_singleton"),
    )
    op.execute("INSERT INTO calendar_refresh_state (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("calendar_refresh_state")
