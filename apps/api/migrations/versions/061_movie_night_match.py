"""a movie night remembers the film it matched on

Revision ID: 061
Revises: 060
Create Date: 2026-10-18

Batch X12a (UX48-05, #282). A match lived only in the live event and in the push, so a push
opened a night that showed none (the review's walk, 11 Oct). The session now holds the
suggestion its latest match was about; the night page reads it back. The votes stay the
truth: nothing is derived from this column, it only remembers the last announcement.

Nullable, no backfill: sessions that matched before this keep showing none, and no live row is
written by the migration. **No foreign key:** a suggestion already points at its session, and a
constraint the other way is a cycle that the weekly copy's restore drill refuses (it orders
tables by foreign keys). Suggestions go only with their session; a read that finds none shows
no match. The roles read this table column by column (``invite_token`` is a credential), so
the new column is granted to both, guarded so CI's database (which has neither role) still
migrates. It holds no credential.

The downgrade drops the column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "061"
down_revision: str | None = "060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "movie_night_sessions",
        sa.Column("matched_suggestion_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT (matched_suggestion_id) ON movie_night_sessions TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        "GRANT SELECT (matched_suggestion_id) ON movie_night_sessions TO mcu_backup; END IF; "
        "END $$"
    )


def downgrade() -> None:
    op.drop_column("movie_night_sessions", "matched_suggestion_id")
