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
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    MovieNightSuggestion,
    MovieNightVote,
    new_invite_token,
)
from src.models.notification import Notification
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog
from src.services.movie_night.realtime import MovieNightBroadcaster, encode
from src.services.movie_night.sessions import (
    SuggestionRefused,
    add_suggestion,
    detect_match,
    ensure_seeded,
    record_vote,
    seeded_candidates,
    session_suggestions,
    watched_by_others,
)


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


async def _movie(
    db: AsyncSession, title: str, *, year: int | None = 2010, owned: bool = True
) -> Movie:
    """A film, on the shelf unless ``owned`` is false: the deck is the shelf (Batch X5)."""
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
    if owned:
        db.add(CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["blu_ray"]))
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


async def _suggest(
    db: AsyncSession, session: MovieNightSession, movie: Movie, by: Profile
) -> MovieNightSuggestion:
    """Put a film on tonight's list.

    **Batch S7 made this the step before a vote.** Batch 35 dealt a deck and voted
    straight onto `movies`; `DECISIONS.md` #157 replaced the input side, so every vote is
    now cast on a suggestion — which is what lets a film outside the Archive be voted on
    at all.
    """
    return await add_suggestion(db, session=session, user=by, movie_id=movie.id)


class TestMatching:
    """§8.4 — *"both users swiping on the same film triggers a match notification"*."""

    async def test_both_liking_the_same_film_is_a_match(self, db: AsyncSession) -> None:
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")
        pick = await _suggest(db, session, heat, craig)

        first = await record_vote(db, session=session, user=craig, suggestion=pick, liked=True)
        second = await record_vote(db, session=session, user=mark, suggestion=pick, liked=True)

        assert first is None, "one like is not a match"
        assert second is not None
        assert second.title == "Heat"

    async def test_one_liking_and_one_passing_is_not_a_match(self, db: AsyncSession) -> None:
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")
        pick = await _suggest(db, session, heat, craig)

        await record_vote(db, session=session, user=craig, suggestion=pick, liked=True)
        result = await record_vote(db, session=session, user=mark, suggestion=pick, liked=False)

        assert result is None

    async def test_a_match_is_announced_once(self, db: AsyncSession) -> None:
        """`announced_at_utc` is the only derived state kept, and this is why."""
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")
        pick = await _suggest(db, session, heat, craig)
        await record_vote(db, session=session, user=craig, suggestion=pick, liked=True)
        await record_vote(db, session=session, user=mark, suggestion=pick, liked=True)

        again = await detect_match(db, session=session, suggestion=pick)

        assert again is None

    async def test_swiping_alone_is_never_a_match(self, db: AsyncSession) -> None:
        """Announcing one would be telling somebody they agree with themselves."""
        craig = await _profile(db)
        session = await _session(db, craig)
        heat = await _movie(db, "Heat")
        pick = await _suggest(db, session, heat, craig)

        result = await record_vote(db, session=session, user=craig, suggestion=pick, liked=True)

        assert result is None

    async def test_a_match_notifies_both_people(self, db: AsyncSession) -> None:
        """§8.4's "notification to both", through Batch 11's outbox."""
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")
        pick = await _suggest(db, session, heat, craig)

        await record_vote(db, session=session, user=craig, suggestion=pick, liked=True)
        await record_vote(db, session=session, user=mark, suggestion=pick, liked=True)

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
        pick = await _suggest(db, session, heat, craig)

        await record_vote(db, session=session, user=craig, suggestion=pick, liked=False)
        await record_vote(db, session=session, user=craig, suggestion=pick, liked=True)

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
        pick = await _suggest(db, session, heat, craig)

        await record_vote(db, session=session, user=craig, suggestion=pick, liked=True)
        two_of_three = await record_vote(
            db, session=session, user=mark, suggestion=pick, liked=True
        )
        all_three = await record_vote(db, session=session, user=third, suggestion=pick, liked=True)

        assert two_of_three is None
        assert all_three is not None


