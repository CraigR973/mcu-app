"""the daily check: each job's heartbeat, each check's result, and escalating PIN locks

Revision ID: 050
Revises: 049
Create Date: 2026-10-12

Batch X2, "Failures reach Craig" (DS44-01, DS44-05, UX48-02's screens).

- ``job_heartbeats``: one row per scheduled job (and the API itself), rewritten every time it
  runs, whatever it did: ran, nothing due, budget spent. Before X2 the spec, valuation and eBay
  jobs wrote nothing when there was nothing to do, so idle and stopped looked alike. The API's
  row carries its readiness at boot, which only the API process can see.
- ``health_checks``: the daily check's latest result for each check, ok or not, with when a
  problem first appeared and when Craig was pushed about it, so a problem is pushed once, not
  every morning it persists.
- ``profiles.lockout_count`` and ``profiles.last_lockout_utc``: how many times a profile has
  locked within a day of the last time, for the escalating lock (15 minutes, 1 hour, 4 hours,
  24 hours), and for the check's "locked in the last day".
- ``notifications.category`` may be ``attention``: the push the check sends Craig when a
  problem first appears. It has no toggle; only the admin receives it.

**Nothing to backfill.** The read-only role is granted the two tables and the two columns,
guarded so CI's database (which has no such role) still migrates; none holds a credential.

The downgrade drops the tables and the columns, deletes any ``attention`` notifications (they
say what was wrong on a day, nothing more) and restores the five categories.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

_CATEGORIES = ("deals", "sale_events", "releases", "loans", "movie_night")

revision: str = "050"
down_revision: str | None = "049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_heartbeats",
        sa.Column("job", sa.Text(), primary_key=True),
        sa.Column("beat_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
    )
    op.create_table(
        "health_checks",
        sa.Column("check_key", sa.Text(), primary_key=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("checked_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("failing_since_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("pushed_utc", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("lockout_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "profiles", sa.Column("last_lockout_utc", sa.DateTime(timezone=False), nullable=True)
    )
    op.drop_constraint("ck_notifications_category", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_category",
        "notifications",
        "category IN (" + ", ".join(f"'{c}'" for c in (*_CATEGORIES, "attention")) + ")",
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT ON job_heartbeats, health_checks TO mcu_readonly; "
        "GRANT SELECT (lockout_count, last_lockout_utc) ON profiles TO mcu_readonly; "
        "END IF; END $$"
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE category = 'attention'")
    op.drop_constraint("ck_notifications_category", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_category",
        "notifications",
        "category IN (" + ", ".join(f"'{c}'" for c in _CATEGORIES) + ")",
    )
    op.drop_column("profiles", "last_lockout_utc")
    op.drop_column("profiles", "lockout_count")
    op.drop_table("health_checks")
    op.drop_table("job_heartbeats")
