"""create admin_actions

Revision ID: 008
Revises: 007
Create Date: 2026-09-08

Roadmap §3.20's audit log — the table Batch 7's acceptance criterion turns on: *"the
audit log records actor, action and target **and survives deletion of the target row**"*.

**``target_id`` is TEXT and carries no foreign key** (`DECISIONS.md` #5). §3.20's table
types it as UUID, and the decision supersedes that: a foreign key would either block the
delete or cascade the evidence away, which defeats the point of keeping the log. TEXT
rather than a bare UUID column so a future target that is not a UUID — a spreadsheet row
number for ``bulk_import``, a composite key — still has somewhere to go.

**``user_id`` is ``SET NULL``, not ``CASCADE``.** Same reasoning applied to the actor:
losing a profile must not silently erase what that profile did. Profiles are soft-deleted
in normal operation and there are only ever two of them, so this is a guard rather than a
path anything is expected to take.

There is deliberately **no ``updated_at``**. An audit row is a statement about a moment;
editing one is not a thing the application should be able to do, so it gets ``created_at``
alone and no ``set_updated_at`` trigger.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("target_table", sa.String(50), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="SET NULL"),
        # §3.20's vocabulary. Constrained in the database rather than only in Pydantic
        # because the log's value is that it can be trusted later: a typo'd action_type
        # would quietly drop rows out of every filtered read of it.
        sa.CheckConstraint(
            "action_type IN ('create', 'update', 'delete', 'restore', 'bulk_import')",
            name="ck_admin_actions_action_type",
        ),
    )

    # "What happened to this disc?" — the item history the detail page reads for §3.11's
    # condition history, and the only query shape that runs per page view.
    op.create_index(
        "ix_admin_actions_target",
        "admin_actions",
        ["target_table", "target_id", sa.text("created_at DESC")],
    )
    # "What changed this month?" — §3.20's stated second query, and the audit log UI's
    # default ordering.
    op.create_index(
        "ix_admin_actions_created_at",
        "admin_actions",
        [sa.text("created_at DESC")],
    )
    op.create_index("ix_admin_actions_user_id", "admin_actions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_actions_user_id", table_name="admin_actions")
    op.drop_index("ix_admin_actions_created_at", table_name="admin_actions")
    op.drop_index("ix_admin_actions_target", table_name="admin_actions")
    op.drop_table("admin_actions")