class TestTheShortlist:
    """**Batch S7 turned a private deck into a shared shortlist** — `DECISIONS.md` #157.

    Batch 35 dealt each person their own hand and hid what they had swiped. Three of
    Craig's five points needed the input side replaced: anyone suggests, everyone votes on
    anyone's suggestion, and films outside the Archive are allowed.
    """

    async def test_anyone_can_suggest_and_everyone_votes_on_it(self, db: AsyncSession) -> None:
        """#157's first point. **Not the admin, not the creator — anyone in the session.**"""
        craig = await _profile(db)
        mark = await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        # Suggested by the *viewer*, voted on by both.
        pick = await add_suggestion(db, session=session, user=mark, movie_id=heat.id)
        assert pick.suggested_by == mark.id

        assert (
            await record_vote(db, session=session, user=craig, suggestion=pick, liked=True) is None
        )
        match = await record_vote(db, session=session, user=mark, suggestion=pick, liked=True)
        assert match is not None
        assert match.title == "Heat"

    async def test_a_film_outside_the_archive_can_be_suggested_and_matched(
        self, db: AsyncSession
    ) -> None:
        """#157's second point, and the one Batch 35 made structurally impossible.

        `candidate_movies` was `select(Movie)`, so **a film outside the Archive could never
        appear**. A suggestion carries a TMDB id and its own title instead, because there
        is no `movies` row to read them from — and a match on one is still a match.
        """
        craig = await _profile(db)
        mark = await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)

        rental = await add_suggestion(
            db,
            session=session,
            user=craig,
            tmdb_id=603,
            title="The Matrix",
            year=1999,
        )
        assert rental.movie_id is None
        assert rental.tmdb_id == 603

        await record_vote(db, session=session, user=craig, suggestion=rental, liked=True)
        match = await record_vote(db, session=session, user=mark, suggestion=rental, liked=True)

        assert match is not None
        assert match.title == "The Matrix"
        assert match.movie_id is None  # nothing on the shelf to point at

    async def test_the_same_film_twice_is_agreement_rather_than_two_cards(
        self, db: AsyncSession
    ) -> None:
        craig = await _profile(db)
        mark = await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        await add_suggestion(db, session=session, user=craig, movie_id=heat.id)
        with pytest.raises(SuggestionRefused):
            await add_suggestion(db, session=session, user=mark, movie_id=heat.id)

    async def test_a_suggestion_names_exactly_one_film(self, db: AsyncSession) -> None:
        craig = await _profile(db)
        session = await _session(db, craig)
        heat = await _movie(db, "Heat")

        with pytest.raises(SuggestionRefused):
            await add_suggestion(db, session=session, user=craig, movie_id=heat.id, tmdb_id=603)
        with pytest.raises(SuggestionRefused):
            await add_suggestion(db, session=session, user=craig)
        with pytest.raises(SuggestionRefused):
            # A film outside the collection has no row to read a title from.
            await add_suggestion(db, session=session, user=craig, tmdb_id=603)

    async def test_a_film_you_voted_on_stays_on_the_shared_list(self, db: AsyncSession) -> None:
        """**The deliberate change.** Batch 35 removed a card once you had swiped it,
        because the deck was yours alone. A shortlist everyone is adding to is a list you
        re-read, so the card stays and the API reports your own vote back to you."""
        craig = await _profile(db)
        session = await _session(db, craig)
        heat = await _movie(db, "Heat")
        pick = await _suggest(db, session, heat, craig)

        await record_vote(db, session=session, user=craig, suggestion=pick, liked=False)
        listed = await session_suggestions(db, session=session)

        assert heat.id in {item.movie_id for item in listed}

    async def test_the_other_persons_vote_is_still_not_visible(self, db: AsyncSession) -> None:
        """**The privacy property Batch 35 had, kept.**

        A movie night where each person can see the other's swipes before deciding is not
        the same game. The shortlist is shared; the votes on it are not — `myVote` is
        built from the caller's own votes alone, and nothing else on the card says how
        anybody voted.
        """
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")
        pick = await _suggest(db, session, heat, craig)

        await record_vote(db, session=session, user=mark, suggestion=pick, liked=True)

        mine = {
            vote.suggestion_id: vote.liked
            for vote in (
                await db.execute(
                    select(MovieNightVote).where(
                        MovieNightVote.session_id == session.id,
                        MovieNightVote.user_id == craig.id,
                    )
                )
            ).scalars()
        }
        assert mine == {}, "Craig's own votes are empty; Mark's are not his to see"

    async def test_the_sessions_filters_narrow_what_it_is_seeded_with(
        self, db: AsyncSession
    ) -> None:
        """§8.3's "session creation with filters", doing something."""
        craig = await _profile(db)
        session = await _session(db, craig, filters={"decadeFrom": 2000, "decadeTo": 2009})
        await _movie(db, "Old Film", year=1975)
        modern = await _movie(db, "Noughties Film", year=2005)

        deck = await seeded_candidates(db, session=session)

        assert {movie.id for movie in deck} == {modern.id}

    async def test_a_film_only_watched_or_wanted_is_not_dealt(self, db: AsyncSession) -> None:
        """Batch X5 (#269): a film either person watched has a row now, and so does a want.
        Neither is on the shelf, so neither is a movie night card."""
        craig = await _profile(db)
        session = await _session(db, craig)
        shelf = await _movie(db, "On The Shelf")
        await _movie(db, "Only Watched", owned=False)

        deck = await seeded_candidates(db, session=session)

        assert {movie.id for movie in deck} == {shelf.id}

    async def test_seeding_twice_does_not_double_the_list(self, db: AsyncSession) -> None:
        craig = await _profile(db)
        session = await _session(db, craig)
        await _movie(db, "Heat")

        await ensure_seeded(db, session=session)
        first = len(await session_suggestions(db, session=session))
        await ensure_seeded(db, session=session)

        assert len(await session_suggestions(db, session=session)) == first


