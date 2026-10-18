"""Keep TMDB's data on the films under six months old — Batch X12c (DS44-06).

TMDB's terms bar caching its data "for longer than 6 months". Every film's fields come from
one fetch when it was identified (1,051 of them on 8 Sep, the first day), and nothing fetched
them again, so most would pass six months on 8 Mar 2027. This refreshes the films whose
``last_tmdb_sync_utc`` is older than :data:`STALE_AFTER` (150 days, a month inside the limit),
stalest first, a few each time the release calendar refreshes (:func:`calendar.refresh_calendar`,
which a read triggers at most daily): 100 a day clears the 1,051 in 11 days, long before 8 Mar.

**A refresh rewrites TMDB's fields and credits and nothing a person set:** the film's title,
year, overview, poster, genres, keywords, cast summary and trailer as TMDB gives them now, and
its credit rows; never its copies, watches, wants or identification. A film with no sync date
is left alone: its age is unknown rather than old, and the first run must not write rows nobody
expected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog
from sqlalchemy import ColumnElement, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.movie import Movie, MovieCredit
from src.services.movie_metadata import (
    credit_rows,
    movie_metadata_values,
    tv_credit_rows,
    tv_metadata_values,
)
from src.tmdb import TMDBClient

logger = structlog.get_logger(__name__)

#: A film's TMDB data is refreshed once it is this old: a month inside TMDB's six.
STALE_AFTER = timedelta(days=150)

#: Films refreshed per calendar refresh. One TMDB call each, one after another.
BATCH_SIZE = 100


@dataclass
class StaleRefreshResult:
    refreshed: int = 0
    failed: int = 0
    #: Still older than :data:`STALE_AFTER` after this run, for the next.
    remaining: int = 0
    errors: list[str] = field(default_factory=list)


def stale_condition(now: datetime) -> tuple[ColumnElement[bool], ...]:
    """Identified, live, and last fetched from TMDB longer ago than :data:`STALE_AFTER`."""
    return (
        Movie.deleted_at.is_(None),
        or_(Movie.tmdb_id.is_not(None), Movie.tmdb_tv_id.is_not(None)),
        Movie.last_tmdb_sync_utc.is_not(None),
        Movie.last_tmdb_sync_utc < now - STALE_AFTER,
    )


async def _refresh_one(db: AsyncSession, tmdb: TMDBClient, movie: Movie, now: datetime) -> None:
    if movie.tmdb_tv_id is not None:
        show = await tmdb.get_tv_full(movie.tmdb_tv_id)
        values = tv_metadata_values(show)
        rows = tv_credit_rows(movie.id, show)
    elif movie.tmdb_id is not None:
        record = await tmdb.get_movie_full(movie.tmdb_id)
        values = movie_metadata_values(record)
        rows = credit_rows(movie.id, record)
    else:  # pragma: no cover - the query selects identified films
        return
    # The sync date is this run's clock, so what counts as stale is read off one clock.
    values = {**values, "last_tmdb_sync_utc": now}
    for name, value in values.items():
        setattr(movie, name, value)
    await db.execute(delete(MovieCredit).where(MovieCredit.movie_id == movie.id))
    for row in rows:
        db.add(
            MovieCredit(
                id=uuid.UUID(row[0]),
                movie_id=movie.id,
                person_name=row[2],
                tmdb_person_id=row[3],
                role=row[4],
                character_name=row[5],
                display_order=row[6],
            )
        )


async def refresh_stale_fields(
    db: AsyncSession, tmdb: TMDBClient, *, now: datetime, limit: int = BATCH_SIZE
) -> StaleRefreshResult:
    """Refresh up to ``limit`` of the stalest films. Each in its own savepoint, so one TMDB
    refusal (a film TMDB has removed) is recorded and the rest go on. Commits at the end."""
    result = StaleRefreshResult()
    films = list(
        (
            await db.scalars(
                select(Movie)
                .where(*stale_condition(now))
                .order_by(Movie.last_tmdb_sync_utc)
                .limit(limit)
            )
        ).all()
    )
    for movie in films:
        try:
            async with db.begin_nested():
                await _refresh_one(db, tmdb, movie, now)
            result.refreshed += 1
        except Exception as exc:  # noqa: BLE001 - one film must not stop the rest
            result.failed += 1
            result.errors.append(f"{movie.title}: {exc}"[:200])
            logger.warning("tmdb_refresh_failed", movie_id=str(movie.id), error=str(exc))
    await db.commit()
    older = await db.scalars(select(Movie.id).where(*stale_condition(now)))
    result.remaining = len(older.all())
    return result
