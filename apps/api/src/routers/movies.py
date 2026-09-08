"""Collection browse, detail, search, and in-app TMDB identification."""

from __future__ import annotations

import math
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Annotated, Literal, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, delete, desc, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import ScalarSelect

from src.auth import CurrentUser
from src.database import get_db
from src.matching import MatchingEngine
from src.models.collection_item import SECTIONS, SHELVED_SECTIONS, CollectionItem
from src.models.movie import Movie, MovieCredit
from src.models.watch_log import WatchLog
from src.schemas.movies import (
    CandidateListResponse,
    CandidateResponse,
    CastResponse,
    CollectionCopyResponse,
    CollectionFacetsResponse,
    CreditResponse,
    DecadeFacetResponse,
    GenreResponse,
    IdentifyMovieRequest,
    LocationResponse,
    MovieDetailResponse,
    MovieListItemResponse,
    MoviePageResponse,
    SearchResponse,
    SectionFacetResponse,
    ShelfFacetResponse,
)
from src.services.movie_metadata import credit_rows, movie_metadata_values
from src.tmdb import TMDBClient

router = APIRouter(prefix="/api/v1", tags=["movies"])


async def get_tmdb_client() -> AsyncIterator[TMDBClient]:
    async with TMDBClient() as client:
        yield client


TmdbClient = Annotated[TMDBClient, Depends(get_tmdb_client)]
Database = Annotated[AsyncSession, Depends(get_db)]


@dataclass(frozen=True)
class _Filters:
    """Every way the collection can be narrowed, in one object.

    It exists because the list endpoint asks the same question twice — once for the
    film count and once for the disc count — and Batch 5 spelled the predicates out
    separately in each. That was survivable with three filters and would be a standing
    invitation to drift with nine.
    """

    genre_id: int | None = None
    year: int | None = None
    format_code: str | None = None
    section: str | None = None
    shelf: str | None = None
    decade_from: int | None = None
    decade_to: int | None = None
    min_rating: float | None = None
    watched: bool | None = None
    user_id: uuid.UUID | None = None


def _item_predicates(filters: _Filters) -> list[ColumnElement[bool]]:
    """Conditions on the disc itself — format and where it is kept."""
    predicates: list[ColumnElement[bool]] = [CollectionItem.deleted_at.is_(None)]
    if filters.format_code is not None:
        predicates.append(CollectionItem.formats.contains([filters.format_code]))
    if filters.section is not None:
        predicates.append(CollectionItem.section == filters.section)
    if filters.shelf is not None:
        predicates.append(CollectionItem.shelf == filters.shelf)
    return predicates


def _watched_exists(user_id: uuid.UUID) -> ColumnElement[bool]:
    return exists(
        select(WatchLog.id).where(
            WatchLog.movie_id == Movie.id,
            WatchLog.user_id == user_id,
            WatchLog.deleted_at.is_(None),
        )
    )


def _movie_predicates(filters: _Filters) -> list[ColumnElement[bool]]:
    """Conditions on the film — genre, when it came out, how it scored, seen or not."""
    predicates: list[ColumnElement[bool]] = [Movie.deleted_at.is_(None)]
    if filters.genre_id is not None:
        predicates.append(Movie.genre_ids.contains([filters.genre_id]))
    if filters.year is not None:
        predicates.append(Movie.year == filters.year)
    if filters.decade_from is not None:
        predicates.append(Movie.year >= filters.decade_from)
    if filters.decade_to is not None:
        # Inclusive of the whole decade: "to 1940s" reaches 1949.
        predicates.append(Movie.year <= filters.decade_to + 9)
    if filters.min_rating is not None:
        # A film with no rating is excluded rather than treated as zero. All 757 of
        # them are unidentified, so "rated 7+" quietly meaning "identified and rated
        # 7+" is the only reading that does not overstate what is known.
        predicates.append(Movie.tmdb_rating >= filters.min_rating)
    if filters.watched is not None and filters.user_id is not None:
        seen = _watched_exists(filters.user_id)
        predicates.append(seen if filters.watched else ~seen)
    return predicates


def _live_copy_exists(filters: _Filters) -> ColumnElement[bool]:
    return exists(
        select(CollectionItem.id).where(
            CollectionItem.movie_id == Movie.id,
            *_item_predicates(filters),
        )
    )


def _all_predicates(filters: _Filters) -> list[ColumnElement[bool]]:
    """The film-level WHERE: the film matches, and it has a disc that matches."""
    return [*_movie_predicates(filters), _live_copy_exists(filters)]


