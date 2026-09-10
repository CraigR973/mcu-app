"""§8.3's sessions and §8.4's matches — Batch 35.

**What is proved here, and what is not.** Match detection, the invite flow, vote
idempotence and the notification are all real, against real Postgres. The `LISTEN`
connection is *not* exercised: the test session runs inside a transaction that is rolled
back, and `NOTIFY` only fires on commit — so a listener would correctly see nothing. The
broadcaster's own fan-out is tested directly instead, without a database.

**§8.4's acceptance is "both users swiping on the same film triggers a match
notification".** The match and the notification row are proved below; the *push arriving on
a device* is the part that needs a device, and is deferred with 6.2 and 5.6.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.movie import Movie
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    MovieNightVote,
    new_invite_token,
)
from src.models.notification import Notification
from src.models.profile import Profile, UserRole
from src.services.movie_night.realtime import MovieNightBroadcaster, encode
from src.services.movie_night.sessions import candidate_movies, detect_match, record_vote

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _profile(db: AsyncSession, role: UserRole = UserRole.admin) -> Profile:
    profile = Profile(id=uuid.uuid4(), display_name=f"P{uuid.uuid4().hex[:8]}", role=role)
    db.add(profile)
    await db.flush()
    return profile


async def _movie(db: AsyncSession, title: str, *, year: int | None = 2010) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
    )
    db.add(movie)
    await db.flush()
    return movie


async def _session(
    db: AsyncSession, *people: Profile, filters: dict | None = None
) -> MovieNightSession:
    session = MovieNightSession(
        id=uuid.uuid4(),
        created_by=people[0].id,
        invite_token=new_invite_token(),
        filters=filters or {},
    )
    db.add(session)
    await db.flush()
    for person in people:
        db.add(MovieNightParticipant(id=uuid.uuid4(), session_id=session.id, user_id=person.id))
    await db.flush()
    return session


class TestMatching:
    """§8.4 — *"both users swiping on the same film triggers a match notification"*."""

    async def test_both_liking_the_same_film_is_a_match(self, db: AsyncSession) -> None:
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        first = await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=True)
        second = await record_vote(db, session=session, user=mark, movie_id=heat.id, liked=True)

        assert first is None, "one like is not a match"
        assert second is not None
        assert second.title == "Heat"

    async def test_one_liking_and_one_passing_is_not_a_match(self, db: AsyncSession) -> None:
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=True)
        result = await record_vote(db, session=session, user=mark, movie_id=heat.id, liked=False)

        assert result is None

    async def test_a_match_is_announced_once(self, db: AsyncSession) -> None:
        """`announced_at_utc` is the only derived state kept, and this is why."""
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")
        await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=True)
        await record_vote(db, session=session, user=mark, movie_id=heat.id, liked=True)

        again = await detect_match(db, session=session, movie_id=heat.id)

        assert again is None

    async def test_swiping_alone_is_never_a_match(self, db: AsyncSession) -> None:
        """Announcing one would be telling somebody they agree with themselves."""
        craig = await _profile(db)
        session = await _session(db, craig)
        heat = await _movie(db, "Heat")

        result = await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=True)

        assert result is None

    async def test_a_match_notifies_both_people(self, db: AsyncSession) -> None:
        """§8.4's "notification to both", through Batch 11's outbox."""
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=True)
        await record_vote(db, session=session, user=mark, movie_id=heat.id, liked=True)

        rows = list(
            (await db.execute(select(Notification).where(Notification.category == "movie_night")))
            .scalars()
            .all()
        )
        recipients = {row.user_id for row in rows}
        assert {craig.id, mark.id}.issubset(recipients)
        assert all("Heat" in row.title for row in rows)

    async def test_changing_your_mind_replaces_the_vote(self, db: AsyncSession) -> None:
        """Swiping twice is not two votes — which for matching would be a match alone."""
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=False)
        await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=True)

        votes = list(
            (await db.execute(select(MovieNightVote).where(MovieNightVote.user_id == craig.id)))
            .scalars()
            .all()
        )
        assert len(votes) == 1
        assert votes[0].liked is True

    async def test_a_match_needs_everyone_not_just_two(self, db: AsyncSession) -> None:
        """The rule is "everyone who is here", which costs nothing and does not bake in 2."""
        craig = await _profile(db)
        mark = await _profile(db, UserRole.viewer)
        third = await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark, third)
        heat = await _movie(db, "Heat")

        await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=True)
        two_of_three = await record_vote(
            db, session=session, user=mark, movie_id=heat.id, liked=True
        )
        all_three = await record_vote(db, session=session, user=third, movie_id=heat.id, liked=True)

        assert two_of_three is None
        assert all_three is not None


class TestCandidates:
    async def test_a_film_you_voted_on_leaves_your_deck(self, db: AsyncSession) -> None:
        craig = await _profile(db)
        session = await _session(db, craig)
        heat = await _movie(db, "Heat")
        await _movie(db, "Nope")

        await record_vote(db, session=session, user=craig, movie_id=heat.id, liked=False)
        deck = await candidate_movies(db, session=session, user=craig)

        assert heat.id not in {movie.id for movie in deck}

    async def test_the_other_persons_votes_do_not_change_your_deck(self, db: AsyncSession) -> None:
        """**A card vanishing because they swiped it would leak their vote.**"""
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        await record_vote(db, session=session, user=mark, movie_id=heat.id, liked=True)
        deck = await candidate_movies(db, session=session, user=craig)

        assert heat.id in {movie.id for movie in deck}

    async def test_the_sessions_filters_narrow_the_deck(self, db: AsyncSession) -> None:
        """§8.3's "session creation with filters", doing something."""
        craig = await _profile(db)
        session = await _session(db, craig, filters={"decadeFrom": 2000, "decadeTo": 2009})
        await _movie(db, "Old Film", year=1975)
        modern = await _movie(db, "Noughties Film", year=2005)

        deck = await candidate_movies(db, session=session, user=craig)

        assert {movie.id for movie in deck} == {modern.id}


