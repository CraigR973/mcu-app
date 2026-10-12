"""why a device stopped: the person removed it, or the push service refused it

Revision ID: 051
Revises: 050
Create Date: 2026-10-12

Batch X3, "Push that heals itself" (DS44-02). One nullable column on ``push_subscriptions``:

- ``revoked_reason``: ``removed`` when the person took the device off their list, ``refused``
  when the push service answered 404 or 410. Before X3 a refused device was deleted with an
  info log, so nothing could say a phone had stopped, or when; Mark's phone was dropped on its
  first push (24 Sep) and Craig's on 8 Oct. A refused device is now kept, and the app
  registers the phone again on its next open; a removed one it leaves alone.

**Backfill:** every row already revoked was revoked by a person (the only path that revoked
before X3), so it is marked ``removed``; on 12 Oct production held two devices and neither
was revoked, so it touches no row there. The read-only role has no grant on
``push_subscriptions`` (it holds the devices' keys), and this column gets none either.

The downgrade drops the column; the devices stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "051"
down_revision: str | None = "050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("push_subscriptions", sa.Column("revoked_reason", sa.Text(), nullable=True))
    op.execute(
        "UPDATE push_subscriptions SET revoked_reason = 'removed' WHERE revoked_at_utc IS NOT NULL"
    )
    op.create_check_constraint(
        "ck_push_subscriptions_revoked_reason",
        "push_subscriptions",
        "(revoked_at_utc IS NULL) = (revoked_reason IS NULL) "
        "AND (revoked_reason IS NULL OR revoked_reason IN ('removed', 'refused'))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_push_subscriptions_revoked_reason", "push_subscriptions", type_="check")
    op.drop_column("push_subscriptions", "revoked_reason")