def _copy_count() -> ScalarSelect[int]:
    return (
        select(func.count(CollectionItem.id))
        .where(
            CollectionItem.movie_id == Movie.id,
            CollectionItem.deleted_at.is_(None),
        )
        .correlate(Movie)
        .scalar_subquery()
    )


def location_label(section: str | None, shelf: str | None) -> str:
    """Compose the one string every surface uses for a place.

    Built here rather than in each of the three collection views so "Front 2nd" cannot
    become "Front 2nd shelf" in one of them and "Front, 2nd" in another.
    """
    if section is None and shelf is None:
        return "Unfiled"
    if shelf is None:
        return section or "Unfiled"
    return f"{section} {shelf}" if section else f"{shelf} shelf"


async def _locations_by_movie(
    db: AsyncSession, movie_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[LocationResponse]]:
    """Where each film's live copies are kept.

    One grouped query for the whole page rather than a correlated aggregate per row —
    the page can be the entire 1,857-film catalogue, and this keeps that one index scan
    instead of 1,857 subquery evaluations.
    """
    if not movie_ids:
        return {}
    rows = (
        await db.execute(
            select(CollectionItem.movie_id, CollectionItem.section, CollectionItem.shelf)
            .where(
                CollectionItem.movie_id.in_(movie_ids),
                CollectionItem.deleted_at.is_(None),
            )
            .group_by(CollectionItem.movie_id, CollectionItem.section, CollectionItem.shelf)
            .order_by(
                CollectionItem.section.asc().nulls_last(),
                CollectionItem.shelf.asc().nulls_last(),
            )
        )
    ).all()
    grouped: dict[uuid.UUID, list[LocationResponse]] = {}
    for movie_id, section, shelf in rows:
        grouped.setdefault(movie_id, []).append(
            LocationResponse(section=section, shelf=shelf, label=location_label(section, shelf))
        )
    return grouped


async def _watched_movie_ids(
    db: AsyncSession, user_id: uuid.UUID, movie_ids: Sequence[uuid.UUID]
) -> set[uuid.UUID]:
    """Which of these films the requesting user has logged a watch for."""
    if not movie_ids:
        return set()
    rows = await db.execute(
        select(WatchLog.movie_id)
        .where(
            WatchLog.user_id == user_id,
            WatchLog.movie_id.in_(movie_ids),
            WatchLog.deleted_at.is_(None),
        )
        .distinct()
    )
    return set(rows.scalars().all())


def _movie_list_item(
    movie: Movie,
    copy_count: int,
    *,
    locations: list[LocationResponse] | None = None,
    watched: bool = False,
) -> MovieListItemResponse:
    return MovieListItemResponse(
        id=movie.id,
        title=movie.title,
        originalTitle=movie.original_title,
        year=movie.year,
        posterPath=movie.poster_path,
        backdropPath=movie.backdrop_path,
        tmdbRating=float(movie.tmdb_rating) if movie.tmdb_rating is not None else None,
        runtimeMinutes=movie.runtime_minutes,
        bestFormatOwned=movie.best_format_owned,
        bestHdrOwned=movie.best_hdr_owned,
        bestAudioOwned=movie.best_audio_owned,
        identified=movie.tmdb_id is not None,
        copyCount=copy_count,
        locations=locations or [],
        watched=watched,
    )


async def _enrich_list_items(
    db: AsyncSession,
    user_id: uuid.UUID,
    rows: Sequence[tuple[Movie, int]],
) -> list[MovieListItemResponse]:
    """Attach location and watched state to a page of films in two extra queries."""
    movie_ids = [movie.id for movie, _ in rows]
    locations = await _locations_by_movie(db, movie_ids)
    watched = await _watched_movie_ids(db, user_id, movie_ids)
    return [
        _movie_list_item(
            movie,
            copies,
            locations=locations.get(movie.id, []),
            watched=movie.id in watched,
        )
        for movie, copies in rows
    ]


async def _get_live_movie(db: AsyncSession, movie_id: uuid.UUID) -> Movie:
    movie = await db.get(Movie, movie_id)
    if movie is None or movie.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    return movie


