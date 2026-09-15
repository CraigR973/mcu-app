"""add movie_night_suggestions, and let a vote be cast on one

Revision ID: 033
Revises: 032
Create Date: 2026-09-15

Batch S7 — snag 6, `DECISIONS.md` #157.

**What Batch 35 built was a random swipe deck over films already in the collection.**
`candidate_movies` is `select(Movie)` filtered by decade and rating, so **a film outside
the Archive can never appear**, and there is no suggestion concept anywhere in the model.
Two of Craig's five points were met; the other three need the input side replaced.

**This migration is additive, and deliberately so.** `movie_night_votes` holds **13 real
rows across 2 sessions that are still open** — measured against live Neon on 2026-09-15 —
so nothing is dropped and no column is rewritten. `movie_id` is *relaxed* to nullable,
because a film outside the Archive has no `movies` row to point at; every existing value
stays exactly where it was, and a backfill gives each existing vote a suggestion so the
two open sessions keep working under the new model rather than becoming history.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "033"
down_revision: str | None = "032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movie_night_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        # SET NULL: the suggestion outlives whoever made it, the way a disc outlives
        # whoever catalogued it. Who suggested what is shown on the card, so losing the
        # person should not lose the film.
        sa.Column("suggested_by", postgresql.UUID(as_uuid=True), nullable=True),
        # Exactly one of these two. A film on the shelf is a `movies` row; a film nobody
        # owns is a TMDB id and the title/poster captured with it, because there is no
        # row to read them from later.
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("poster_path", sa.Text(), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["movie_night_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suggested_by"], ["profiles.id"], ondelete="SET NULL"),
        # RESTRICT, matching `watch_log.movie_id`: a suggestion is something a person did,
        # and must not be swept away as a side effect of tidying a film row.
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "(movie_id IS NOT NULL) <> (tmdb_id IS NOT NULL)",
            name="ck_movie_night_suggestion_one_reference",
        ),
    )
    # One suggestion per film per session, however many people suggest it. Partial,
    # because only one of the two columns is ever set.
    op.create_index(
        "uq_movie_night_suggestion_movie",
        "movie_night_suggestions",
        ["session_id", "movie_id"],
        unique=True,
        postgresql_where=sa.text("movie_id IS NOT NULL"),
    )
    op.create_index(
        "uq_movie_night_suggestion_tmdb",
        "movie_night_suggestions",
        ["session_id", "tmdb_id"],
        unique=True,
        postgresql_where=sa.text("tmdb_id IS NOT NULL"),
    )
    op.create_index("ix_movie_night_suggestions_session", "movie_night_suggestions", ["session_id"])

    op.add_column(
        "movie_night_votes",
        sa.Column("suggestion_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_movie_night_votes_suggestion",
        "movie_night_votes",
        "movie_night_suggestions",
        ["suggestion_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # **Relaxed, not rewritten.** A film outside the Archive has no `movies` row, so a
    # vote on one cannot carry a `movie_id`. Every existing value is untouched.
    op.alter_column("movie_night_votes", "movie_id", nullable=True)

    # Backfill, so the two sessions that are open today keep working rather than becoming
    # history the moment this deploys. One suggestion per (session, film) already voted
    # on, credited to nobody — because nobody suggested them; Batch 35 dealt them.
    op.execute(
        """
        INSERT INTO movie_night_suggestions
            (id, session_id, suggested_by, movie_id, tmdb_id, title, year, poster_path,
             overview, created_at_utc)
        SELECT gen_random_uuid(), v.session_id, NULL, v.movie_id, NULL,
               m.title, m.year, m.poster_path, m.overview, now()
        FROM (SELECT DISTINCT session_id, movie_id FROM movie_night_votes
              WHERE movie_id IS NOT NULL) AS v
        JOIN movies m ON m.id = v.movie_id;
        """
    )
    op.execute(
        """
        UPDATE movie_night_votes v
        SET suggestion_id = s.id
        FROM movie_night_suggestions s
        WHERE s.session_id = v.session_id
          AND s.movie_id = v.movie_id
          AND v.suggestion_id IS NULL;
        """
    )

    # Every vote must name what it is about, one way or the other. Not `suggestion_id
    # NOT NULL`, because that would refuse the legacy shape this migration just filled in
    # — and a constraint that only holds because a backfill happened to succeed is a
    # constraint that fails on the one database where it did not.
    op.create_check_constraint(
        "ck_movie_night_vote_subject",
        "movie_night_votes",
        "movie_id IS NOT NULL OR suggestion_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_movie_night_vote_subject", "movie_night_votes", type_="check")
    # Rows whose only subject is a suggestion cannot survive the column going back to NOT
    # NULL, and they are exactly the films outside the Archive this batch added. Removing
    # them is what "downgrade" means here, and it is why the reversal is tested.
    op.execute("DELETE FROM movie_night_votes WHERE movie_id IS NULL;")
    op.alter_column("movie_night_votes", "movie_id", nullable=False)
    op.drop_constraint("fk_movie_night_votes_suggestion", "movie_night_votes", type_="foreignkey")
    op.drop_column("movie_night_votes", "suggestion_id")
    op.drop_index("ix_movie_night_suggestions_session", table_name="movie_night_suggestions")
    op.drop_index("uq_movie_night_suggestion_tmdb", table_name="movie_night_suggestions")
    op.drop_index("uq_movie_night_suggestion_movie", table_name="movie_night_suggestions")
    op.drop_table("movie_night_suggestions")
