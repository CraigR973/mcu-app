"""Watch history, Batch X5: films only watched, the backfill, the 15, the weekly sync (#269).

Postgres-backed, so these run in CI. TMDB is a stub everywhere; T9's identifier is stood in
for by one that answers from a table, because what these test is what the backfill and the
re-point *do* with an identification, not how T9 reaches one (``test_identify_films.py``).

**What this proves:** a film only watched is kept out of Home's counts; the backfill plan
decides owned, existing, new and doubtful as the rules say and writes nothing; applying it
writes exactly the plan once; the 15 are found by the film they sit on and the year they
were logged with, and moved; the weekly sync runs for whoever is a week stale and records
``cron``; Sync now fills in what the weekly sync could only add bare.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.letterboxd_sync import LetterboxdSync
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog
from src.services.identify.matcher import Candidate, Counters, Proposal
from src.services.letterboxd import sync as sync_module
from src.services.letterboxd.backfill import BackfillPlan, apply_backfill, plan_backfill
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.importer import fill_bare_films
from src.services.letterboxd.repoint import RepointPlan, apply_repoint, plan_repoint
from src.services.letterboxd.sync import SYNC_EVERY, sync_due
from src.tmdb.models import Movie as TmdbMovie

NOW = datetime(2026, 10, 14, 8, 0)


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
async def person(db: AsyncSession) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Watcher {uuid.uuid4().hex[:8]}",
        role=UserRole.admin,
    )
    db.add(profile)
    await db.flush()
    return profile


async def _film(
    db: AsyncSession, title: str, year: int | None, tmdb_id: int | None, *, owned: bool
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
        genre_ids=[18],
    )
    db.add(movie)
    await db.flush()
    if owned:
        db.add(CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["blu_ray"]))
        await db.flush()
    return movie


def _entry(viewing_id: str, title: str, year: int | None) -> DiaryEntry:
    return DiaryEntry(
        viewing_id=viewing_id,
        watched_at=date(2025, 5, 1),
        title=title,
        year=year,
        rating=None,
        is_rewatch=False,
    )


class _Identifier:
    """T9's identifier, answered from a table of (title, year) → TMDB id or a doubt."""

    def __init__(self, answers: dict[tuple[str, int | None], int | str]) -> None:
        self.answers = answers
        self.counters = Counters()
        self.asked: list[str] = []

    async def identify(self, parsed: Any, *, held: Any = None) -> Proposal:
        del held
        self.asked.append(parsed.raw)
        answer = self.answers.get((parsed.main, parsed.year))
        if isinstance(answer, int):
            chosen = Candidate(
                tmdb_id=answer, title=parsed.main, original_title=parsed.main, year=parsed.year
            )
            return Proposal("identify", evidence=["the year agrees"], chosen=chosen)
        return Proposal("ask", reason=str(answer or "three films of that title"))


class _Details:
    def __init__(self) -> None:
        self.asked: list[int] = []

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        del language
        self.asked.append(movie_id)
        return TmdbMovie(
            id=movie_id,
            title=f"Film {movie_id}",
            original_title=f"Film {movie_id}",
            overview="",
            release_date="2013-01-01",
            poster_path=f"/{movie_id}.jpg",
        )


# ---------------------------------------------------------------------------
# Kept out of the collection's counts
# ---------------------------------------------------------------------------


async def test_a_film_only_watched_is_not_counted_on_home(
    db: AsyncSession, person: Profile
) -> None:
    """Home's Films, Identified, genres and decades are the shelf's (#269)."""

    async def stats() -> dict[str, Any]:
        async def override_db() -> AsyncIterator[AsyncSession]:
            yield db

        async def override_user() -> Profile:
            return person

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                response = await c.get("/api/v1/collection/stats")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    before = await stats()
    await _film(db, "Watched Elsewhere", 1999, 990_501, owned=False)
    after = await stats()

    assert after["totalMovies"] == before["totalMovies"]
    assert after["identifiedMovies"] == before["identifiedMovies"]
    assert after["decades"] == before["decades"]
    assert after["genres"] == before["genres"]


# ---------------------------------------------------------------------------
# The backfill
# ---------------------------------------------------------------------------


