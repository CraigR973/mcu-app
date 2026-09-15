"""drop gift_links

Revision ID: 030
Revises: 029
Create Date: 2026-09-15

Batch S1 — snag 4. `DECISIONS.md` #154's neighbour in the 2026-09-14 triage: the feature
was built in Batch 27 and **never used**. Measured against live Neon on 2026-09-14,
`gift_links` holds **0 rows** and has recorded **0 views**, so dropping it destroys nothing
and does not trip the close-out's destructive-operation stop, which `AGENTS.md` scopes to
"tables holding real rows".

**The downgrade recreates the table in full**, byte for byte with `018`'s upgrade —
constraints, indexes and both triggers. CI proves `upgrade head` → `downgrade base`, and
`018.downgrade` drops a table that must therefore exist by the time the chain reaches it.
A `downgrade` that merely passed would break the reversal at `018`, not here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "030"
down_revision: str | None = "029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The triggers go with the table, but naming them keeps the intent legible and makes
    # a partially-applied state recoverable.
    op.execute("DROP TRIGGER IF EXISTS gift_links_soft_delete ON gift_links;")
    op.execute("DROP TRIGGER IF EXISTS gift_links_set_updated_at ON gift_links;")
    op.drop_index("ix_gift_links_deleted_at", table_name="gift_links")
    op.drop_index("ix_gift_links_slug", table_name="gift_links")
    op.drop_table("gift_links")


def downgrade() -> None:
    op.create_table(
        "gift_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "filter_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_viewed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.CheckConstraint("length(slug) >= 16", name="ck_gift_links_slug_length"),
        sa.CheckConstraint("slug ~ '^[A-Za-z0-9_-]+$'", name="ck_gift_links_slug_charset"),
        sa.CheckConstraint(
            "jsonb_typeof(filter_config) = 'object'", name="ck_gift_links_filters_object"
        ),
        sa.CheckConstraint("view_count >= 0", name="ck_gift_links_view_count"),
    )
    op.create_index("ix_gift_links_slug", "gift_links", ["slug"], unique=True)
    op.create_index("ix_gift_links_deleted_at", "gift_links", ["deleted_at"])
    op.execute(
        """
        CREATE TRIGGER gift_links_set_updated_at
        BEFORE UPDATE ON gift_links
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER gift_links_soft_delete
        BEFORE DELETE ON gift_links
        FOR EACH ROW EXECUTE FUNCTION soft_delete();
        """
    )
