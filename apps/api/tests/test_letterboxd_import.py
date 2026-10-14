"""Batch S8's importer — snag 10b, `DECISIONS.md` #160, #161.

Postgres-backed, so these skip on this machine and run in CI (`STATUS.md` gotcha 3).

**The criterion these exist for is idempotency**, and it is not a nicety: a real run
writes ~1,530 rows, and the first thing anyone does after an import that looked wrong is
run it again.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.importer import run_import
from src.tmdb.models import Movie as TmdbMovie


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
        display_name=f"Diary Owner {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.admin,
    )
    db.add(profile)
    await db.flush()
    return profile


async def _film(
    db: AsyncSession, title: str, year: int | None = None, tmdb_id: int | None = None
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
    )
    db.add(movie)
    await db.flush()
    return movie


def _entry(
    viewing_id: str,
    title: str,
    *,
    year: int | None = None,
    rating: Decimal | None = None,
    rewatch: bool = False,
    watched: date = date(2026, 9, 1),
) -> DiaryEntry:
    return DiaryEntry(
        viewing_id=viewing_id,
        watched_at=watched,
        title=title,
        year=year,
        rating=rating,
        is_rewatch=rewatch,
    )


async def _watch_count(db: AsyncSession, person: Profile) -> int:
    return int(
        (
            await db.execute(select(func.count(WatchLog.id)).where(WatchLog.user_id == person.id))
        ).scalar_one()
    )


# ---------------------------------------------------------------------------
# The dry run
# ---------------------------------------------------------------------------


async def test_a_dry_run_reports_every_count_and_writes_nothing(
    db: AsyncSession, person: Profile
) -> None:
    """The criterion, and the reason `dry_run` defaults to True.

    The dry run has to be a genuine rehearsal — the same matching, the same counts — or it
    is a different code path that happens to print numbers, and the number it prints is
    the one somebody decides to write 1,530 rows on.
    """
    await _film(db, "Heat", year=1995, tmdb_id=949)
    await _film(db, "Collector, The")

    report = await run_import(
        db,
        person,
        [
            _entry("1", "Heat", year=1995),
            _entry("2", "The Collector", year=1965),
            _entry("3", "A Film Nobody Owns", year=1999),
        ],
    )

    assert report.dry_run is True
    assert report.entries == 3
    assert report.matched_identified == 1
    assert report.matched_unidentified == 1
    assert report.not_in_collection == 1
    assert report.would_write == 2
    assert report.written == 0
    assert await _watch_count(db, person) == 0


async def test_the_dry_run_and_the_real_run_agree_on_what_they_would_write(
    db: AsyncSession, person: Profile
) -> None:
    await _film(db, "Heat", year=1995, tmdb_id=949)
    entries = [_entry("1", "Heat", year=1995), _entry("2", "A Film Nobody Owns")]

    dry = await run_import(db, person, entries)
    wet = await run_import(db, person, entries, dry_run=False)

    assert dry.would_write == wet.written == 1


# ---------------------------------------------------------------------------
# Idempotency — the criterion, stated as "a second run writes zero new rows"
# ---------------------------------------------------------------------------


async def test_a_second_run_of_the_same_file_writes_nothing(
    db: AsyncSession, person: Profile
) -> None:
    await _film(db, "Heat", year=1995, tmdb_id=949)
    await _film(db, "Get Out", year=2017, tmdb_id=419430)
    entries = [_entry("1489750098", "Heat", year=1995), _entry("1485310138", "Get Out", year=2017)]

    first = await run_import(db, person, entries, dry_run=False)
    assert first.written == 2
    assert await _watch_count(db, person) == 2

    second = await run_import(db, person, entries, dry_run=False)
    assert second.written == 0
    assert second.already_imported == 2
    assert await _watch_count(db, person) == 2


async def test_a_rewatch_on_a_later_date_is_a_second_row_not_a_duplicate(
    db: AsyncSession, person: Profile
) -> None:
    """`DECISIONS.md` #159: a rewatch is a *different* viewing id, so idempotency keyed on
    that id gets this right without comparing dates or titles."""
    await _film(db, "Get Out", year=2017, tmdb_id=419430)
    await run_import(
        db,
        person,
        [
            _entry("111", "Get Out", year=2017, watched=date(2020, 1, 1)),
            _entry("222", "Get Out", year=2017, watched=date(2026, 9, 5), rewatch=True),
        ],
        dry_run=False,
    )

    rows = list(
        await db.scalars(
            select(WatchLog).where(WatchLog.user_id == person.id).order_by(WatchLog.watched_at)
        )
    )
    assert len(rows) == 2
    assert [row.is_rewatch for row in rows] == [False, True]


async def test_an_rss_sync_cannot_re_import_a_viewing_the_file_already_wrote(
    db: AsyncSession, person: Profile
) -> None:
    """**S5's criterion, met here.**

    The feed's `<guid>` is `letterboxd-watch-<id>` wrapping the same number the CSV calls
    `ViewingId`, so storing the bare id is what collapses the two sources to one row. Doing
    it in S8 rather than S5 is the point: the alternative is discovering it after 2,322
    rows are already in.
    """
    await _film(db, "Heat", year=1995, tmdb_id=949)
    from_file = _entry("1489750098", "Heat", year=1995)
    await run_import(db, person, [from_file], dry_run=False)

    # What S5 will build from `<guid>letterboxd-watch-1489750098</guid>` — same id, and it
    # knows the TMDB id the file did not.
    from_feed = DiaryEntry(
        viewing_id="1489750098",
        watched_at=date(2026, 9, 9),
        title="Heat",
        year=1995,
        rating=None,
        is_rewatch=False,
        tmdb_id=949,
    )
    second = await run_import(db, person, [from_feed], dry_run=False)

    assert second.written == 0
    assert second.already_imported == 1
    assert await _watch_count(db, person) == 1


async def test_two_people_can_each_log_their_own_viewing_of_the_same_film(
    db: AsyncSession, person: Profile
) -> None:
    """The uniqueness is scoped per person, not global — two diaries, two sets of ids."""
    other = Profile(
        id=uuid.uuid4(),
        display_name=f"Other Owner {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
    )
    db.add(other)
    await db.flush()

    await _film(db, "Heat", year=1995, tmdb_id=949)
    await run_import(db, person, [_entry("111", "Heat", year=1995)], dry_run=False)
    await run_import(db, other, [_entry("222", "Heat", year=1995)], dry_run=False)

    assert await _watch_count(db, person) == 1
    assert await _watch_count(db, other) == 1


# ---------------------------------------------------------------------------
# What gets written
# ---------------------------------------------------------------------------


async def test_the_rating_and_the_rewatch_flag_survive_the_import(
    db: AsyncSession, person: Profile
) -> None:
    await _film(db, "Heat", year=1995, tmdb_id=949)
    await run_import(
        db,
        person,
        [_entry("111", "Heat", year=1995, rating=Decimal("4.5"), rewatch=True)],
        dry_run=False,
    )
    row = (await db.scalars(select(WatchLog).where(WatchLog.user_id == person.id))).one()
    assert row.personal_rating == Decimal("4.5")
    assert row.is_rewatch is True
    assert row.watched_at == date(2026, 9, 1)
    assert row.letterboxd_viewing_id == "111"


async def test_a_null_rating_is_written_as_null(db: AsyncSession, person: Profile) -> None:
    """**Mark rates nothing**, and 0 of 1,149 is correct data rather than missing data."""
    await _film(db, "Heat", year=1995, tmdb_id=949)
    await run_import(db, person, [_entry("111", "Heat", year=1995)], dry_run=False)
    row = (await db.scalars(select(WatchLog).where(WatchLog.user_id == person.id))).one()
    assert row.personal_rating is None


async def test_an_ambiguous_entry_writes_nothing_and_is_reported(
    db: AsyncSession, person: Profile
) -> None:
    """**Offered, never guessed** — even on a real run, and even though skipping it means
    the watch is not logged. Six entries across 2,322; a wrong film logged silently is
    worse than a watch a person has to place by hand."""
    await _film(db, "Death on the Nile")
    await _film(db, "Death on the Nile [1978]")

    report = await run_import(
        db, person, [_entry("111", "Death on the Nile", year=2022)], dry_run=False
    )

    assert report.written == 0
    assert len(report.ambiguous) == 1
    assert await _watch_count(db, person) == 0


# ---------------------------------------------------------------------------
# Identification is T9's now (Batch X5, CT46-01)
# ---------------------------------------------------------------------------
#
# S8's import filled in owned films the April import never identified, through
# `MatchingEngine`, and put three diary films on the wrong owned rows doing it (CT46-01).
# Since X5 it identifies nothing; `identifiable` still counts the owned rows a watch landed
# on that carry no TMDB id, for T9's `identify_films`. The tests of the removed step went
# with it; these keep what remains.


async def test_an_already_imported_entry_is_not_counted_as_a_row_to_write(
    db: AsyncSession, person: Profile
) -> None:
    """`would_write` must keep meaning "rows a real run would insert"."""
    await _film(db, "Collector, The")
    entries = [_entry("111", "The Collector", year=1965)]
    await run_import(db, person, entries, dry_run=False)

    report = await run_import(db, person, entries)

    assert report.already_imported == 1
    assert report.matched_unidentified == 0
    assert report.matched_identified == 0
    assert report.would_write == 0
    assert len(report.identifiable) == 1, "still one film needing a tmdb_id"


async def test_the_import_never_rewrites_an_owned_film(db: AsyncSession, person: Profile) -> None:
    """A watch lands on an unidentified owned row by title, and the row is left as it was:
    no `MatchingEngine`, no TMDB, no identification (X5)."""
    collector = await _film(db, "Collector, The")
    report = await run_import(
        db, person, [_entry("111", "The Collector", year=1965)], dry_run=False
    )

    await db.refresh(collector)
    assert (collector.tmdb_id, collector.title) == (None, "Collector, The")
    assert report.written == 1
    assert sorted(report.identifiable.values()) == ["Collector, The"]


# ---------------------------------------------------------------------------
# Films not owned — Batch X5 (#269)
# ---------------------------------------------------------------------------


class _Details:
    """TMDB's details for a film, counted. The importer asks for nothing else."""

    def __init__(self) -> None:
        self.asked: list[int] = []

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        del language
        self.asked.append(movie_id)
        return TmdbMovie(
            id=movie_id,
            title="The Heat",
            original_title="The Heat",
            overview="Two cops.",
            release_date="2013-06-28",
            runtime=117,
            poster_path="/heat2013.jpg",
        )


