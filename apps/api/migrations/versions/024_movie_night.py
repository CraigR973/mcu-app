"""create movie_night_sessions, participants and votes

Revision ID: 024
Revises: 023
Create Date: 2026-09-10

Batch 35 — roadmap §8.3 and §8.4.

**A match is derived, never stored.** Two people liking the same film is a fact about the
votes table; a `matches` row would be a second copy of it that a deleted vote could leave
behind, and gotcha 1b is this project's record of what a stale derived value costs. What
*is* stored is `announced_at` on the vote pair's session, so the same match is not
announced twice.

**`filters` is JSONB and reuses Batch 12's smart-collection shape.** §8.3 says "session
creation with filters", and the app already has one way of saying "unwatched 4Ks from the
2010s". A second filter language would be two things to keep in step.

**The invite token is a capability, like Batch 17's feed token and Batch 27's gift slug.**
128 bits, and it is checked against a live, unfinished session — an invite is not a
password and the URL is the whole credential.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "024"
down_revision: str | None = "023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movie_night_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        # `token_urlsafe(16)` — 128 bits, the same floor Batch 27 settled on after §6.26's
        # 32-bit example was found to be enumerable.
        sa.Column("invite_token", sa.String(64), nullable=False),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("ended_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('open', 'ended')", name="ck_movie_night_status"),
        sa.CheckConstraint("length(invite_token) >= 16", name="ck_movie_night_token_length"),
        sa.CheckConstraint(
            "jsonb_typeof(filters) = 'object'", name="ck_movie_night_filters_object"
        ),
    )
    op.create_index(
        "uq_movie_night_invite_token", "movie_night_sessions", ["invite_token"], unique=True
    )

    op.create_table(
        "movie_night_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "joined_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["movie_night_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        # Joining twice is the same person, not a second participant — otherwise a
        # refreshed invite link would make a two-person match need three votes.
        sa.UniqueConstraint("session_id", "user_id", name="uq_movie_night_participant"),
    )

    op.create_table(
        "movie_night_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("liked", sa.Boolean(), nullable=False),
        # Set on the *pair* when a match is announced, so it is announced once. Written on
        # both rows of the pair, because either one is enough to find it later.
        sa.Column("announced_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["movie_night_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        # One vote per person per film per session. A swipe is a decision, and a
        # double-tap must not become two — which for match detection would be a match
        # with itself.
        sa.UniqueConstraint("session_id", "user_id", "movie_id", name="uq_movie_night_vote"),
    )
    # The match query's own index: everyone who liked this film in this session.
    op.create_index(
        "ix_movie_night_votes_liked",
        "movie_night_votes",
        ["session_id", "movie_id"],
        postgresql_where=sa.text("liked"),
    )

    op.execute(
        """
        CREATE TRIGGER movie_night_sessions_set_updated_at
        BEFORE UPDATE ON movie_night_sessions
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS movie_night_sessions_set_updated_at ON movie_night_sessions;"
    )
    op.drop_index("ix_movie_night_votes_liked", table_name="movie_night_votes")
    op.drop_table("movie_night_votes")
    op.drop_table("movie_night_participants")
    op.drop_index("uq_movie_night_invite_token", table_name="movie_night_sessions")
    op.drop_table("movie_night_sessions")
