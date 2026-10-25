"""Two likes cast at the same moment make exactly one match — Batch Z1 (`DECISIONS.md` #287).

Batch 38's WebKit run saw two votes, cast milliseconds apart, both miss the match: each
transaction ran `detect_match` seeing only its own uncommitted like. `record_vote` now holds
the night's row (`SELECT … FOR UPDATE`) until the vote commits, so the second voter waits and
then reads the first like.

**This needs real commits on two connections**, so it cannot live in `test_movie_night.py`,
whose session is rolled back: a race between two transactions needs two transactions. The
rows are its own (two throwaway profiles; deleting them cascades to their nights, votes and
notifications), removed in ``finally``.

Every night is cast twice at once, many times over. Half the nights widen the window: a
pause between the vote's write and the match check, the gap the race lives in. Without the
lock those nights end with no match at all, which is how this test was shown to bite.

Skipped when ``DATABASE_URL`` is unset. CI always sets it and applies migrations first.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import Settings
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    MovieNightSuggestion,
    MovieNightVote,
    new_invite_token,
)
from src.models.notification import Notification
from src.models.profile import Profile, UserRole
from src.services.movie_night import sessions as night
from tests.conftest import DATABASE_URL

#: Nights cast at natural timing, and nights with the window held open.
NIGHTS = 20
#: Long enough that the second vote is always written inside the first one's window.
PAUSE_SECONDS = 0.05


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
async def people(engine: AsyncEngine) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """Two throwaway people, removed afterwards with everything that hangs off them."""
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    ids = (uuid.uuid4(), uuid.uuid4())
    async with sessionmaker() as db:
        for person, role in zip(ids, (UserRole.admin, UserRole.viewer), strict=True):
            db.add(Profile(id=person, display_name=f"z1-{person.hex[:12]}", role=role))
        await db.commit()
    try:
        yield ids
    finally:
        async with sessionmaker() as db:
            await db.execute(delete(Profile).where(Profile.id.in_(ids)))
            await db.commit()


async def _night(
    sessionmaker: async_sessionmaker[AsyncSession], people: tuple[uuid.UUID, uuid.UUID]
) -> tuple[uuid.UUID, uuid.UUID]:
    """A committed night for both people, with one film on it nobody owns."""
    async with sessionmaker() as db:
        session = MovieNightSession(
            id=uuid.uuid4(),
            created_by=people[0],
            invite_token=new_invite_token(),
            filters={},
        )
        db.add(session)
        await db.flush()
        for person in people:
            db.add(MovieNightParticipant(id=uuid.uuid4(), session_id=session.id, user_id=person))
        await db.flush()
        creator = await db.get(Profile, people[0])
        assert creator is not None
        pick = await night.add_suggestion(
            db, session=session, user=creator, tmdb_id=1201, title="Rooftop Opera", year=2014
        )
        await db.commit()
        return session.id, pick.id


async def _like(
    sessionmaker: async_sessionmaker[AsyncSession],
    session_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    person: uuid.UUID,
) -> night.Match | None:
    """One phone's like, as the vote endpoint casts it: its own session, then commit."""
    async with sessionmaker() as db:
        session = await db.get(MovieNightSession, session_id)
        suggestion = await db.get(MovieNightSuggestion, suggestion_id)
        user = await db.get(Profile, person)
        assert session is not None and suggestion is not None and user is not None
        match = await night.record_vote(
            db, session=session, user=user, suggestion=suggestion, liked=True
        )
        await db.commit()
        return match


