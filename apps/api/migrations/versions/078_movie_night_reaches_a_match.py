"""AE10 (#355): movie night that reaches a match — who is choosing now, and what was logged.

Three nullable columns, no table, nothing backfilled:

- ``movie_night_participants.last_seen_utc``: when each person last had the night open, so
  the other person's line can say "choosing now" (proposal C). Stamped by the night's own
  reads, votes and suggestions.
- ``movie_night_sessions.logged_suggestion_id`` and ``logged_at_utc``: which match "Log it for
  both of us" logged, and when (proposal D), so it cannot log the same night twice. No foreign
  key, as with ``matched_suggestion_id`` (migration 061): a suggestion already points at its
  session, and a second constraint the other way is a cycle the restore drill refuses.

Revision ID: 078
Revises: 077
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "078"
down_revision: str | None = "077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _grant(table: str, columns: str) -> None:
    """Column grants to the read-only and backup roles, guarded for CI's database, which has
    neither. Column by column: ``invite_token`` on ``movie_night_sessions`` must stay unreadable,
    and a column grant on a table already granted whole is harmless."""
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        f"GRANT SELECT ({columns}) ON {table} TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        f"GRANT SELECT ({columns}) ON {table} TO mcu_backup; END IF; "
        "END $$"
    )


def upgrade() -> None:
    op.add_column(
        "movie_night_participants",
        sa.Column("last_seen_utc", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "movie_night_sessions",
        sa.Column("logged_suggestion_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "movie_night_sessions",
        sa.Column("logged_at_utc", sa.DateTime(timezone=False), nullable=True),
    )
    _grant("movie_night_participants", "last_seen_utc")
    _grant("movie_night_sessions", "logged_suggestion_id, logged_at_utc")


def downgrade() -> None:
    op.drop_column("movie_night_sessions", "logged_at_utc")
    op.drop_column("movie_night_sessions", "logged_suggestion_id")
    op.drop_column("movie_night_participants", "last_seen_utc")
