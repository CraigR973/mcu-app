"""A page for each person — AE9 (#355). Read-only.

Any signed-in person can read anyone active's page: their photo and name, how many films they
have watched this year and ever, their last ten diary entries, the copies they added lately,
their wants and the discs they have now. Nothing from Settings is read or returned. An inactive
or removed profile is not found.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.clock import utcnow
from src.models.collection_item import CollectionItem, owned_copy
from src.models.loan import Loan, loan_state
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.routers.movies import Database
from src.schemas.people import (
    PersonAddedCopy,
    PersonDiaryEntry,
    PersonFilm,
    PersonLoan,
    PersonPageResponse,
)

router = APIRouter(prefix="/api/v1", tags=["people"])

LONDON = ZoneInfo("Europe/London")

#: The diary and the copies added: the last ten of each. Wants: the first twenty.
RECENT = 10
WANTS = 20


async def _watched(db: AsyncSession, person: uuid.UUID, since: date | None) -> int:
    query = select(func.count(func.distinct(WatchLog.movie_id))).where(
        WatchLog.user_id == person, WatchLog.deleted_at.is_(None)
    )
    if since is not None:
        query = query.where(WatchLog.watched_at >= since)
    return int(await db.scalar(query) or 0)


@router.get("/people/{profile_id}", response_model=PersonPageResponse)
async def person_page(profile_id: uuid.UUID, user: CurrentUser, db: Database) -> PersonPageResponse:
    """One person's page, for anyone signed in. Read-only."""
    person = await db.get(Profile, profile_id)
    if person is None or not person.is_active or person.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such person")
    year_start = date(_london_today(utcnow()).year, 1, 1)

    diary = (
        await db.execute(
            select(WatchLog, Movie)
            .join(Movie, Movie.id == WatchLog.movie_id)
            .where(WatchLog.user_id == person.id, WatchLog.deleted_at.is_(None))
            .order_by(WatchLog.watched_at.desc(), WatchLog.created_at.desc(), WatchLog.id.desc())
            .limit(RECENT)
        )
    ).all()
    added = (
        await db.execute(
            select(CollectionItem, Movie)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(
                CollectionItem.added_by == person.id,
                CollectionItem.added_at_utc.is_not(None),
                owned_copy(),
                Movie.deleted_at.is_(None),
            )
            .order_by(CollectionItem.added_at_utc.desc(), CollectionItem.id.desc())
            .limit(RECENT)
        )
    ).all()
    wanted = (
        WantedItem.added_by == person.id,
        WantedItem.is_active.is_(True),
        WantedItem.deleted_at.is_(None),
        Movie.deleted_at.is_(None),
    )
    wants = (
        await db.execute(
            select(Movie)
            .join(WantedItem, WantedItem.movie_id == Movie.id)
            .where(*wanted)
            .order_by(WantedItem.added_at.desc(), Movie.id)
            .limit(WANTS)
        )
    ).scalars()
    wants_total = await db.scalar(
        select(func.count(WantedItem.id))
        .join(Movie, Movie.id == WantedItem.movie_id)
        .where(*wanted)
    )
    loans = (
        await db.execute(
            select(Loan, Movie)
            .join(CollectionItem, CollectionItem.id == Loan.collection_item_id)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(
                Loan.borrower_profile_id == person.id,
                Loan.returned_date.is_(None),
                owned_copy(),
                Movie.deleted_at.is_(None),
            )
            .order_by(Loan.created_at.desc(), Loan.id)
        )
    ).all()

    return PersonPageResponse(
        profileId=person.id,
        displayName=person.display_name,
        isYou=person.id == user.id,
        watchedThisYear=await _watched(db, person.id, year_start),
        watchedTotal=await _watched(db, person.id, None),
        diary=[
            PersonDiaryEntry(
                movieId=movie.id,
                title=movie.title,
                year=movie.year,
                posterPath=movie.poster_path,
                watchedOn=watch.watched_at,
                rating=float(watch.personal_rating) if watch.personal_rating is not None else None,
                rewatch=watch.is_rewatch,
            )
            for watch, movie in diary
        ],
        recentlyAdded=[
            PersonAddedCopy(
                copyId=item.id,
                movieId=movie.id,
                title=movie.title,
                posterPath=movie.poster_path,
                formats=list(item.formats or []),
                addedOn=_london_today(item.added_at_utc),
            )
            for item, movie in added
            if item.added_at_utc is not None
        ],
        wants=[
            PersonFilm(movieId=m.id, title=m.title, year=m.year, posterPath=m.poster_path)
            for m in wants
        ],
        wantsTotal=int(wants_total or 0),
        loans=[
            PersonLoan(
                loanId=loan.id,
                movieId=movie.id,
                title=movie.title,
                posterPath=movie.poster_path,
                state="asked_for" if loan_state(loan) == "asked_for" else "out",
                lentDate=loan.lent_date,
                dueDate=loan.due_date,
                neededBy=loan.needed_by_date,
            )
            for loan, movie in loans
            if loan_state(loan) in ("asked_for", "out")
        ],
    )


def _london_today(moment: datetime) -> date:
    """The London day of a naive-UTC moment."""
    return moment.replace(tzinfo=UTC).astimezone(LONDON).date()
