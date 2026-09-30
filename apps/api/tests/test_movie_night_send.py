"""Batch T4, snag 11 — send a movie night to the other person, and push it now.

**What this proves:** one tap puts the other person in the night and queues one push per
person per night that opens *this* night; their settings and quiet hours still apply; and
the push goes out at once, where until 23 Sep it waited for a job that never ran — which
also held back "It's a match".

**What it does not:** a push arriving on a phone. That needs two real devices and is the
owner's check, as Batch 11's 6.2 has been since 10 Sep.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.database import get_db
from src.main import app
from src.models.movie import Movie
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    MovieNightSuggestion,
    new_invite_token,
)
from src.models.notification import Notification, PushSubscription
from src.models.profile import Profile, UserRole
from src.routers.movie_night import _invite_body
from src.services.movie_night.sessions import invite_key
from src.services.notifications import (
    DeliveryOutcome,
    DeliveryResult,
    get_or_create_preferences,
)
from src.services.push_transport import set_push_sender

pytestmark = pytest.mark.asyncio


class RecordingSender:
    """A push service that records instead of sending."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, subscription: PushSubscription, payload: bytes) -> DeliveryResult:
        del payload
        self.sent.append(subscription.endpoint)
        return DeliveryResult(DeliveryOutcome.delivered, 201)


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def pushes() -> AsyncIterator[RecordingSender]:
    recorder = RecordingSender()
    set_push_sender(recorder)
    try:
        yield recorder
    finally:
        set_push_sender(None)


async def _person(db: AsyncSession, name: str) -> Profile:
    # A PIN hash, because only someone who can sign in can be sent a night. Not a real
    # hash: nothing here signs in.
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"{name} {uuid.uuid4().hex[:6]}",
        role=UserRole.viewer,
        pin_hash="test-pin-hash",
    )
    db.add(profile)
    await db.flush()
    return profile


async def _phone(db: AsyncSession, person: Profile) -> str:
    endpoint = f"https://push.example.com/{uuid.uuid4().hex}"
    db.add(
        PushSubscription(
            id=uuid.uuid4(), user_id=person.id, endpoint=endpoint, p256dh="p" * 87, auth="a" * 22
        )
    )
    await db.flush()
    return endpoint


async def _night(db: AsyncSession, *people: Profile) -> MovieNightSession:
    night = MovieNightSession(
        id=uuid.uuid4(), created_by=people[0].id, invite_token=new_invite_token(), filters={}
    )
    db.add(night)
    await db.flush()
    for person in people:
        db.add(MovieNightParticipant(id=uuid.uuid4(), session_id=night.id, user_id=person.id))
    await db.flush()
    return night


def _as(db: AsyncSession, person: Profile) -> AsyncClient:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return person

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


async def _invites(
    db: AsyncSession, night: MovieNightSession, person: Profile
) -> list[Notification]:
    return list(
        (
            await db.execute(
                select(Notification).where(
                    Notification.dedupe_key == invite_key(night.id, person.id)
                )
            )
        ).scalars()
    )