async def test_two_likes_at_once_always_make_exactly_one_match(
    engine: AsyncEngine,
    people: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    real_publish = night.publish
    widen = False
    announced: list[uuid.UUID] = []

    async def publish(db: AsyncSession, session_id: uuid.UUID, kind: str, data: dict) -> None:
        await real_publish(db, session_id, kind, data)
        if kind == "match":
            announced.append(session_id)
        # `record_vote` tells the room between writing the vote and checking for a match:
        # holding it here keeps both votes written and both checks still to come.
        if kind == "vote" and widen:
            await asyncio.sleep(PAUSE_SECONDS)

    monkeypatch.setattr(night, "publish", publish)

    outcomes: list[str] = []
    for round_ in range(NIGHTS * 2):
        widen = round_ >= NIGHTS
        session_id, suggestion_id = await _night(sessionmaker, people)
        results = await asyncio.gather(
            _like(sessionmaker, session_id, suggestion_id, people[0]),
            _like(sessionmaker, session_id, suggestion_id, people[1]),
        )

        async with sessionmaker() as db:
            stored = await db.get(MovieNightSession, session_id)
            votes = list(
                (
                    await db.execute(
                        select(MovieNightVote).where(MovieNightVote.session_id == session_id)
                    )
                ).scalars()
            )
            pushes = await db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.dedupe_key.like(f"movie-night-match:{session_id}:%"))
            )
        matches = sum(result is not None for result in results)
        outcomes.append(
            f"night {round_} ({'widened' if widen else 'natural'}): {matches} match(es), "
            f"{announced.count(session_id)} announcement(s), {pushes} push(es)"
        )
        assert stored is not None
        assert matches == 1, "\n".join(outcomes)
        assert announced.count(session_id) == 1, "\n".join(outcomes)
        assert pushes == 2, "\n".join(outcomes)
        assert stored.matched_suggestion_id == suggestion_id
        assert len(votes) == 2
        assert len({vote.announced_at_utc for vote in votes}) == 1
        assert votes[0].announced_at_utc is not None


async def test_two_people_promoting_one_random_pick_keep_the_first_credit_and_votes(
    engine: AsyncEngine,
    people: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    session_id, suggestion_id = await _night(sessionmaker, people)
    async with sessionmaker() as db:
        suggestion = await db.get(MovieNightSuggestion, suggestion_id)
        assert suggestion is not None
        suggestion.suggested_by = None
        await db.commit()
    await _like(sessionmaker, session_id, suggestion_id, people[0])

    first_written = asyncio.Event()
    release_first = asyncio.Event()
    real_publish = night.publish

    async def publish(db: AsyncSession, session_id: uuid.UUID, kind: str, data: dict) -> None:
        await real_publish(db, session_id, kind, data)
        if kind == "suggestion" and not first_written.is_set():
            first_written.set()
            await release_first.wait()

    monkeypatch.setattr(night, "publish", publish)
    app_name = f"aa4-{uuid.uuid4().hex}"

    async def promote(person: uuid.UUID, *, second: bool = False) -> uuid.UUID | None:
        async with sessionmaker() as db:
            if second:
                await db.execute(
                    text("SELECT set_config('application_name', :name, true)"), {"name": app_name}
                )
            session = await db.get(MovieNightSession, session_id)
            user = await db.get(Profile, person)
            assert session is not None and user is not None
            try:
                result = await night.add_suggestion(
                    db, session=session, user=user, tmdb_id=1201, title="Rooftop Opera"
                )
            except night.SuggestionRefused:
                await db.rollback()
                return None
            await db.commit()
            return result.id

    first = asyncio.create_task(promote(people[0]))
    second = None
    try:
        await asyncio.wait_for(first_written.wait(), timeout=5)
        second = asyncio.create_task(promote(people[1], second=True))

        async def wait_for_lock() -> None:
            async with engine.connect() as conn:
                while not await conn.scalar(
                    text(
                        "SELECT EXISTS (SELECT FROM pg_stat_activity "
                        "WHERE application_name = :name AND wait_event_type = 'Lock')"
                    ),
                    {"name": app_name},
                ):
                    # PG caches statistics per transaction; observe a fresh snapshot each time.
                    await conn.rollback()
                    await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_for_lock(), timeout=5)
        release_first.set()
        results = await asyncio.gather(first, second)
        assert results == [suggestion_id, None]
        async with sessionmaker() as db:
            stored = await db.get(MovieNightSuggestion, suggestion_id)
            assert stored is not None and stored.suggested_by == people[0]
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(MovieNightVote)
                    .where(MovieNightVote.suggestion_id == suggestion_id)
                )
                == 1
            )
    finally:
        release_first.set()
        await asyncio.gather(
            first, *([second] if second is not None else []), return_exceptions=True
        )
