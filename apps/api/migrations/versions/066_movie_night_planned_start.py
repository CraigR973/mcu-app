"""Optional planned start for a movie night; existing nights stay unplanned.

Revision ID: 066
Revises: 065
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "066"
down_revision: str | None = "065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "movie_night_sessions",
        sa.Column("planned_start_utc", sa.DateTime(timezone=False), nullable=True),
    )
    # Column grants: invite_token on this same table must remain unreadable.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT (planned_start_utc) ON movie_night_sessions TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        "GRANT SELECT (planned_start_utc) ON movie_night_sessions TO mcu_backup; END IF; "
        "END $$"
    )


def downgrade() -> None:
    op.drop_column("movie_night_sessions", "planned_start_utc")
