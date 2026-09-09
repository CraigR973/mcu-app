"""Streaming availability, recommendations and new releases — §7.1, §7.2, §6.5.

Everything here is a live TMDB read with nothing stored. That is deliberate: streaming
rights move constantly — a film on Netflix this week is rented-only the next — so a cached
answer is a *wrong* answer with a plausible face, and there is no user-visible signal that
it has gone stale. `completion_sets` caches because a filmography barely changes; this does
not, for the opposite reason.

**"Wanted" is missing from the ownership flags on purpose.** §7.2 asks for "owned / wanted
/ unowned" and the wanted list is §3.5, which **Batch 18** builds. Two states are what this
app can actually distinguish today; a third that never appears is a legend entry pointing at
nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.routers.movies import Database, TmdbClient
from src.routers.stats import GENRE_NAMES
from src.schemas.discovery import (
    NewReleaseListResponse,
    NewReleaseResponse,
    RecommendationListResponse,
    RecommendationResponse,
    StreamingOfferResponse,
    StreamingResponse,
)
from src.services.movie_metadata import parse_year
from src.tmdb.models import SearchResult, WatchProviderCountry

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["discovery"])

#: The three buckets TMDB reports, in the order a person cares about: already paid for,
#: then cheap, then expensive.
OFFER_ORDER: tuple[str, ...] = ("flatrate", "rent", "buy")


async def _live_movie(db: AsyncSession, movie_id: uuid.UUID) -> Movie:
    movie = await db.get(Movie, movie_id)
    if movie is None or movie.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    return movie


async def _owned_by_tmdb_id(db: AsyncSession, tmdb_ids: Sequence[int]) -> dict[int, uuid.UUID]:
    """Which of these TMDB ids this collection holds — one query for the whole page.

    Counts a film as owned only if it still has a live disc. A film whose only copy is in
    the trash is not one you can watch tonight, which is the question a recommendation is
    answering.
    """
    if not tmdb_ids:
        return {}
    rows = (
        await db.execute(
            select(Movie.tmdb_id, Movie.id)
            .join(CollectionItem, CollectionItem.movie_id == Movie.id)
            .where(
                Movie.tmdb_id.in_(list(tmdb_ids)),
                Movie.deleted_at.is_(None),
                CollectionItem.deleted_at.is_(None),
            )
            .distinct()
        )
    ).all()
    return {int(tmdb_id): movie_id for tmdb_id, movie_id in rows if tmdb_id is not None}


def _offers(country: WatchProviderCountry) -> list[StreamingOfferResponse]:
    offers: list[StreamingOfferResponse] = []
    seen: set[tuple[int, str]] = set()
    for kind in OFFER_ORDER:
        for provider in getattr(country, kind, []) or []:
            key = (provider.provider_id, kind)
            if key in seen:
                continue
            seen.add(key)
            offers.append(
                StreamingOfferResponse(
                    providerId=provider.provider_id,
                    providerName=provider.provider_name,
                    logoPath=provider.logo_path,
                    kind=kind,  # type: ignore[arg-type]
                )
            )
    return offers


@router.get("/movies/{movie_id}/streaming", response_model=StreamingResponse)
async def movie_streaming(
    movie_id: uuid.UUID,
    user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
    region: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
) -> StreamingResponse:
    """§7.1 — where this film can be streamed, in the caller's region.

    The region comes from the profile and can be overridden per request, which is what
    makes "is this on Netflix at my sister's in Ireland?" answerable without changing a
    setting.
    """
    movie = await _live_movie(db, movie_id)
    chosen = (region or user.streaming_region or "GB").upper()

    if movie.tmdb_id is None:
        # Nothing to look up. Distinct from "TMDB knows it and has no offers", which is a
        # real answer — and the difference is what the detail page needs to say.
        return StreamingResponse(
            movieId=movie.id,
            region=chosen,
            link=None,
            offers=[],
            unidentified=True,
            unavailable=False,
        )

    try:
        providers = await tmdb.get_watch_providers(movie.tmdb_id)
    except httpx.HTTPError:
        # Answered, not 502'd. A 5xx from this app is classified as a *network* failure by
        # the web client — correctly, per `DECISIONS.md` #43 — so raising one here makes
        # the page say "waiting for the network" when the network is fine and TMDB is the
        # thing that is down. Observed in the browser during this batch.
        logger.warning("tmdb_watch_providers_unavailable", movie_id=str(movie.id))
        return StreamingResponse(
            movieId=movie.id,
            region=chosen,
            link=None,
            offers=[],
            unidentified=False,
            unavailable=True,
        )

    country = providers.results.get(chosen)
    return StreamingResponse(
        movieId=movie.id,
        region=chosen,
        link=country.link if country else None,
        offers=_offers(country) if country else [],
        unidentified=False,
        unavailable=False,
    )


def _recommendation(result: SearchResult, owned: dict[int, uuid.UUID]) -> RecommendationResponse:
    movie_id = owned.get(result.id)
    return RecommendationResponse(
        tmdbId=result.id,
        title=result.title,
        year=parse_year(result.release_date),
        overview=result.overview,
        posterPath=result.poster_path,
        ownership="owned" if movie_id else "unowned",
        movieId=movie_id,
    )


@router.get("/movies/{movie_id}/recommendations", response_model=RecommendationListResponse)
async def movie_recommendations(
    movie_id: uuid.UUID,
    _user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
) -> RecommendationListResponse:
    """§7.2 — TMDB's recommendations, flagged against what is on the shelf.

    §7.2's acceptance asks for "10+ recommendations with correct ownership flags". TMDB
    returns 20 per page for a well-known film and can return **none** for an obscure one;
    the endpoint reports what there is rather than padding, because a padded list would
    make the flag meaningless.
    """
    movie = await _live_movie(db, movie_id)
    if movie.tmdb_id is None:
        return RecommendationListResponse(movieId=movie.id, items=[], ownedCount=0)

    try:
        results = await tmdb.get_recommendations(movie.tmdb_id)
    except httpx.HTTPError:
        logger.warning("tmdb_recommendations_unavailable", movie_id=str(movie.id))
        return RecommendationListResponse(
            movieId=movie.id, items=[], ownedCount=0, unavailable=True
        )

    owned = await _owned_by_tmdb_id(db, [result.id for result in results.results])
    items = [_recommendation(result, owned) for result in results.results]
    return RecommendationListResponse(
        movieId=movie.id,
        items=items,
        ownedCount=sum(1 for item in items if item.ownership == "owned"),
    )


async def _collected_genres(db: AsyncSession, limit: int) -> list[int]:
    """The genres this collection actually leans on, commonest first.

    §7.2 says the new-releases feed is "filtered by collected genres", and taking them
    from the collection rather than from a settings screen means the feed is right on day
    one and stays right as the shelves change.
    """
    element = func.unnest(Movie.genre_ids).table_valued("genre_id").render_derived()
    rows = (
        await db.execute(
            select(element.c.genre_id, func.count(func.distinct(Movie.id)))
            .select_from(Movie)
            .join(element, true())
            .where(Movie.deleted_at.is_(None))
            .group_by(element.c.genre_id)
            .order_by(func.count(func.distinct(Movie.id)).desc())
            .limit(limit)
        )
    ).all()
    return [int(genre_id) for genre_id, _ in rows]


@router.get("/discover/new-releases", response_model=NewReleaseListResponse)
async def new_releases(
    _user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
    genre_limit: Annotated[int, Query(alias="genreLimit", ge=1, le=10)] = 5,
) -> NewReleaseListResponse:
    """§7.2's "new releases feed filtered by collected genres".

    Every result says *which* of the collection's genres put it there. A suggestion that
    cannot explain itself is indistinguishable from a random one.
    """
    genres = await _collected_genres(db, genre_limit)
    genre_set = set(genres)

    try:
        results = await tmdb.get_upcoming(region=(_user.streaming_region or "GB").upper())
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="New releases are temporarily unavailable",
        ) from exc

    owned = await _owned_by_tmdb_id(db, [result.id for result in results.results])
    items: list[NewReleaseResponse] = []
    for result in results.results:
        matched = sorted(genre_set.intersection(result.genre_ids or []))
        if genre_set and not matched:
            continue
        movie_id = owned.get(result.id)
        items.append(
            NewReleaseResponse(
                tmdbId=result.id,
                title=result.title,
                releaseDate=result.release_date,
                posterPath=result.poster_path,
                overview=result.overview,
                matchedGenres=[GENRE_NAMES.get(g, str(g)) for g in matched],
                ownership="owned" if movie_id else "unowned",
                movieId=movie_id,
            )
        )

    return NewReleaseListResponse(
        items=items,
        basedOnGenres=[GENRE_NAMES.get(g, str(g)) for g in genres],
    )
