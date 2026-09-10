"""Movie night — §8.3's sessions and §8.4's votes.

**There is no matches table.** Two people liking the same film is a fact about the votes,
and a stored copy is a second source of truth that a deleted vote can leave stale — gotcha
1b is this project's record of what that costs. `announced_at_utc` on the votes is the only
derived state kept, and it exists solely so a match is announced once.
"""

import secrets
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

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
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )


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
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    liked: Mapped[bool] = mapped_column(Boolean, nullable=False)

    #: Written on every vote in a matched pair when the match is announced, so it is
    #: announced once however many times either person reloads.
    announced_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
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
