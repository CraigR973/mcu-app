"""Collection browse, detail, search, and in-app TMDB identification."""

from __future__ import annotations

import math
import uuid
from collections.abc import AsyncIterator
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
from src.models.collection_item import CollectionItem
from src.models.movie import Movie, MovieCredit
from src.schemas.movies import (
    CandidateListResponse,
    CandidateResponse,
    CastResponse,
    CollectionCopyResponse,
    CreditResponse,
    GenreResponse,
    IdentifyMovieRequest,
    MovieDetailResponse,
    MovieListItemResponse,
    MoviePageResponse,
    SearchResponse,
)
from src.services.movie_metadata import credit_rows, movie_metadata_values
from src.tmdb import TMDBClient

router = APIRouter(prefix="/api/v1", tags=["movies"])


async def get_tmdb_client() -> AsyncIterator[TMDBClient]:
    async with TMDBClient() as client:
        yield client


TmdbClient = Annotated[TMDBClient, Depends(get_tmdb_client)]
Database = Annotated[AsyncSession, Depends(get_db)]


def _live_copy_exists(*, format_code: str | None = None) -> ColumnElement[bool]:
    predicates = [
        CollectionItem.movie_id == Movie.id,
        CollectionItem.deleted_at.is_(None),
    ]
    if format_code is not None:
        predicates.append(CollectionItem.formats.contains([format_code]))
    return exists(select(CollectionItem.id).where(*predicates))


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


def _movie_filters(
    genre_id: int | None,
    year: int | None,
    format_code: str | None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [Movie.deleted_at.is_(None), _live_copy_exists()]
    if genre_id is not None:
        filters.append(Movie.genre_ids.contains([genre_id]))
    if year is not None:
        filters.append(Movie.year == year)
    if format_code is not None:
        filters.append(_live_copy_exists(format_code=format_code))
    return filters


def _movie_list_item(movie: Movie, copy_count: int) -> MovieListItemResponse:
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
    )


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


@router.get("/movies", response_model=MoviePageResponse)
async def list_movies(
    _user: CurrentUser,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(alias="perPage", ge=1, le=100)] = 60,
    genre_id: Annotated[int | None, Query(alias="genreId", gt=0)] = None,
    year: Annotated[int | None, Query(ge=1870, le=2200)] = None,
    format_code: Annotated[str | None, Query(alias="format", min_length=1, max_length=50)] = None,
    sort_by: Annotated[Literal["title", "year", "rating"], Query(alias="sort")] = "title",
    order: Literal["asc", "desc"] = "asc",
) -> MoviePageResponse:
    filters = _movie_filters(genre_id, year, format_code)
    total_movies = int(
        (await db.execute(select(func.count(Movie.id)).where(*filters))).scalar_one()
    )

    total_items = int(
        (
            await db.execute(
                select(func.count(CollectionItem.id))
                .join(Movie, Movie.id == CollectionItem.movie_id)
                .where(
                    CollectionItem.deleted_at.is_(None),
                    Movie.deleted_at.is_(None),
                    *([Movie.genre_ids.contains([genre_id])] if genre_id is not None else []),
                    *([Movie.year == year] if year is not None else []),
                    *(
                        [CollectionItem.formats.contains([format_code])]
                        if format_code is not None
                        else []
                    ),
                )
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
            .where(*filters)
            .order_by(direction(sort_column).nulls_last(), asc(func.lower(Movie.title)))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    return MoviePageResponse(
        items=[_movie_list_item(movie, int(copies)) for movie, copies in rows],
        totalMovies=total_movies,
        totalItems=total_items,
        page=page,
        perPage=per_page,
        pages=math.ceil(total_movies / per_page),
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
        )
        for copy in copies
    ]


@router.get("/search", response_model=SearchResponse)
async def search_movies(
    _user: CurrentUser,
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
        _live_copy_exists(),
        Movie.search_vector.op("@@")(tsquery),
    ]
    total = int((await db.execute(select(func.count(Movie.id)).where(*filters))).scalar_one())
    rank = func.ts_rank_cd(Movie.search_vector, tsquery).label("rank")
    copy_count = _copy_count().label("copy_count")
    rows = (
        await db.execute(
            select(Movie, copy_count, rank)
            .where(*filters)
            .order_by(desc(rank), asc(func.lower(Movie.title)))
            .limit(limit)
        )
    ).all()
    return SearchResponse(
        items=[_movie_list_item(movie, int(copies)) for movie, copies, _rank in rows],
        query=query,
        total=total,
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
