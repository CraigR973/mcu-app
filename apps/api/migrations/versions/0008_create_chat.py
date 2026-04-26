"""create chat_conversations and chat_messages tables

chat_conversations — top-level container for an AI assistant chat session per user.

chat_messages — individual turns (user, assistant, tool roles) with token/cost
tracking for per-user API usage caps and audit trails.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_MSG_ROLE = ("user", "assistant", "tool")
_INPUT_METHOD = ("text", "voice")


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # chat_conversations — one row per named conversation thread
    # -------------------------------------------------------------------------
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Auto-generated from first user message
        sa.Column("title", sa.String(255)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index("idx_chat_conversations_user_id", "chat_conversations", ["user_id"])
    op.create_index("idx_chat_conversations_updated_at", "chat_conversations", ["updated_at"])

    op.execute("""
        CREATE TRIGGER chat_conversations_set_updated_at
        BEFORE UPDATE ON chat_conversations
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    # -------------------------------------------------------------------------
    # chat_messages — individual turns; tool_calls/results stored as JSONB
    # -------------------------------------------------------------------------
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text()),
        # Populated for assistant messages that make tool calls
        sa.Column("tool_calls", JSONB()),
        sa.Column("tool_results", JSONB()),
        # text or voice; only relevant for role='user'
        sa.Column("input_method", sa.String(20), server_default=sa.text("'text'")),
        # Claude API billing counters
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        # Estimated cost in integer cents for usage-cap queries
        sa.Column("cost_cents", sa.Integer()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_chat_messages_role",
        "chat_messages",
        f"role IN {_MSG_ROLE}",
    )
    op.create_check_constraint(
        "ck_chat_messages_input_method",
        "chat_messages",
        f"input_method IS NULL OR input_method IN {_INPUT_METHOD}",
    )
    op.create_check_constraint(
        "ck_chat_messages_tokens",
        "chat_messages",
        "input_tokens IS NULL OR input_tokens >= 0",
    )

    op.create_index("idx_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_index("idx_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("idx_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_constraint("ck_chat_messages_tokens", "chat_messages", type_="check")
    op.drop_constraint("ck_chat_messages_input_method", "chat_messages", type_="check")
    op.drop_constraint("ck_chat_messages_role", "chat_messages", type_="check")
    op.drop_table("chat_messages")

    op.execute("DROP TRIGGER IF EXISTS chat_conversations_set_updated_at ON chat_conversations;")
    op.drop_index("idx_chat_conversations_updated_at", table_name="chat_conversations")
    op.drop_index("idx_chat_conversations_user_id", table_name="chat_conversations")
    op.drop_table("chat_conversations")