async def test_the_plan_decides_each_entry_and_writes_nothing(
    db: AsyncSession, person: Profile
) -> None:
    psycho_1960 = await _film(db, "Psycho", 1960, 539, owned=True)
    listed = await _film(db, "Wanted Film", 2001, 990_601, owned=False)
    entries = [
        _entry("1", "Psycho", 1960),  # owned, by title and year
        _entry("2", "Psycho", 1998),  # the year excludes the owned film; TMDB knows it
        _entry("3", "Wanted Film", 2001),  # identifies as a film already listed
        _entry("4", "Emma", None),  # TMDB has several: doubtful
        _entry("5", "Psycho", 1998),  # a rewatch: the same film, asked once
    ]
    identifier = _Identifier(
        {("Psycho", 1998): 11252, ("Wanted Film", 2001): 990_601, ("Emma", None): "fifty Emmas"}
    )

    plan = await plan_backfill(db, (person.id, person.display_name), entries, identifier)

    actions = {entry.viewing_id: entry.action for entry in plan.entries}
    assert actions == {"1": "owned", "2": "new", "3": "existing", "4": "doubtful", "5": "new"}
    by_id = {entry.viewing_id: entry for entry in plan.entries}
    assert by_id["1"].movie_id == str(psycho_1960.id) and by_id["1"].tmdb_id is None
    assert by_id["3"].movie_id == str(listed.id)
    assert "fifty Emmas" in by_id["4"].reason
    assert identifier.asked.count("Psycho (1998)") == 1
    assert plan.counts() == {"owned": 1, "existing": 1, "new": 2, "doubtful": 1}
    assert plan.films_to_add() == 1
    assert (
        await db.scalar(select(func.count(WatchLog.id)).where(WatchLog.user_id == person.id)) == 0
    )


async def test_applying_the_plan_writes_it_exactly_once(db: AsyncSession, person: Profile) -> None:
    await _film(db, "Psycho", 1960, 539, owned=True)
    entries = [_entry("1", "Psycho", 1960), _entry("2", "Psycho", 1998), _entry("4", "Emma", None)]
    identifier = _Identifier({("Psycho", 1998): 11252})
    plan = await plan_backfill(db, (person.id, person.display_name), entries, identifier)
    # The plan survives its JSON, as the live run reads it from the file.
    plan = BackfillPlan.from_json(plan.to_json())
    details = _Details()

    first = await apply_backfill(db, plan, details)
    second = await apply_backfill(db, plan, details)

    assert (first.written, first.films_added, first.films_filled) == (2, 1, 1)
    assert (second.written, second.already) == (0, 2)
    rows = list(await db.scalars(select(WatchLog).where(WatchLog.user_id == person.id)))
    assert {row.letterboxd_viewing_id for row in rows} == {"1", "2"}, "Emma, doubtful, is not"
    new = (await db.scalars(select(Movie).where(Movie.tmdb_id == 11252))).one()
    assert (
        await db.scalar(
            select(func.count(CollectionItem.id)).where(CollectionItem.movie_id == new.id)
        )
        == 0
    )
    assert details.asked == [11252]


# ---------------------------------------------------------------------------
# The 15
# ---------------------------------------------------------------------------


async def test_a_watch_of_the_heat_on_heat_moves_to_the_heat(
    db: AsyncSession, person: Profile
) -> None:
    heat = await _film(db, "Heat", 1995, 949, owned=True)
    of_heat = WatchLog(
        id=uuid.uuid4(),
        movie_id=heat.id,
        user_id=person.id,
        watched_at=date(2016, 3, 1),
        letterboxd_viewing_id="70001",
    )
    of_mann = WatchLog(
        id=uuid.uuid4(),
        movie_id=heat.id,
        user_id=person.id,
        watched_at=date(2017, 3, 1),
        letterboxd_viewing_id="70002",
    )
    db.add_all([of_heat, of_mann])
    await db.flush()
    diaries = {"70001": _entry("70001", "The Heat", 2013), "70002": _entry("70002", "Heat", 1995)}

    plan = await plan_repoint(db, diaries, _Identifier({("The Heat", 2013): 136795}))
    plan = RepointPlan.from_json(plan.to_json())
    moves = [move for move in plan.moves if move.action == "move"]
    assert [move.viewing_id for move in moves] == ["70001"], "only the 2013 film moves"
    assert moves[0].to_tmdb_id == 136795 and moves[0].to_movie_id is None

    result = await apply_repoint(db, plan, _Details())

    assert (result.moved, result.films_added) == (1, 1)
    await db.refresh(of_heat)
    await db.refresh(of_mann)
    moved_to = await db.get(Movie, of_heat.movie_id)
    assert moved_to is not None and moved_to.tmdb_id == 136795
    assert of_heat.tmdb_id == 136795
    assert of_mann.movie_id == heat.id, "Michael Mann's film keeps its own watch"
    # A second apply finds the watch moved and leaves it.
    again = await apply_repoint(db, plan, _Details())
    assert again.moved == 0 and "moved since the plan" in again.skipped[0]


