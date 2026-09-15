"""add profiles.letterboxd_username and the letterboxd_syncs table

Revision ID: 032
Revises: 031
Create Date: 2026-09-15

Batch S5 — snag 10a. `DECISIONS.md` #156, #158, #159.

**Two things, and the second exists because of the 50-entry cap.** The feed returns only
the most recent 50 entries: Craig's reaches back to 2026-01-26, **Mark's only to
2026-07-20**, because he watches far more. A sync running less often than roughly monthly
would silently drop his entries, so *when it last ran* is a correctness property rather
than a nicety — and a number nobody wrote down cannot be checked (the same argument
`scrape_runs` was built on in Batch 20).

`letterboxd_username` is per profile because each person has their own diary. It is a
public username, not a credential: `DECISIONS.md` #161 is explicit that no Letterboxd
credential is ever stored.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "032"
down_revision: str | None = "031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("letterboxd_username", sa.String(64), nullable=True),
    )
    # Letterboxd's own username rules, enforced here so a value that could not name a
    # real diary cannot be saved — and, more to the point, so nothing that looks like a
    # path segment or a full URL can reach the feed URL builder.
    op.create_check_constraint(
        "ck_profiles_letterboxd_username",
        "profiles",
        "letterboxd_username IS NULL OR letterboxd_username ~ '^[A-Za-z0-9_]{1,64}$'",
    )

    op.create_table(
        "letterboxd_syncs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=False), nullable=False),
        # NULL while in flight, so a sync that died halfway is visible as one that died
        # halfway rather than as no row at all. `scrape_runs` learned this first.
        sa.Column("finished_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("entries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("already_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ambiguous", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("not_in_collection", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("trigger IN ('manual', 'cron')", name="ck_letterboxd_syncs_trigger"),
        sa.CheckConstraint(
            "entries >= 0 AND written >= 0 AND already_imported >= 0 "
            "AND ambiguous >= 0 AND not_in_collection >= 0",
            name="ck_letterboxd_syncs_counts",
        ),
    )
    # "When did *I* last sync?" is the only question this table is asked, and the UI asks
    # it on every render of the panel.
    op.create_index(
        "ix_letterboxd_syncs_user_started",
        "letterboxd_syncs",
        ["user_id", sa.text("started_at_utc DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_letterboxd_syncs_user_started", table_name="letterboxd_syncs")
    op.drop_table("letterboxd_syncs")
    op.drop_constraint("ck_profiles_letterboxd_username", "profiles", type_="check")
    op.drop_column("profiles", "letterboxd_username")
