"""each person's eBay sign-in — their sealed tokens, and the one-time states that start it

Revision ID: 047
Revises: 046
Create Date: 2026-10-04

Batch T8b, "Connect eBay" (`DECISIONS.md` #142, #216, #227, #245). Two tables:

- ``ebay_accounts``: one per profile that has connected eBay. The access and refresh tokens
  are stored sealed (AES-256-GCM under a key derived from ``EBAY_TOKEN_KEY``, bound to the
  profile), never as plain text, with when each expires. **No eBay identity is stored**: the
  account's name is read live for display. Disconnecting deletes the row.
- ``ebay_connect_states``: the one-time ``state`` each "Connect eBay" sends to eBay, kept as
  a SHA-256 hash, tied to the person who started it, single use and short lived.

**Neither table is granted to the read-only role.** The first holds a credential and the
second a secret that could complete someone else's sign-in; the role's lack of default
privileges keeps both unreadable (`AGENTS.md`, "Cloud sessions").

The downgrade drops both: every person would connect again.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "047"
down_revision: str | None = "046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ebay_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_token_sealed", sa.LargeBinary(), nullable=False),
        sa.Column("access_expires_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("refresh_token_sealed", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_expires_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("connected_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("refreshed_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_used_utc", sa.DateTime(timezone=False), nullable=True),
        sa.UniqueConstraint("profile_id", name="uq_ebay_accounts_profile"),
        sa.CheckConstraint(
            "length(access_token_sealed) > 28 AND length(refresh_token_sealed) > 28",
            name="ck_ebay_accounts_sealed",
        ),
    )

    op.create_table(
        "ebay_connect_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state_hash", sa.Text(), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("expires_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("used_utc", sa.DateTime(timezone=False), nullable=True),
        sa.UniqueConstraint("state_hash", name="uq_ebay_connect_states_hash"),
        sa.CheckConstraint("length(state_hash) = 64", name="ck_ebay_connect_states_hash"),
        sa.CheckConstraint("expires_utc > created_utc", name="ck_ebay_connect_states_expiry"),
    )
    op.create_index("ix_ebay_connect_states_profile", "ebay_connect_states", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_ebay_connect_states_profile", table_name="ebay_connect_states")
    op.drop_table("ebay_connect_states")
    op.drop_table("ebay_accounts")
