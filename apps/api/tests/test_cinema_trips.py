"""AC5: cinema trips — invite, reply, suggest another time (#335 point 4; the contract is #345).

Real Postgres, programme rows written as the refresh stores them, the clock fixed at 08:00 GMT
on Mon 9 Nov 2026: the morning pass of the checkpoint's worked example (Wild Horse Nine at ODEON
Glasgow Quay that evening at 20:10; at Cineworld Glasgow Silverburn on Tue 10 Nov at 20:00).
Each request acts as one person; every push is read back from the outbox.
"""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Connection, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.cinema import CinemaCoverage, CinemaFilm, CinemaScreening, CinemaVenue
from src.models.cinema_trip import CinemaTrip, CinemaTripInvitee
from src.models.movie import Movie
from src.models.notification import Notification
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog
from src.routers import cinema_trips as trips_router
from src.routers import needs_you as needs_you_router
from src.services import reminders
from src.services.cinema_trips import words
from src.services.cinemas import films as cinema_films
from src.services.cinemas.venues import BY_SLUG
from src.services.notifications import get_or_create_preferences
from src.services.push_transport import set_push_sender
from tests.test_movie_night_send import RecordingSender

NOW = datetime(2026, 11, 9, 8, 0)
MON = date(2026, 11, 9)
TUE = date(2026, 11, 10)
QUAY = BY_SLUG["odeon-glasgow-quay"]
SILVERBURN = BY_SLUG["cineworld-silverburn"]
WHN = 891621


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (trips_router, needs_you_router, cinema_films):
        monkeypatch.setattr(module, "utcnow", lambda: NOW)


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()
        app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def pushes() -> AsyncIterator[RecordingSender]:
    recorder = RecordingSender()
    set_push_sender(recorder)
    try:
        yield recorder
    finally:
        set_push_sender(None)


async def person(db: AsyncSession, name: str, *, active: bool = True) -> Profile:
    # A PIN hash, because only someone who can sign in can be invited. Nothing signs in.
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"{name} {uuid.uuid4().hex[:6]}",
        role=UserRole.viewer,
        pin_hash="test-pin-hash",
        is_active=active,
    )
    db.add(profile)
    await db.flush()
    return profile


@pytest_asyncio.fixture
async def craig(db: AsyncSession) -> Profile:
    return await person(db, "Craig")


@pytest_asyncio.fixture
async def mark(db: AsyncSession) -> Profile:
    return await person(db, "Mark")


@pytest_asyncio.fixture
async def alex(db: AsyncSession) -> Profile:
    return await person(db, "Alex")


@pytest_asyncio.fixture
async def sam(db: AsyncSession) -> Profile:
    """A fourth active profile, on no trip."""
    return await person(db, "Sam")


Call = Callable[..., Any]


@pytest_asyncio.fixture
async def as_(db: AsyncSession) -> Call:
    """``await as_(person, "post", path, json)``: one request, as that person."""

    async def call(who: Profile | None, method: str, path: str, body: Any = None) -> Response:
        async def override_db() -> AsyncIterator[AsyncSession]:
            yield db

        app.dependency_overrides[get_db] = override_db
        if who is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = lambda: who
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            return await http.request(method, f"/api/v1{path}", json=body)

    return call


async def film(db: AsyncSession, venue: Any, title: str = "Wild Horse Nine", tmdb: int = WHN):
    """One cinema's row for a film AC3 has linked, as the refresh stores it."""
    row = CinemaFilm(
        id=uuid.uuid4(),
        source=venue.source,
        source_key=f"ac5:{uuid.uuid4()}",
        title=title,
        identity_status="verified",
        evidence={"tmdbId": tmdb, "posterPath": f"/{tmdb}.jpg"},
        original_year=2026,
    )
    db.add(row)
    await db.flush()
    return row


async def showing(
    db: AsyncSession,
    venue: Any,
    cinema_film: CinemaFilm,
    day: date,
    at: str,
    *,
    formats: list[str] | None = None,
    confirmation: str = "confirmed",
) -> CinemaScreening:
    """A showing at ``at`` (GMT, which is UTC in November), with a ticket link and a current
    listing behind it, so Check tickets follows AB7's rule."""
    hour, minute = (int(part) for part in at.split(":"))
    row = CinemaScreening(
        id=uuid.uuid4(),
        venue_id=venue.id,
        film_id=cinema_film.id,
        source_key=f"ac5:{uuid.uuid4()}",
        identity_strength="opaque",
        local_date=day,
        source_local_start=f"{day.isoformat()}T{at}:00",
        starts_utc=datetime(day.year, day.month, day.day, hour, minute),
        formats=formats if formats is not None else ["Format.Projection.Digital"],
        booking_url="https://www.odeon.co.uk/ticketing/seat-picker/?showtimeId=ac5"
        if venue.source == "cinematimes"
        else "https://web.cineworld.co.uk/order/showtimes/ac5",
        release_category="newRelease",
        category_evidence={"run": "firstRun", "runReason": "UK release 30 Oct 2026 · first run"},
        confirmation=confirmation,
        first_seen_utc=NOW - timedelta(hours=1),
        last_seen_utc=NOW - timedelta(hours=1),
    )
    db.add(row)
    stored = await db.get(CinemaVenue, venue.id)
    assert stored is not None
    stored.collection_enabled = True
    known = await db.scalar(
        select(CinemaCoverage).where(
            CinemaCoverage.venue_id == venue.id, CinemaCoverage.local_date == day
        )
    )
    if known is None:
        db.add(
            CinemaCoverage(
                id=uuid.uuid4(),
                venue_id=venue.id,
                local_date=day,
                status="healthy",
                observed=True,
                complete=True,
                last_attempt_utc=NOW - timedelta(hours=1),
                last_success_utc=NOW - timedelta(hours=1),
            )
        )
    await db.flush()
    return row