async def _movie_detail(db: AsyncSession, movie: Movie) -> MovieDetailResponse:
    copy_count = int(
        (
            await db.execute(
                select(func.count(CollectionItem.id)).where(
                    CollectionItem.movie_id == movie.id,
                    CollectionItem.deleted_at.is_(None),
                )
            )
        ).scalar_one()
    )
    credits = (
        (
            await db.execute(
                select(MovieCredit)
                .where(MovieCredit.movie_id == movie.id)
                .order_by(MovieCredit.role, MovieCredit.display_order.asc().nulls_last())
            )
        )
        .scalars()
        .all()
    )

    profile_paths: dict[int, str | None] = {}
    for member in movie.top_cast_summary or []:
        person_id = member.get("tmdb_person_id")
        if isinstance(person_id, int):
            raw_path = member.get("profile_path")
            profile_paths[person_id] = raw_path if isinstance(raw_path, str) else None

    cast_members = [
        CastResponse(
            personName=credit.person_name,
            tmdbPersonId=credit.tmdb_person_id,
            characterName=credit.character_name,
            profilePath=(
                profile_paths.get(credit.tmdb_person_id)
                if credit.tmdb_person_id is not None
                else None
            ),
        )
        for credit in credits
        if credit.role == "cast"
    ]
    crew = [
        CreditResponse(
            personName=credit.person_name,
            tmdbPersonId=credit.tmdb_person_id,
            role=cast(Literal["director", "writer", "producer", "composer"], credit.role),
        )
        for credit in credits
        if credit.role != "cast"
    ]
    genres = [
        GenreResponse(id=genre["id"], name=genre["name"])
        for genre in movie.genres or []
        if isinstance(genre.get("id"), int) and isinstance(genre.get("name"), str)
    ]

    return MovieDetailResponse(
        **_movie_list_item(movie, copy_count).model_dump(),
        imdbId=movie.imdb_id,
        overview=movie.overview,
        tagline=movie.tagline,
        genres=genres,
        cast=cast_members,
        crew=crew,
        trailerKey=movie.trailer_key,
        letterboxdSlug=movie.letterboxd_slug,
        mediaType=movie.media_type,
    )


def _validate_decade(value: int | None, name: str) -> int | None:
    if value is not None and value % 10 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{name} must be the first year of a decade, such as 1940",
        )
    return value


