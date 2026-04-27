from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, func, literal, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Movie, MovieCredit
from ..schemas.movies import (
    CreditOut,
    MovieDetail,
    MovieDetailResponse,
    MovieListItem,
    MovieListResponse,
    PaginationMeta,
)

router = APIRouter(prefix="/api/v1/movies", tags=["movies"])

_SORT_COLS = {
    "title": Movie.title,
    "release_date": Movie.release_date,
    "popularity": Movie.popularity,
    "vote_average": Movie.vote_average,
}

SortField = Literal["title", "release_date", "popularity", "vote_average"]


@router.get("", response_model=MovieListResponse)
def list_movies(
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: SortField = "popularity",
    order: Literal["asc", "desc"] = "desc",
    genre_id: int | None = None,
    year: int | None = None,
    format: str | None = None,
    db: Session = Depends(get_db),
) -> MovieListResponse:
    sort_col = _SORT_COLS[sort]
    ordered = sort_col.asc() if order == "asc" else sort_col.desc()

    q = select(Movie)
    if genre_id is not None:
        # Checks: genre_id = ANY(genre_ids)
        q = q.where(literal(genre_id, type_=Integer()).op("= ANY")(Movie.genre_ids))
    if year is not None:
        q = q.where(func.extract("year", Movie.release_date) == year)
    if format is not None:
        q = q.where(Movie.best_format_owned == format)

    total: int = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.execute(
        q.order_by(ordered, Movie.id).offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()

    pages = (total + per_page - 1) // per_page if total else 0

    return MovieListResponse(
        data=[MovieListItem.model_validate(r) for r in rows],
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )


@router.get("/{movie_id}", response_model=MovieDetailResponse)
def get_movie(movie_id: int, db: Session = Depends(get_db)) -> MovieDetailResponse:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    credits = (
        db.execute(
            select(MovieCredit)
            .where(MovieCredit.movie_id == movie_id)
            .order_by(MovieCredit.credit_order.nulls_last())
        )
        .scalars()
        .all()
    )

    detail = MovieDetail.model_validate(movie)
    detail.cast = [CreditOut.model_validate(c) for c in credits if c.credit_type == "cast"]
    detail.crew = [CreditOut.model_validate(c) for c in credits if c.credit_type == "crew"]

    return MovieDetailResponse(data=detail)
