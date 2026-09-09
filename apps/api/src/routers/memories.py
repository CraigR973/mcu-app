"""On-this-day memories and rewatch suggestions — Batch 37, roadmap §11.6.

Both queries are scoped to the caller. Watch history is personal: a film Mark watched last
week is not evidence that Craig has watched it recently, and vice versa.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from src.auth import CurrentUser
from src.clock import utc_today
from src.models.movie import Movie
from src.models.watch_log import WatchLog
from src.routers.movies import Database
from src.schemas.memories import OnThisDayMemoryResponse, RewatchSuggestionResponse

router = APIRouter(prefix="/api/v1", tags=["memories"])


def _months_before(on: date, months: int) -> date:
    """Return the calendar date ``months`` before ``on``, clamping short months."""
    month_index = on.year * 12 + on.month - 1 - months
    year, month_zero_index = divmod(month_index, 12)
    month = month_zero_index + 1
    return date(year, month, min(on.day, calendar.monthrange(year, month)[1]))


@router.get("/memories/on-this-day", response_model=list[OnThisDayMemoryResponse])
async def on_this_day(user: CurrentUser, db: Database) -> list[OnThisDayMemoryResponse]:
    """The caller's watches from this month and day in earlier years."""
    today = utc_today()
    rows = (
        await db.execute(
            select(WatchLog, Movie)
            .join(Movie, Movie.id == WatchLog.movie_id)
            .where(
                WatchLog.user_id == user.id,
                WatchLog.deleted_at.is_(None),
                Movie.deleted_at.is_(None),
                WatchLog.watched_at < today,
                func.extract("month", WatchLog.watched_at) == today.month,
                func.extract("day", WatchLog.watched_at) == today.day,
            )
            .order_by(WatchLog.watched_at.desc(), Movie.title.asc())
        )
    ).all()
    return [
        OnThisDayMemoryResponse(
            id=entry.id,
            movieId=movie.id,
            movieTitle=movie.title,
            posterPath=movie.poster_path,
            watchedAt=entry.watched_at,
            yearsAgo=today.year - entry.watched_at.year,
            personalRating=(
                float(entry.personal_rating) if entry.personal_rating is not None else None
            ),
        )
        for entry, movie in rows
    ]


@router.get("/memories/rewatch-suggestions", response_model=list[RewatchSuggestionResponse])
async def rewatch_suggestions(
    user: CurrentUser,
    db: Database,
    months: Annotated[int, Query(ge=1, le=120)] = 6,
    min_rating: Annotated[float, Query(alias="minRating", ge=0.5, le=5.0)] = 4.0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[RewatchSuggestionResponse]:
    """Highly rated films the caller has not watched within ``months`` calendar months."""
    latest_watches = (
        select(
            WatchLog.movie_id.label("movie_id"),
            func.max(WatchLog.watched_at).label("last_watched_at"),
            func.max(WatchLog.personal_rating).label("personal_rating"),
        )
        .where(WatchLog.user_id == user.id, WatchLog.deleted_at.is_(None))
        .group_by(WatchLog.movie_id)
        .subquery()
    )
    cutoff = _months_before(utc_today(), months)
    rows = (
        await db.execute(
            select(
                Movie,
                latest_watches.c.last_watched_at,
                latest_watches.c.personal_rating,
            )
            .join(latest_watches, latest_watches.c.movie_id == Movie.id)
            .where(
                Movie.deleted_at.is_(None),
                latest_watches.c.last_watched_at < cutoff,
                latest_watches.c.personal_rating >= Decimal(str(min_rating)),
            )
            .order_by(
                latest_watches.c.personal_rating.desc(),
                latest_watches.c.last_watched_at.asc(),
                Movie.title.asc(),
            )
            .limit(limit)
        )
    ).all()
    return [
        RewatchSuggestionResponse(
            movieId=movie.id,
            movieTitle=movie.title,
            posterPath=movie.poster_path,
            lastWatchedAt=last_watched_at,
            personalRating=float(personal_rating),
        )
        for movie, last_watched_at, personal_rating in rows
    ]