@router.get("/movies", response_model=MoviePageResponse)
async def list_movies(
    user: CurrentUser,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    # The virtualised collection views request the complete ~2,000-film catalogue so
    # their scroll range represents every owned film, while callers that want ordinary
    # pagination can still choose a smaller page size.
    per_page: Annotated[int, Query(alias="perPage", ge=1, le=2000)] = 60,
    genre_id: Annotated[int | None, Query(alias="genreId", gt=0)] = None,
    year: Annotated[int | None, Query(ge=1870, le=2200)] = None,
    format_code: Annotated[str | None, Query(alias="format", min_length=1, max_length=50)] = None,
    section: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    shelf: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    decade_from: Annotated[int | None, Query(alias="decadeFrom", ge=1870, le=2200)] = None,
    decade_to: Annotated[int | None, Query(alias="decadeTo", ge=1870, le=2200)] = None,
    min_rating: Annotated[float | None, Query(alias="minRating", ge=0, le=10)] = None,
    watched: Annotated[bool | None, Query()] = None,
    sort_by: Annotated[Literal["title", "year", "rating"], Query(alias="sort")] = "title",
    order: Literal["asc", "desc"] = "asc",
) -> MoviePageResponse:
    if section is not None and section not in SECTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown section. Expected one of: {', '.join(SECTIONS)}",
        )
    decade_from = _validate_decade(decade_from, "decadeFrom")
    decade_to = _validate_decade(decade_to, "decadeTo")
    if decade_from is not None and decade_to is not None and decade_from > decade_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="decadeFrom must not be later than decadeTo",
        )

    filters = _Filters(
        genre_id=genre_id,
        year=year,
        format_code=format_code,
        section=section,
        shelf=shelf,
        decade_from=decade_from,
        decade_to=decade_to,
        min_rating=min_rating,
        watched=watched,
        user_id=user.id,
    )
    predicates = _all_predicates(filters)

    total_movies = int(
        (await db.execute(select(func.count(Movie.id)).where(*predicates))).scalar_one()
    )

    # The disc count answers a different question from the film count — "how many
    # objects match" rather than "how many titles" — so it counts items directly
    # rather than reusing the EXISTS.
    total_items = int(
        (
            await db.execute(
                select(func.count(CollectionItem.id))
                .join(Movie, Movie.id == CollectionItem.movie_id)
                .where(*_item_predicates(filters), *_movie_predicates(filters))
            )
        ).scalar_one()
    )

    sort_column = {
        "title": func.lower(Movie.title),
        "year": Movie.year,
        "rating": Movie.tmdb_rating,
    }[sort_by]
    direction = asc if order == "asc" else desc
    copy_count = _copy_count().label("copy_count")
    rows = (
        await db.execute(
            select(Movie, copy_count)
            .where(*predicates)
            .order_by(direction(sort_column).nulls_last(), asc(func.lower(Movie.title)))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    return MoviePageResponse(
        items=await _enrich_list_items(db, user.id, [(m, int(c)) for m, c in rows]),
        totalMovies=total_movies,
        totalItems=total_items,
        page=page,
        perPage=per_page,
        pages=math.ceil(total_movies / per_page),
    )


@router.get("/collection/facets", response_model=CollectionFacetsResponse)
async def get_collection_facets(_user: CurrentUser, db: Database) -> CollectionFacetsResponse:
    """The vocabulary the filter bar offers, counted from the data.

    Serving it rather than hard-coding it is what keeps the shelf picker honest: it can
    never offer "Front 7th" because no such shelf exists, and it cannot miss a shelf
    that a newly added disc has just created. Genres and formats stay static in the web
    app because those are closed vocabularies; where 1,857 discs actually live is not.
    """
    rows = (
        await db.execute(
            select(
                CollectionItem.section,
                CollectionItem.shelf,
                func.count(CollectionItem.id),
                func.count(func.distinct(CollectionItem.movie_id)),
            )
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(CollectionItem.deleted_at.is_(None), Movie.deleted_at.is_(None))
            .group_by(CollectionItem.section, CollectionItem.shelf)
        )
    ).all()

    unsectioned = sum(items for sec, _shelf, items, _movies in rows if sec is None)
    by_section: dict[str, list[tuple[str | None, int, int]]] = {}
    for sec, shelf, items, movies in rows:
        if sec is None:
            continue
        by_section.setdefault(sec, []).append((shelf, int(items), int(movies)))

    # SECTIONS order, not count order or alphabetical: the five §3.4 areas first and
    # the cabinets after, which is how the shelves are laid out in the room.
    sections = [
        SectionFacetResponse(
            section=name,
            itemCount=sum(items for _shelf, items, _movies in by_section[name]),
            movieCount=sum(movies for _shelf, _items, movies in by_section[name]),
            shelves=[
                ShelfFacetResponse(shelf=shelf, itemCount=items, movieCount=movies)
                for shelf, items, movies in sorted(
                    ((s, i, m) for s, i, m in by_section[name] if s is not None),
                    key=lambda row: row[0],
                )
            ]
            if name in SHELVED_SECTIONS
            else [],
        )
        for name in SECTIONS
        if name in by_section
    ]

    decade = (func.floor(Movie.year / 10) * 10).label("decade")
    decade_rows = (
        await db.execute(
            select(decade, func.count(Movie.id))
            .where(
                Movie.deleted_at.is_(None),
                Movie.year.is_not(None),
                _live_copy_exists(_Filters()),
            )
            .group_by(decade)
            .order_by(decade)
        )
    ).all()

    undated = int(
        (
            await db.execute(
                select(func.count(Movie.id)).where(
                    Movie.deleted_at.is_(None),
                    Movie.year.is_(None),
                    _live_copy_exists(_Filters()),
                )
            )
        ).scalar_one()
    )

    return CollectionFacetsResponse(
        sections=sections,
        unsectionedItemCount=int(unsectioned),
        decades=[
            DecadeFacetResponse(decade=int(value), movieCount=int(count))
            for value, count in decade_rows
        ],
        undatedMovieCount=undated,
    )


@router.get("/movies/{movie_id}", response_model=MovieDetailResponse)
async def get_movie(movie_id: uuid.UUID, _user: CurrentUser, db: Database) -> MovieDetailResponse:
    return await _movie_detail(db, await _get_live_movie(db, movie_id))


@router.get("/movies/{movie_id}/copies", response_model=list[CollectionCopyResponse])
async def get_movie_copies(
    movie_id: uuid.UUID,
    _user: CurrentUser,
    db: Database,
) -> list[CollectionCopyResponse]:
    await _get_live_movie(db, movie_id)
    copies = (
        (
            await db.execute(
                select(CollectionItem)
                .where(
                    CollectionItem.movie_id == movie_id,
                    CollectionItem.deleted_at.is_(None),
                )
                .order_by(CollectionItem.created_at, CollectionItem.id)
            )
        )
        .scalars()
        .all()
    )
    return [
        CollectionCopyResponse(
            id=copy.id,
            formats=copy.formats,
            location=copy.location,
            section=copy.section,
            shelf=copy.shelf,
            subCategory=copy.sub_category,
            notes=copy.notes,
            purchasePrice=(str(copy.purchase_price) if copy.purchase_price is not None else None),
            purchaseSource=copy.purchase_source,
            purchaseDate=copy.purchase_date,
            condition=copy.condition,
            hasPlaybackIssues=copy.has_playback_issues,
            playbackNotes=copy.playback_notes,
            videoSpecs=copy.video_specs,
            audioSpecs=copy.audio_specs,
            specialFeatures=copy.special_features,
            regionCode=copy.region_code,
            releaseLabel=copy.release_label,
            listingStatus=copy.listing_status,
            updatedAt=copy.updated_at,
        )
        for copy in copies
    ]


@router.get("/search", response_model=SearchResponse)
async def search_movies(
    user: CurrentUser,
    db: Database,
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResponse:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query too short",
        )

    tsquery = func.websearch_to_tsquery("english", query)
    filters = [
        Movie.deleted_at.is_(None),
        _live_copy_exists(_Filters()),
        Movie.search_vector.op("@@")(tsquery),
    ]
    rank = func.ts_rank_cd(Movie.search_vector, tsquery).label("rank")
    copy_count = _copy_count().label("copy_count")
    total_matches = func.count(Movie.id).over().label("total_matches")
    rows = (
        await db.execute(
            select(Movie, copy_count, rank, total_matches)
            .where(*filters)
            .order_by(desc(rank), asc(func.lower(Movie.title)))
            .limit(limit)
        )
    ).all()
    return SearchResponse(
        items=await _enrich_list_items(
            db, user.id, [(movie, int(copies)) for movie, copies, _rank, _total in rows]
        ),
        query=query,
        total=int(rows[0].total_matches) if rows else 0,
    )


@router.get("/movies/{movie_id}/candidates", response_model=CandidateListResponse)
async def get_movie_candidates(
    movie_id: uuid.UUID,
    _user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
    query: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
) -> CandidateListResponse:
    movie = await _get_live_movie(db, movie_id)
    search_title = query.strip() if query is not None else movie.title
    if not search_title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query is empty",
        )
    try:
        result = await MatchingEngine(tmdb).match(search_title)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TMDB search is temporarily unavailable",
        ) from exc

    return CandidateListResponse(
        movieId=movie.id,
        title=movie.title,
        query=result.query,
        candidates=[
            CandidateResponse(
                tmdbId=candidate.tmdb_id,
                title=candidate.title,
                year=candidate.year,
                overview=candidate.overview,
                posterPath=candidate.poster_path,
                confidence=candidate.confidence,
                titleSimilarity=candidate.title_similarity,
            )
            for candidate in result.candidates
        ],
    )


