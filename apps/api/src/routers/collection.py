from __future__ import annotations

import contextlib
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import CollectionItem, Movie, MovieCredit
from ..schemas.movies import CollectionItemOut
from ..tmdb.client import TMDBClient

router = APIRouter(tags=["collection"])

_VALID_FORMATS = frozenset(
    {"4k_bluray", "bluray", "dvd", "digital", "laserdisc", "vhs", "hddvd"}
)
_VALID_CONDITIONS = frozenset({"sealed", "mint", "very_good", "good", "fair", "poor"})


# ---------- Schemas ----------


class TMDBSearchResult(BaseModel):
    id: int
    title: str
    release_date: str | None = None
    poster_path: str | None = None
    overview: str | None = None
    vote_average: float | None = None


class TMDBSearchResponse(BaseModel):
    results: list[TMDBSearchResult]
    total_results: int
    page: int


class CollectionItemCreate(BaseModel):
    tmdb_id: int
    format: str
    condition: str = "very_good"
    edition: str | None = None
    purchase_price: Decimal | None = None
    purchase_date: date | None = None
    purchase_source: str | None = None
    notes: str | None = None


class AddToCollectionResponse(BaseModel):
    data: CollectionItemOut
    movie_id: int
    duplicate_warning: bool
    existing_formats: list[str]


# ---------- Routes ----------


@router.get("/api/v1/tmdb/search", response_model=TMDBSearchResponse)
async def tmdb_search(
    q: Annotated[str, Query(min_length=1)],
    year: int | None = None,
    page: int = 1,
    _: dict = Depends(require_admin),  # type: ignore[type-arg]
) -> TMDBSearchResponse:
    async with TMDBClient() as client:
        results = await client.search_movie(q, year=year, page=page)
    return TMDBSearchResponse(
        results=[
            TMDBSearchResult(
                id=r.id,
                title=r.title,
                release_date=r.release_date or None,
                poster_path=r.poster_path,
                overview=r.overview or None,
                vote_average=r.vote_average or None,
            )
            for r in results.results
        ],
        total_results=results.total_results,
        page=results.page,
    )


@router.post("/api/v1/collection", response_model=AddToCollectionResponse, status_code=201)
async def add_to_collection(
    body: CollectionItemCreate,
    _: dict = Depends(require_admin),  # type: ignore[type-arg]
    db: Session = Depends(get_db),
) -> AddToCollectionResponse:
    if body.format not in _VALID_FORMATS:
        raise HTTPException(status_code=422, detail=f"Invalid format: {body.format}")
    if body.condition not in _VALID_CONDITIONS:
        raise HTTPException(status_code=422, detail=f"Invalid condition: {body.condition}")

    # Upsert movie + credits from TMDB if not yet in our DB
    if db.get(Movie, body.tmdb_id) is None:
        async with TMDBClient() as client:
            tmdb = await client.get_movie_full(body.tmdb_id)

        release_date: date | None = None
        if tmdb.release_date:
            with contextlib.suppress(ValueError):
                release_date = date.fromisoformat(tmdb.release_date)

        db.merge(
            Movie(
                id=tmdb.id,
                title=tmdb.title,
                original_title=tmdb.original_title,
                overview=tmdb.overview,
                tagline=tmdb.tagline,
                release_date=release_date,
                runtime=tmdb.runtime,
                popularity=tmdb.popularity,
                vote_average=tmdb.vote_average,
                vote_count=tmdb.vote_count,
                adult=tmdb.adult,
                status=tmdb.status,
                budget=tmdb.budget or None,
                revenue=tmdb.revenue or None,
                imdb_id=tmdb.imdb_id,
                homepage=tmdb.homepage,
                poster_path=tmdb.poster_path,
                backdrop_path=tmdb.backdrop_path,
                genre_ids=[g.id for g in tmdb.genres],
            )
        )
        db.flush()

        if tmdb.credits:
            for cast_member in tmdb.credits.cast[:50]:
                db.add(
                    MovieCredit(
                        movie_id=tmdb.id,
                        person_id=cast_member.id,
                        person_name=cast_member.name,
                        credit_type="cast",
                        character=cast_member.character,
                        credit_order=cast_member.order,
                        profile_path=cast_member.profile_path,
                    )
                )
            for crew_member in tmdb.credits.crew:
                db.add(
                    MovieCredit(
                        movie_id=tmdb.id,
                        person_id=crew_member.id,
                        person_name=crew_member.name,
                        credit_type="crew",
                        department=crew_member.department,
                        job=crew_member.job,
                        profile_path=crew_member.profile_path,
                    )
                )
        db.flush()

    # Check for existing non-deleted copies (duplicate warning)
    existing = (
        db.execute(
            select(CollectionItem)
            .where(CollectionItem.movie_id == body.tmdb_id)
            .where(CollectionItem.deleted_at.is_(None))
        )
        .scalars()
        .all()
    )
    duplicate_warning = len(existing) > 0
    existing_formats = list({item.format for item in existing})

    item = CollectionItem(
        movie_id=body.tmdb_id,
        format=body.format,
        condition=body.condition,
        edition=body.edition,
        purchase_price=body.purchase_price,
        purchase_date=body.purchase_date,
        purchase_source=body.purchase_source,
        notes=body.notes,
        is_for_sale=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return AddToCollectionResponse(
        data=CollectionItemOut.model_validate(item),
        movie_id=body.tmdb_id,
        duplicate_warning=duplicate_warning,
        existing_formats=existing_formats,
    )
