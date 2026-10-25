"""The people, shelf and cached metadata on a night (AA5). Never creates a copy/film."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import httpx
import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.movie_night import MovieNightParticipant, MovieNightSuggestion
from src.models.profile import Profile
from src.models.watch_log import WatchLog
from src.services.imdb_ratings import IMDB_ID
from src.tmdb import TMDBClient
from src.tmdb.models import Movie as TmdbMovie

logger = structlog.get_logger(__name__)
METADATA_AGE = timedelta(days=150)


async def films_for_suggestions(
    db: AsyncSession, suggestions: list[MovieNightSuggestion]
) -> tuple[dict[uuid.UUID, Movie], dict[int, Movie]]:
    ids = [s.movie_id for s in suggestions if s.movie_id]
    tmdb_ids = [s.tmdb_id for s in suggestions if s.tmdb_id]
    movies = list(
        await db.scalars(
            select(Movie).where(
                or_(
                    Movie.id.in_(ids),
                    and_(Movie.deleted_at.is_(None), Movie.tmdb_id.in_(tmdb_ids)),
                )
            )
        )
    )
    return {m.id: m for m in movies}, {m.tmdb_id: m for m in movies if m.tmdb_id is not None}


async def fill_suggestion_metadata(
    db: AsyncSession,
    suggestions: list[MovieNightSuggestion],
    by_tmdb: dict[int, Movie],
    tmdb: TMDBClient,
) -> None:
    """One bounded TMDB lookup per distinct missing external id, cached on its suggestion.

    Current catalogue metadata takes precedence. Existing snapshot title/year/poster and all
    identity/vote fields stay unchanged. Fetches happen after ending the read transaction.
    """
    now = utcnow()
    due = [
        s
        for s in suggestions
        if s.tmdb_id is not None
        and (
            s.tmdb_id not in by_tmdb
            or by_tmdb[s.tmdb_id].imdb_id is None
            or by_tmdb[s.tmdb_id].runtime_minutes is None
        )
        and (s.metadata_checked_utc is None or s.metadata_checked_utc < now - METADATA_AGE)
    ]
    await db.commit()
    if not due:
        return
    semaphore = asyncio.Semaphore(4)

    async def fetch(tmdb_id: int) -> tuple[int, TmdbMovie | None]:
        async with semaphore:
            try:
                return tmdb_id, await tmdb.get_movie_full(tmdb_id)
            except (httpx.HTTPError, RuntimeError) as exc:
                logger.warning("night_metadata_unavailable", tmdb_id=tmdb_id, error=str(exc))
                return tmdb_id, None

    fetched = dict(
        await asyncio.gather(*(fetch(i) for i in {s.tmdb_id for s in due if s.tmdb_id is not None}))
    )
    # Re-read after the network wait, so a concurrent refresh or promotion is preserved.
    fresh = list(
        await db.scalars(
            select(MovieNightSuggestion)
            .where(MovieNightSuggestion.id.in_([s.id for s in due]))
            .order_by(MovieNightSuggestion.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    for suggestion in fresh:
        record = fetched.get(suggestion.tmdb_id) if suggestion.tmdb_id is not None else None
        if record is None:
            continue
        imdb_id = record.imdb_id if record.imdb_id and IMDB_ID.fullmatch(record.imdb_id) else None
        if imdb_id != suggestion.imdb_id:
            suggestion.imdb_ratings_id = None
            suggestion.imdb_rating = None
            suggestion.imdb_vote_count = None
            suggestion.imdb_ratings_checked_utc = None
        suggestion.imdb_id = imdb_id
        suggestion.runtime_minutes = record.runtime or None
        suggestion.metadata_checked_utc = now
    await db.commit()


async def people_history(
    db: AsyncSession, session_id: uuid.UUID, movie_ids: list[uuid.UUID]
) -> tuple[
    list[tuple[uuid.UUID, str]],
    dict[tuple[uuid.UUID, uuid.UUID], tuple[date | None, Decimal | None]],
]:
    people = list(
        (
            await db.execute(
                select(Profile.id, Profile.display_name)
                .join(MovieNightParticipant, MovieNightParticipant.user_id == Profile.id)
                .where(MovieNightParticipant.session_id == session_id)
                .order_by(MovieNightParticipant.joined_at_utc)
            )
        ).tuples()
    )
    history: dict[tuple[uuid.UUID, uuid.UUID], tuple[date | None, Decimal | None]] = {}
    if not movie_ids:
        return people, history
    watches = await db.scalars(
        select(WatchLog)
        .join(Movie, Movie.id == WatchLog.movie_id)
        .where(
            WatchLog.movie_id.in_(movie_ids),
            WatchLog.user_id.in_([p[0] for p in people]),
            WatchLog.deleted_at.is_(None),
            # A known namesake mismatch is not evidence that this film was watched.
            or_(
                WatchLog.tmdb_id.is_(None),
                Movie.tmdb_id.is_(None),
                WatchLog.tmdb_id == Movie.tmdb_id,
            ),
        )
        .order_by(WatchLog.watched_at.desc(), WatchLog.created_at.desc(), WatchLog.id.desc())
    )
    for watch in watches:
        key = (watch.movie_id, watch.user_id)
        last, rating = history.get(key, (None, None))
        history[key] = (
            last or watch.watched_at,
            rating if rating is not None else watch.personal_rating,
        )
    return people, history


async def copy_places(
    db: AsyncSession, movie_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[CollectionItem]]:
    places: dict[uuid.UUID, list[CollectionItem]] = {}
    if movie_ids:
        for copy in await db.scalars(
            select(CollectionItem)
            .where(CollectionItem.movie_id.in_(movie_ids), owned_copy())
            .order_by(CollectionItem.created_at)
        ):
            places.setdefault(copy.movie_id, []).append(copy)
    return places


def imdb_details(
    movie: Movie | None,
    suggestion: MovieNightSuggestion,
) -> tuple[str | None, Decimal | None, int | None, datetime | None]:
    """Use the newest cache for the current IMDb identity, including after a film is bought."""
    imdb_id = movie.imdb_id if movie and movie.imdb_id else suggestion.imdb_id
    sources = [
        source
        for source in (movie, suggestion)
        if source is not None
        and imdb_id is not None
        and source.imdb_id == imdb_id
        and source.imdb_ratings_id == imdb_id
        and source.imdb_ratings_checked_utc is not None
    ]
    if not sources:
        return imdb_id, None, None, None
    source = max(sources, key=lambda row: row.imdb_ratings_checked_utc or datetime.min)
    return imdb_id, source.imdb_rating, source.imdb_vote_count, source.imdb_ratings_checked_utc
