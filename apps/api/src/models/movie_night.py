"""Movie night — §8.3's sessions and §8.4's votes.

**There is no matches table.** Two people liking the same film is a fact about the votes,
and a stored copy is a second source of truth that a deleted vote can leave stale — gotcha
1b is this project's record of what that costs. `announced_at_utc` on the votes is the only
derived state kept, and it exists solely so a match is announced once.
"""

import secrets
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

SESSION_STATUSES = ("open", "ended")

#: 128 bits, matching the floor Batch 27 settled on (`DECISIONS.md` #83) after §6.26's
#: 32-bit example turned out to be enumerable in an afternoon.
INVITE_TOKEN_BYTES = 16


def new_invite_token() -> str:
    return secrets.token_urlsafe(INVITE_TOKEN_BYTES)


class MovieNightSession(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """One sitting — §8.3."""

    __tablename__ = "movie_night_sessions"

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )

    #: The invite URL's whole credential. Checked against a live, unfinished session — an
    #: invite is not a password, and a link that still worked next month would be worse.
    invite_token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, default=new_invite_token
    )

    #: §8.3's "session creation with filters", in Batch 12's smart-collection shape. A
    #: second filter language would be two things to keep in step.
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    #: Batch X12a (UX48-05): the suggestion the latest match was about, set when it is
    #: announced, so the night page can still show it once the live event and the push are
    #: gone. The votes stay the truth (`sessions.detect_match`); this only remembers which
    #: suggestion the last announcement was about. **No foreign key, deliberately:** a suggestion
    #: already points at its session, and a second constraint the other way is a cycle the
    #: restore drill refuses (it orders tables by foreign keys, `docs/restore-runbook.md`).
    #: Suggestions go only with their session, and a read that finds none shows no match.
    #: Migration 061.
    matched_suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    planned_start_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    ended_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<MovieNightSession {self.id} {self.status}>"


class MovieNightParticipant(Base, UUIDPrimaryKeyMixin):
    """Somebody in the session. Joining twice is the same person."""

    __tablename__ = "movie_night_participants"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_movie_night_participant"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movie_night_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    joined_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )


class MovieNightSuggestion(Base, UUIDPrimaryKeyMixin):
    """A film somebody put forward for this session — Batch S7, snag 6.

    **Batch 35 had no suggestion concept at all.** `candidate_movies` dealt a random deck
    from `movies`, so a film outside the Archive could never appear and nobody could put
    one forward. `DECISIONS.md` #157: *"anyone suggests films, everyone votes on anyone's
    suggestion, films outside the Archive are allowed"*.

    **Exactly one of `movie_id` and `tmdb_id`**, enforced by a CHECK. A film on the shelf
    is a `movies` row and reads its metadata from there; a film nobody owns is a TMDB id
    plus the title and poster captured at the moment it was suggested, because there is no
    row to read them back from.
    """

    __tablename__ = "movie_night_suggestions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movie_night_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: ``SET NULL``: the suggestion outlives whoever made it. Who put a film forward is
    #: shown on its card, so losing the person should not lose the film.
    suggested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    #: ``RESTRICT``, matching `watch_log.movie_id` rather than a cascade: a suggestion is
    #: something a person did, not a fact about the film.
    movie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="RESTRICT"), nullable=True
    )
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: AA5: metadata for a TMDB-only suggestion, without making a catalogue film.
    runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imdb_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metadata_checked_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    imdb_ratings_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    imdb_rating: Mapped[Decimal | None] = mapped_column(Numeric(), nullable=True)
    imdb_vote_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imdb_ratings_checked_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<MovieNightSuggestion {self.title}>"


class MovieNightVote(Base, UUIDPrimaryKeyMixin):
    """One swipe — §8.4."""

    __tablename__ = "movie_night_votes"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", "movie_id", name="uq_movie_night_vote"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movie_night_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    #: Batch S7 relaxed this to nullable: **a film outside the Archive has no `movies`
    #: row to point at.** Every pre-S7 vote still carries one, and the backfill in
    #: migration 033 gave each of them a suggestion too, so the two sessions that were
    #: open at the time kept working rather than becoming history.
    movie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=True
    )

    #: Batch S7. **What the vote is actually about.** A CHECK requires one of this and
    #: `movie_id` to be set — not `suggestion_id NOT NULL`, which would refuse the legacy
    #: shape the migration just filled in, and a constraint that only holds because a
    #: backfill happened to succeed fails on the one database where it did not.
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movie_night_suggestions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    liked: Mapped[bool] = mapped_column(Boolean, nullable=False)

    #: Written on every vote in a matched pair when the match is announced, so it is
    #: announced once however many times either person reloads.
    announced_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<MovieNightVote {self.user_id} {'liked' if self.liked else 'passed'}>"


__all__ = [
    "INVITE_TOKEN_BYTES",
    "SESSION_STATUSES",
    "MovieNightParticipant",
    "MovieNightSession",
    "MovieNightVote",
    "new_invite_token",
]
