"""Feeling lucky: one owned film, with no persisted run or outside-world request."""

from fastapi import APIRouter
from sqlalchemy import exists, func, or_, select

from src.auth import CurrentUser
from src.models.collection_item import CollectionItem, owned_copy, owned_film
from src.models.movie import Movie
from src.models.movie_night import MovieNightSuggestion
from src.models.watch_log import WatchLog
from src.routers.movie_night import _session_for
from src.routers.movies import Database, _enrich_list_items
from src.schemas.lucky import LuckyRequest, LuckyResponse

router = APIRouter(prefix="/api/v1", tags=["feeling-lucky"])


@router.post("/feeling-lucky", response_model=LuckyResponse)
async def deal_film(payload: LuckyRequest, user: CurrentUser, db: Database) -> LuckyResponse:
    """POST carries the exclusion list without a URL-length limit; this only reads."""
    query = select(Movie).where(
        Movie.deleted_at.is_(None),
        owned_film(),
        or_(Movie.media_type.is_(None), Movie.media_type == "film"),
        Movie.tmdb_tv_id.is_(None),
        Movie.id.not_in(payload.excludedIds),
    )
    if payload.unwatchedOnly:
        query = query.where(
            ~exists(
                select(WatchLog.id).where(
                    WatchLog.movie_id == Movie.id,
                    WatchLog.user_id == user.id,
                    WatchLog.deleted_at.is_(None),
                )
            )
        )
    if payload.sessionId is not None:
        night = await _session_for(db, payload.sessionId, user, must_be_open=True)
        filters = night.filters or {}
        # Same inclusive year/rating bounds as the night's seeded Archive shortlist.
        if isinstance(filters.get("decadeFrom"), int):
            query = query.where(Movie.year >= filters["decadeFrom"])
        if isinstance(filters.get("decadeTo"), int):
            query = query.where(Movie.year <= filters["decadeTo"])
        if isinstance(filters.get("minRating"), int | float):
            query = query.where(Movie.tmdb_rating >= filters["minRating"])
        # A random seed may be promoted; a person's existing suggestion is already taken.
        query = query.where(
            ~exists(
                select(MovieNightSuggestion.id).where(
                    MovieNightSuggestion.session_id == night.id,
                    MovieNightSuggestion.suggested_by.is_not(None),
                    or_(
                        MovieNightSuggestion.movie_id == Movie.id,
                        MovieNightSuggestion.tmdb_id == Movie.tmdb_id,
                    ),
                )
            )
        )
    movie = (await db.execute(query.order_by(func.random()).limit(1))).scalar_one_or_none()
    if movie is None:
        return LuckyResponse(film=None)
    copies = int(
        await db.scalar(
            select(func.count(CollectionItem.id)).where(
                CollectionItem.movie_id == movie.id, owned_copy()
            )
        )
        or 0
    )
    films = await _enrich_list_items(db, user.id, [(movie, copies)])
    return LuckyResponse(film=films[0])
