"""Two invitees replying at the same moment both land, and each push counts the other — AC5.

#345 §2: every write on a trip first locks the trip's row (`SELECT … FOR UPDATE`), so writes to
one trip run one after another. Without the lock both replies still land (they are different
rows), but each transaction counts only its own uncommitted Going, so the proposer is told
"2 of 3 going." twice and never "3 of 3".

**This needs real commits on two connections**, so it cannot live in `test_cinema_trips.py`,
whose session is rolled back. The rows are its own (three throwaway profiles and one cinema
film; deleting them cascades to their trips, replies, showings and notifications), removed in
``finally``. Half the rounds widen the window: a pause between a reply's write and its tally.

Skipped when ``DATABASE_URL`` is unset. CI always sets it and applies migrations first.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.clock import utcnow
from src.config import Settings
from src.models.cinema import CinemaFilm, CinemaScreening
from src.models.cinema_trip import CinemaTrip, CinemaTripInvitee
from src.models.notification import Notification
from src.models.profile import Profile, UserRole
from src.schemas.cinema_trips import ProposeTrip, ReplyToTrip
from src.services.cinema_trips import trips
from src.services.cinemas.venues import BY_SLUG
from tests.conftest import DATABASE_URL

#: Rounds at natural timing, and rounds with the window held open.
ROUNDS = 10
#: Long enough that the second reply is always written inside the first one's window.
PAUSE_SECONDS = 0.05
TMDB = 9_105_005


@dataclass
class World:
    craig: uuid.UUID
    mark: uuid.UUID
    alex: uuid.UUID
    showing: uuid.UUID


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set — Postgres-backed tests skipped")
    built = create_async_engine(Settings(database_url=DATABASE_URL).database_url)
    try:
        yield built
    finally:
        await built.dispose()


@pytest_asyncio.fixture
async def world(engine: AsyncEngine) -> AsyncIterator[World]:
    """Three throwaway people and one showing of one film, removed afterwards."""
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    ids = [uuid.uuid4() for _ in range(3)]
    venue = BY_SLUG["odeon-glasgow-quay"]
    film_id = uuid.uuid4()
    # Two days on, in the stored fortnight whatever the real clock says.
    day = (utcnow() + timedelta(days=2)).date()
    starts = datetime(day.year, day.month, day.day, 20, 10)
    async with sessionmaker() as db:
        for person in ids:
            db.add(
                Profile(
                    id=person,
                    display_name=f"ac5-{person.hex[:12]}",
                    role=UserRole.viewer,
                    pin_hash="test-pin-hash",
                )
            )
        db.add(
            CinemaFilm(
                id=film_id,
                source=venue.source,
                source_key=f"ac5-race:{film_id}",
                title="Wild Horse Nine",
                identity_status="verified",
                evidence={"tmdbId": TMDB},
            )
        )
        await db.flush()
        showing = CinemaScreening(
            id=uuid.uuid4(),
            venue_id=venue.id,
            film_id=film_id,
            source_key=f"ac5-race:{uuid.uuid4()}",
            identity_strength="opaque",
            local_date=day,
            source_local_start=f"{day.isoformat()}T20:10:00",
            starts_utc=starts,
            formats=[],
            release_category="newRelease",
            category_evidence={},
            confirmation="confirmed",
        )
        db.add(showing)
        await db.commit()
    try:
        yield World(*ids, showing.id)
    finally:
        async with sessionmaker() as db:
            await db.execute(delete(Profile).where(Profile.id.in_(ids)))
            await db.execute(delete(CinemaFilm).where(CinemaFilm.id == film_id))
            await db.commit()


async def _trip(sessionmaker: async_sessionmaker[AsyncSession], world: World) -> uuid.UUID:
    """A committed trip from Craig to Mark and Alex."""
    async with sessionmaker() as db:
        craig = await db.get(Profile, world.craig)
        assert craig is not None
        trip, _ = await trips.propose(
            db,
            craig,
            ProposeTrip(
                clientRequestId=uuid.uuid4(),
                filmKey=f"tmdb-{TMDB}",
                showingId=world.showing,
                inviteeIds=[world.mark, world.alex],
            ),
            utcnow(),
        )
        await db.commit()
        return trip.id


async def _going(
    sessionmaker: async_sessionmaker[AsyncSession], trip_id: uuid.UUID, person: uuid.UUID
) -> None:
    """One phone's Going, as the reply endpoint makes it: its own session, then commit."""
    async with sessionmaker() as db:
        user = await db.get(Profile, person)
        assert user is not None
        await trips.reply(db, user, trip_id, ReplyToTrip(revision=1, reply="going"), utcnow())
        await db.commit()


async def test_two_replies_at_once_both_land_and_the_second_push_counts_the_first(
    engine: AsyncEngine, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    real_tally = trips._tally
    widen = False

    async def tally(db: AsyncSession, trip: CinemaTrip) -> str:
        # Between the reply's write and its count: the gap the race lives in.
        if widen:
            await asyncio.sleep(PAUSE_SECONDS)
        return await real_tally(db, trip)

    monkeypatch.setattr(trips, "_tally", tally)

    outcomes: list[str] = []
    for round_ in range(ROUNDS * 2):
        widen = round_ >= ROUNDS
        trip_id = await _trip(sessionmaker, world)
        await asyncio.gather(
            _going(sessionmaker, trip_id, world.mark),
            _going(sessionmaker, trip_id, world.alex),
        )
        async with sessionmaker() as db:
            replies = (
                await db.scalars(
                    select(CinemaTripInvitee.reply).where(CinemaTripInvitee.trip_id == trip_id)
                )
            ).all()
            told = (
                await db.scalars(
                    select(Notification.body).where(
                        Notification.user_id == world.craig,
                        Notification.dedupe_key.like(f"cinema-trip-reply:{trip_id}:%"),
                    )
                )
            ).all()
        tallies = sorted(body.rsplit(". ", 1)[-1] for body in told)
        outcomes.append(f"round {round_} ({'widened' if widen else 'natural'}): {tallies}")
        assert sorted(replies) == ["going", "going"], "\n".join(outcomes)
        assert tallies == ["2 of 3 going.", "3 of 3 going."], "\n".join(outcomes)