class TestBroadcaster:
    """The fan-out half of #113, without a database.

    `NOTIFY` fires on commit and the test session is rolled back, so a real listener would
    correctly see nothing — the dispatch is therefore driven directly.
    """

    async def test_an_event_reaches_the_subscribers_of_its_session(self) -> None:
        broadcaster = MovieNightBroadcaster()
        # Subscribe without opening a connection: `_ensure_listening` is what would, and
        # the point here is the routing rather than the socket.
        queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        broadcaster._subscribers["abc"] = {queue}

        broadcaster._dispatch(None, 0, "mcu_movie_night", encode("abc", "match", {"title": "Heat"}))  # type: ignore[arg-type]

        assert queue.get_nowait()["title"] == "Heat"

    async def test_an_event_does_not_reach_another_session(self) -> None:
        broadcaster = MovieNightBroadcaster()
        mine: asyncio.Queue = asyncio.Queue(maxsize=10)
        broadcaster._subscribers["mine"] = {mine}

        broadcaster._dispatch(None, 0, "mcu_movie_night", encode("theirs", "match", {}))  # type: ignore[arg-type]

        assert mine.empty()

    async def test_a_backgrounded_tab_cannot_stall_everybody_else(self) -> None:
        """A full queue drops its oldest rather than blocking the listener."""
        broadcaster = MovieNightBroadcaster()
        queue: asyncio.Queue = asyncio.Queue(maxsize=2)
        broadcaster._subscribers["abc"] = {queue}

        for index in range(5):
            broadcaster._dispatch(  # type: ignore[arg-type]
                None, 0, "mcu_movie_night", encode("abc", "vote", {"n": index})
            )

        assert queue.qsize() == 2
        assert queue.get_nowait()["n"] == 3, "the oldest went, the newest stayed"

    async def test_a_malformed_payload_does_not_kill_the_listener(self) -> None:
        """asyncpg swallows an exception here and carries on delivering nothing."""
        broadcaster = MovieNightBroadcaster()
        queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        broadcaster._subscribers["abc"] = {queue}

        broadcaster._dispatch(None, 0, "mcu_movie_night", "not json at all")  # type: ignore[arg-type]

        assert queue.empty()

    async def test_it_holds_no_connection_when_nobody_is_watching(self) -> None:
        """#113's constraint: a `LISTEN` connection is held only while it is needed."""
        broadcaster = MovieNightBroadcaster()

        assert broadcaster.listening is False

    def test_the_payload_names_its_session(self) -> None:
        import json as json_module

        payload = json_module.loads(encode("s1", "match", {"title": "Heat"}))

        assert payload["sessionId"] == "s1"
        assert payload["kind"] == "match"
        assert payload["title"] == "Heat"