def _feed_entry(viewing_id: str, title: str, year: int, tmdb_id: int) -> DiaryEntry:
    return DiaryEntry(
        viewing_id=viewing_id,
        watched_at=date(2026, 10, 1),
        title=title,
        year=year,
        rating=None,
        is_rewatch=False,
        tmdb_id=tmdb_id,
    )


async def test_a_film_not_in_the_catalogue_gets_a_row_and_the_watch(
    db: AsyncSession, person: Profile
) -> None:
    """The feed's *The Heat* (2013) beside an owned *Heat* (1995): a row of its own, filled
    in from TMDB, with no copies, and the watch on it carrying the feed's id."""
    heat_1995 = await _film(db, "Heat", 1995, tmdb_id=949)
    details = _Details()
    entries = [
        _feed_entry("501", "The Heat", 2013, 136795),
        _feed_entry("502", "The Heat", 2013, 136795),
    ]

    report = await run_import(db, person, entries, dry_run=False, tmdb=details)

    assert (report.written, report.matched_not_owned, report.films_filled) == (2, 2, 1)
    assert report.films_added == {136795: "The Heat"}
    assert details.asked == [136795], "one TMDB call per film, not per watch"
    rows = list(await db.scalars(select(WatchLog).where(WatchLog.user_id == person.id)))
    assert {row.tmdb_id for row in rows} == {136795}
    assert heat_1995.id not in {row.movie_id for row in rows}
    film = await db.get(Movie, rows[0].movie_id)
    assert film is not None
    assert (film.title, film.year, film.poster_path) == ("The Heat", 2013, "/heat2013.jpg")
    assert film.last_tmdb_sync_utc is not None


