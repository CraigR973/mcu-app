"""How far each person has got, and who is choosing now — AE10's proposal C (#355).

**A count, never the films.** "Mark has added 3 · choosing now" says how far he has got and
nothing about which films: the other person's picks stay hidden until a match (#157). The
live "vote" event names no film for the same reason (`sessions.record_vote`).

**"Choosing now" is read from the database, not from the live connection.** A phone's event
stream drops and reconnects often, and a count of open streams would flicker with it. The
night's own reads, votes and suggestions stamp ``last_seen_utc``, the night page reads the
session again every minute while it is on screen, and a stamp within ``CHOOSING_NOW`` is
"choosing now".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.movie_night import MovieNightParticipant, MovieNightVote

CHOOSING_NOW = timedelta(minutes=5)


@dataclass(frozen=True)
class Progress:
    """One person on one night: how many films they have added, and when they last had it
    open."""

    added: int = 0
    last_seen: datetime | None = None

    def choosing_now(self, now: datetime) -> bool:
        return self.last_seen is not None and now - self.last_seen <= CHOOSING_NOW


async def stamp_seen(
    db: AsyncSession, *, session_id: uuid.UUID, user_id: uuid.UUID, now: datetime | None = None
) -> None:
    """This person has the night open. The caller commits."""
    await db.execute(
        update(MovieNightParticipant)
        .where(
            MovieNightParticipant.session_id == session_id,
            MovieNightParticipant.user_id == user_id,
        )
        .values(last_seen_utc=now or utcnow())
    )


async def progress(db: AsyncSession, session_id: uuid.UUID) -> dict[uuid.UUID, Progress]:
    """Everyone in the night, with their count of added films and their last visit."""
    # A comprehension, not `dict(result)`: a result has `keys()`, so `dict()` would read it
    # as a mapping of column names.
    added = {
        user_id: count
        for user_id, count in (
            await db.execute(
                select(MovieNightVote.user_id, func.count(MovieNightVote.id))
                .where(MovieNightVote.session_id == session_id, MovieNightVote.liked.is_(True))
                .group_by(MovieNightVote.user_id)
            )
        ).tuples()
    }
    seen = (
        await db.execute(
            select(MovieNightParticipant.user_id, MovieNightParticipant.last_seen_utc).where(
                MovieNightParticipant.session_id == session_id
            )
        )
    ).tuples()
    return {
        user_id: Progress(added=int(added.get(user_id, 0)), last_seen=last_seen)
        for user_id, last_seen in seen
    }
