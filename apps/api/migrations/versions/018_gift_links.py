"""create gift_links

Revision ID: 018
Revises: 017
Create Date: 2026-09-09

Roadmap §3.21 and §6.26 — Batch 27's phases 12.1 and 12.2.

**This is the application's second unauthenticated surface**, after Batch 17's `.ics` feed,
and the ledger flags it as "the app's only public surface; needs its own security review".
Two shapes therefore differ from §3.21 as drawn:

**The slug is its own column, not the primary key.** §3.21 says *"id | UUID (PK) | Public
slug used in the URL"*, and §6.26's worked example is `/gift/a8f3b2c1` — **eight hex
characters, 32 bits**. That is four billion possibilities: enumerable by anyone willing to
spend an afternoon, and the thing being enumerated is a list of things a named person wants.
A separate `slug` column holds ``secrets.token_urlsafe(16)`` — 128 bits — so guessing is not
a threat anyone needs to think about again. Splitting it from the PK also means the internal
id never appears in a URL, and a slug can be rotated without the row changing identity.

**The slug is stored in plaintext, unlike Batch 17's feed token.** That is a deliberate
difference, not an oversight (`DECISIONS.md` #83). A calendar feed is for one person and is
shown once; a gift link is *made to be re-shared* — §6.26 step 2 is "shares the generated
link via text, email, WhatsApp", and step 5 is tracking views and revoking. All of that
needs the admin to see the link again, which hashing would make impossible. The compensating
controls are expiry, revocation, and a page that carries nothing but a wanted list.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gift_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        # 128 bits of `token_urlsafe(16)`, ~22 characters. Not the primary key, and not
        # §6.26's eight hex characters.
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
        # A short slug is a guessable slug. The floor is enforced here as well as in the
        # generator, so a hand-inserted row cannot create a weak public URL.
        sa.CheckConstraint("length(slug) >= 16", name="ck_gift_links_slug_length"),
        # URL-safe base64 only — the alphabet `token_urlsafe` produces. Anything else in a
        # path segment is either an encoding bug or an attempt at one.
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
    # Soft-deleting, so it joins §13.5's Trash like the tables Batch 18 added.
    op.execute(
        """
        CREATE TRIGGER gift_links_soft_delete
        BEFORE DELETE ON gift_links
        FOR EACH ROW EXECUTE FUNCTION soft_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS gift_links_soft_delete ON gift_links;")
    op.execute("DROP TRIGGER IF EXISTS gift_links_set_updated_at ON gift_links;")
    op.drop_index("ix_gift_links_deleted_at", table_name="gift_links")
    op.drop_index("ix_gift_links_slug", table_name="gift_links")
    op.drop_table("gift_links")
