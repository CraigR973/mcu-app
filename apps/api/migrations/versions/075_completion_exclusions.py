"""Completion films that do not count, per set (AE3, #355). Frozen DDL; no application imports.

Revision ID: 075
Revises: 074
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "075"
down_revision: str | None = "074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "completion_exclusions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("excluded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "excluded_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["set_id"], ["completion_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["excluded_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("set_id", "tmdb_id", name="uq_completion_exclusion"),
        sa.CheckConstraint("tmdb_id > 0", name="ck_completion_exclusion_tmdb_id"),
    )
    # The read-only and backup roles, guarded and in one block, so CI's database (which has
    # neither role) still migrates. The table holds no credential.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname='mcu_readonly') THEN "
        "GRANT SELECT ON completion_exclusions TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname='mcu_backup') THEN "
        "GRANT SELECT ON completion_exclusions TO mcu_backup; END IF; "
        "END $$"
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM completion_exclusions) THEN "
        "RAISE EXCEPTION 'Completion films are set not to count; downgrade 075 requires owner "
        "review'; END IF; END $$"
    )
    op.drop_table("completion_exclusions")
