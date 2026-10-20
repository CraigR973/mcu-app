"""every naive-UTC timestamp column defaults to UTC, whatever the session's time zone

Revision ID: 063
Revises: 062
Create Date: 2026-10-20

Every ``timestamp without time zone`` column here holds naive UTC (AGENTS.md), but 54 of them
defaulted to a bare ``now()``. ``now()`` is a ``timestamptz``, and Postgres casts it to a naive
timestamp in the **session's** time zone, so on any database not set to UTC each of those
defaults wrote local time. ``set_updated_at`` has always wrapped its value in
``AT TIME ZONE 'utc'`` (``003``, ``009``), so the two disagreed.

The stale-edit guard (#42) is where that bites. A disc inserted under Europe/London in summer
got an ``updated_at`` an hour *ahead* of UTC from the default; the first edit's trigger then
stamped true UTC, an hour *behind* it, so ``row.updated_at > baseUpdatedAt`` was false and a
stale edit was accepted. Found by the API suite on a local Postgres set to Europe/London; CI and
Neon run in UTC, so production has not met it.

``timezone('utc', now())`` is the same value as the trigger's ``now() AT TIME ZONE 'utc'``.
Only the defaults change: no row is rewritten, and ``SET DEFAULT`` is a catalogue update, not
a table rewrite. The downgrade puts the bare ``now()`` back.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "063"
down_revision: str | None = "062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Every column that defaulted to a bare ``now()`` at ``062``, read from the catalogue.
COLUMNS: tuple[tuple[str, str], ...] = (
    ("admin_actions", "created_at"),
    ("ai_conversations", "created_at"),
    ("ai_conversations", "updated_at"),
    ("ai_messages", "created_at_utc"),
    ("ai_settings", "created_at"),
    ("ai_settings", "updated_at"),
    ("ai_tool_calls", "created_at_utc"),
    ("ai_usage_log", "created_at_utc"),
    ("barcode_lookups", "confirmed_at_utc"),
    ("box_sets", "created_at"),
    ("box_sets", "updated_at"),
    ("calendar_feed_tokens", "created_at_utc"),
    ("collection_items", "created_at"),
    ("collection_items", "updated_at"),
    ("completion_sets", "created_at"),
    ("completion_sets", "updated_at"),
    ("deals", "first_seen_at_utc"),
    ("deals", "last_seen_at_utc"),
    ("ebay_targets", "created_at_utc"),
    ("identify_doubts", "created_utc"),
    ("identify_lookups", "created_utc"),
    ("item_photos", "created_at_utc"),
    ("loans", "created_at"),
    ("loans", "updated_at"),
    ("movie_credits", "created_at"),
    ("movie_night_participants", "joined_at_utc"),
    ("movie_night_sessions", "created_at"),
    ("movie_night_sessions", "updated_at"),
    ("movie_night_suggestions", "created_at_utc"),
    ("movie_night_votes", "created_at_utc"),
    ("movie_title_aliases", "created_utc"),
    ("movies", "created_at"),
    ("movies", "updated_at"),
    ("notification_preferences", "created_at"),
    ("notification_preferences", "updated_at"),
    ("notifications", "created_at_utc"),
    ("price_checks", "checked_at"),
    ("price_history_daily", "created_at_utc"),
    ("profiles", "created_at"),
    ("profiles", "updated_at"),
    ("push_subscriptions", "created_at"),
    ("push_subscriptions", "updated_at"),
    ("release_calendar", "added_at"),
    ("release_calendar", "updated_at"),
    ("retailers", "added_at"),
    ("retailers", "updated_at"),
    ("smart_collections", "created_at"),
    ("smart_collections", "updated_at"),
    ("spec_candidates", "created_utc"),
    ("spec_lookups", "created_utc"),
    ("wanted_list", "added_at"),
    ("wanted_list", "updated_at"),
    ("watch_log", "created_at"),
    ("watch_log", "updated_at"),
)


def upgrade() -> None:
    for table, column in COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT timezone('utc', now())")


def downgrade() -> None:
    for table, column in COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT now()")
