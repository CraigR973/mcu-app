"""set_updated_at uses clock_timestamp, not now()

Revision ID: 009
Revises: 008
Create Date: 2026-09-08

``NOW()`` in Postgres is the **transaction start time**, not the moment of the statement.
For a column meaning "when was this row last modified" that is wrong in two ways, and
Batch 8 turned the second one into a defect rather than a curiosity:

1. **Every row written by one transaction carries the same timestamp.** The collection
   import writes 1,857 rows in a handful of transactions, so their ``updated_at`` values
   say when the import began rather than when each row was written.

2. **``updated_at`` is now a concurrency token.** Batch 8 lets a client send the
   ``updatedAt`` its edit was based on so a queued offline write cannot overwrite a newer
   change (`DECISIONS.md` #42). A token that does not advance when the row changes cannot
   detect that the row changed — and two updates inside one transaction produced
   *identical* tokens, so the guard silently passed anything.

   Caught by this batch's own tests in CI, where the whole test runs in one transaction
   and the "someone else edited it first" setup therefore produced no change at all.

``clock_timestamp()`` is the actual wall clock at statement execution and advances within
a transaction. It stays wrapped in ``AT TIME ZONE 'utc'`` for the same reason ``NOW()``
was: every timestamp column here is naive UTC, and an unwrapped value would be cast using
the *session* time zone.

The function is shared by every ``*_set_updated_at`` trigger, so replacing it here updates
``movies``, ``collection_items``, ``watch_log`` and ``profiles`` together. No data is
rewritten; only future updates are affected.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = (clock_timestamp() AT TIME ZONE 'utc');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = (NOW() AT TIME ZONE 'utc');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
