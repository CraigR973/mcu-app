"""create ai_conversations, ai_messages and ai_tool_calls

Revision ID: 023
Revises: 022
Create Date: 2026-09-10

Batch 31 — roadmap §9.2, §9.3 and §9.4.

**`ai_messages.content` stores the raw content blocks, not just the text.** The API is
stateless: every turn re-sends the whole conversation, and a turn that used a tool is
three messages — the assistant's `tool_use`, the `tool_result`, and the answer. Storing
only rendered text would make the history unreplayable, and the failure is subtle rather
than loud: Claude would answer as though the tool call had never happened.

**`ai_tool_calls` exists because §9.4's confirmation crosses an HTTP boundary.** Claude
asks to call a write tool, the browser has to show a prompt, and the answer arrives in a
*later request* — so the agent loop is suspended, not paused in memory. The pending call
is a row; confirming or cancelling it resumes the turn. Doing this with an in-process
future would lose every pending confirmation on the next deploy.

**A cancelled call is kept, not deleted.** "Cancelling aborts" is the acceptance criterion,
and the way to be sure nothing was left behind is to be able to read afterwards that the
call was asked for, refused, and never executed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "023"
down_revision: str | None = "022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Derived from the first question rather than asked for. Nobody titles a chat.
        sa.Column("title", sa.String(200), nullable=False, server_default="New conversation"),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.execute(
        """
        CREATE TRIGGER ai_conversations_set_updated_at
        BEFORE UPDATE ON ai_conversations
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    op.create_table(
        "ai_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        # The blocks exactly as the API produced or consumes them. This is what gets
        # replayed; `text` is only for rendering.
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        # Monotonic within a conversation. `created_at` alone is not enough: several
        # messages are written in one transaction, and `NOW()` is the transaction's start
        # time, so they would all share a timestamp and their order would be undefined
        # (gotcha 24).
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'tool_result')", name="ck_ai_messages_role"
        ),
        sa.CheckConstraint("jsonb_typeof(content) = 'array'", name="ck_ai_messages_content"),
    )
    op.create_index(
        "uq_ai_messages_sequence",
        "ai_messages",
        ["conversation_id", "sequence"],
        unique=True,
    )

    op.create_table(
        "ai_tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        # The API's own id for the call. The `tool_result` must quote it back exactly or
        # the conversation is rejected on the next turn.
        sa.Column("tool_use_id", sa.String(80), nullable=False),
        sa.Column("tool_name", sa.String(80), nullable=False),
        sa.Column(
            "tool_input",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # `pending` only ever applies to a write tool. Reads execute immediately — a
        # confirmation prompt for "search my collection" trains people to click yes.
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'failed')",
            name="ck_ai_tool_calls_status",
        ),
        # One row per call. Without this a double-tapped Confirm executes the write twice,
        # which for "add to wanted list" is two rows and for anything else is worse.
        sa.UniqueConstraint("tool_use_id", name="uq_ai_tool_calls_tool_use_id"),
    )
    op.create_index(
        "ix_ai_tool_calls_pending",
        "ai_tool_calls",
        ["conversation_id"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_ai_tool_calls_pending", table_name="ai_tool_calls")
    op.drop_table("ai_tool_calls")
    op.drop_index("uq_ai_messages_sequence", table_name="ai_messages")
    op.drop_table("ai_messages")
    op.execute("DROP TRIGGER IF EXISTS ai_conversations_set_updated_at ON ai_conversations;")
    op.drop_index("ix_ai_conversations_user_id", table_name="ai_conversations")
    op.drop_table("ai_conversations")
