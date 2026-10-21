"""Home's Highlights panel — Batch V5, snag 9 (`DECISIONS.md` #228: "a mix of all").

Three short rows in one request: films on the shelf rated 4½ or 5 stars and whose ratings
those are, the most rewatched films across both diaries, and the most valuable discs at
their stored value; and, since V9, the best reviewed: owned films by Blu-ray.com's
review score for a format on the shelf.

Unlike Batch 37's memories this is not caller-scoped: it is the collection's highlights,
shared by both people, and each rating and viewing says whose it is.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.ebay.pricing import AS_USED_COPIES
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.reviews import FilmReview
from src.models.valuation import DiscValuation
from src.models.watch_log import WatchLog
from src.routers.movies import Database
from src.schemas.highlights import (
    BestReviewedFilmResponse,
    HighlightRatingResponse,
    HighlightsResponse,
    PersonViewingsResponse,
    RewatchedFilmResponse,
    TopRatedFilmResponse,
    TopRatedRowResponse,
    ValuableDiscResponse,
)
from src.services.valuation import current_value, owned_valued_discs

router = APIRouter(prefix="/api/v1", tags=["highlights"])

#: A short row: enough to scroll on a phone, few enough to take in.
ROW_LENGTH = 12

#: 4½ stars and up. Ratings are stored on the half-star scale, 0.5 to 5.0.
TOP_RATING = Decimal("4.5")

#: "Rewatched" means watched twice or more, whoever watched.
MIN_VIEWINGS = 2


@dataclass
class _Film:
    movie_id: uuid.UUID
    title: str
    year: int | None
    poster_path: str | None
    ratings: list[HighlightRatingResponse] = field(default_factory=list)


async def _top_rated(db: AsyncSession) -> TopRatedRowResponse:
    best = func.max(WatchLog.personal_rating)
    last = func.max(WatchLog.watched_at)
    on_the_shelf = exists().where(CollectionItem.movie_id == Movie.id, owned_copy())
    rows = (
        await db.execute(
            select(
                Movie.id,
                Movie.title,
                Movie.year,
                Movie.poster_path,
                Profile.display_name,
                best,
            )
            .join(WatchLog, WatchLog.movie_id == Movie.id)
            .join(Profile, Profile.id == WatchLog.user_id)
            .where(
                Movie.deleted_at.is_(None),
                WatchLog.deleted_at.is_(None),
                WatchLog.personal_rating.is_not(None),
                on_the_shelf,
            )
            .group_by(Movie.id, Profile.display_name)
            .having(best >= TOP_RATING)
            .order_by(best.desc(), last.desc(), Movie.title, Profile.display_name)
            # One row per person per film: room for both people on every film.
            .limit(ROW_LENGTH * 2)
        )
    ).all()

    films: dict[uuid.UUID, _Film] = {}
    for movie_id, title, year, poster_path, person, rating in rows:
        film = films.setdefault(movie_id, _Film(movie_id, title, year, poster_path))
        film.ratings.append(HighlightRatingResponse(personName=person, rating=float(rating)))

    people = (
        await db.execute(
            select(Profile.display_name, func.count(WatchLog.personal_rating))
            .outerjoin(
                WatchLog, and_(WatchLog.user_id == Profile.id, WatchLog.deleted_at.is_(None))
            )
            .where(Profile.deleted_at.is_(None), Profile.is_active.is_(True))
            .group_by(Profile.display_name)
            .order_by(Profile.display_name)
        )
    ).all()

    return TopRatedRowResponse(
        items=[
            TopRatedFilmResponse(
                movieId=film.movie_id,
                title=film.title,
                year=film.year,
                posterPath=film.poster_path,
                ratings=film.ratings,
            )
            for film in list(films.values())[:ROW_LENGTH]
        ],
        ratedBy=[name for name, rated in people if rated > 0],
        notRatedBy=[name for name, rated in people if rated == 0],
    )


async def _most_rewatched(db: AsyncSession) -> list[RewatchedFilmResponse]:
    viewings = func.count(WatchLog.id)
    last = func.max(WatchLog.watched_at)
    top = (
        select(WatchLog.movie_id, viewings.label("viewings"), last.label("last_watched"))
        .join(Movie, Movie.id == WatchLog.movie_id)
        .where(WatchLog.deleted_at.is_(None), Movie.deleted_at.is_(None))
        .group_by(WatchLog.movie_id)
        .having(viewings >= MIN_VIEWINGS)
        .order_by(viewings.desc(), last.desc())
        .limit(ROW_LENGTH)
        .subquery()
    )
    rows = (
        await db.execute(
            select(
                Movie.id,
                Movie.title,
                Movie.year,
                Movie.poster_path,
                top.c.viewings,
                Profile.display_name,
                func.count(WatchLog.id),
            )
            .join(top, top.c.movie_id == Movie.id)
            .join(WatchLog, and_(WatchLog.movie_id == Movie.id, WatchLog.deleted_at.is_(None)))
            .join(Profile, Profile.id == WatchLog.user_id)
            .group_by(Movie.id, top.c.viewings, top.c.last_watched, Profile.display_name)
            .order_by(
                top.c.viewings.desc(),
                top.c.last_watched.desc(),
                Movie.title,
                Profile.display_name,
            )
        )
    ).all()

    films: dict[uuid.UUID, RewatchedFilmResponse] = {}
    for movie_id, title, year, poster_path, total, person, count in rows:
        film = films.setdefault(
            movie_id,
            RewatchedFilmResponse(
                movieId=movie_id,
                title=title,
                year=year,
                posterPath=poster_path,
                viewings=int(total),
                byPerson=[],
            ),
        )
        film.byPerson.append(PersonViewingsResponse(personName=person, viewings=int(count)))
    return list(films.values())


async def _most_valuable(db: AsyncSession) -> list[ValuableDiscResponse]:
    discs = owned_valued_discs()
    copies = func.count(discs.c.id)
    sales = and_(DiscValuation.sales_count >= 3, DiscValuation.sales_price.is_not(None))
    effective_price = case((sales, DiscValuation.sales_price), else_=DiscValuation.price)
    rows = (
        await db.execute(
            select(DiscValuation, Movie.title, Movie.year, Movie.poster_path, copies)
            .join(
                discs,
                and_(
                    discs.c.movie_id == DiscValuation.movie_id,
                    discs.c.format_code == DiscValuation.format_code,
                ),
            )
            .join(Movie, Movie.id == DiscValuation.movie_id)
            .where(or_(DiscValuation.status == "priced", sales), current_value())
            .group_by(DiscValuation.id, Movie.id)
            .order_by(effective_price.desc(), Movie.title)
            .limit(ROW_LENGTH)
        )
    ).all()
    return [
        ValuableDiscResponse(
            movieId=valuation.movie_id,
            title=title,
            year=year,
            posterPath=poster_path,
            formatCode=valuation.format_code,
            price=str(valuation.effective_price),
            currency=valuation.currency,
            basis="observed sold listings" if valuation.sales_backed else valuation.basis,
            sampleSize=valuation.sales_count if valuation.sales_backed else valuation.sample_size,
            valueBasis="sales"
            if valuation.sales_backed
            else ("new_scaled" if valuation.value_basis == "new_scaled" else "used"),
            factor=str(valuation.factor)
            if valuation.factor is not None and not valuation.sales_backed
            else None,
            low=str(valuation.sales_low if valuation.sales_backed else valuation.low),
            high=str(valuation.sales_high if valuation.sales_backed else valuation.high),
            valuedAs=AS_USED_COPIES,
            checkedAt=(valuation.sales_checked_utc or valuation.checked_utc)
            if valuation.sales_backed
            else valuation.checked_utc,
            copies=int(count),
        )
        for valuation, title, year, poster_path, count in rows
    ]


async def _best_reviewed(db: AsyncSession) -> list[BestReviewedFilmResponse]:
    """Owned films by their best Blu-ray.com review score, of a format a copy is on (V9).

    One entry a film; a tie between its formats goes to 4K. AVForums has no scores (#241).
    """
    on_the_shelf = exists().where(
        CollectionItem.movie_id == Movie.id,
        owned_copy(),
        CollectionItem.formats.has_key(FilmReview.format_code),
    )
    rows = (
        await db.execute(
            select(
                Movie.id,
                Movie.title,
                Movie.year,
                Movie.poster_path,
                FilmReview.overall,
                FilmReview.out_of,
                FilmReview.format_code,
            )
            .join(FilmReview, FilmReview.movie_id == Movie.id)
            .where(
                Movie.deleted_at.is_(None),
                FilmReview.site == "bluray_com",
                FilmReview.status == "scored",
                on_the_shelf,
            )
            .order_by(
                FilmReview.overall.desc(),
                (FilmReview.format_code == "4k_uhd").desc(),
                Movie.title,
            )
            .limit(ROW_LENGTH * 3)
        )
    ).all()
    films: dict[uuid.UUID, BestReviewedFilmResponse] = {}
    for movie_id, title, year, poster_path, overall, out_of, format_code in rows:
        if movie_id in films or overall is None or out_of is None:
            continue
        films[movie_id] = BestReviewedFilmResponse(
            movieId=movie_id,
            title=title,
            year=year,
            posterPath=poster_path,
            overall=float(overall),
            outOf=int(out_of),
            formatCode=format_code,
        )
    return list(films.values())[:ROW_LENGTH]


@router.get("/highlights", response_model=HighlightsResponse)
async def highlights(_user: CurrentUser, db: Database) -> HighlightsResponse:
    """Home's Highlights, four rows in one request. A row with nothing in it comes back empty."""
    return HighlightsResponse(
        topRated=await _top_rated(db),
        mostRewatched=await _most_rewatched(db),
        mostValuable=await _most_valuable(db),
        bestReviewed=await _best_reviewed(db),
    )
