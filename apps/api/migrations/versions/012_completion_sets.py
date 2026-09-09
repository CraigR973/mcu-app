"""create completion_sets

Revision ID: 012
Revises: 011
Create Date: 2026-09-09

Roadmap §3.15 — the cached reference filmographies behind Batch 13's phases 11.1 and 11.2.

**Empty on creation.** The rows are written by `src/scripts/refresh_completion_sets.py`,
which calls TMDB; a migration cannot and should not make network requests. CI's migration
job runs against an empty schema and so proves this applies and reverses, which is all
there is to prove here (`STATUS.md` gotcha 18).

Two shapes differ from §3.15 as drawn:

**``member_tmdb_ids`` is ``INTEGER[]``, not JSONB.** §3.15 says "JSONB | Array of TMDB
movie IDs". The whole purpose of the column is the intersection with ``movies.tmdb_id``
that §3.15's own note describes, and a Postgres array does that with `&&`/`unnest` and a
GIN index. JSONB would make the one query the table exists for the slow path.

**``metadata`` gains a defined shape: ``{"members": [{tmdbId, title, year, posterPath}]}``.**
§11.2 asks for a missing-films list *with posters*, and a missing film is precisely one
this database has no row for — so the display fields have to be cached here or fetched
from TMDB per film, per view, forever.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SET_TYPES = ("director", "actor", "franchise", "box_set", "award", "curated_list")


def upgrade() -> None:
    op.create_table(
        "completion_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("set_type", sa.String(50), nullable=False),
        sa.Column("set_key", sa.String(255), nullable=False),
        sa.Column("set_name", sa.String(255), nullable=False),
        sa.Column(
            "member_tmdb_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{}'::integer[]"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_refreshed", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "set_type IN (" + ", ".join(f"'{value}'" for value in SET_TYPES) + ")",
            name="ck_completion_sets_set_type",
        ),
        # What makes the refresh idempotent: a second run updates Hitchcock's row rather
        # than adding a second Hitchcock. 11.1's third acceptance clause — "re-running
        # after a TMDB change updates the affected rows" — is this constraint.
        sa.UniqueConstraint("set_type", "set_key", name="uq_completion_sets_type_key"),
    )
    op.create_index("ix_completion_sets_set_type", "completion_sets", ["set_type"])
    # The insights page's one real query: which of these ids do we own?
    op.create_index(
        "ix_completion_sets_members",
        "completion_sets",
        ["member_tmdb_ids"],
        postgresql_using="gin",
    )
    op.execute(
        """
        CREATE TRIGGER completion_sets_set_updated_at
        BEFORE UPDATE ON completion_sets
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS completion_sets_set_updated_at ON completion_sets;")
    op.drop_index("ix_completion_sets_members", table_name="completion_sets")
    op.drop_index("ix_completion_sets_set_type", table_name="completion_sets")
    op.drop_table("completion_sets")
