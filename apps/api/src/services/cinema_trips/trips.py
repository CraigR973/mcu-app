"""Cinema trips: who is on one, what it says, and every way it changes — AC5 (#345).

**Every write on a trip locks the trip's row first,** so writes to one trip run one after
another: two invitees replying at once both land, and a move and a reply never interleave.
A write names the trip ``revision`` (and, to act on a suggestion, its ``reply_revision``) it
was made against; one made against a screen that is now out of date is refused (409). A
retried request whose first answer was lost is answered with the trip as it now is, and
changes and pushes nothing twice.

**A time can be proposed, suggested or moved to only while the film page lists it as
confirmed and still to start**: "another showing of the same film" is "any time on the
film's page", by AC4's own read (`services.cinemas.films.film`), so a listing that a morning
has since linked offers every cinema's times of the film.

**The flag and Check tickets come from the live row** on every read; the trip shows its
snapshot. The flag clears by itself if a cinema lists the time again.

Pushes go through the outbox under Movie night, each with a dedupe key that carries the
revision it is about. The caller commits, then delivers (`movie_night.sessions.deliver_now`).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cinema import CinemaFilm, CinemaScreening, CinemaVenue
from src.models.cinema_trip import CinemaTrip, CinemaTripInvitee
from src.models.notification import NotificationCategory
from src.models.profile import Profile
from src.schemas.cinema_trips import (
    CinemaTripList,
    CinemaTripResponse,
    InviteMore,
    KeepTime,
    MoveTrip,
    ProposeTrip,
    ReplyToTrip,
    ShowingFlag,
    TripCounts,
    TripInvitee,
    TripPerson,
    TripReply,
    TripShowing,
    TripStatus,
    TripSuggestion,
)
from src.schemas.cinemas import ProgrammeVenue
from src.schemas.needs_you import NeedsYouTripItem, NextTrip
from src.services.cinema_trips import words
from src.services.cinemas import films
from src.services.cinemas.programme import Window, load_window
from src.services.notifications import queue_notification

#: Who can be invited, and who is told: the people movie nights can be sent to.
CAN_BE_TOLD = (
    Profile.is_active.is_(True),
    Profile.deleted_at.is_(None),
    Profile.pin_hash.is_not(None),
)

_WIRE: dict[str, TripReply] = {
    "invited": "invited",
    "going": "going",
    "not_going": "notGoing",
    "another_time": "anotherTime",
}
_STORED = {"going": "going", "notGoing": "not_going", "anotherTime": "another_time"}

#: The flags that mean the cinema no longer lists the time as the trip has it: the proposer is
#: asked to pick another time or cancel (#345 §3, decision 7).
NOT_LISTED: frozenset[ShowingFlag] = frozenset({"withdrawn", "cancelled"})


def _refuse(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _not_found() -> HTTPException:
    return _refuse(status.HTTP_404_NOT_FOUND, "Trip not found")


def _no_longer_listed() -> HTTPException:
    return _refuse(status.HTTP_409_CONFLICT, "That time is no longer listed")


def trip_url(trip: CinemaTrip) -> str:
    return f"/movie-night/trips/{trip.id}"


def trip_status(trip: CinemaTrip, now: datetime) -> TripStatus:
    if trip.cancelled_at_utc is not None:
        return "cancelled"
    return "past" if trip.starts_utc <= now else "upcoming"


def flag(row: CinemaScreening | None, starts_utc: datetime) -> ShowingFlag | None:
    """What the live programme says about a showing the trip keeps at ``starts_utc``.

    A showing the programme no longer holds, or now lists at another time, reads as withdrawn:
    the cinema no longer lists the time the trip has, and following the row to its new time
    is the proposer's move to make, never the trip's (#345 §3).
    """
    if row is None or row.deleted_at is not None or row.confirmation == "withdrawn":
        return "withdrawn"
    if row.confirmation == "cancelled":
        return "cancelled"
    if row.starts_utc != starts_utc:
        return "withdrawn"
    if row.confirmation == "unconfirmed":
        return "unconfirmed"
    return None


def _local_date(starts_utc: datetime, zone: str) -> date:
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("Europe/London")
    return starts_utc.replace(tzinfo=UTC).astimezone(tz).date()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


async def _trip_for(
    db: AsyncSession, trip_id: uuid.UUID, user: Profile, *, lock: bool
) -> CinemaTrip:
    """The trip, if ``user`` is on it; "Trip not found" for everyone else, as for no trip."""
    # `populate_existing`: a row this session already holds is read again, so neither a read
    # nor a write (under its lock) decides on a version another request has since changed.
    query = (
        select(CinemaTrip).where(CinemaTrip.id == trip_id).execution_options(populate_existing=True)
    )
    if lock:
        query = query.with_for_update()
    trip = await db.scalar(query)
    if trip is None:
        raise _not_found()
    if trip.proposer_id != user.id:
        invited = await db.scalar(
            select(CinemaTripInvitee.id).where(
                CinemaTripInvitee.trip_id == trip.id, CinemaTripInvitee.profile_id == user.id
            )
        )
        if invited is None:
            raise _not_found()
    return trip


async def _invitees(
    db: AsyncSession, trip_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[CinemaTripInvitee, Profile]]]:
    rows = (
        await db.execute(
            select(CinemaTripInvitee, Profile)
            .join(Profile, Profile.id == CinemaTripInvitee.profile_id)
            .where(CinemaTripInvitee.trip_id.in_(trip_ids))
            .order_by(Profile.display_name, Profile.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    by_trip: dict[uuid.UUID, list[tuple[CinemaTripInvitee, Profile]]] = defaultdict(list)
    for invitee, person in rows:
        by_trip[invitee.trip_id].append((invitee, person))
    return by_trip


async def _profiles(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, Profile]:
    if not ids:
        return {}
    return {p.id: p for p in (await db.scalars(select(Profile).where(Profile.id.in_(ids)))).all()}


@dataclass
class _Live:
    """The programme's current rows for a set of trips, and their window for ticket links."""

    rows: dict[uuid.UUID, tuple[CinemaScreening, CinemaFilm]]
    venues: dict[uuid.UUID, ProgrammeVenue]
    window: Window | None


async def _live(db: AsyncSession, ids: set[uuid.UUID], now: datetime) -> _Live:
    if not ids:
        return _Live({}, {}, None)
    found = (
        await db.execute(
            select(CinemaScreening, CinemaFilm)
            .join(CinemaFilm, CinemaFilm.id == CinemaScreening.film_id)
            .where(CinemaScreening.id.in_(ids))
        )
    ).all()
    rows = {showing.id: (showing, film) for showing, film in found}
    dates = sorted({showing.local_date for showing, _ in rows.values()})
    if not dates:
        return _Live(rows, {}, None)
    window = await load_window(db, dates, now)
    venues = {v.id: v for v in window.venue_responses()}
    return _Live(rows, venues, window)


def _showing(trip: CinemaTrip, live: _Live, now: datetime) -> TripShowing:
    row = live.rows.get(trip.showing_id) if trip.showing_id else None
    current = trip_status(trip, now) == "upcoming"
    showing_flag = flag(row[0] if row else None, trip.starts_utc) if current else None
    programme = None
    venue = None
    # Only while the cinema still lists the trip's own time: a row the cinema has moved to
    # another time would book the other time.
    if (
        current
        and row is not None
        and showing_flag in (None, "unconfirmed")
        and live.window is not None
        and row[0].venue_id in live.venues
    ):
        showing, cinema_film = row
        programme = live.window.showing(
            showing, cinema_film, verified=cinema_film.identity_status == "verified"
        )
        venue = live.venues[showing.venue_id]
    return TripShowing(
        showingId=trip.showing_id,
        venueId=trip.venue_id,
        venueName=trip.venue_name,
        venueTimezone=trip.venue_timezone,
        startsAtUtc=trip.starts_utc,
        endsAtUtc=trip.ends_utc,
        screen=trip.screen,
        formats=list(trip.formats or []),
        flag=showing_flag,
        live=programme,
        venue=venue,
    )


def _suggestion(invitee: CinemaTripInvitee, live: _Live) -> TripSuggestion | None:
    if invitee.reply != "another_time" or invitee.suggested_starts_utc is None:
        return None
    row = live.rows.get(invitee.suggested_showing_id) if invitee.suggested_showing_id else None
    return TripSuggestion(
        showingId=invitee.suggested_showing_id,
        venueName=invitee.suggested_venue_name or "",
        startsAtUtc=invitee.suggested_starts_utc,
        formats=list(invitee.suggested_formats or []),
        flag=flag(row[0] if row else None, invitee.suggested_starts_utc),
    )


async def describe(
    db: AsyncSession, trips: list[CinemaTrip], user: Profile, now: datetime
) -> list[CinemaTripResponse]:
    """The trips as their members read them, in the order given."""
    if not trips:
        return []
    invitees = await _invitees(db, [t.id for t in trips])
    proposers = await _profiles(db, {t.proposer_id for t in trips})
    ids = {t.showing_id for t in trips if t.showing_id} | {
        i.suggested_showing_id
        for rows in invitees.values()
        for i, _ in rows
        if i.suggested_showing_id
    }
    live = await _live(db, ids, now)
    described = []
    for trip in trips:
        people = invitees.get(trip.id, [])
        proposer = proposers[trip.proposer_id]
        replies = [i.reply for i, _ in people]
        mine = next((i for i, p in people if p.id == user.id), None)
        described.append(
            CinemaTripResponse(
                id=trip.id,
                filmKey=trip.film_key,
                filmTitle=trip.film_title,
                posterPath=trip.poster_path,
                proposer=TripPerson(
                    profileId=proposer.id,
                    displayName=proposer.display_name,
                    isYou=proposer.id == user.id,
                ),
                status=trip_status(trip, now),
                revision=trip.revision,
                showing=_showing(trip, live, now),
                invitees=[
                    TripInvitee(
                        profileId=person.id,
                        displayName=person.display_name,
                        isYou=person.id == user.id,
                        reply=_WIRE[invitee.reply],
                        replyRevision=invitee.reply_revision,
                        repliedAtUtc=invitee.replied_at_utc,
                        suggestion=_suggestion(invitee, live),
                    )
                    for invitee, person in people
                ],
                counts=TripCounts(
                    going=1 + replies.count("going"),
                    notGoing=replies.count("not_going"),
                    anotherTime=replies.count("another_time"),
                    invited=replies.count("invited"),
                ),
                yourReply=_WIRE[mine.reply] if mine is not None else None,
                createdAtUtc=trip.created_at,
                movedAtUtc=trip.moved_at_utc,
                cancelledAtUtc=trip.cancelled_at_utc,
            )
        )
    return described


def _mine(user: Profile) -> ColumnElement[bool]:
    """Trips ``user`` proposed or is invited to."""
    return or_(
        CinemaTrip.proposer_id == user.id,
        CinemaTrip.id.in_(
            select(CinemaTripInvitee.trip_id).where(CinemaTripInvitee.profile_id == user.id)
        ),
    )


async def trips_of(db: AsyncSession, user: Profile, now: datetime) -> CinemaTripList:
    trips = list(
        (
            await db.scalars(
                select(CinemaTrip)
                .where(_mine(user))
                .order_by(CinemaTrip.starts_utc, CinemaTrip.id)
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    upcoming = [t for t in trips if trip_status(t, now) == "upcoming"]
    past = sorted(
        (t for t in trips if trip_status(t, now) != "upcoming"),
        key=lambda t: (t.starts_utc, t.id),
        reverse=True,
    )
    return CinemaTripList(
        upcoming=await describe(db, upcoming, user, now),
        past=await describe(db, past, user, now),
    )


async def one(
    db: AsyncSession, trip_id: uuid.UUID, user: Profile, now: datetime
) -> CinemaTripResponse:
    trip = await _trip_for(db, trip_id, user, lock=False)
    [described] = await describe(db, [trip], user, now)
    return described


async def invitable(db: AsyncSession, user: Profile) -> list[TripPerson]:
    people = (
        await db.scalars(
            select(Profile)
            .where(*CAN_BE_TOLD, Profile.id != user.id)
            .order_by(Profile.display_name, Profile.id)
        )
    ).all()
    return [TripPerson(profileId=p.id, displayName=p.display_name, isYou=False) for p in people]


# ---------------------------------------------------------------------------
# Picking a time
# ---------------------------------------------------------------------------


@dataclass
class _Picked:
    key: str
    title: str
    poster: str | None
    row: CinemaScreening
    venue: CinemaVenue


async def _pick(
    db: AsyncSession, user: Profile, film_key: str, showing_id: uuid.UUID, now: datetime
) -> _Picked:
    """A time on the film's page that is confirmed and still to start, or a refusal."""
    try:
        detail = await films.film(db, user.id, film_key)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise _no_longer_listed() from exc
        raise
    shown = next((s for s in detail.showings if s.id == showing_id), None)
    row = await db.get(CinemaScreening, showing_id)
    if row is None:
        raise _no_longer_listed()
    if shown is None:
        current = (
            row.deleted_at is None
            and not row.source_expired
            and row.confirmation == "confirmed"
            and row.starts_utc > now
        )
        if current:
            # A time still listed, but not on this film's page: another film's.
            raise _refuse(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "That time isn't a showing of this film"
            )
        raise _no_longer_listed()
    if shown.confirmation != "confirmed" or row.starts_utc <= now:
        raise _no_longer_listed()
    venue = await db.get(CinemaVenue, row.venue_id)
    if venue is None:
        raise _no_longer_listed()
    return _Picked(detail.film.key, detail.film.title, detail.film.posterPath, row, venue)


def _snapshot(trip: CinemaTrip, picked: _Picked) -> None:
    row, venue = picked.row, picked.venue
    trip.showing_id = row.id
    trip.venue_id = venue.id
    trip.venue_name = venue.name
    trip.venue_timezone = venue.timezone or "Europe/London"
    trip.starts_utc = row.starts_utc
    trip.ends_utc = row.ends_utc
    trip.screen = row.screen
    trip.formats = list(row.formats or [])
    trip.booking_url = row.booking_url


def _same_time(trip: CinemaTrip, row: CinemaScreening) -> bool:
    return trip.showing_id == row.id and trip.starts_utc == row.starts_utc


# ---------------------------------------------------------------------------
# Pushes
# ---------------------------------------------------------------------------


async def _told(db: AsyncSession, ids: set[uuid.UUID]) -> set[uuid.UUID]:
    """Of ``ids``, the people a push can still reach: an inactive profile is told nothing."""
    if not ids:
        return set()
    found = await db.scalars(select(Profile.id).where(Profile.id.in_(ids), *CAN_BE_TOLD))
    return set(found.all())


async def _push(
    db: AsyncSession,
    trip: CinemaTrip,
    person: uuid.UUID,
    heading: str,
    body: str,
    key: str,
    now: datetime,
) -> None:
    await queue_notification(
        db,
        user_id=person,
        category=NotificationCategory.movie_night,
        title=words.title(heading),
        body=body,
        url=trip_url(trip),
        dedupe_key=key,
        now=now,
    )


def _line(trip: CinemaTrip) -> str:
    """ "Wild Horse Nine, Mon 9 Nov at 20:10, ODEON Glasgow Quay." """
    at = words.when(trip.starts_utc, trip.venue_timezone, trip.formats)
    return f"{trip.film_title}, {at}, {trip.venue_name}."


async def _invite(
    db: AsyncSession, trip: CinemaTrip, proposer: Profile, people: list[uuid.UUID], now: datetime
) -> list[uuid.UUID]:
    told = await _told(db, set(people))
    for person in people:
        if person in told:
            await _push(
                db,
                trip,
                person,
                f"{proposer.display_name} invited you to the cinema",
                f"{_line(trip)} Going, not going, or another time?",
                f"cinema-trip-invite:{trip.id}:{person}",
                now,
            )
    return [p for p in people if p in told]


# ---------------------------------------------------------------------------
# Writes. Each returns the people to deliver to once the caller has committed.
# ---------------------------------------------------------------------------


def _guard_open(trip: CinemaTrip, proposer: Profile, now: datetime) -> None:
    if trip.cancelled_at_utc is not None:
        raise _refuse(status.HTTP_409_CONFLICT, f"{proposer.display_name} cancelled this trip")
    if trip.starts_utc <= now:
        raise _refuse(status.HTTP_409_CONFLICT, "This showing has started")


def _guard_revision(trip: CinemaTrip, revision: int) -> None:
    if revision != trip.revision:
        raise _refuse(
            status.HTTP_409_CONFLICT, "The trip has moved. Check the new time and reply again."
        )


def _guard_proposer(trip: CinemaTrip, user: Profile, proposer: Profile) -> None:
    if trip.proposer_id != user.id:
        raise _refuse(
            status.HTTP_403_FORBIDDEN, f"Only {proposer.display_name} can change this trip"
        )


async def _named_people(db: AsyncSession, user: Profile, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """The people named, each once, if every one of them can be invited."""
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick at least one person")
    if user.id in wanted:
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "Not everyone named can be invited")
    found = await _told(db, set(wanted))
    if len(found) != len(wanted):
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "Not everyone named can be invited")
    return wanted


async def propose(
    db: AsyncSession, user: Profile, payload: ProposeTrip, now: datetime
) -> tuple[CinemaTrip, list[uuid.UUID]]:
    """A new trip with one Invited row per person, each invited. A send whose answer was lost
    (the same ``clientRequestId``) returns the trip it made and invites nobody twice."""
    existing = await db.scalar(
        select(CinemaTrip).where(
            CinemaTrip.proposer_id == user.id,
            CinemaTrip.client_request_id == payload.clientRequestId,
        )
    )
    if existing is not None:
        return existing, []
    people = await _named_people(db, user, payload.inviteeIds)
    picked = await _pick(db, user, payload.filmKey, payload.showingId, now)
    trip_id = uuid.uuid4()
    inserted = await db.scalar(
        pg_insert(CinemaTrip)
        .values(
            id=trip_id,
            client_request_id=payload.clientRequestId,
            proposer_id=user.id,
            film_key=picked.key,
            film_title=picked.title,
            poster_path=picked.poster,
            showing_id=picked.row.id,
            venue_id=picked.venue.id,
            venue_name=picked.venue.name,
            venue_timezone=picked.venue.timezone or "Europe/London",
            starts_utc=picked.row.starts_utc,
            ends_utc=picked.row.ends_utc,
            screen=picked.row.screen,
            formats=list(picked.row.formats or []),
            booking_url=picked.row.booking_url,
            revision=1,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_cinema_trip_request")
        .returning(CinemaTrip.id)
    )
    if inserted is None:
        # The same send, racing itself: the first one made the trip.
        raced = await db.scalar(
            select(CinemaTrip).where(
                CinemaTrip.proposer_id == user.id,
                CinemaTrip.client_request_id == payload.clientRequestId,
            )
        )
        assert raced is not None
        return raced, []
    trip = await db.get(CinemaTrip, trip_id)
    assert trip is not None
    for person in people:
        db.add(CinemaTripInvitee(id=uuid.uuid4(), trip_id=trip.id, profile_id=person))
    await db.flush()
    return trip, await _invite(db, trip, user, people, now)


async def _row_of(
    db: AsyncSession, trip: CinemaTrip, person: uuid.UUID
) -> CinemaTripInvitee | None:
    row: CinemaTripInvitee | None = await db.scalar(
        select(CinemaTripInvitee)
        .where(CinemaTripInvitee.trip_id == trip.id, CinemaTripInvitee.profile_id == person)
        .execution_options(populate_existing=True)
    )
    return row


def _clear_suggestion(row: CinemaTripInvitee) -> None:
    row.suggested_showing_id = None
    row.suggested_venue_name = None
    row.suggested_starts_utc = None
    row.suggested_formats = None


def _set_reply(row: CinemaTripInvitee, reply: str, now: datetime) -> None:
    row.reply = reply
    row.replied_at_utc = None if reply == "invited" else now
    if reply != "another_time":
        _clear_suggestion(row)
    row.reply_revision += 1


async def _tally(db: AsyncSession, trip: CinemaTrip) -> str:
    """ " 2 of 3 going." with two or more invitees, the proposer counted as going (#345 §5)."""
    replies = (
        await db.scalars(
            select(CinemaTripInvitee.reply).where(CinemaTripInvitee.trip_id == trip.id)
        )
    ).all()
    return words.tally(1 + replies.count("going"), 1 + len(replies), invitees=len(replies))


async def reply(
    db: AsyncSession, user: Profile, trip_id: uuid.UUID, payload: ReplyToTrip, now: datetime
) -> tuple[CinemaTrip, list[uuid.UUID]]:
    """An invitee's Going, Not going or Another time; the proposer alone is told."""
    trip = await _trip_for(db, trip_id, user, lock=True)
    proposer = await db.get(Profile, trip.proposer_id)
    assert proposer is not None
    if trip.proposer_id == user.id:
        raise _refuse(status.HTTP_403_FORBIDDEN, "You're organising this trip")
    row = await _row_of(db, trip, user.id)
    assert row is not None  # `_trip_for` let a member through
    stored = _STORED[payload.reply]
    # The same reply again changes nothing, whatever has happened since: a retry whose first
    # answer was lost is answered with the trip as it now is (#345 §2).
    if row.reply == stored and (
        stored != "another_time" or row.suggested_showing_id == payload.showingId
    ):
        return trip, []
    _guard_open(trip, proposer, now)
    _guard_revision(trip, payload.revision)
    picked = None
    if stored == "another_time":
        assert payload.showingId is not None  # the schema pairs them
        picked = await _pick(db, user, trip.film_key, payload.showingId, now)
        if _same_time(trip, picked.row):
            raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "That's already the trip's time")
    _set_reply(row, stored, now)
    if picked is not None:
        row.suggested_showing_id = picked.row.id
        row.suggested_venue_name = picked.venue.name
        row.suggested_starts_utc = picked.row.starts_utc
        row.suggested_formats = list(picked.row.formats or [])
    await db.flush()

    name = user.display_name
    key = f"cinema-trip-reply:{trip.id}:{user.id}:{row.reply_revision}"
    if stored == "going":
        heading, body = f"{name} is going", f"{_line(trip)}{await _tally(db, trip)}"
    elif stored == "not_going":
        heading, body = f"{name} can't make it", f"{_line(trip)}{await _tally(db, trip)}"
    else:
        assert picked is not None
        suggested = words.when(
            picked.row.starts_utc, picked.venue.timezone or "Europe/London", picked.row.formats
        )
        heading = f"{name} suggests another time"
        body = (
            f"{trip.film_title}: {suggested}, {picked.venue.name}, instead of "
            f"{words.when(trip.starts_utc, trip.venue_timezone, trip.formats)}. "
            "Open it to accept or keep your time."
        )
    told = await _told(db, {proposer.id})
    if proposer.id in told:
        await _push(db, trip, proposer.id, heading, body, key, now)
    return trip, list(told)


async def move(
    db: AsyncSession, user: Profile, trip_id: uuid.UUID, payload: MoveTrip, now: datetime
) -> tuple[CinemaTrip, list[uuid.UUID]]:
    """Accept a suggestion, or move to a time of the proposer's own. The trip takes the live
    showing's facts; an accepted suggester is Going; everyone else is Invited again."""
    trip = await _trip_for(db, trip_id, user, lock=True)
    proposer = await db.get(Profile, trip.proposer_id)
    assert proposer is not None
    _guard_proposer(trip, user, proposer)
    if (
        payload.revision + 1 == trip.revision
        and trip.showing_id == payload.showingId
        and trip.cancelled_at_utc is None
    ):
        # This move, already made: only the proposer moves a trip, so the one move since the
        # screen was drawn, to this very showing, is this request's first try.
        return trip, []
    _guard_open(trip, proposer, now)
    _guard_revision(trip, payload.revision)
    people = await _invitees(db, [trip.id])
    rows = people.get(trip.id, [])
    suggester: tuple[CinemaTripInvitee, Profile] | None = None
    if payload.fromProfileId is not None:
        suggester = next(((i, p) for i, p in rows if p.id == payload.fromProfileId), None)
        if suggester is None:
            raise _not_found()
        invitee, person = suggester
        if (
            invitee.reply != "another_time"
            or invitee.reply_revision != payload.fromReplyRevision
            or invitee.suggested_showing_id != payload.showingId
        ):
            raise _refuse(status.HTTP_409_CONFLICT, f"{person.display_name} changed their reply")
    picked = await _pick(db, user, trip.film_key, payload.showingId, now)
    if _same_time(trip, picked.row):
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "That's already the trip's time")
    if suggester is not None and suggester[0].suggested_starts_utc != picked.row.starts_utc:
        # The cinema moved the suggested time since it was suggested.
        raise _no_longer_listed()
    _snapshot(trip, picked)
    trip.revision += 1
    trip.moved_at_utc = now
    for invitee, person in rows:
        if suggester is not None and person.id == suggester[1].id:
            _set_reply(invitee, "going", now)
        elif invitee.reply != "invited" or invitee.suggested_starts_utc is not None:
            _set_reply(invitee, "invited", now)
    await db.flush()

    told = await _told(db, {p.id for _, p in rows})
    at = words.when(trip.starts_utc, trip.venue_timezone, trip.formats)
    for _, person in rows:
        if person.id not in told:
            continue
        if suggester is not None and person.id == suggester[1].id:
            heading = f"{proposer.display_name} accepted your time"
            body = f"{_line(trip)} You're down as going."
        elif suggester is not None:
            heading = f"Cinema trip moved: {trip.film_title}"
            body = (
                f"Now {at}, {trip.venue_name}, {words.possessive(suggester[1].display_name)} "
                "suggestion. Going or not?"
            )
        else:
            heading = f"Cinema trip moved: {trip.film_title}"
            body = f"{proposer.display_name} moved it to {at}, {trip.venue_name}. Going or not?"
        key = f"cinema-trip-change:{trip.id}:{trip.revision}:{person.id}"
        await _push(db, trip, person.id, heading, body, key, now)
    return trip, [p.id for _, p in rows if p.id in told]


async def keep(
    db: AsyncSession, user: Profile, trip_id: uuid.UUID, payload: KeepTime, now: datetime
) -> tuple[CinemaTrip, list[uuid.UUID]]:
    """The proposer turns a suggestion down: its suggester is Invited again, and told."""
    trip = await _trip_for(db, trip_id, user, lock=True)
    proposer = await db.get(Profile, trip.proposer_id)
    assert proposer is not None
    _guard_proposer(trip, user, proposer)
    row = await _row_of(db, trip, payload.profileId)
    if row is None:
        raise _not_found()
    if row.reply == "invited" and row.reply_revision == payload.replyRevision + 1:
        # The suggestion is gone and nothing else has happened since: this keep, already
        # made (or a move that reset it, which told them). Nothing to change or say twice.
        return trip, []
    _guard_open(trip, proposer, now)
    person = await db.get(Profile, payload.profileId)
    assert person is not None
    if row.reply != "another_time" or row.reply_revision != payload.replyRevision:
        raise _refuse(status.HTTP_409_CONFLICT, f"{person.display_name} changed their reply")
    _set_reply(row, "invited", now)
    await db.flush()
    told = await _told(db, {person.id})
    if person.id in told:
        await _push(
            db,
            trip,
            person.id,
            f"{proposer.display_name} is keeping the original time",
            f"{_line(trip)} Going or not?",
            f"cinema-trip-keep:{trip.id}:{person.id}:{row.reply_revision}",
            now,
        )
    return trip, list(told)


async def invite_more(
    db: AsyncSession, user: Profile, trip_id: uuid.UUID, payload: InviteMore, now: datetime
) -> tuple[CinemaTrip, list[uuid.UUID]]:
    """New Invited rows, and an invitation to the new invitees only; someone already invited
    is left as they are, so a retried request invites nobody twice."""
    trip = await _trip_for(db, trip_id, user, lock=True)
    proposer = await db.get(Profile, trip.proposer_id)
    assert proposer is not None
    _guard_proposer(trip, user, proposer)
    _guard_open(trip, proposer, now)
    wanted = await _named_people(db, user, payload.profileIds)
    present = set(
        (
            await db.scalars(
                select(CinemaTripInvitee.profile_id).where(CinemaTripInvitee.trip_id == trip.id)
            )
        ).all()
    )
    new = [p for p in wanted if p not in present]
    for person in new:
        db.add(CinemaTripInvitee(id=uuid.uuid4(), trip_id=trip.id, profile_id=person))
    await db.flush()
    return trip, await _invite(db, trip, user, new, now)


async def cancel(
    db: AsyncSession, user: Profile, trip_id: uuid.UUID, now: datetime
) -> tuple[CinemaTrip, list[uuid.UUID]]:
    """The proposer cancels; everyone not Not going is told. Cancelling again is a no-op."""
    trip = await _trip_for(db, trip_id, user, lock=True)
    proposer = await db.get(Profile, trip.proposer_id)
    assert proposer is not None
    _guard_proposer(trip, user, proposer)
    if trip.cancelled_at_utc is not None:
        return trip, []
    if trip.starts_utc <= now:
        raise _refuse(status.HTTP_409_CONFLICT, "This showing has started")
    trip.cancelled_at_utc = now
    await db.flush()
    rows = (await _invitees(db, [trip.id])).get(trip.id, [])
    told = await _told(db, {p.id for i, p in rows if i.reply != "not_going"})
    at = words.when(trip.starts_utc, trip.venue_timezone, trip.formats)
    for _, person in rows:
        if person.id in told:
            await _push(
                db,
                trip,
                person.id,
                "Cinema trip cancelled",
                f"{proposer.display_name} cancelled {trip.film_title} on {at}, {trip.venue_name}.",
                f"cinema-trip-cancel:{trip.id}:{person.id}",
                now,
            )
    return trip, list(told)


# ---------------------------------------------------------------------------
# Home: Needs you and the top slot
# ---------------------------------------------------------------------------


async def needs_you_trips(
    db: AsyncSession, person: Profile, now: datetime
) -> list[NeedsYouTripItem]:
    """What only ``person`` can do about a trip now, soonest showing first: an invitation
    waiting for their reply; and, to the proposer, a suggestion waiting for them and a showing
    the cinema no longer lists as the trip has it (#345, decision 7)."""
    upcoming = list(
        (
            await db.scalars(
                select(CinemaTrip).where(
                    CinemaTrip.cancelled_at_utc.is_(None),
                    CinemaTrip.starts_utc > now,
                    _mine(person),
                )
            )
        ).all()
    )
    if not upcoming:
        return []
    invitees = await _invitees(db, [t.id for t in upcoming])
    proposers = await _profiles(db, {t.proposer_id for t in upcoming})
    live = await _live(db, {t.showing_id for t in upcoming if t.showing_id}, now)
    items: list[tuple[tuple[datetime, int, str], NeedsYouTripItem]] = []
    for trip in upcoming:
        base = {
            "tripId": trip.id,
            "filmTitle": trip.film_title,
            "posterPath": trip.poster_path,
            "venueName": trip.venue_name,
            "venueTimezone": trip.venue_timezone,
            "startsAtUtc": trip.starts_utc,
            "proposerName": proposers[trip.proposer_id].display_name,
        }
        rows = invitees.get(trip.id, [])
        if trip.proposer_id == person.id:
            row = live.rows.get(trip.showing_id) if trip.showing_id else None
            showing_flag = flag(row[0] if row else None, trip.starts_utc)
            if showing_flag in NOT_LISTED:
                items.append(
                    (
                        (trip.starts_utc, 1, ""),
                        NeedsYouTripItem(kind="tripWithdrawn", flag=showing_flag, **base),
                    )
                )
            for invitee, who in rows:
                if invitee.reply == "another_time":
                    items.append(
                        (
                            (trip.starts_utc, 2, who.display_name.casefold()),
                            NeedsYouTripItem(
                                kind="tripSuggestion", fromName=who.display_name, **base
                            ),
                        )
                    )
        else:
            mine = next((i for i, p in rows if p.id == person.id), None)
            if mine is not None and mine.reply == "invited":
                items.append(
                    ((trip.starts_utc, 0, ""), NeedsYouTripItem(kind="tripInvite", **base))
                )
    return [item for _, item in sorted(items, key=lambda pair: pair[0])]


async def next_trip(db: AsyncSession, person: Profile, now: datetime) -> NextTrip | None:
    """The soonest trip still to start that ``person`` proposed or is going on."""
    trip = await db.scalar(
        select(CinemaTrip)
        .where(
            CinemaTrip.cancelled_at_utc.is_(None),
            CinemaTrip.starts_utc > now,
            or_(
                CinemaTrip.proposer_id == person.id,
                CinemaTrip.id.in_(
                    select(CinemaTripInvitee.trip_id).where(
                        CinemaTripInvitee.profile_id == person.id,
                        CinemaTripInvitee.reply == "going",
                    )
                ),
            ),
        )
        .order_by(CinemaTrip.starts_utc, CinemaTrip.id)
        .limit(1)
    )
    if trip is None:
        return None
    rows = (await _invitees(db, [trip.id])).get(trip.id, [])
    proposer = await db.get(Profile, trip.proposer_id)
    assert proposer is not None
    others = [proposer.display_name] if proposer.id != person.id else []
    others += [p.display_name for i, p in rows if i.reply == "going" and p.id != person.id]
    return NextTrip(
        tripId=trip.id,
        filmTitle=trip.film_title,
        venueName=trip.venue_name,
        venueTimezone=trip.venue_timezone,
        startsAtUtc=trip.starts_utc,
        withNames=others,
    )


# ---------------------------------------------------------------------------
# The morning reminder (#345, decision 2)
# ---------------------------------------------------------------------------


async def remind_today(db: AsyncSession, now: datetime) -> tuple[int, int]:
    """Queue the morning-of reminder for every trip whose showing is today, in the cinema's
    own date, and still to start: to the proposer and everyone Going. It is worth nothing
    later, so one that quiet hours or digest mode would hold past this pass is written as not
    sent (`too_late`). Returns (trips reminded, notifications written)."""
    candidates = list(
        (
            await db.scalars(
                select(CinemaTrip)
                .where(CinemaTrip.cancelled_at_utc.is_(None), CinemaTrip.starts_utc > now)
                .order_by(CinemaTrip.starts_utc, CinemaTrip.id)
            )
        ).all()
    )
    today = [
        t
        for t in candidates
        if _local_date(t.starts_utc, t.venue_timezone) == _local_date(now, t.venue_timezone)
    ]
    if not today:
        return 0, 0
    invitees = await _invitees(db, [t.id for t in today])
    proposers = await _profiles(db, {t.proposer_id for t in today})
    rows = {
        s.id: s
        for s in (
            await db.scalars(
                select(CinemaScreening).where(
                    CinemaScreening.id.in_([t.showing_id for t in today if t.showing_id])
                )
            )
        ).all()
    }
    written = 0
    for trip in today:
        proposer = proposers[trip.proposer_id]
        going = [proposer] + [p for i, p in invitees.get(trip.id, []) if i.reply == "going"]
        told = await _told(db, {p.id for p in going})
        showing_flag = flag(rows.get(trip.showing_id) if trip.showing_id else None, trip.starts_utc)
        at = words.clock(trip.starts_utc, trip.venue_timezone, trip.formats)
        for person in going:
            if person.id not in told:
                continue
            others = [p.display_name for p in going if p.id != person.id]
            company = f", with {words.names(others)}" if others else ""
            notification = await queue_notification(
                db,
                user_id=person.id,
                category=NotificationCategory.movie_night,
                title=words.title(f"Cinema today: {trip.film_title}"),
                body=f"{at} at {trip.venue_name}{company}.{words.flag_sentence(showing_flag)}",
                url=trip_url(trip),
                dedupe_key=f"cinema-trip-reminder:{trip.id}:{trip.revision}:{person.id}",
                now=now,
                deliver_by_utc=now,
            )
            written += notification is not None
    return len(today), written
