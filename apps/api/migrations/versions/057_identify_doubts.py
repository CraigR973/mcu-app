"""identification in doubt: a proposal about a film already identified

Revision ID: 057
Revises: 056
Create Date: 2026-10-15

Batch X9, CT46-01 and CT46-03. 30 copies are confidently the wrong film, and the app already
sees some of them: a disc page or a review for the copy's own title in another year only
parked the disc on Disc specs with "pick the right page". ``identify_doubts`` holds one
proposal that an identified film is the wrong one, from the re-check of the old paths'
films (``recheck``), the spec job (``specs``) or the review job (``review``), with the
evidence, the films offered and the copy it is about. It waits on Identify films while
``open``; Craig keeps the film (``kept``), identifies it again (``corrected``) or moves the
copy to another film (``moved``). ``decided_action_id`` is the audit row of the change that
settled it, so undoing that change opens the doubt again.

One open doubt per film and source, or per copy and source when it names a copy.

Granted to both read-only roles, guarded so CI's database (which has neither) still
migrates (``AGENTS.md``, "Cloud sessions"). It holds no credential.

The downgrade drops the table: the films stay as they are, and the doubts are lost.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "057"
down_revision: str | None = "056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identify_doubts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "collection_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collection_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("identified_as", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "candidates",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("proposed_tmdb_id", sa.Integer(), nullable=True),
        sa.Column("search_hint", sa.Text(), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("decided_action_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source IN ('recheck', 'specs', 'review')", name="ck_identify_doubts_source"
        ),
        sa.CheckConstraint(
            "status IN ('open', 'kept', 'corrected', 'moved')", name="ck_identify_doubts_status"
        ),
        sa.CheckConstraint(
            "(status = 'open') = (decided_utc IS NULL)", name="ck_identify_doubts_decided"
        ),
        sa.CheckConstraint("length(btrim(note)) > 0", name="ck_identify_doubts_note"),
    )
    op.create_index("ix_identify_doubts_movie", "identify_doubts", ["movie_id"])
    op.create_index("ix_identify_doubts_status", "identify_doubts", ["status"])
    op.create_index(
        "uq_identify_doubts_open_film",
        "identify_doubts",
        ["movie_id", "source"],
        unique=True,
        postgresql_where=sa.text("status = 'open' AND collection_item_id IS NULL"),
    )
    op.create_index(
        "uq_identify_doubts_open_copy",
        "identify_doubts",
        ["collection_item_id", "source"],
        unique=True,
        postgresql_where=sa.text("status = 'open' AND collection_item_id IS NOT NULL"),
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT ON identify_doubts TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        "GRANT SELECT ON identify_doubts TO mcu_backup; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_index("uq_identify_doubts_open_copy", table_name="identify_doubts")
    op.drop_index("uq_identify_doubts_open_film", table_name="identify_doubts")
    op.drop_index("ix_identify_doubts_status", table_name="identify_doubts")
    op.drop_index("ix_identify_doubts_movie", table_name="identify_doubts")
    op.drop_table("identify_doubts")
