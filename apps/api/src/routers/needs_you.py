"""Home's "Needs you" row: what the person signed in can act on now — Batch AC1 (#335).

**Derived from the loan rows on every read, never stored.** A disc confirmed shelved leaves
everyone's row at once, and no job has to keep a list true between runs. AC5 adds cinema trip
replies to the same row.

**Who sees what** (#335):

- A disc back but not shelved, and a disc asked for and waiting to be handed over, go to the
  people who keep the shelves. Whoever asked is waiting rather than acting, so their own
  request is not theirs to hand over.
- A loan past its due date, or out 14 days or more with none, goes to its borrower and to the
  people who keep the shelves.
- Anyone else, such as a later onboarded person who neither keeps the shelves nor borrowed
  the disc, sees nothing of it.

Only each copy's current loan counts, as on Loans: returned history never makes a task. The
row only reads; every action is Loans' own, so there is no second write path.

Since AC2 the same read carries the reader's next planned screening, so Home's top slot is one
request.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.clock import utc_today, utcnow
from src.models.collection_item import CollectionItem, owned_copy
from src.models.loan import Loan, loan_state
from src.models.movie import Movie
from src.models.movie_night import MovieNightParticipant, MovieNightSession, MovieNightSuggestion
from src.models.profile import Profile, UserRole
from src.routers.movies import Database, location_label
from src.schemas.needs_you import NeedsYouLoanItem, NeedsYouResponse, NextScreening
from src.services.assigned_reviews import list_reviews
from src.services.cinema_trips import trips
from src.services.collection_additions import MARK_PROFILE_ID
from src.services.movie_night.sessions import film_face

router = APIRouter(prefix="/api/v1", tags=["needs-you"])

#: A loan with no due date joins the row once it has been out this long (#335).
OPEN_ENDED_AFTER = timedelta(days=14)

#: Someone waiting comes first, then a disc that should be home, then the shelving.
_ORDER: dict[str, int] = {"handOver": 0, "overdue": 1, "putBack": 2}


def keeps_the_shelves(person: Profile) -> bool:
    """The people who keep the shelves: admins, and Mark by his stable profile id (#335).

    Defined once, here, until an onboarding plan says something better. Mark is matched by
    id, never by role or display name (#306), so a later viewer is given no shelf jobs.
    """
    return person.role == UserRole.admin or person.id == MARK_PROFILE_ID


def _overdue_from(loan: Loan) -> date | None:
    """The first day an out loan belongs on the row: the day after it was due, or 14 days
    after it went out when it has no due date."""
    if loan.due_date is not None:
        return loan.due_date + timedelta(days=1)
    if loan.lent_date is not None:
        return loan.lent_date + OPEN_ENDED_AFTER
    return None


async def _current_loans(db: AsyncSession) -> list[tuple[Loan, CollectionItem, Movie]]:
    """Each copy's current loan, chosen in the order Loans and every transition use."""
    current = (
        select(Loan.id)
        .distinct(Loan.collection_item_id)
        .order_by(
            Loan.collection_item_id,
            Loan.returned_date.is_(None).desc(),
            Loan.updated_at.desc(),
            Loan.created_at.desc(),
            Loan.id.desc(),
        )
        .subquery()
    )
    rows = await db.execute(
        select(Loan, CollectionItem, Movie)
        .join(current, current.c.id == Loan.id)
        .join(CollectionItem, CollectionItem.id == Loan.collection_item_id)
        .join(Movie, Movie.id == CollectionItem.movie_id)
        # A binned, sold or donated copy has no shelf to go back to and nobody to chase.
        .where(owned_copy(), Movie.deleted_at.is_(None))
    )
    return [(loan, item, movie) for loan, item, movie in rows.all()]


async def needs_you_items(
    db: AsyncSession, person: Profile, *, today: date
) -> list[NeedsYouLoanItem]:
    """What ``person`` can act on now, most pressing first."""
    keeper = keeps_the_shelves(person)
    found: list[tuple[tuple[int, date, str], NeedsYouLoanItem]] = []
    for loan, item, movie in await _current_loans(db):
        state = loan_state(loan)
        yours = loan.borrower_profile_id is not None and loan.borrower_profile_id == person.id
        kind: Literal["putBack", "handOver", "overdue"]
        if state == "back" and keeper:
            kind, since = "putBack", loan.returned_date or today
        elif state == "asked_for" and keeper and not yours:
            kind, since = "handOver", loan.needed_by_date or today
        elif state == "out" and (keeper or yours):
            overdue_from = _overdue_from(loan)
            if overdue_from is None or overdue_from > today:
                continue
            kind, since = "overdue", overdue_from
        else:
            continue
        found.append(
            (
                (_ORDER[kind], since, movie.title.casefold()),
                NeedsYouLoanItem(
                    kind=kind,
                    loanId=loan.id,
                    movieId=movie.id,
                    movieTitle=movie.title,
                    posterPath=movie.poster_path,
                    locationLabel=location_label(item.section, item.shelf),
                    borrowerName=loan.borrower_name,
                    borrowerIsYou=yours,
                    lentDate=loan.lent_date,
                    returnedDate=loan.returned_date,
                    neededBy=loan.needed_by_date,
                    dueDate=loan.due_date,
                    daysOverdue=(
                        (today - loan.due_date).days
                        if kind == "overdue" and loan.due_date is not None
                        else None
                    ),
                    # Never negative, even for a legacy row lent "tomorrow" somewhere east.
                    daysOut=(
                        max(0, (today - loan.lent_date).days)
                        if kind == "overdue" and loan.lent_date is not None
                        else None
                    ),
                ),
            )
        )
    return [entry for _, entry in sorted(found, key=lambda pair: pair[0])]


async def next_screening(db: AsyncSession, person: Profile) -> NextScreening | None:
    """The soonest open screening ``person`` is in with a planned start still ahead (AC2)."""
    session = await db.scalar(
        select(MovieNightSession)
        .join(MovieNightParticipant, MovieNightParticipant.session_id == MovieNightSession.id)
        .where(
            MovieNightParticipant.user_id == person.id,
            MovieNightSession.status == "open",
            MovieNightSession.planned_start_utc > utcnow(),
        )
        .order_by(MovieNightSession.planned_start_utc, MovieNightSession.id)
        .limit(1)
    )
    if session is None or session.planned_start_utc is None:
        return None
    names = (
        await db.scalars(
            select(Profile.display_name)
            .join(MovieNightParticipant, MovieNightParticipant.user_id == Profile.id)
            .where(MovieNightParticipant.session_id == session.id, Profile.id != person.id)
            .order_by(MovieNightParticipant.joined_at_utc)
        )
    ).all()
    match = None
    if session.matched_suggestion_id is not None:
        suggestion = await db.get(MovieNightSuggestion, session.matched_suggestion_id)
        if suggestion is not None:
            match, _, _ = await film_face(db, suggestion)
    return NextScreening(
        sessionId=session.id,
        plannedStart=session.planned_start_utc,
        withNames=list(names),
        matchTitle=match,
    )


@router.get("/needs-you", response_model=NeedsYouResponse)
async def needs_you(user: CurrentUser, db: Database) -> NeedsYouResponse:
    """What the person signed in can act on now, and their next screening."""
    now = utcnow()
    return NeedsYouResponse(
        reviews=[review for review in await list_reviews(db, user) if review.status != "resolved"],
        items=await needs_you_items(db, user, today=utc_today()),
        nextScreening=await next_screening(db, user),
        trips=await trips.needs_you_trips(db, user, now),
        nextTrip=await trips.next_trip(db, user, now),
    )
