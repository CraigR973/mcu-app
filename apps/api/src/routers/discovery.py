"""Streaming availability, recommendations and new releases — §7.1, §7.2, §6.5.

Everything here is a live TMDB read with nothing stored. That is deliberate: streaming
rights move constantly — a film on Netflix this week is rented-only the next — so a cached
answer is a *wrong* answer with a plausible face, and there is no user-visible signal that
it has gone stale. `completion_sets` caches because a filmography barely changes; this does
not, for the opposite reason.

**All three of §7.2's ownership flags are live since Batch 18.** Batch 16 shipped two —
"owned" and "unowned" — because §3.5's `wanted_list` did not exist and a "wanted" badge that
could never appear is a legend entry pointing at nothing. The table exists now, so the third
state is real.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import exists, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.matching.engine import canonical_title
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.wanted import WantedItem
from src.routers.movies import Database, TmdbClient, last_watched_by_movie
from src.routers.stats import GENRE_NAMES
from src.schemas.discovery import (
    BeyondResultResponse,
    BeyondSearchResponse,
    ExternalFilmResponse,
    MaybeOwnedResponse,
    NewReleaseListResponse,
    NewReleaseResponse,
    OfferKind,
    OwnershipState,
    RecommendationListResponse,
    RecommendationResponse,
    StreamingOfferResponse,
    StreamingResponse,
)
from src.services.movie_metadata import parse_year
from src.tmdb import TMDBClient
from src.tmdb.models import SearchResult, WatchProvider, WatchProviderCountry

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["discovery"])

#: The three buckets TMDB reports, in the order a person cares about: already paid for,
#: then cheap, then expensive.
#: Typed as the ``OfferKind`` literal, not ``tuple[str, ...]``, so the loop variable is
#: already narrowed where it is used. With a bare ``str`` the constructor below needs a
#: ``# type: ignore[arg-type]`` — and `STATUS.md` gotcha 21 is the record of what that
#: costs: mypy is unpinned, this machine's called the ignore *necessary* and CI's called it
#: *unused*, and ``warn_unused_ignores`` turned the disagreement into a red gate. The fix
#: is to need no ignore.
OFFER_ORDER: tuple[OfferKind, ...] = ("flatrate", "rent", "buy")


async def _live_movie(db: AsyncSession, movie_id: uuid.UUID) -> Movie:
    movie = await db.get(Movie, movie_id)
    if movie is None or movie.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    return movie


async def _wanted_tmdb_ids(db: AsyncSession, tmdb_ids: Sequence[int]) -> set[int]:
    """Which of these films are on the wanted list — Batch 18's third ownership state.

    Live, **active** entries only: an entry marked "no longer looking" is a decision, and
    showing it as *wanted* would contradict it.
    """
    if not tmdb_ids:
        return set()
    rows = await db.execute(
        select(Movie.tmdb_id)
        .join(WantedItem, WantedItem.movie_id == Movie.id)
        .where(
            Movie.tmdb_id.in_(list(tmdb_ids)),
            Movie.deleted_at.is_(None),
            WantedItem.deleted_at.is_(None),
            WantedItem.is_active.is_(True),
        )
        .distinct()
    )
    return {int(value) for value in rows.scalars().all() if value is not None}


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
                owned_copy(),
            )
            .distinct()
        )
    ).all()
    return {int(tmdb_id): movie_id for tmdb_id, movie_id in rows if tmdb_id is not None}


def _offers(country: WatchProviderCountry) -> list[StreamingOfferResponse]:
    offers: list[StreamingOfferResponse] = []
    seen: set[tuple[int, OfferKind]] = set()
    for kind in OFFER_ORDER:
        providers: list[WatchProvider] = getattr(country, kind, []) or []
        for provider in providers:
            key = (provider.provider_id, kind)
            if key in seen:
                continue
            seen.add(key)
            offers.append(
                StreamingOfferResponse(
                    providerId=provider.provider_id,
                    providerName=provider.provider_name,
                    logoPath=provider.logo_path,
                    kind=kind,
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


def _ownership(tmdb_id: int, movie_id: uuid.UUID | None, wanted: set[int]) -> OwnershipState:
    """Owned beats wanted.

    Both can be true at once — a DVD-to-4K upgrade is exactly a film you own *and* want —
    and "you already have this" is the more useful thing to say on a card whose job is to
    suggest something to watch or buy.
    """
    if movie_id is not None:
        return "owned"
    return "wanted" if tmdb_id in wanted else "unowned"


def _recommendation(
    result: SearchResult, owned: dict[int, uuid.UUID], wanted: set[int]
) -> RecommendationResponse:
    movie_id = owned.get(result.id)
    return RecommendationResponse(
        tmdbId=result.id,
        title=result.title,
        year=parse_year(result.release_date),
        overview=result.overview,
        posterPath=result.poster_path,
        ownership=_ownership(result.id, movie_id, wanted),
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

    ids = [result.id for result in results.results]
    owned = await _owned_by_tmdb_id(db, ids)
    wanted = await _wanted_tmdb_ids(db, ids)
    items = [_recommendation(result, owned, wanted) for result in results.results]
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

    upcoming_ids = [result.id for result in results.results]
    owned = await _owned_by_tmdb_id(db, upcoming_ids)
    wanted = await _wanted_tmdb_ids(db, upcoming_ids)
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
                ownership=_ownership(result.id, movie_id, wanted),
                movieId=movie_id,
            )
        )

    return NewReleaseListResponse(
        items=items,
        basedOnGenres=[GENRE_NAMES.get(g, str(g)) for g in genres],
    )


# ---------------------------------------------------------------------------
# Batch T2 — search beyond the shelf, and a card for a film we don't hold
# ---------------------------------------------------------------------------

#: How many results get a streaming lookup. Each one is a TMDB call, and this search runs
#: while somebody types.
STREAMING_LOOKUPS = 5
#: How long one film's streaming line is reused: long enough to cover one search, while
#: typing "the god", "the godf", "the godfa" asks about the same films three times. Kept
#: short on purpose — `StreamingPanel` caches nothing, because a stale "on Netflix" is a
#: wrong answer — so this is a search's worth of reuse, not a store.
STREAMING_TTL_SECONDS = 30 * 60
_STREAMING_CACHE_LIMIT = 2_000
_streaming_cache: dict[tuple[int, str], tuple[float, list[str]]] = {}


async def _cached_streaming_names(tmdb: TMDBClient, tmdb_id: int, region: str) -> list[str] | None:
    """Subscription services for one film in one region, or ``None`` when TMDB failed.

    **A failed lookup costs the line, never the result**, and is not cached, so the next
    search asks again.
    """
    key = (tmdb_id, region)
    now = time.monotonic()
    cached = _streaming_cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]
    try:
        providers = await tmdb.get_watch_providers(tmdb_id)
    except Exception:  # noqa: BLE001 - see the docstring
        logger.warning("tmdb_watch_providers_unavailable", tmdb_id=tmdb_id)
        return None
    country = providers.results.get(region)
    names = [provider.provider_name for provider in (country.flatrate if country else [])][:4]
    if len(_streaming_cache) >= _STREAMING_CACHE_LIMIT:
        _streaming_cache.clear()
    _streaming_cache[key] = (now + STREAMING_TTL_SECONDS, names)
    return names


async def _movie_rows_by_tmdb_id(db: AsyncSession, tmdb_ids: Sequence[int]) -> dict[int, uuid.UUID]:
    """Any live ``movies`` row carrying these TMDB ids — owned, watched, wanted or sold."""
    if not tmdb_ids:
        return {}
    rows = await db.execute(
        select(Movie.tmdb_id, Movie.id).where(
            Movie.tmdb_id.in_(list(tmdb_ids)), Movie.deleted_at.is_(None)
        )
    )
    return {int(tmdb_id): movie_id for tmdb_id, movie_id in rows.all() if tmdb_id is not None}


@dataclass(frozen=True)
class _Unidentified:
    movie_id: uuid.UUID
    title: str
    canonical: str
    year: int | None


async def _unidentified_owned(db: AsyncSession) -> list[_Unidentified]:
    """Owned films nothing has matched to TMDB yet, with their titles made comparable.

    A few hundred rows at most, and falling as identification proceeds.
    """
    has_disc = exists(
        select(CollectionItem.id).where(CollectionItem.movie_id == Movie.id, owned_copy())
    )
    rows = await db.execute(
        select(Movie.id, Movie.title, Movie.year).where(
            Movie.tmdb_id.is_(None), Movie.deleted_at.is_(None), has_disc
        )
    )
    films: list[_Unidentified] = []
    for movie_id, title, year in rows.all():
        canonical, title_year = canonical_title(title)
        films.append(_Unidentified(movie_id, title, canonical, year or title_year))
    return films


def _lookalike(
    films: Sequence[_Unidentified], title: str, year: int | None
) -> _Unidentified | None:
    canonical, _ = canonical_title(title)
    for film in films:
        if film.canonical != canonical:
            continue
        if film.year is None or year is None or film.year == year:
            return film
    return None


@router.get("/search/beyond", response_model=BeyondSearchResponse)
async def search_beyond(
    user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
    q: Annotated[str, Query(min_length=2, max_length=200)],
) -> BeyondSearchResponse:
    """Films that match a search and are **not** on the shelf — Batch T2, snag 14.

    ``GET /search`` answers "do we own it, and where is it?". This answers the rest: what
    else goes by that name, where it streams, and whether it might be one of ours that
    nothing has identified yet. A film with a live disc never appears here; it is
    ``/search``'s, and showing it twice would be the duplicate the criterion forbids.
    """
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Query too short"
        )
    try:
        results = await tmdb.search_movie(query)
    except Exception:  # noqa: BLE001 - "TMDB did not answer" is a state, not a 5xx
        logger.warning("tmdb_search_unavailable")
        return BeyondSearchResponse(query=query, items=[], unavailable=True)

    top = results.results[:10]
    ids = [result.id for result in top]
    owned = await _owned_by_tmdb_id(db, ids)
    rows = await _movie_rows_by_tmdb_id(db, ids)
    last_watched = await last_watched_by_movie(db, user.id, list(rows.values()))
    unidentified = await _unidentified_owned(db)
    region = (user.streaming_region or "GB").upper()

    beyond = [result for result in top if result.id not in owned]
    looked_up = await asyncio.gather(
        *(_cached_streaming_names(tmdb, r.id, region) for r in beyond[:STREAMING_LOOKUPS])
    )

    items: list[BeyondResultResponse] = []
    for index, result in enumerate(beyond):
        year = parse_year(result.release_date)
        names = looked_up[index] if index < len(looked_up) else None
        movie_id = rows.get(result.id)
        lookalike = _lookalike(unidentified, result.title, year)
        items.append(
            BeyondResultResponse(
                tmdbId=result.id,
                title=result.title,
                year=year,
                posterPath=result.poster_path,
                overview=result.overview,
                movieId=movie_id,
                lastWatchedAt=last_watched.get(movie_id) if movie_id else None,
                streamingOn=names or [],
                streamingChecked=names is not None,
                maybeOwned=(
                    MaybeOwnedResponse(movieId=lookalike.movie_id, title=lookalike.title)
                    if lookalike
                    else None
                ),
            )
        )
    return BeyondSearchResponse(query=query, items=items)


@router.get("/films/tmdb/{tmdb_id}", response_model=ExternalFilmResponse)
async def external_film(
    tmdb_id: Annotated[int, Path(ge=1)],
    user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
) -> ExternalFilmResponse:
    """A film card for something the collection does not hold — Batch T2.

    One TMDB call: details, credits and watch providers arrive together through
    ``append_to_response``. Says whether the film is owned, so the web app can send an
    owned film to its own page instead of showing it as a stranger.
    """
    try:
        film = await tmdb.get_movie_full(tmdb_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="TMDB has no film with that id"
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TMDB didn't answer. Try again in a moment.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TMDB didn't answer. Try again in a moment.",
        ) from exc

    region = (user.streaming_region or "GB").upper()
    rows = await _movie_rows_by_tmdb_id(db, [tmdb_id])
    owned = await _owned_by_tmdb_id(db, [tmdb_id])
    wanted = await _wanted_tmdb_ids(db, [tmdb_id])
    country = film.watch_providers.results.get(region) if film.watch_providers else None
    cast_members = (
        [member.name for member in sorted(film.credits.cast, key=lambda m: m.order)[:5]]
        if film.credits
        else []
    )
    directors = (
        [member.name for member in film.credits.crew if member.job == "Director"][:2]
        if film.credits
        else []
    )
    return ExternalFilmResponse(
        tmdbId=film.id,
        title=film.title,
        year=parse_year(film.release_date),
        posterPath=film.poster_path,
        backdropPath=film.backdrop_path,
        overview=film.overview,
        runtimeMinutes=film.runtime or None,
        genres=[genre.name for genre in film.genres],
        cast=cast_members,
        directors=directors,
        movieId=rows.get(tmdb_id),
        owned=tmdb_id in owned,
        wanted=tmdb_id in wanted,
        region=region,
        link=country.link if country else None,
        offers=_offers(country) if country else [],
    )
