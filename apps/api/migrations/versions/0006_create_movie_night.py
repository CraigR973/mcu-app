"""create movie_night_sessions and movie_night_votes tables

movie_night_sessions — a collaborative swipe session where multiple users each vote
on a candidate film; ends when both agree (matched) or the session expires.

movie_night_votes — individual like/skip votes within a session; unique per
(session, user, movie) to prevent double-voting.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_SESSION_STATUS = ("active", "matched", "expired")


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # movie_night_sessions — one session per group viewing decision event
    # -------------------------------------------------------------------------
    op.create_table(
        "movie_night_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_by",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Genre, decade, runtime filters selected when starting the session
        sa.Column("filters", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "matched_movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_movie_night_sessions_status",
        "movie_night_sessions",
        f"status IN {_SESSION_STATUS}",
    )

    op.create_index("idx_movie_night_sessions_created_by", "movie_night_sessions", ["created_by"])
    op.create_index("idx_movie_night_sessions_status", "movie_night_sessions", ["status"])

    # -------------------------------------------------------------------------
    # movie_night_votes — one row per (session, user, movie) vote
    # -------------------------------------------------------------------------
    op.create_table(
        "movie_night_votes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.BigInteger(),
            sa.ForeignKey("movie_night_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # TRUE = like/yes, FALSE = skip/no
        sa.Column("vote", sa.Boolean(), nullable=False),
        sa.Column(
            "voted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_unique_constraint(
        "uq_movie_night_votes_session_user_movie",
        "movie_night_votes",
        ["session_id", "user_id", "movie_id"],
    )

    op.create_index("idx_movie_night_votes_session_id", "movie_night_votes", ["session_id"])
    op.create_index("idx_movie_night_votes_user_id", "movie_night_votes", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_movie_night_votes_user_id", table_name="movie_night_votes")
    op.drop_index("idx_movie_night_votes_session_id", table_name="movie_night_votes")
    op.drop_constraint(
        "uq_movie_night_votes_session_user_movie", "movie_night_votes", type_="unique"
    )
    op.drop_table("movie_night_votes")

    op.drop_index("idx_movie_night_sessions_status", table_name="movie_night_sessions")
    op.drop_index("idx_movie_night_sessions_created_by", table_name="movie_night_sessions")
    op.drop_constraint("ck_movie_night_sessions_status", "movie_night_sessions", type_="check")
    op.drop_table("movie_night_sessions")