class Programme:
    """The worked example's programme: Wild Horse Nine at two cinemas, and another film."""

    def __init__(
        self,
        monday: CinemaScreening,
        tuesday: CinemaScreening,
        early: CinemaScreening,
        other: CinemaScreening,
    ) -> None:
        self.monday = monday  # Mon 9 Nov 20:10, ODEON Glasgow Quay
        self.tuesday = tuesday  # Tue 10 Nov 20:00, Cineworld Glasgow Silverburn
        self.early = early  # Tue 10 Nov 18:00, ODEON Glasgow Quay
        self.other = other  # another film, Mon 9 Nov 19:00, ODEON Glasgow Quay


@pytest_asyncio.fixture
async def programme(db: AsyncSession) -> Programme:
    quay = await film(db, QUAY)
    silverburn = await film(db, SILVERBURN)
    another = await film(db, QUAY, "Clayface", 9_100_003)
    return Programme(
        await showing(db, QUAY, quay, MON, "20:10"),
        await showing(db, SILVERBURN, silverburn, TUE, "20:00"),
        await showing(db, QUAY, quay, TUE, "18:00"),
        await showing(db, QUAY, another, MON, "19:00"),
    )


async def propose(
    as_: Call, who: Profile, at: CinemaScreening, *people: Profile, request: uuid.UUID | None = None
) -> dict[str, Any]:
    response = await as_(
        who,
        "post",
        "/cinema-trips",
        {
            "clientRequestId": str(request or uuid.uuid4()),
            "filmKey": f"tmdb-{WHN}",
            "showingId": str(at.id),
            "inviteeIds": [str(p.id) for p in people],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def answer(
    as_: Call,
    who: Profile,
    trip: dict[str, Any],
    reply: str,
    at: CinemaScreening | None = None,
    *,
    revision: int | None = None,
) -> Response:
    body: dict[str, Any] = {"revision": revision or trip["revision"], "reply": reply}
    if at is not None:
        body["showingId"] = str(at.id)
    return await as_(who, "put", f"/cinema-trips/{trip['id']}/reply", body)


async def outbox(db: AsyncSession, trip: dict[str, Any]) -> list[Notification]:
    rows = await db.scalars(
        select(Notification)
        .where(Notification.dedupe_key.like(f"cinema-trip-%:{trip['id']}:%"))
        .order_by(Notification.created_at_utc, Notification.dedupe_key)
    )
    return list(rows.all())


def to(rows: list[Notification], who: Profile) -> list[tuple[str, str]]:
    return sorted((n.title, n.body) for n in rows if n.user_id == who.id)


def pushed(rows: list[Notification], who: Profile, kind: str) -> list[tuple[str, str]]:
    """One person's pushes of one kind (``invite``, ``reply``, ``change``, ``keep``, ``cancel``,
    ``reminder``), by dedupe key: every push here is written at the same fixed instant."""
    return sorted(
        (n.title, n.body)
        for n in rows
        if n.user_id == who.id and (n.dedupe_key or "").startswith(f"cinema-trip-{kind}:")
    )


def invitee(trip: dict[str, Any], who: Profile) -> dict[str, Any]:
    return next(i for i in trip["invitees"] if i["profileId"] == str(who.id))


LINE = "Wild Horse Nine, Mon 9 Nov at 20:10, ODEON Glasgow Quay."
MOVED_TO = "Tue 10 Nov at 20:00, Cineworld Glasgow Silverburn"


# ---------------------------------------------------------------------------
# Who can see, propose and be invited
# ---------------------------------------------------------------------------


async def test_every_trip_route_needs_a_signed_in_person(as_: Call) -> None:
    trip = uuid.uuid4()
    for method, path in [
        ("get", "/cinema-trips"),
        ("get", "/cinema-trips/people"),
        ("get", f"/cinema-trips/{trip}"),
        ("post", "/cinema-trips"),
        ("put", f"/cinema-trips/{trip}/reply"),
        ("post", f"/cinema-trips/{trip}/move"),
        ("post", f"/cinema-trips/{trip}/keep"),
        ("post", f"/cinema-trips/{trip}/invitees"),
        ("post", f"/cinema-trips/{trip}/cancel"),
    ]:
        assert (await as_(None, method, path, {})).status_code == 401, path


async def test_anyone_active_who_can_sign_in_can_be_invited_except_you(
    db: AsyncSession, as_: Call, craig: Profile, mark: Profile, alex: Profile
) -> None:
    gone = await person(db, "Gone", active=False)
    no_pin = await person(db, "Nopin")
    no_pin.pin_hash = None
    await db.flush()
    response = await as_(craig, "get", "/cinema-trips/people")
    assert response.status_code == 200, response.text
    people = {p["profileId"] for p in response.json()["people"]}
    assert {str(mark.id), str(alex.id)} <= people
    assert not people & {str(craig.id), str(gone.id), str(no_pin.id)}


async def test_asked_for_a_matched_film_each_person_s_latest_watch_says_who_has_seen_it(
    db: AsyncSession,
    as_: Call,
    programme: Programme,
    craig: Profile,
    mark: Profile,
    alex: Profile,
) -> None:
    """AE6 (#355, point 6): with a matched film's address, the invite list carries each
    person's latest watch of it, by movie night's rule (S7): a deleted watch never counts, nor
    one a namesake mismatch makes doubtful. The film is found by its TMDB id, though no cinema
    row links to its catalogue film here."""
    movie = Movie(
        id=uuid.uuid4(), tmdb_id=WHN, title="Wild Horse Nine", original_title="Wild Horse Nine"
    )
    db.add(movie)
    await db.flush()
    db.add_all(
        [
            WatchLog(movie_id=movie.id, user_id=mark.id, watched_at=date(2022, 1, 5)),
            WatchLog(movie_id=movie.id, user_id=mark.id, watched_at=date(2024, 3, 12)),
            WatchLog(
                movie_id=movie.id, user_id=mark.id, watched_at=date(2025, 6, 1), deleted_at=NOW
            ),
            WatchLog(
                movie_id=movie.id, user_id=alex.id, watched_at=date(2025, 1, 1), tmdb_id=WHN + 1
            ),
        ]
    )
    await db.flush()
    response = await as_(craig, "get", f"/cinema-trips/people?filmKey=tmdb-{WHN}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["seenKnown"] is True
    seen = {p["profileId"]: p["lastWatchedOn"] for p in body["people"]}
    assert seen[str(mark.id)] == "2024-03-12"
    assert seen[str(alex.id)] is None
    assert str(craig.id) not in seen

    # A listing not matched yet, an address that names nothing, or no film: nothing said.
    listing = CinemaFilm(
        id=uuid.uuid4(),
        source=QUAY.source,
        source_key=f"ac5:{uuid.uuid4()}",
        title="Untitled Preview",
        identity_status="unverified",
        evidence={},
    )
    db.add(listing)
    await db.flush()
    await showing(db, QUAY, listing, MON, "21:00")
    for path in (
        "/cinema-trips/people",
        f"/cinema-trips/people?filmKey=listing-{listing.id}",
        "/cinema-trips/people?filmKey=tmdb-999999",
    ):
        quiet = await as_(craig, "get", path)
        assert quiet.status_code == 200, (path, quiet.text)
        assert quiet.json()["seenKnown"] is False, path
        assert all(p["lastWatchedOn"] is None for p in quiet.json()["people"]), path
    assert (await as_(craig, "get", "/cinema-trips/people?filmKey=nonsense")).status_code == 422


async def test_proposing_keeps_the_showing_and_invites_each_person_once(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    request = uuid.uuid4()
    trip = await propose(as_, craig, programme.monday, mark, request=request)
    assert trip["status"] == "upcoming" and trip["revision"] == 1
    assert trip["filmKey"] == f"tmdb-{WHN}" and trip["filmTitle"] == "Wild Horse Nine"
    assert trip["posterPath"] == f"/{WHN}.jpg"
    assert trip["proposer"] == {
        "profileId": str(craig.id),
        "displayName": craig.display_name,
        "isYou": True,
    }
    showing = trip["showing"]
    assert showing["showingId"] == str(programme.monday.id)
    assert showing["venueName"] == "ODEON Glasgow Quay"
    assert showing["startsAtUtc"].startswith("2026-11-09T20:10:00")
    assert showing["flag"] is None and showing["live"]["bookingUrl"]
    # The proposer is not an invitee and always counts as going.
    assert [i["profileId"] for i in trip["invitees"]] == [str(mark.id)]
    assert invitee(trip, mark)["reply"] == "invited" and trip["yourReply"] is None
    assert trip["counts"] == {"going": 1, "notGoing": 0, "anotherTime": 0, "invited": 1}

    [invite] = await outbox(db, trip)
    assert (invite.user_id, invite.category, invite.url) == (
        mark.id,
        "movie_night",
        f"/movie-night/trips/{trip['id']}",
    )
    assert invite.title == f"{craig.display_name} invited you to the cinema"
    assert invite.body == f"{LINE} Going, not going, or another time?"
    assert invite.dedupe_key == f"cinema-trip-invite:{trip['id']}:{mark.id}"

    # A send whose answer was lost: the same trip, nobody invited twice.
    again = await propose(as_, craig, programme.monday, mark, request=request)
    assert again["id"] == trip["id"]
    assert len(await outbox(db, trip)) == 1
    assert await db.scalar(
        select(CinemaTrip.id).where(CinemaTrip.client_request_id == request)
    ) == uuid.UUID(trip["id"])


async def test_a_proposal_needs_people_who_can_be_invited_and_a_time_still_listed(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    gone = await person(db, "Gone", active=False)

    async def refused(at: CinemaScreening, people: list[uuid.UUID]) -> tuple[int, str]:
        response = await as_(
            craig,
            "post",
            "/cinema-trips",
            {
                "clientRequestId": str(uuid.uuid4()),
                "filmKey": f"tmdb-{WHN}",
                "showingId": str(at.id),
                "inviteeIds": [str(p) for p in people],
            },
        )
        return response.status_code, response.json()["detail"]

    assert await refused(programme.monday, []) == (422, "Pick at least one person")
    for nobody in (craig.id, gone.id, uuid.uuid4()):
        assert await refused(programme.monday, [mark.id, nobody]) == (
            422,
            "Not everyone named can be invited",
        )
    assert await refused(programme.other, [mark.id]) == (
        422,
        "That time isn't a showing of this film",
    )
    programme.monday.confirmation = "unconfirmed"
    await db.flush()
    assert await refused(programme.monday, [mark.id]) == (409, "That time is no longer listed")
    programme.monday.confirmation = "confirmed"
    programme.monday.starts_utc = NOW - timedelta(minutes=1)
    await db.flush()
    assert await refused(programme.monday, [mark.id]) == (409, "That time is no longer listed")
    assert await db.scalar(select(CinemaTrip.id).where(CinemaTrip.proposer_id == craig.id)) is None


async def test_nobody_off_the_trip_can_see_it_reply_to_it_or_be_told_of_it(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile, sam: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    path = f"/cinema-trips/{trip['id']}"
    for method, suffix, body in [
        ("get", "", None),
        ("put", "/reply", {"revision": 1, "reply": "going"}),
        ("post", "/cancel", {}),
        ("post", "/invitees", {"profileIds": [str(sam.id)]}),
    ]:
        response = await as_(sam, method, f"{path}{suffix}", body)
        assert (response.status_code, response.json()["detail"]) == (404, "Trip not found")
    assert (await as_(sam, "get", "/cinema-trips")).json() == {"upcoming": [], "past": []}
    needs = (await as_(sam, "get", "/needs-you")).json()
    assert needs["trips"] == [] and needs["nextTrip"] is None
    assert to(await outbox(db, trip), sam) == []


# ---------------------------------------------------------------------------
# Replies
# ---------------------------------------------------------------------------


async def test_a_reply_tells_the_proposer_alone_and_the_same_reply_again_changes_nothing(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    going = await answer(as_, mark, trip, "going")
    assert going.status_code == 200, going.text
    seen = going.json()
    assert seen["yourReply"] == "going" and invitee(seen, mark)["replyRevision"] == 1
    assert seen["counts"]["going"] == 2
    again = await answer(as_, mark, trip, "going")
    assert again.status_code == 200 and invitee(again.json(), mark)["replyRevision"] == 1
    assert to(await outbox(db, trip), craig) == [(f"{mark.display_name} is going", LINE)]

    no = await answer(as_, mark, trip, "notGoing")
    assert no.status_code == 200 and no.json()["counts"]["notGoing"] == 1
    assert pushed(await outbox(db, trip), craig, "reply") == sorted(
        [(f"{mark.display_name} is going", LINE), (f"{mark.display_name} can't make it", LINE)]
    )
    # The proposer has no reply of their own: to drop out, they cancel.
    mine = await answer(as_, craig, trip, "notGoing")
    assert mine.status_code == 403


async def test_three_people_on_one_trip_each_see_every_reply_and_the_tally(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile, alex: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark, alex)
    assert (await answer(as_, mark, trip, "going")).status_code == 200
    assert (await answer(as_, alex, trip, "notGoing")).status_code == 200
    assert to(await outbox(db, trip), craig) == sorted(
        [
            (f"{mark.display_name} is going", f"{LINE} 2 of 3 going."),
            (f"{alex.display_name} can't make it", f"{LINE} 2 of 3 going."),
        ]
    )
    for who in (craig, mark, alex):
        seen = (await as_(who, "get", f"/cinema-trips/{trip['id']}")).json()
        assert {i["displayName"]: i["reply"] for i in seen["invitees"]} == {
            mark.display_name: "going",
            alex.display_name: "notGoing",
        }
        assert seen["counts"] == {"going": 2, "notGoing": 1, "anotherTime": 0, "invited": 0}
        assert seen["proposer"]["isYou"] is (who is craig)


async def test_another_time_suggests_a_listed_showing_of_the_same_film(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    same = await answer(as_, mark, trip, "anotherTime", programme.monday)
    assert (same.status_code, same.json()["detail"]) == (422, "That's already the trip's time")
    other = await answer(as_, mark, trip, "anotherTime", programme.other)
    assert (other.status_code, other.json()["detail"]) == (
        422,
        "That time isn't a showing of this film",
    )
    suggested = await answer(as_, mark, trip, "anotherTime", programme.tuesday)
    assert suggested.status_code == 200, suggested.text
    mine = invitee(suggested.json(), mark)
    assert mine["reply"] == "anotherTime"
    assert mine["suggestion"]["showingId"] == str(programme.tuesday.id)
    assert mine["suggestion"]["venueName"] == "Cineworld Glasgow Silverburn"
    assert mine["suggestion"]["flag"] is None
    assert to(await outbox(db, trip), craig) == [
        (
            f"{mark.display_name} suggests another time",
            f"Wild Horse Nine: {MOVED_TO}, instead of Mon 9 Nov at 20:10. "
            "Open it to accept or keep your time.",
        )
    ]
    needs = (await as_(craig, "get", "/needs-you")).json()["trips"]
    assert [(n["kind"], n["fromName"]) for n in needs] == [("tripSuggestion", mark.display_name)]


async def test_two_suggested_times_at_once_then_one_accepted(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile, alex: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark, alex)
    assert (await answer(as_, mark, trip, "anotherTime", programme.tuesday)).status_code == 200
    two = await answer(as_, alex, trip, "anotherTime", programme.early)
    assert two.status_code == 200
    seen = two.json()
    assert seen["counts"]["anotherTime"] == 2
    marks = invitee(seen, mark)

    accepted = await as_(
        craig,
        "post",
        f"/cinema-trips/{trip['id']}/move",
        {
            "revision": 1,
            "showingId": str(programme.tuesday.id),
            "fromProfileId": str(mark.id),
            "fromReplyRevision": marks["replyRevision"],
        },
    )
    assert accepted.status_code == 200, accepted.text
    moved = accepted.json()
    assert moved["revision"] == 2 and moved["movedAtUtc"] is not None
    assert moved["showing"]["showingId"] == str(programme.tuesday.id)
    assert moved["showing"]["venueName"] == "Cineworld Glasgow Silverburn"
    assert moved["showing"]["startsAtUtc"].startswith("2026-11-10T20:00:00")
    # Its suggester picked the time, so is going; the other suggester is asked again.
    assert invitee(moved, mark)["reply"] == "going"
    assert invitee(moved, alex)["reply"] == "invited"
    assert invitee(moved, alex)["suggestion"] is None

    rows = await outbox(db, trip)
    assert pushed(rows, mark, "change") == [
        (
            f"{craig.display_name} accepted your time",
            f"Wild Horse Nine, {MOVED_TO}. You're down as going.",
        )
    ]
    assert pushed(rows, alex, "change") == [
        (
            "Cinema trip moved: Wild Horse Nine",
            f"Now {MOVED_TO}, {mark.display_name}'s suggestion. Going or not?",
        )
    ]
    assert pushed(rows, craig, "change") == []
    changes = {n.dedupe_key for n in rows if n.dedupe_key.startswith("cinema-trip-change:")}
    assert changes == {f"cinema-trip-change:{trip['id']}:2:{p.id}" for p in (mark, alex)}

    # The same accept again, its answer lost: nothing moves, nobody is told twice.
    again = await as_(
        craig,
        "post",
        f"/cinema-trips/{trip['id']}/move",
        {
            "revision": 1,
            "showingId": str(programme.tuesday.id),
            "fromProfileId": str(mark.id),
            "fromReplyRevision": marks["replyRevision"],
        },
    )
    assert again.status_code == 200 and again.json()["revision"] == 2
    assert len(await outbox(db, trip)) == len(rows)
    # A reply made against the old time is refused rather than applied to the new one.
    stale = await answer(as_, alex, trip, "going", revision=1)
    assert (stale.status_code, stale.json()["detail"]) == (
        409,
        "The trip has moved. Check the new time and reply again.",
    )


async def test_a_suggestion_changed_or_withdrawn_since_it_was_shown_cannot_be_accepted(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    shown = invitee((await answer(as_, mark, trip, "anotherTime", programme.tuesday)).json(), mark)
    assert (await answer(as_, mark, trip, "going")).status_code == 200
    changed = await as_(
        craig,
        "post",
        f"/cinema-trips/{trip['id']}/move",
        {
            "revision": 1,
            "showingId": str(programme.tuesday.id),
            "fromProfileId": str(mark.id),
            "fromReplyRevision": shown["replyRevision"],
        },
    )
    assert (changed.status_code, changed.json()["detail"]) == (
        409,
        f"{mark.display_name} changed their reply",
    )

    again = invitee((await answer(as_, mark, trip, "anotherTime", programme.tuesday)).json(), mark)
    programme.tuesday.confirmation = "withdrawn"
    await db.flush()
    seen = (await as_(craig, "get", f"/cinema-trips/{trip['id']}")).json()
    assert invitee(seen, mark)["suggestion"]["flag"] == "withdrawn"
    withdrawn = await as_(
        craig,
        "post",
        f"/cinema-trips/{trip['id']}/move",
        {
            "revision": 1,
            "showingId": str(programme.tuesday.id),
            "fromProfileId": str(mark.id),
            "fromReplyRevision": again["replyRevision"],
        },
    )
    assert (withdrawn.status_code, withdrawn.json()["detail"]) == (
        409,
        "That time is no longer listed",
    )
    stored = await db.get(CinemaTrip, uuid.UUID(trip["id"]))
    assert stored is not None and stored.revision == 1


async def test_keep_this_time_turns_a_suggestion_down_and_tells_its_suggester(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    shown = invitee((await answer(as_, mark, trip, "anotherTime", programme.tuesday)).json(), mark)
    body = {"profileId": str(mark.id), "replyRevision": shown["replyRevision"]}
    refused = await as_(mark, "post", f"/cinema-trips/{trip['id']}/keep", body)
    assert (refused.status_code, refused.json()["detail"]) == (
        403,
        f"Only {craig.display_name} can change this trip",
    )
    kept = await as_(craig, "post", f"/cinema-trips/{trip['id']}/keep", body)
    assert kept.status_code == 200, kept.text
    assert invitee(kept.json(), mark)["reply"] == "invited"
    assert invitee(kept.json(), mark)["suggestion"] is None
    assert kept.json()["revision"] == 1
    assert pushed(await outbox(db, trip), mark, "keep") == [
        (f"{craig.display_name} is keeping the original time", f"{LINE} Going or not?")
    ]
    # Pressed again, its answer lost: no change, no second push.
    count = len(await outbox(db, trip))
    again = await as_(craig, "post", f"/cinema-trips/{trip['id']}/keep", body)
    assert again.status_code == 200 and len(await outbox(db, trip)) == count
    assert (await as_(craig, "get", "/needs-you")).json()["trips"] == []


async def test_the_proposer_moves_the_trip_to_a_time_of_their_own(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile, alex: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark, alex)
    assert (await answer(as_, mark, trip, "going")).status_code == 200
    by_invitee = await as_(
        mark,
        "post",
        f"/cinema-trips/{trip['id']}/move",
        {"revision": 1, "showingId": str(programme.tuesday.id)},
    )
    assert by_invitee.status_code == 403
    same = await as_(
        craig,
        "post",
        f"/cinema-trips/{trip['id']}/move",
        {"revision": 1, "showingId": str(programme.monday.id)},
    )
    assert (same.status_code, same.json()["detail"]) == (422, "That's already the trip's time")
    moved = await as_(
        craig,
        "post",
        f"/cinema-trips/{trip['id']}/move",
        {"revision": 1, "showingId": str(programme.tuesday.id)},
    )
    assert moved.status_code == 200, moved.text
    assert {i["reply"] for i in moved.json()["invitees"]} == {"invited"}
    rows = await outbox(db, trip)
    for who in (mark, alex):
        assert pushed(rows, who, "change") == [
            (
                "Cinema trip moved: Wild Horse Nine",
                f"{craig.display_name} moved it to {MOVED_TO}. Going or not?",
            )
        ]
    assert to(rows, craig) == [(f"{mark.display_name} is going", f"{LINE} 2 of 3 going.")]


async def test_inviting_more_people_later_invites_only_them(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile, alex: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    assert (await answer(as_, mark, trip, "going")).status_code == 200
    more = await as_(
        craig,
        "post",
        f"/cinema-trips/{trip['id']}/invitees",
        {"profileIds": [str(alex.id), str(mark.id)]},
    )
    assert more.status_code == 200, more.text
    assert invitee(more.json(), alex)["reply"] == "invited"
    assert invitee(more.json(), mark)["reply"] == "going"
    again = await as_(
        craig, "post", f"/cinema-trips/{trip['id']}/invitees", {"profileIds": [str(alex.id)]}
    )
    assert again.status_code == 200
    rows = await outbox(db, trip)
    # One invitation each, Mark's from the proposal and Alex's from the later invite, and none
    # twice. Both are written at the same fixed instant, so their order is not a fact to test.
    invites = [n.dedupe_key for n in rows if (n.dedupe_key or "").startswith("cinema-trip-invite:")]
    assert sorted(invites) == sorted(
        f"cinema-trip-invite:{trip['id']}:{person.id}" for person in (mark, alex)
    )
    nobody = await as_(craig, "post", f"/cinema-trips/{trip['id']}/invitees", {"profileIds": []})
    assert (nobody.status_code, nobody.json()["detail"]) == (422, "Pick at least one person")


async def test_a_cancelled_trip_is_frozen_and_everyone_not_saying_no_is_told(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile, alex: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark, alex)
    assert (await answer(as_, mark, trip, "going")).status_code == 200
    assert (await answer(as_, alex, trip, "notGoing")).status_code == 200
    cancelled = await as_(craig, "post", f"/cinema-trips/{trip['id']}/cancel", {})
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["showing"]["flag"] is None
    rows = await outbox(db, trip)
    assert pushed(rows, mark, "cancel") == [
        (
            "Cinema trip cancelled",
            f"{craig.display_name} cancelled Wild Horse Nine on Mon 9 Nov at 20:10, "
            "ODEON Glasgow Quay.",
        )
    ]
    assert pushed(rows, alex, "cancel") == []
    # A reply after the cancel is refused; the same reply again changes nothing.
    late = await answer(as_, alex, trip, "going")
    assert (late.status_code, late.json()["detail"]) == (
        409,
        f"{craig.display_name} cancelled this trip",
    )
    assert (await answer(as_, mark, trip, "going")).status_code == 200
    again = await as_(craig, "post", f"/cinema-trips/{trip['id']}/cancel", {})
    assert again.status_code == 200 and len(await outbox(db, trip)) == len(rows)
    listed = (await as_(mark, "get", "/cinema-trips")).json()
    assert listed["upcoming"] == [] and [t["id"] for t in listed["past"]] == [trip["id"]]
    assert (await as_(mark, "get", "/needs-you")).json()["nextTrip"] is None


async def test_a_trip_whose_showing_has_started_is_past_and_frozen(
    db: AsyncSession,
    as_: Call,
    programme: Programme,
    craig: Profile,
    mark: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    later = datetime(2026, 11, 9, 20, 30)
    for module in (trips_router, needs_you_router, cinema_films):
        monkeypatch.setattr(module, "utcnow", lambda: later)
    seen = (await as_(mark, "get", f"/cinema-trips/{trip['id']}")).json()
    assert seen["status"] == "past" and seen["showing"]["flag"] is None
    late = await answer(as_, mark, trip, "going")
    assert (late.status_code, late.json()["detail"]) == (409, "This showing has started")
    assert (await as_(craig, "post", f"/cinema-trips/{trip['id']}/cancel", {})).status_code == 409
    assert (await as_(mark, "get", "/needs-you")).json()["trips"] == []


# ---------------------------------------------------------------------------
# The showing: snapshot, flag and ticket link
# ---------------------------------------------------------------------------


async def test_a_showing_the_cinema_withdraws_or_cancels_is_flagged_from_the_live_row(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)

    async def seen(who: Profile = craig) -> dict[str, Any]:
        return (await as_(who, "get", f"/cinema-trips/{trip['id']}")).json()["showing"]

    async def needs(who: Profile = craig) -> list[tuple[str, str | None]]:
        items = (await as_(who, "get", "/needs-you")).json()["trips"]
        return [(n["kind"], n["flag"]) for n in items]

    assert (await seen())["live"]["bookingUrl"] and await needs() == []
    for confirmation, expected in (("withdrawn", "withdrawn"), ("cancelled", "cancelled")):
        programme.monday.confirmation = confirmation
        await db.flush()
        showing = await seen()
        assert showing["flag"] == expected and showing["live"] is None
        assert showing["venueName"] == "ODEON Glasgow Quay"  # still the snapshot
        assert await needs() == [("tripWithdrawn", expected)]
        assert await needs(mark) == [("tripInvite", None)]
    programme.monday.confirmation = "unconfirmed"
    await db.flush()
    showing = await seen()
    assert showing["flag"] == "unconfirmed" and showing["live"]["bookingUrl"] is None
    assert await needs() == []
    # Listed again: the flag clears by itself.
    programme.monday.confirmation = "confirmed"
    await db.flush()
    assert (await seen())["flag"] is None
    # The same row moved to another time no longer lists the trip's time, and its ticket link
    # would book the other time.
    programme.monday.starts_utc = datetime(2026, 11, 9, 21, 0)
    await db.flush()
    assert (await seen())["flag"] == "withdrawn" and (await seen())["live"] is None


async def test_a_trip_still_reads_from_its_snapshot_after_the_clean_up_deletes_its_showing(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    await db.execute(
        text("DELETE FROM cinema_screenings WHERE id = :id"), {"id": programme.monday.id}
    )
    db.expunge_all()
    showing = (await as_(mark, "get", f"/cinema-trips/{trip['id']}")).json()["showing"]
    assert showing["showingId"] is None
    assert (showing["venueName"], showing["startsAtUtc"][:16]) == (
        "ODEON Glasgow Quay",
        "2026-11-09T20:10",
    )
    assert showing["flag"] == "withdrawn" and showing["live"] is None


# ---------------------------------------------------------------------------
# Home: Needs you and the top slot
# ---------------------------------------------------------------------------


async def test_needs_you_shows_the_invitation_until_a_reply_then_home_shows_the_next_trip(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    needs = (await as_(mark, "get", "/needs-you")).json()
    [item] = needs["trips"]
    assert item["kind"] == "tripInvite" and item["tripId"] == trip["id"]
    assert (item["filmTitle"], item["venueName"], item["proposerName"]) == (
        "Wild Horse Nine",
        "ODEON Glasgow Quay",
        craig.display_name,
    )
    assert item["startsAtUtc"].startswith("2026-11-09T20:10:00")
    assert needs["nextTrip"] is None  # invited, not going
    assert (await as_(craig, "get", "/needs-you")).json()["nextTrip"]["withNames"] == []

    assert (await answer(as_, mark, trip, "going")).status_code == 200
    needs = (await as_(mark, "get", "/needs-you")).json()
    assert needs["trips"] == []
    assert needs["nextTrip"]["tripId"] == trip["id"]
    assert needs["nextTrip"]["withNames"] == [craig.display_name]
    assert (await as_(craig, "get", "/needs-you")).json()["nextTrip"]["withNames"] == [
        mark.display_name
    ]


async def test_the_movie_night_switch_off_leaves_suppressed_rows_and_the_invitation_on_home(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    preference = await get_or_create_preferences(db, mark.id)
    preference.movie_night_enabled = False
    await db.flush()
    trip = await propose(as_, craig, programme.monday, mark)
    [invite] = await outbox(db, trip)
    assert (invite.status, invite.suppressed_reason) == ("suppressed", "category_disabled")
    assert [n["kind"] for n in (await as_(mark, "get", "/needs-you")).json()["trips"]] == [
        "tripInvite"
    ]


# ---------------------------------------------------------------------------
# The morning reminder (#345, decision 2)
# ---------------------------------------------------------------------------


async def test_the_morning_reminder_goes_once_to_the_proposer_and_everyone_going(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile, alex: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark, alex)
    tomorrow = await propose(as_, craig, programme.tuesday, mark)
    assert (await answer(as_, mark, trip, "going")).status_code == 200
    assert (await answer(as_, alex, trip, "notGoing")).status_code == 200
    summary = await reminders.run_reminders(db, now=NOW, seed_seasons=False)
    assert summary.cinema_trips == 1
    again = await reminders.run_reminders(db, now=NOW, seed_seasons=False)
    assert again.cinema_trips == 1 and again.queued == 0
    sent = [n for n in await outbox(db, trip) if n.dedupe_key.startswith("cinema-trip-reminder:")]
    assert sorted((n.user_id, n.title, n.body) for n in sent) == sorted(
        [
            (
                craig.id,
                "Cinema today: Wild Horse Nine",
                f"20:10 at ODEON Glasgow Quay, with {mark.display_name}.",
            ),
            (
                mark.id,
                "Cinema today: Wild Horse Nine",
                f"20:10 at ODEON Glasgow Quay, with {craig.display_name}.",
            ),
        ]
    )
    assert {n.status for n in sent} == {"queued"}
    assert [n for n in await outbox(db, tomorrow) if "reminder" in n.dedupe_key] == []


async def test_a_reminder_quiet_hours_or_digest_would_hold_past_the_pass_is_written_too_late(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile, alex: Profile
) -> None:
    quiet = await get_or_create_preferences(db, craig.id)
    quiet.quiet_hours_start, quiet.quiet_hours_end = time(22, 0), time(9, 0)
    quiet.quiet_hours_timezone = "Europe/London"
    digest = await get_or_create_preferences(db, mark.id)
    digest.digest_mode, digest.digest_hour_local = True, 9
    off = await get_or_create_preferences(db, alex.id)
    off.movie_night_enabled = False
    await db.flush()
    trip = await propose(as_, craig, programme.monday, mark, alex)
    for who in (mark, alex):
        assert (await answer(as_, who, trip, "going")).status_code == 200
    await reminders.run_reminders(db, now=NOW, seed_seasons=False)
    sent = {
        n.user_id: (n.status, n.suppressed_reason)
        for n in await outbox(db, trip)
        if n.dedupe_key.startswith("cinema-trip-reminder:")
    }
    assert sent == {
        craig.id: ("suppressed", "too_late"),
        mark.id: ("suppressed", "too_late"),
        alex.id: ("suppressed", "category_disabled"),
    }


async def test_the_reminder_names_two_others_then_counts_and_says_the_cinema_withdrew_it(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile
) -> None:
    people = [await person(db, name) for name in ("Ann", "Ben", "Cat", "Dan")]
    trip = await propose(as_, craig, programme.monday, *people)
    for who in people:
        assert (await answer(as_, who, trip, "going")).status_code == 200
    programme.monday.confirmation = "withdrawn"
    await db.flush()
    await reminders.run_reminders(db, now=NOW, seed_seasons=False)
    [mine] = [
        n for n in await outbox(db, trip) if n.user_id == craig.id and "reminder" in n.dedupe_key
    ]
    first, second = sorted(p.display_name for p in people)[:2]
    assert mine.body == (
        f"20:10 at ODEON Glasgow Quay, with {first}, {second} and 2 others."
        " The cinema no longer lists this time; check before you go."
    )


async def test_someone_made_inactive_after_being_invited_is_told_nothing_more(
    db: AsyncSession, as_: Call, programme: Programme, craig: Profile, mark: Profile
) -> None:
    trip = await propose(as_, craig, programme.monday, mark)
    assert (await answer(as_, mark, trip, "going")).status_code == 200
    mark.is_active = False
    await db.flush()
    before = to(await outbox(db, trip), mark)
    await reminders.run_reminders(db, now=NOW, seed_seasons=False)
    assert (await as_(craig, "post", f"/cinema-trips/{trip['id']}/cancel", {})).status_code == 200
    assert to(await outbox(db, trip), mark) == before
    seen = (await as_(craig, "get", f"/cinema-trips/{trip['id']}")).json()
    assert invitee(seen, mark)["reply"] == "going"  # others still see their last reply


# ---------------------------------------------------------------------------
# The wording, and the migration
# ---------------------------------------------------------------------------


def test_the_push_wording_reads_times_formats_names_and_tallies_as_approved() -> None:
    monday = datetime(2026, 11, 9, 20, 10)
    tuesday = datetime(2026, 11, 10, 20, 0)
    assert words.when(monday, "Europe/London") == "Mon 9 Nov at 20:10"
    assert words.when(tuesday, "Europe/London", ["IMAX"]) == "Tue 10 Nov at 20:00 IMAX"
    assert words.clock(tuesday, "Europe/London", ["Format.Projection.Digital"]) == "20:00"
    assert words.clock(tuesday, "Europe/London", ["Format.Projection.3D"]) == "20:00 3D"
    # British Summer Time: the cinema's own clock, not UTC.
    assert words.clock(datetime(2026, 7, 1, 19, 0), "Europe/London") == "20:00"
    assert words.names(["Mark"]) == "Mark"
    assert words.names(["Mark", "Alex"]) == "Mark and Alex"
    assert words.names(["Mark", "Alex", "Sam"]) == "Mark, Alex and 1 other"
    assert words.names(["Mark", "Alex", "Sam", "Jo"]) == "Mark, Alex and 2 others"
    assert words.tally(2, 3, invitees=2) == " 2 of 3 going."
    assert words.tally(2, 2, invitees=1) == ""
    assert len(words.title("x" * 300)) == words.TITLE_LIMIT


def _migration_072() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "migrations/versions/072_cinema_trips.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(step: Callable[[], None]) -> Callable[[Connection], None]:
    def run(sync_conn: Connection) -> None:
        with Operations.context(MigrationContext.configure(sync_conn)):
            step()

    return run


async def test_072_will_not_drop_a_trip_and_round_trips_when_there_is_none(
    db_conn: AsyncConnection,
) -> None:
    migration = _migration_072()
    proposer = uuid.uuid4()
    await db_conn.execute(
        text("INSERT INTO profiles (id, display_name, role) VALUES (:id, :name, 'viewer')"),
        {"id": proposer, "name": f"ac5-{proposer.hex[:8]}"},
    )
    await db_conn.execute(
        text(
            "INSERT INTO cinema_trips (id, client_request_id, proposer_id, film_key, film_title,"
            " venue_name, starts_utc) VALUES (:id, :request, :proposer, 'tmdb-891621',"
            " 'Wild Horse Nine', 'ODEON Glasgow Quay', '2026-11-09 20:10')"
        ),
        {"id": uuid.uuid4(), "request": uuid.uuid4(), "proposer": proposer},
    )
    with pytest.raises(Exception, match="downgrade 072 requires owner review"):
        async with db_conn.begin_nested():
            await db_conn.run_sync(_run(migration.downgrade))
    await db_conn.execute(
        text("DELETE FROM cinema_trips WHERE proposer_id = :id"), {"id": proposer}
    )
    await db_conn.run_sync(_run(migration.downgrade))
    gone = await db_conn.scalar(text("SELECT to_regclass('cinema_trips')"))
    assert gone is None
    await db_conn.run_sync(_run(migration.upgrade))
    names = (
        (
            await db_conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE tablename IN ('cinema_trips',"
                    " 'cinema_trip_invitees') ORDER BY 1"
                )
            )
        )
        .scalars()
        .all()
    )
    assert set(names) >= {
        "ix_cinema_trips_proposer",
        "ix_cinema_trips_upcoming",
        "ix_cinema_trips_film",
        "ix_cinema_trips_showing",
        "ix_cinema_trip_invitees_profile",
        "ix_cinema_trip_invitees_suggested",
        "uq_cinema_trip_request",
        "uq_cinema_trip_invitee",
    }


async def test_the_tables_hold_their_shape_whatever_the_api_does(db: AsyncSession) -> None:
    """The checks in §1: a reply and its time agree, a suggestion is whole, a move is counted."""
    proposer = await person(db, "Craig")
    guest = await person(db, "Mark")
    row = CinemaTrip(
        id=uuid.uuid4(),
        client_request_id=uuid.uuid4(),
        proposer_id=proposer.id,
        film_key="tmdb-891621",
        film_title="Wild Horse Nine",
        venue_name="ODEON Glasgow Quay",
        starts_utc=datetime(2026, 11, 9, 20, 10),
    )
    db.add(row)
    await db.flush()
    bad = [
        "UPDATE cinema_trips SET film_key = 'tmdb-603; drop' WHERE id = :trip",
        "UPDATE cinema_trips SET revision = 2 WHERE id = :trip",
        "UPDATE cinema_trips SET ends_utc = starts_utc WHERE id = :trip",
        "INSERT INTO cinema_trip_invitees (id, trip_id, profile_id, reply)"
        " VALUES (gen_random_uuid(), :trip, :guest, 'going')",
        "INSERT INTO cinema_trip_invitees (id, trip_id, profile_id, reply, replied_at_utc)"
        " VALUES (gen_random_uuid(), :trip, :guest, 'another_time', now())",
        "INSERT INTO cinema_trip_invitees (id, trip_id, profile_id, reply)"
        " VALUES (gen_random_uuid(), :trip, :guest, 'maybe')",
    ]
    for statement in bad:
        with pytest.raises(Exception, match="violates check constraint"):
            async with db.begin_nested():
                await db.execute(text(statement), {"trip": row.id, "guest": guest.id})
    invitee_row = CinemaTripInvitee(id=uuid.uuid4(), trip_id=row.id, profile_id=guest.id)
    db.add(invitee_row)
    await db.flush()
    assert (invitee_row.reply, invitee_row.reply_revision) == ("invited", 0)
