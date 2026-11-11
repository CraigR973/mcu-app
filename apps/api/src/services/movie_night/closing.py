"""Nights nobody touched close themselves — AE10's proposal E (#355).

Seven of the 11 nights since 10 Sep never had a vote, and the open 6 Nov one had never been
opened: a night left open is a night in everybody's list, and a link that still works.

**The rule:** an open night with no votes closes ``UNTOUCHED_FOR`` after it started, or after
its planned start when it has one. A night anybody voted on stays open until somebody ends it.
Its ``ended_at_utc`` is when it became due, not when it was noticed, and its suggestions stay:
a closed night keeps its history.

**Computed when nights are read, not by a job.** The sketch asked for no new scheduled job;
the list, a night's page, an invite and anything that changes a night run this first, so a
night that is due is closed before anybody can act on it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import case, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.movie_night import MovieNightSession, MovieNightVote
from src.services.movie_night.sessions import publish

UNTOUCHED_FOR = timedelta(days=2)


async def close_untouched(db: AsyncSession, *, now: datetime | None = None) -> list[uuid.UUID]:
    """Close every open night that is due, and say so to anybody watching one. The caller
    commits. Returns the nights closed."""
    now = now or utcnow()
    due_at = case(
        (
            MovieNightSession.planned_start_utc.is_not(None),
            MovieNightSession.planned_start_utc + UNTOUCHED_FOR,
        ),
        else_=MovieNightSession.created_at + UNTOUCHED_FOR,
    )
    untouched = ~exists(
        select(MovieNightVote.id).where(MovieNightVote.session_id == MovieNightSession.id)
    )
    closed = list(
        (
            await db.execute(
                update(MovieNightSession)
                .where(MovieNightSession.status == "open", untouched, due_at <= now)
                .values(status="ended", ended_at_utc=due_at)
                .returning(MovieNightSession.id)
                .execution_options(synchronize_session="fetch")
            )
        ).scalars()
    )
    for session_id in closed:
        await publish(db, session_id, "ended", {})
    return closed
