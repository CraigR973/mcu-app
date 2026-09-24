"""spec backfill — finding each disc's Blu-ray.com page, and the batches that do it

Revision ID: 037
Revises: 036
Create Date: 2026-09-24

Batch T7, `DECISIONS.md` #202. Three tables:

- ``spec_runs``: one per batch, with its Brave search budget and its Blu-ray.com fetch
  budget, and what it did. The partial unique index allows one running batch at a time.
- ``spec_lookups``: one per disc searched for, with where it stands and why.
- ``spec_candidates``: the pages each search proposed, as the matcher judged them.

Both page columns are held to Blu-ray.com's release path by a CHECK, so no bug can store a
search route or another site. Everything here is working state the next batch can rebuild,
so the downgrade drops it; the specs themselves live on ``collection_items``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "037"
down_revision: str | None = "036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RELEASE_PATH = r"~ '^https?://(www\.)?blu-ray\.com/movies/'"


def upgrade() -> None:
    op.create_table(
        "spec_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column(
            "started_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("heartbeat_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("finished_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("search_budget", sa.Integer(), nullable=False),
        sa.Column("searches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("searched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_match", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("restored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetch_budget", sa.Integer(), nullable=False),
        sa.Column("fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("applied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_back", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetch_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("trigger IN ('job', 'admin')", name="ck_spec_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running', 'finished', 'budget_spent', 'stopped', 'halted', 'abandoned')",
            name="ck_spec_runs_status",
        ),
        sa.CheckConstraint(
            "search_budget >= 0 AND fetch_budget >= 0 AND searches >= 0",
            name="ck_spec_runs_counts",
        ),
    )
    op.create_index("ix_spec_runs_started_utc", "spec_runs", ["started_utc"])
    op.create_index(
        "uq_spec_runs_one_running",
        "spec_runs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "spec_lookups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "collection_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collection_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("accepted_url", sa.Text(), nullable=True),
        sa.Column("how", sa.Text(), nullable=True),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("search_query", sa.Text(), nullable=True),
        sa.Column("searched_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spec_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_utc", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("collection_item_id", name="uq_spec_lookups_item"),
        sa.CheckConstraint(
            "status IN ('needs_you', 'no_match', 'accepted', 'done', 'skipped')",
            name="ck_spec_lookups_status",
        ),
        sa.CheckConstraint(
            "how IS NULL OR how IN ('auto', 'confirmed', 'pasted', 'restored')",
            name="ck_spec_lookups_how",
        ),
        sa.CheckConstraint(
            "(status IN ('accepted', 'done')) = (accepted_url IS NOT NULL)",
            name="ck_spec_lookups_url_when_chosen",
        ),
        sa.CheckConstraint(
            f"accepted_url IS NULL OR accepted_url {RELEASE_PATH}",
            name="ck_spec_lookups_release_path",
        ),
    )
    op.create_index("ix_spec_lookups_status", "spec_lookups", ["status"])

    op.create_table(
        "spec_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "lookup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spec_lookups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("format_label", sa.Text(), nullable=True),
        sa.Column("edition", sa.Text(), nullable=True),
        sa.Column("matches", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("origin", sa.Text(), nullable=False, server_default="search"),
        sa.Column(
            "created_utc", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("lookup_id", "url", name="uq_spec_candidates_lookup_url"),
        sa.CheckConstraint(f"url {RELEASE_PATH}", name="ck_spec_candidates_release_path"),
        sa.CheckConstraint("origin IN ('search', 'restored')", name="ck_spec_candidates_origin"),
    )


def downgrade() -> None:
    op.drop_table("spec_candidates")
    op.drop_index("ix_spec_lookups_status", table_name="spec_lookups")
    op.drop_table("spec_lookups")
    op.drop_index("uq_spec_runs_one_running", table_name="spec_runs")
    op.drop_index("ix_spec_runs_started_utc", table_name="spec_runs")
    op.drop_table("spec_runs")
