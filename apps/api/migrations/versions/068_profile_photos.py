"""Private profile pictures (AA7), no backfill or credential grants.

Revision ID: 068
Revises: 067
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "068"
down_revision: str | None = "067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profile_photos",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "octet_length(data) BETWEEN 1 AND 307200", name="ck_profile_photo_size"
        ),
    )
    for role in ("mcu_readonly", "mcu_backup"):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN "
            f"GRANT SELECT ON profile_photos TO {role}; END IF; END $$"
        )


def downgrade() -> None:
    op.drop_table("profile_photos")