async def test_one_tap_puts_them_in_the_night_and_pushes_it_now(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    marks_phone = await _phone(db, mark)
    night = await _night(db, craig)

    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/send", json={})

    assert response.status_code == 200, response.text
    body = response.json()
    invited = {person["id"]: person["invited"] for person in body["people"]}
    assert invited[str(craig.id)] is False
    assert invited[str(mark.id)] is True
    assert str(mark.id) not in {person["id"] for person in body["invitable"]}
    assert pushes.sent == [marks_phone]

    (invite,) = await _invites(db, night, mark)
    assert invite.url == f"/movie-night/{night.id}"
    assert invite.status == "sent"

    async with _as(db, mark) as client:
        listed = (await client.get("/api/v1/movie-night")).json()
    assert str(night.id) in {session["id"] for session in listed["items"]}


async def test_the_invite_names_the_shortlist_not_a_deck_to_swipe(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    """Batch V3: a night is its shortlist now (#228), so the push says so — and counts right."""
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    await _phone(db, mark)
    night = await _night(db, craig)
    for tmdb_id, title in ((11050, "The Card Player"), (8321, "In Bruges")):
        db.add(
            MovieNightSuggestion(
                id=uuid.uuid4(),
                session_id=night.id,
                suggested_by=craig.id,
                tmdb_id=tmdb_id,
                title=title,
            )
        )
    await db.flush()

    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/send", json={})

    assert response.status_code == 200, response.text
    (invite,) = await _invites(db, night, mark)
    assert invite.body == "2 films on the shortlist. Tap to open it."
    assert "swipe" not in invite.body


async def test_the_invite_says_one_film_not_one_films() -> None:
    assert _invite_body(1) == "1 film on the shortlist. Tap to open it."
    assert _invite_body(0) == "Tap to open it."


async def test_sending_twice_does_not_buzz_a_phone_twice(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    await _phone(db, mark)
    night = await _night(db, craig)

    async with _as(db, craig) as client:
        await client.post(f"/api/v1/movie-night/{night.id}/send", json={})
        again = await client.post(
            f"/api/v1/movie-night/{night.id}/send", json={"userIds": [str(mark.id)]}
        )

    assert again.status_code == 200
    assert len(pushes.sent) == 1
    assert len(await _invites(db, night, mark)) == 1


async def test_quiet_hours_hold_the_push_for_the_morning(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    await _phone(db, mark)
    now = utcnow()
    preference = await get_or_create_preferences(db, mark.id)
    preference.quiet_hours_timezone = "UTC"
    preference.quiet_hours_start = (now - timedelta(hours=1)).time().replace(microsecond=0)
    preference.quiet_hours_end = (now + timedelta(hours=1)).time().replace(microsecond=0)
    await db.flush()
    night = await _night(db, craig)

    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/send", json={})

    assert response.status_code == 200
    assert pushes.sent == []
    (invite,) = await _invites(db, night, mark)
    assert invite.status == "queued"
    assert invite.deliver_after_utc is not None and invite.deliver_after_utc > now


async def test_a_night_that_has_ended_cannot_be_sent(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    night = await _night(db, craig)
    night.status = "ended"
    await db.flush()

    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/send", json={})

    assert response.status_code == 409
    assert pushes.sent == []
    assert await _invites(db, night, mark) == []


async def test_only_people_in_the_night_can_send_it(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    night = await _night(db, craig)

    async with _as(db, mark) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/send", json={})

    assert response.status_code == 404
    assert pushes.sent == []


async def test_a_match_is_pushed_to_both_at_once(db: AsyncSession, pushes: RecordingSender) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    craigs_phone, marks_phone = await _phone(db, craig), await _phone(db, mark)
    night = await _night(db, craig, mark)
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title="Sofa Test",
        original_title="Sofa Test",
        media_type="film",
    )
    db.add(film)
    await db.flush()
    suggestion = MovieNightSuggestion(
        id=uuid.uuid4(),
        session_id=night.id,
        suggested_by=craig.id,
        movie_id=film.id,
        title="Sofa Test",
    )
    db.add(suggestion)
    await db.flush()

    async with _as(db, craig) as client:
        first = await client.post(
            f"/api/v1/movie-night/{night.id}/votes",
            json={"suggestionId": str(suggestion.id), "liked": True},
        )
    assert first.json()["match"] is None
    assert pushes.sent == []

    async with _as(db, mark) as client:
        second = await client.post(
            f"/api/v1/movie-night/{night.id}/votes",
            json={"suggestionId": str(suggestion.id), "liked": True},
        )

    assert second.json()["match"]["title"] == "Sofa Test"
    assert sorted(pushes.sent) == sorted([craigs_phone, marks_phone])


async def test_the_invite_key_names_the_night_and_the_person() -> None:
    night, person = uuid.uuid4(), uuid.uuid4()
    assert invite_key(night, person) == f"movie-night-invite:{night}:{person}"


async def test_someone_who_cannot_sign_in_is_not_sent_a_night(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig = await _person(db, "Craig")
    unset = Profile(
        id=uuid.uuid4(), display_name=f"No PIN {uuid.uuid4().hex[:6]}", role=UserRole.viewer
    )
    db.add(unset)
    await db.flush()
    night = await _night(db, craig)

    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/send", json={})

    body = response.json()
    assert str(unset.id) not in {person["id"] for person in body["people"]}
    assert str(unset.id) not in {person["id"] for person in body["invitable"]}