# ---------------------------------------------------------------------------
# The weekly sync, and filling in what it adds bare
# ---------------------------------------------------------------------------


def _empty_feed() -> httpx.AsyncClient:
    feed = '<?xml version="1.0"?><rss><channel></channel></rss>'
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=feed))
    )


async def test_the_weekly_sync_runs_for_whoever_is_a_week_stale(
    db: AsyncSession, person: Profile
) -> None:
    fresh = Profile(id=uuid.uuid4(), display_name=f"Fresh {uuid.uuid4().hex[:6]}")
    fresh.letterboxd_username = "freshone"
    person.letterboxd_username = "staleone"
    db.add(fresh)
    await db.flush()
    db.add_all(
        [
            LetterboxdSync(
                id=uuid.uuid4(),
                user_id=fresh.id,
                started_at_utc=NOW - timedelta(days=2),
                trigger="manual",
            ),
            LetterboxdSync(
                id=uuid.uuid4(),
                user_id=person.id,
                started_at_utc=NOW - SYNC_EVERY - timedelta(minutes=1),
                trigger="manual",
            ),
        ]
    )
    await db.flush()

    results = await sync_due(db, now=NOW, client=_empty_feed())

    synced = {result.run.user_id for result in results}
    assert person.id in synced and fresh.id not in synced
    assert all(result.run.trigger == "cron" for result in results)


@pytest.mark.parametrize("failing", ["first", "second"])
async def test_one_persons_failed_sync_leaves_the_other_synced_and_is_recorded(
    db_conn: AsyncConnection, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    """AG1 (CR49-01): one of two people fails; the other still syncs.

    Both profiles are committed before the job's session starts, as the owner's and the
    viewer's are, so the job's rollback expires them rather than erasing them: the shape in
    which reading ``person.id`` after the rollback raised ``MissingGreenlet``, lost the first
    error and skipped the second person. The failure is now on a committed row of its own,
    so the failed person is not left due for the same crash tomorrow, and every result is
    still readable once the job's session has closed, as the job prints them then.
    """
    first_id, second_id = uuid.uuid4(), uuid.uuid4()
    failed_id, other_id = (first_id, second_id) if failing == "first" else (second_id, first_id)
    setup = AsyncSession(bind=db_conn, join_transaction_mode="create_savepoint")
    setup.add_all(
        [
            Profile(id=first_id, display_name="AAA first", letterboxd_username="firstone"),
            Profile(id=second_id, display_name="AAB second", letterboxd_username="secondone"),
        ]
    )
    await setup.commit()
    await setup.close()

    real_import = sync_module.run_import

    async def failing_import(db: AsyncSession, profile: Profile, *args: Any, **kwargs: Any) -> Any:
        if profile.id == failed_id:
            raise RuntimeError("a new matcher rule broke")
        return await real_import(db, profile, *args, **kwargs)

    monkeypatch.setattr(sync_module, "run_import", failing_import)

    # As the 08:00 job opens it.
    job = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        results = await sync_due(job, now=utcnow(), client=_empty_feed())
    finally:
        await job.close()

    by_person = {result.run.user_id: result.run for result in results}
    assert set(by_person) >= {first_id, second_id}
    assert by_person[failed_id].error == "RuntimeError: a new matcher rule broke"
    assert by_person[other_id].error is None and by_person[other_id].finished_at_utc
    assert by_person[other_id].entries == 0

    check = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        stored = list(
            await check.scalars(
                select(LetterboxdSync).where(LetterboxdSync.user_id.in_([first_id, second_id]))
            )
        )
        assert sorted((row.user_id == failed_id, row.error) for row in stored) == [
            (False, None),
            (True, "RuntimeError: a new matcher rule broke"),
        ]
        # Recorded, so tomorrow's 08:00 job does not run the same crash again.
        again = await sync_due(check, now=utcnow() + timedelta(days=1), client=_empty_feed())
        assert {result.run.user_id for result in again} & {first_id, second_id} == set()
    finally:
        await check.close()


async def test_sync_now_fills_in_a_film_the_weekly_sync_added_bare(db: AsyncSession) -> None:
    bare = await _film(db, "The Heat", 2013, 136795, owned=False)
    filled_already = await _film(db, "Owned", 2001, 990_701, owned=True)
    details = _Details()

    filled = await fill_bare_films(db, details)

    assert filled >= 1
    assert 136795 in details.asked and 990_701 not in details.asked
    await db.refresh(bare)
    assert bare.poster_path == "/136795.jpg" and bare.last_tmdb_sync_utc is not None
    await db.refresh(filled_already)
    assert filled_already.last_tmdb_sync_utc is None, "a film with a disc is not this job's"
