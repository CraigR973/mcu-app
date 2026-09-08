"""Personal watch history — roadmap §3.7's table and §6.5's two endpoints.

Everything here is scoped to the requesting user and never to a supplied id. A private
two-person app makes it tempting to let either person read the other's history "since
they can see everything anyway", but watched-status is the one thing in this app that is
genuinely per-person: the facet exists so Mark can find what *he* has not seen.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from src.auth import CurrentUser
from src.clock import latest_plausible_today, utc_today
from src.models.movie import Movie
from src.models.watch_log import WatchLog
from src.routers.movies import Database
from src.schemas.movies import (
    WatchLogCreateRequest,
    WatchLogPageResponse,
    WatchLogResponse,
)

router = APIRouter(prefix="/api/v1", tags=["watch-log"])


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _response(entry: WatchLog, movie: Movie) -> WatchLogResponse:
    return WatchLogResponse(
        id=entry.id,
        movieId=entry.movie_id,
        movieTitle=movie.title,
        posterPath=movie.poster_path,
        watchedAt=entry.watched_at,
        isRewatch=entry.is_rewatch,
        personalRating=(
            float(entry.personal_rating) if entry.personal_rating is not None else None
        ),
        review=entry.review,
    )


@router.post(
    "/watch-log",
    response_model=WatchLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_watch(
    payload: WatchLogCreateRequest,
    user: CurrentUser,
    db: Database,
) -> WatchLogResponse:
    movie = await db.get(Movie, payload.movieId)
    if movie is None or movie.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    watched_at = payload.watchedAt or utc_today()
    # Not ``date.today()``: that reads the *server's* timezone, so the default computed
    # one line above could be refused by the guard below on any host not running UTC.
    if watched_at > latest_plausible_today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="watchedAt cannot be in the future",
        )

    entry = WatchLog(
        id=uuid.uuid4(),
        movie_id=movie.id,
        user_id=user.id,
        watched_at=watched_at,
        is_rewatch=payload.isRewatch,
        personal_rating=payload.personalRating,
        review=payload.review,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _response(entry, movie)


@router.get("/watch-log", response_model=WatchLogPageResponse)
async def list_watches(
    user: CurrentUser,
    db: Database,
    movie_id: Annotated[uuid.UUID | None, Query(alias="movieId")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(alias="perPage", ge=1, le=200)] = 50,
) -> WatchLogPageResponse:
    """The caller's own history, newest first, optionally for one film.

    ``movieId`` is what the detail page uses to show "you watched this on …" without a
    second endpoint that would answer the same question in a second shape.
    """
    predicates = [WatchLog.user_id == user.id, WatchLog.deleted_at.is_(None)]
    if movie_id is not None:
        predicates.append(WatchLog.movie_id == movie_id)

    total = int((await db.execute(select(func.count(WatchLog.id)).where(*predicates))).scalar_one())
    rows = (
        await db.execute(
            select(WatchLog, Movie)
            .join(Movie, Movie.id == WatchLog.movie_id)
            .where(*predicates)
            .order_by(WatchLog.watched_at.desc(), WatchLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    return WatchLogPageResponse(
        items=[_response(entry, movie) for entry, movie in rows],
        total=total,
        page=page,
        perPage=per_page,
        pages=math.ceil(total / per_page),
    )


@router.delete("/watch-log/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watch(entry_id: uuid.UUID, user: CurrentUser, db: Database) -> None:
    """Soft-delete one of the caller's own entries.

    Soft, because §13.5 sends deleted watch logs to Trash — and because the realistic
    failure here is a mis-tap on a phone, which should not permanently lose the record
    that someone watched something.

    A 404 rather than a 403 for another user's entry: whether a given id exists in
    someone else's history is not something this response should confirm.
    """
    entry = await db.get(WatchLog, entry_id)
    if entry is None or entry.deleted_at is not None or entry.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Watch log entry not found"
        )
    entry.deleted_at = _utcnow()
    await db.commit()
