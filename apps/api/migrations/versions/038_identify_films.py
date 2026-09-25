"""identify films — the films TMDB never matched, what became of each, and their old titles

Revision ID: 038
Revises: 037
Create Date: 2026-09-25

Batch T9. Three tables:

- ``identify_runs``: one per live run of a plan, with the Brave searches the plan spent, so
  they count against the monthly ceiling T7's batches share. One runs at a time.
- ``identify_lookups``: one per film identification has looked at: waiting for Craig with
  its candidates, identified, set aside as TV or not a film, or skipped.
- ``movie_title_aliases``: a title a film used to have. Identification retitles
  "Peepiing Tom" as "Peeping Tom", and the spreadsheet still says "Peepiing Tom", so the
  collection refresh looks films up by these as well as by their titles (`DECISIONS.md`
  #198's guard). Every alias is also in the audit log, which is where the downgrade's loss
  would be recovered from.

The first two hold working state the next run rebuilds, so the downgrade drops them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "038"
down_revision: str | None = "037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identify_runs",
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
        sa.Column("planned_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("searches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("films", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("identified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("set_aside", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("trigger IN ('job', 'admin')", name="ck_identify_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running', 'finished', 'stopped', 'abandoned')",
            name="ck_identify_runs_status",
        ),
        sa.CheckConstraint("searches >= 0", name="ck_identify_runs_searches"),
    )
    op.create_index("ix_identify_runs_started_utc", "identify_runs", ["started_utc"])
    op.create_index(
        "uq_identify_runs_one_running",
        "identify_runs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "identify_lookups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("set_aside_as", sa.Text(), nullable=True),
        sa.Column("how", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "candidates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("proposed_tmdb_id", sa.Integer(), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("replaced_title", sa.Text(), nullable=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identify_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_utc", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("movie_id", name="uq_identify_lookups_movie"),
        sa.CheckConstraint(
            "status IN ('needs_you', 'identified', 'set_aside', 'skipped')",
            name="ck_identify_lookups_status",
        ),
        sa.CheckConstraint(
            "(status = 'set_aside') = (set_aside_as IS NOT NULL)",
            name="ck_identify_lookups_set_aside_as",
        ),
        sa.CheckConstraint(
            "set_aside_as IS NULL OR set_aside_as IN ('tv', 'not_film')",
            name="ck_identify_lookups_set_aside_kind",
        ),
        sa.CheckConstraint(
            "how IS NULL OR how IN ('auto', 'picked', 'searched')",
            name="ck_identify_lookups_how",
        ),
        sa.CheckConstraint(
            "(status = 'identified') = (tmdb_id IS NOT NULL)",
            name="ck_identify_lookups_tmdb_when_identified",
        ),
    )
    op.create_index("ix_identify_lookups_status", "identify_lookups", ["status"])

    op.create_table(
        "movie_title_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="identification"),
        sa.Column(
            "created_utc", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("movie_id", "title", name="uq_movie_title_aliases_movie_title"),
        sa.CheckConstraint("source IN ('identification')", name="ck_movie_title_aliases_source"),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_movie_title_aliases_title"),
    )
    op.create_index("ix_movie_title_aliases_movie", "movie_title_aliases", ["movie_id"])


def downgrade() -> None:
    op.drop_index("ix_movie_title_aliases_movie", table_name="movie_title_aliases")
    op.drop_table("movie_title_aliases")
    op.drop_index("ix_identify_lookups_status", table_name="identify_lookups")
    op.drop_table("identify_lookups")
    op.drop_index("uq_identify_runs_one_running", table_name="identify_runs")
    op.drop_index("ix_identify_runs_started_utc", table_name="identify_runs")
    op.drop_table("identify_runs")