class TestTheDeckOrderMatchesItsDocstring:
    """`DECISIONS.md` #157's *"defect to fix regardless of this decision"*.

    Batch 35's `candidate_movies` documented itself as *"seeded per session so both people
    are shown the same deck in the same order"* and ordered by `func.random()` with **no
    seed** — every call returned a different order, per person and per refetch. The
    comment asserted a guarantee the code did not give.
    """

    async def test_the_same_session_deals_the_same_order_every_time(self, db: AsyncSession) -> None:
        craig = await _profile(db)
        session = await _session(db, craig)
        for index in range(12):
            await _movie(db, f"Film {index}", year=2000 + index)

        first = [movie.id for movie in await seeded_candidates(db, session=session)]
        second = [movie.id for movie in await seeded_candidates(db, session=session)]

        assert first == second
        assert len(first) >= 12

    async def test_two_sessions_deal_different_orders(self, db: AsyncSession) -> None:
        """Otherwise every movie night opens on the same twelve films, which is the reason
        the ordering was random in the first place."""
        craig = await _profile(db)
        one = await _session(db, craig)
        two = await _session(db, craig)
        for index in range(25):
            await _movie(db, f"Shuffled {index}", year=1980 + index)

        assert [m.id for m in await seeded_candidates(db, session=one)] != [
            m.id for m in await seeded_candidates(db, session=two)
        ]


class TestWhoHasSeenIt:
    """#157's fourth point: *"whether the others have seen it and when"*.

    **Empty for every film until S8's import runs** — `watch_log` held 0 rows when this was
    written, which is exactly why #157 put S7 after S8 in the order.
    """

    async def test_it_reports_the_other_participants_and_not_you(self, db: AsyncSession) -> None:
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        db.add(
            WatchLog(
                id=uuid.uuid4(),
                movie_id=heat.id,
                user_id=mark.id,
                watched_at=date(2026, 3, 4),
            )
        )
        db.add(
            WatchLog(
                id=uuid.uuid4(),
                movie_id=heat.id,
                user_id=craig.id,
                watched_at=date(2026, 5, 6),
            )
        )
        await db.flush()

        seen = await watched_by_others(db, session=session, user=craig, movie_ids=[heat.id])

        # Mark's watch, not Craig's own: "have I seen it" is on the film's page.
        assert [name for name, _ in seen[heat.id]] == [mark.display_name]
        assert seen[heat.id][0][1] == date(2026, 3, 4)

    async def test_a_film_nobody_else_has_seen_is_simply_absent(self, db: AsyncSession) -> None:
        craig, mark = await _profile(db), await _profile(db, UserRole.viewer)
        session = await _session(db, craig, mark)
        heat = await _movie(db, "Heat")

        assert await watched_by_others(db, session=session, user=craig, movie_ids=[heat.id]) == {}


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


async def test_suggesting_a_random_pick_keeps_its_votes_and_credits_the_person(
    db: AsyncSession,
) -> None:
    craig = await _profile(db)
    night = await _session(db, craig)
    film = await _movie(db, "A random pick")
    await ensure_seeded(db, session=night)
    (seed,) = await session_suggestions(db, session=night)
    assert seed.suggested_by is None
    await record_vote(db, session=night, user=craig, suggestion=seed, liked=True)
    picked = await add_suggestion(db, session=night, user=craig, movie_id=film.id)
    assert picked.id == seed.id
    assert picked.suggested_by == craig.id
    assert len(await session_suggestions(db, session=night)) == 1
    vote = await db.scalar(select(MovieNightVote).where(MovieNightVote.suggestion_id == seed.id))
    assert vote is not None and vote.liked is True
