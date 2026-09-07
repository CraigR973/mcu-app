"""auth — profiles, refresh tokens, durable rate-limit counters

Revision ID: 002
Revises: 001
Create Date: 2026-09-07

Batch 3. Creates the two seeded profiles with ``pin_hash = NULL`` — *no credential* —
so no PIN is ever written into a migration or into git history. Each person sets their
own through ``POST /api/v1/auth/pin``.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The two people. Roles per `DECISIONS.md` #11 — Craig administers, Mark views.
#: Seeded here rather than by a script so a fresh database is immediately usable and
#: the row ids are stable across environments.
_SEED_PROFILES = (
    ("Craig", "admin"),
    ("Mark", "viewer"),
)


def upgrade() -> None:
    user_role = sa.Enum("admin", "viewer", name="user_role")
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "profiles",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("pin_hash", sa.String(60), nullable=True),
        sa.Column("role", user_role, nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_login_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_profiles_display_name", "profiles", ["display_name"])
    # Functional and case-insensitive: login looks the name up with `lower()`, so
    # "Craig" and "craig" must not be able to coexist and make that lookup ambiguous.
    # A plain unique constraint on the column would allow exactly that.
    op.create_index(
        "uq_profiles_display_name_lower",
        "profiles",
        [sa.text("lower(display_name)")],
        unique=True,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("revoked_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=False), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    op.create_table(
        "rate_limit_counters",
        sa.Column("bucket_key", sa.String(200), primary_key=True),
        sa.Column("limit_item", sa.String(64), primary_key=True),
        sa.Column("window_start_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at_utc", sa.DateTime(timezone=False), nullable=False),
    )
    op.create_index(
        "ix_rate_limit_counters_expires_at_utc", "rate_limit_counters", ["expires_at_utc"]
    )

    profiles = sa.table(
        "profiles",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("display_name", sa.String),
        sa.column("role", sa.String),
    )
    op.bulk_insert(
        profiles,
        [{"id": uuid.uuid4(), "display_name": name, "role": role} for name, role in _SEED_PROFILES],
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_counters_expires_at_utc", table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("uq_profiles_display_name_lower", table_name="profiles")
    op.drop_index("ix_profiles_display_name", table_name="profiles")
    op.drop_table("profiles")
    # The enum is a database-level object and outlives its table — dropping it is what
    # makes `downgrade base` leave nothing behind, which CI asserts on every push.
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
