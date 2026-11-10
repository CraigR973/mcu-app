"""Cinema trips — AC5 (#335, point 4; #345). Behind sign-in, members only.

Every write commits its change and its pushes together, then delivers as movie nights do: a
failed delivery never fails the request, and the push stays queued for the next pass. Each
answer is the trip as its reader now sees it, so a phone redraws from one response.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from src.auth import CurrentUser
from src.clock import utcnow
from src.models.cinema_trip import FILM_KEY_PATTERN, CinemaTrip
from src.models.profile import Profile
from src.routers.movies import Database
from src.schemas.cinema_trips import (
    CinemaTripList,
    CinemaTripResponse,
    InvitablePeople,
    InviteMore,
    KeepTime,
    MoveTrip,
    ProposeTrip,
    ReplyToTrip,
)
from src.services.cinema_trips import trips
from src.services.movie_night.sessions import deliver_now

router = APIRouter(prefix="/api/v1/cinema-trips", tags=["cinema-trips"])


async def _answer(
    db: Database, user: Profile, trip: CinemaTrip, told: list[uuid.UUID]
) -> CinemaTripResponse:
    await db.commit()
    if told:
        await deliver_now(db, told)
    return await trips.one(db, trip.id, user, utcnow())


@router.get("", response_model=CinemaTripList)
async def list_trips(user: CurrentUser, db: Database) -> CinemaTripList:
    """The reader's trips: upcoming soonest first, then past and cancelled, latest first."""
    return await trips.trips_of(db, user, utcnow())


@router.get("/people", response_model=InvitablePeople)
async def invitable_people(
    user: CurrentUser,
    db: Database,
    filmKey: Annotated[str | None, Query(pattern=FILM_KEY_PATTERN)] = None,
) -> InvitablePeople:
    """Everyone the reader can invite: active profiles with a PIN, not themselves. AE6
    (#355): with a film page's address, each person's latest watch of a matched film, by
    movie night's rule (S7), so Propose a trip shows who has seen it."""
    return await trips.invitable(db, user, filmKey)


@router.get("/{trip_id}", response_model=CinemaTripResponse)
async def get_trip(trip_id: uuid.UUID, user: CurrentUser, db: Database) -> CinemaTripResponse:
    return await trips.one(db, trip_id, user, utcnow())


@router.post("", response_model=CinemaTripResponse, status_code=201)
async def propose_trip(payload: ProposeTrip, user: CurrentUser, db: Database) -> CinemaTripResponse:
    """A time from the film's page, and the people to invite. A retried send returns the
    same trip."""
    trip, told = await trips.propose(db, user, payload, utcnow())
    return await _answer(db, user, trip, told)


@router.put("/{trip_id}/reply", response_model=CinemaTripResponse)
async def reply_to_trip(
    trip_id: uuid.UUID, payload: ReplyToTrip, user: CurrentUser, db: Database
) -> CinemaTripResponse:
    """An invitee's Going, Not going or Another time. The same reply again changes nothing."""
    trip, told = await trips.reply(db, user, trip_id, payload, utcnow())
    return await _answer(db, user, trip, told)


@router.post("/{trip_id}/move", response_model=CinemaTripResponse)
async def move_trip(
    trip_id: uuid.UUID, payload: MoveTrip, user: CurrentUser, db: Database
) -> CinemaTripResponse:
    """The proposer accepts a suggestion, or moves the trip to a time of their own."""
    trip, told = await trips.move(db, user, trip_id, payload, utcnow())
    return await _answer(db, user, trip, told)


@router.post("/{trip_id}/keep", response_model=CinemaTripResponse)
async def keep_time(
    trip_id: uuid.UUID, payload: KeepTime, user: CurrentUser, db: Database
) -> CinemaTripResponse:
    """The proposer turns a suggestion down and keeps the trip's time."""
    trip, told = await trips.keep(db, user, trip_id, payload, utcnow())
    return await _answer(db, user, trip, told)


@router.post("/{trip_id}/invitees", response_model=CinemaTripResponse)
async def invite_more(
    trip_id: uuid.UUID, payload: InviteMore, user: CurrentUser, db: Database
) -> CinemaTripResponse:
    """The proposer invites more people; someone already invited is left as they are."""
    trip, told = await trips.invite_more(db, user, trip_id, payload, utcnow())
    return await _answer(db, user, trip, told)


@router.post("/{trip_id}/cancel", response_model=CinemaTripResponse)
async def cancel_trip(trip_id: uuid.UUID, user: CurrentUser, db: Database) -> CinemaTripResponse:
    """The proposer cancels. Cancelling again changes nothing."""
    trip, told = await trips.cancel(db, user, trip_id, utcnow())
    return await _answer(db, user, trip, told)
