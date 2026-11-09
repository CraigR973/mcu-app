"""Assigned identity reviews (AD1, approved #351). No production assignment or provider call.

Revision ID: 074
Revises: 073
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "074"
down_revision: str | None = "073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assigned_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("answer", sa.String(30), nullable=True),
        sa.Column("answered_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["assigned_to"], ["profiles.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "kind IN ('titanic_disc', 'wanted_identity', 'shetland_series')",
            name="ck_assigned_review_kind",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_assigned_review_revision"),
        sa.CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="ck_assigned_review_snapshot"),
        sa.CheckConstraint(
            "answer IS NULL OR answer = 'unsure' OR "
            "(kind = 'titanic_disc' AND answer IN ('1953', '1997')) OR "
            "(kind = 'wanted_identity' AND answer IN ('1940', '2004')) OR "
            "(kind = 'shetland_series' AND answer IN ('use_series', 'keep_separate'))",
            name="ck_assigned_review_answer",
        ),
    )
    op.create_index(
        "uq_assigned_review_target",
        "assigned_reviews",
        ["kind", "target_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_assigned_reviews_person", "assigned_reviews", ["assigned_to"])
    op.execute(
        "CREATE TRIGGER assigned_reviews_set_updated_at BEFORE UPDATE ON assigned_reviews "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )
    for role in ("mcu_readonly", "mcu_backup"):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN "
            f"GRANT SELECT ON assigned_reviews TO {role}; END IF; END $$"
        )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM assigned_reviews) THEN "
        "RAISE EXCEPTION 'Assigned reviews exist; downgrade 074 requires owner review'; "
        "END IF; END $$"
    )
    op.drop_table("assigned_reviews")
