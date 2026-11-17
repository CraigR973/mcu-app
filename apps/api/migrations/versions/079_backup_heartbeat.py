"""AG2 (DS50-01): the weekly backup writes its own heartbeat, and nothing else.

The backup workflow reads the database as ``mcu_backup``, which can read every table but holds
no credential and writes nothing (X4, #268). For the daily check to see the backup at all, the
run must leave a row in ``job_heartbeats``. Rather than give the role write access to that table
(it could then forge any job's heartbeat), one function writes the ``backup`` row and no other:

``record_backup_heartbeat(outcome, detail)`` upserts ``job = 'backup'`` with the clock's UTC
time. It runs as its owner (``SECURITY DEFINER``) with a pinned ``search_path``, its execute
right is taken from ``PUBLIC``, and only ``mcu_backup`` is granted it, guarded for CI's database,
which has no such role. No table, column or row changes.

Revision ID: 079
Revises: 078
Create Date: 2026-11-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "079"
down_revision: str | None = "078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SIGNATURE = "record_backup_heartbeat(text, jsonb)"


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION record_backup_heartbeat(p_outcome text, p_detail jsonb)
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            INSERT INTO job_heartbeats (job, beat_utc, outcome, detail)
            VALUES ('backup', timezone('utc', now()), left(p_outcome, 200), p_detail)
            ON CONFLICT (job) DO UPDATE
            SET beat_utc = EXCLUDED.beat_utc,
                outcome = EXCLUDED.outcome,
                detail = EXCLUDED.detail;
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO mcu_backup; END IF; END $$"
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {SIGNATURE}")
