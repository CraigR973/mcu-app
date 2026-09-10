"""create ai_usage_log and ai_settings

Revision ID: 022
Revises: 021
Create Date: 2026-09-10

Batch 30 — roadmap §9.1 and §9.7.

**`ai_usage_log` is one row per call to the model, not per chat message.** §9.1 asks for
"token + cost logging per message" and §9.7 needs a daily total to enforce against; both
are questions about *requests*, and a request is what has tokens. Batch 31 adds the
conversation and message tables the chat UI reads — keeping them apart means the usage log
survives a conversation being deleted, which is the only way "what did I spend last month"
stays answerable.

**`cost_usd` is `NUMERIC(10,6)`, not money's usual two places.** One short question costs a
small fraction of a penny; rounding each call to the nearest cent would record every one of
them as zero and make the cost cap unenforceable. Rounding belongs where a total is shown.

**A failed call is still a row.** It has tokens (the input was sent and billed even when
the response never arrived) and it is the only record of *why* the assistant did not
answer. A log that only holds successes cannot explain an outage — which is exactly the
shape of the TMDB failure this project keeps learning from.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # The id actually used, recorded per row rather than read from config later: config
        # changes, and a historic row must keep describing the call that happened.
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        # Priced at the rate in force when the call was made. Never back-applied.
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("stop_reason", sa.String(40), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        # Set when the call failed. The row exists either way — see the module docstring.
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("input_tokens >= 0", name="ck_ai_usage_input_tokens"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_ai_usage_output_tokens"),
        sa.CheckConstraint("cache_read_tokens >= 0", name="ck_ai_usage_cache_read"),
        sa.CheckConstraint("cache_write_tokens >= 0", name="ck_ai_usage_cache_write"),
        sa.CheckConstraint("cost_usd >= 0", name="ck_ai_usage_cost"),
    )
    # The cap's own query: this person, today. Composite and in this order because the
    # lookup is always "one user, a date range" and never a range across everybody.
    op.create_index("ix_ai_usage_log_user_created", "ai_usage_log", ["user_id", "created_at_utc"])

    op.create_table(
        "ai_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # §9.7's "per-user daily message / cost cap". Defaults come from config on first
        # read rather than being seeded, so a profile added later is not left capless.
        sa.Column("daily_message_cap", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("daily_cost_cap_usd", sa.Numeric(8, 2), nullable=False, server_default="2.00"),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        # A cap of zero is meaningful — "no AI for me" — so the floor is 0, not 1. The
        # ceilings stop a typo becoming an unbounded bill.
        sa.CheckConstraint(
            "daily_message_cap >= 0 AND daily_message_cap <= 10000",
            name="ck_ai_settings_message_cap",
        ),
        sa.CheckConstraint(
            "daily_cost_cap_usd >= 0 AND daily_cost_cap_usd <= 1000",
            name="ck_ai_settings_cost_cap",
        ),
    )
    op.create_index("ix_ai_settings_user_id", "ai_settings", ["user_id"], unique=True)
    op.execute(
        """
        CREATE TRIGGER ai_settings_set_updated_at
        BEFORE UPDATE ON ai_settings
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ai_settings_set_updated_at ON ai_settings;")
    op.drop_index("ix_ai_settings_user_id", table_name="ai_settings")
    op.drop_table("ai_settings")
    op.drop_index("ix_ai_usage_log_user_created", table_name="ai_usage_log")
    op.drop_table("ai_usage_log")
