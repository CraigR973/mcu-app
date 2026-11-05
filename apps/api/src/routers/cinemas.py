"""Programme reads only: public sources never run in a person's request."""

import uuid
from datetime import UTC, date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from src.auth import AdminUser, CurrentUser
from src.clock import utcnow
from src.routers.movies import Database
from src.schemas.cinemas import (
    CinemaFilmDetail,
    CinemaFilmsResponse,
    CinemaProgrammeResponse,
    ReleaseFilter,
    ReviewDecision,
    ReviewList,
)
from src.services.cinemas import films, review
from src.services.cinemas.domain import LONDON
from src.services.cinemas.programme import programme

router = APIRouter(prefix="/api/v1/cinemas", tags=["cinemas"])


@router.get("/programme", response_model=CinemaProgrammeResponse)
async def get_programme(
    user: CurrentUser,
    db: Database,
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    venue_ids: Annotated[list[uuid.UUID] | None, Query(alias="venueIds")] = None,
    release_category: Annotated[ReleaseFilter, Query(alias="releaseCategory")] = "all",
) -> CinemaProgrammeResponse:
    start = date_from or utcnow().replace(tzinfo=UTC).astimezone(LONDON).date()
    try:
        return await programme(db, user.id, start, date_to or start, venue_ids, release_category)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/films", response_model=CinemaFilmsResponse)
async def get_films(user: CurrentUser, db: Database) -> CinemaFilmsResponse:
    """AC4: every film and listing still to show in the stored fortnight, film first."""
    return await films.films(db, user.id)


@router.get("/films/{key}", response_model=CinemaFilmDetail)
async def get_film(key: str, user: CurrentUser, db: Database) -> CinemaFilmDetail:
    """AC4: one film's every showing across the nine. ``key`` is the film page's address:
    ``tmdb-<id>``, or ``listing-<id>``, which opens the film once the listing is linked."""
    return await films.film(db, user.id, key)


@router.get("/review", response_model=ReviewList)
async def get_review_list(_user: AdminUser, db: Database) -> ReviewList:
    """AC3 (#335): programme films waiting for Craig, most showings first. Admin only."""
    return await review.review_list(db, utcnow())


@router.post("/review/{key}", response_model=ReviewList)
async def decide_review(
    key: str, payload: ReviewDecision, user: AdminUser, db: Database
) -> ReviewList:
    """Link a review item to one of its films, or mark it not a film, and relabel its
    showings now. The decision holds until the listing's title or facts change."""
    now = utcnow()
    await review.decide(db, key, payload, user.id, now)
    await db.commit()
    return await review.review_list(db, now)
