"""a line from Mark to Craig, held until Craig clears it

Revision ID: 062
Revises: 061
Create Date: 2026-10-18

Batch X12a (UX48-05's "Tell Craig", #282). Mark had no way to say "this is wrong" from the app
except a chat message outside it. A line typed on his You page lands here and in Home's "Needs
attention" row (X2) for Craig, who clears it once he has read it.

One small table: who, what (at most 300 characters, checked in the database as well as at the
API), when, and when it was cleared. ``ON DELETE SET NULL`` on the author, so a note outlives
the profile. Both read-only roles are granted it, guarded so CI's database (which has neither)
still migrates; a note is prose a person typed, never a credential.

The downgrade drops the table and its notes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "062"
down_revision: str | None = "061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "craig_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "from_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("cleared_utc", sa.DateTime(timezone=False), nullable=True),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 300", name="ck_craig_notes_body_length"
        ),
    )
    op.create_index(
        "ix_craig_notes_open",
        "craig_notes",
        ["created_utc"],
        postgresql_where=sa.text("cleared_utc IS NULL"),
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT ON craig_notes TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        "GRANT SELECT ON craig_notes TO mcu_backup; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_index("ix_craig_notes_open", table_name="craig_notes")
    op.drop_table("craig_notes")