async def _apply_identification(
    db: AsyncSession,
    source: Movie,
    tmdb_movie: object,
) -> Movie:
    from src.tmdb.models import Movie as TmdbMovie

    if not isinstance(tmdb_movie, TmdbMovie):  # defensive boundary for dependency overrides
        raise TypeError("Expected a validated TMDB movie")

    existing = await db.scalar(
        select(Movie).where(
            Movie.tmdb_id == tmdb_movie.id,
            Movie.id != source.id,
        )
    )
    target = existing or source
    values = movie_metadata_values(tmdb_movie)
    for name, value in values.items():
        setattr(target, name, value)

    await db.execute(delete(MovieCredit).where(MovieCredit.movie_id == target.id))
    for row in credit_rows(target.id, tmdb_movie):
        db.add(
            MovieCredit(
                id=uuid.UUID(row[0]),
                movie_id=target.id,
                person_name=row[2],
                tmdb_person_id=row[3],
                role=row[4],
                character_name=row[5],
                display_order=row[6],
            )
        )

    if existing is not None:
        await db.execute(
            update(CollectionItem)
            .where(CollectionItem.movie_id == source.id)
            .values(movie_id=target.id)
        )
        # Watch history moves with the discs. Without this the ``RESTRICT`` on
        # ``watch_log.movie_id`` refuses the delete below and identification fails for
        # any film someone had already logged a watch against — which is precisely the
        # film they cared enough about to watch.
        await db.execute(
            update(WatchLog).where(WatchLog.movie_id == source.id).values(movie_id=target.id)
        )
        await db.execute(delete(MovieCredit).where(MovieCredit.movie_id == source.id))
        await db.delete(source)

    await db.commit()
    await db.refresh(target)
    return target


@router.post("/movies/{movie_id}/identify", response_model=MovieDetailResponse)
async def identify_movie(
    movie_id: uuid.UUID,
    payload: IdentifyMovieRequest,
    _user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
) -> MovieDetailResponse:
    source = await _get_live_movie(db, movie_id)
    try:
        tmdb_movie = await tmdb.get_movie_full(payload.tmdbId)
    except httpx.HTTPError as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail="TMDB movie could not be loaded") from exc

    target = await _apply_identification(db, source, tmdb_movie)
    return await _movie_detail(db, target)
