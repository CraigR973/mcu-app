"""create watch_log

Revision ID: 006
Revises: 005
Create Date: 2026-09-08

Roadmap §3.7's personal watch history — the table that had no owning phase.

§3.7 designs it, §6.5 lists ``POST``/``GET /api/v1/watch-log``, and the ledger's Batch 37
is defined as "inert until ``watch_log`` has ~a year of history" — but no phase in §16
ever created it. Batch 6 was asked for a "watched status" facet on top of a table that
did not exist. Built here by owner decision (`DECISIONS.md` #35).

Two shapes differ from §3.7 and both are deliberate:

**``deleted_at``.** §13.5 sends deleted watch logs to Trash alongside collection items
and wanted entries, which a hard delete cannot support. Every read path filters on it.

**``movie_id`` is ``RESTRICT``.** A watch is something a person did, not a fact about the
film, so it must not cascade away when a movie row is tidied up. The app's one hard-delete
path for a movie is the identify flow's merge, which now repoints these rows the same way
it already repoints ``collection_items``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watch_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("watched_at", sa.Date(), nullable=False),
        sa.Column("is_rewatch", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("personal_rating", sa.Numeric(2, 1), nullable=True),
        sa.Column("review", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        # §3.7's scale is 0.5–5.0 in half-stars. The modulo clause is what stops a 3.7
        # arriving from a hand-rolled request and rendering as three and a half stars
        # plus a rounding error.
        sa.CheckConstraint(
            "personal_rating IS NULL OR ("
            "personal_rating >= 0.5 AND personal_rating <= 5.0 "
            "AND (personal_rating * 10)::int % 5 = 0)",
            name="ck_watch_log_personal_rating",
        ),
        # A watch cannot be logged in the future. Guards the fat-fingered year far more
        # cheaply than discovering it in an on-this-day memory a decade from now.
        sa.CheckConstraint(
            "watched_at <= (CURRENT_DATE + INTERVAL '1 day')",
            name="ck_watch_log_watched_at_not_future",
        ),
    )

    op.create_index("ix_watch_log_movie_id", "watch_log", ["movie_id"])
    op.create_index("ix_watch_log_user_id", "watch_log", ["user_id"])
    op.create_index("ix_watch_log_deleted_at", "watch_log", ["deleted_at"])

    # The watched-status facet asks "which films has *this* user watched?" once per
    # list request, as a correlated EXISTS over 1,857 films. Partial on the live rows
    # because that is the only set the facet ever counts.
    op.create_index(
        "ix_watch_log_user_movie_live",
        "watch_log",
        ["user_id", "movie_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # "My history, newest first" — the GET endpoint's only ordering.
    op.create_index(
        "ix_watch_log_user_watched_at",
        "watch_log",
        ["user_id", sa.text("watched_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_watch_log_user_watched_at", table_name="watch_log")
    op.drop_index("ix_watch_log_user_movie_live", table_name="watch_log")
    op.drop_index("ix_watch_log_deleted_at", table_name="watch_log")
    op.drop_index("ix_watch_log_user_id", table_name="watch_log")
    op.drop_index("ix_watch_log_movie_id", table_name="watch_log")
    op.drop_table("watch_log")
