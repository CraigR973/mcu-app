"""create notification_preferences and admin_actions tables

notification_preferences — one row per user; controls which push-alert categories
are active and whether to use realtime, daily, or weekly digest mode.

admin_actions — immutable audit log of every create/update/delete the admin
performs; retained for 2 years then archived.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_DIGEST_MODE = ("realtime", "daily", "weekly")


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # notification_preferences — user_id is both PK and FK (one row per user)
    # -------------------------------------------------------------------------
    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "price_drops",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "deals",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "new_releases",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "loan_reminders",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "purchase_candidates",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "on_this_day",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "digest_mode",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'realtime'"),
        ),
        # Time-of-day for digest delivery, e.g. '09:00'
        sa.Column("digest_send_time", sa.Time()),
        sa.Column("quiet_hours_start", sa.Time()),
        sa.Column("quiet_hours_end", sa.Time()),
    )

    op.create_check_constraint(
        "ck_notification_preferences_digest_mode",
        "notification_preferences",
        f"digest_mode IN {_DIGEST_MODE}",
    )

    # -------------------------------------------------------------------------
    # admin_actions — append-only audit log; never soft-deleted
    # -------------------------------------------------------------------------
    op.create_table(
        "admin_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        ),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("target_table", sa.String(50), nullable=False),
        sa.Column("target_id", sa.Text()),
        # JSON diff: {"old": {...}, "new": {...}}
        sa.Column("changes", JSONB()),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index("idx_admin_actions_user_id", "admin_actions", ["user_id"])
    op.create_index("idx_admin_actions_target_table", "admin_actions", ["target_table"])
    op.create_index("idx_admin_actions_timestamp", "admin_actions", ["timestamp"])
    # "What changed this month" queries
    op.create_index(
        "idx_admin_actions_table_timestamp",
        "admin_actions",
        ["target_table", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("idx_admin_actions_table_timestamp", table_name="admin_actions")
    op.drop_index("idx_admin_actions_timestamp", table_name="admin_actions")
    op.drop_index("idx_admin_actions_target_table", table_name="admin_actions")
    op.drop_index("idx_admin_actions_user_id", table_name="admin_actions")
    op.drop_table("admin_actions")

    op.drop_constraint(
        "ck_notification_preferences_digest_mode",
        "notification_preferences",
        type_="check",
    )
    op.drop_table("notification_preferences")
