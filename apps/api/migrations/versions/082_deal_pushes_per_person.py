"""AG6 (MK53-05, #383): each person may hear only of Wanted-list deals, and new people start
with quiet hours.

- ``notification_preferences.deals_wanted_only``: false on every row, so nobody's pushes change
  by this column alone.
- ``quiet_hours_start`` and ``quiet_hours_end`` default to 22:00 and 07:00 for a row written
  from now on. **No existing row is changed here:** both people's rows hold no quiet hours, and
  setting them is a write to live data, left to the owner's word
  (``src.scripts.deal_pushes_owner_step``).

Grants are untouched: ``mcu_readonly`` and ``mcu_backup`` hold SELECT on the table, which
covers a new column. The downgrade drops the column and the two defaults.

Revision ID: 082
Revises: 081
Create Date: 2026-11-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "082"
down_revision: str | None = "081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column(
            "deals_wanted_only", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.alter_column(
        "notification_preferences", "quiet_hours_start", server_default=sa.text("'22:00'")
    )
    op.alter_column(
        "notification_preferences", "quiet_hours_end", server_default=sa.text("'07:00'")
    )


def downgrade() -> None:
    op.alter_column("notification_preferences", "quiet_hours_end", server_default=None)
    op.alter_column("notification_preferences", "quiet_hours_start", server_default=None)
    op.drop_column("notification_preferences", "deals_wanted_only")
