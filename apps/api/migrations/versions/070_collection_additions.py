"""Mark's additions preference and successful collection-add receipts (AB3).

Revision ID: 070
Revises: 069
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from src.models.base import UTC_NOW

revision: str = "070"
down_revision: str | None = "069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CATEGORIES = "'deals', 'sale_events', 'releases', 'loans', 'movie_night', 'attention'"


def upgrade() -> None:
    op.drop_constraint("ck_notifications_category", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_category",
        "notifications",
        f"category IN ({_OLD_CATEGORIES}, 'collection_additions')",
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "collection_additions_enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
    )
    op.create_table(
        "collection_add_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("response_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at_utc", sa.DateTime(timezone=False), nullable=False, server_default=UTC_NOW
        ),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["collection_items.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_collection_add_request"),
    )
    for role in ("mcu_readonly", "mcu_backup"):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN "
            f"GRANT SELECT (collection_additions_enabled) ON notification_preferences TO {role}; "
            f"GRANT SELECT ON collection_add_requests TO {role}; END IF; END $$"
        )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM notifications "
        "WHERE category='collection_additions') THEN "
        "RAISE EXCEPTION 'Retain addition notifications; downgrade 070 requires owner review'; "
        "END IF; END $$"
    )
    op.drop_constraint("ck_notifications_category", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_category", "notifications", f"category IN ({_OLD_CATEGORIES})"
    )
    op.drop_table("collection_add_requests")
    op.drop_column("notification_preferences", "collection_additions_enabled")