async def test_without_tmdb_the_row_keeps_the_feeds_title_and_year(
    db: AsyncSession, person: Profile
) -> None:
    """The 08:00 job holds no TMDB token: the row is bare until a Sync now fills it."""
    report = await run_import(
        db, person, [_feed_entry("601", "The Heat", 2013, 136795)], dry_run=False
    )
    film = (await db.scalars(select(Movie).where(Movie.tmdb_id == 136795))).one()
    assert (film.title, film.year, film.last_tmdb_sync_utc) == ("The Heat", 2013, None)
    assert report.films_filled == 0


async def test_a_dry_run_counts_the_films_it_would_add_and_adds_none(
    db: AsyncSession, person: Profile
) -> None:
    entries = [_feed_entry("701", "The Heat", 2013, 136795)]
    report = await run_import(db, person, entries)
    assert (report.matched_not_owned, report.would_write, report.written) == (1, 1, 0)
    assert report.films_added == {136795: "The Heat"}
    assert await db.scalar(select(func.count(Movie.id)).where(Movie.tmdb_id == 136795)) == 0


async def test_a_film_in_the_trash_holding_the_id_is_left_alone(
    db: AsyncSession, person: Profile
) -> None:
    from datetime import datetime

    trashed = await _film(db, "The Heat", 2013, tmdb_id=136795)
    trashed.deleted_at = datetime(2026, 10, 1)
    await db.flush()

    report = await run_import(
        db, person, [_feed_entry("801", "The Heat", 2013, 136795)], dry_run=False
    )

    assert report.written == 0
    assert report.in_trash == ["The Heat (2013)"]
