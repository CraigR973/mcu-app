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

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.matching import MatchingEngine
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.importer import run_import
from src.tmdb.models import Movie as TmdbMovie
from src.tmdb.models import SearchResult, SearchResults

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
# Identification — the criterion's fifth clause
# ---------------------------------------------------------------------------


class _StubTmdb:
    """Answers the two calls identification makes, and counts them.

    Deliberately narrow. The point of these tests is what the *importer* does with a
    confident match and with an unconfident one, not TMDB's wire format — which
    `test_matching.py` already covers against captured payloads.
    """

    def __init__(self, *, title: str, tmdb_id: int, year: str, confident: bool = True) -> None:
        self.title = title
        self.tmdb_id = tmdb_id
        self.year = year
        self.confident = confident
        self.searches = 0
        self.fetches = 0

    async def search_movie(
        self,
        query: str,
        year: int | None = None,
        page: int = 1,
        language: str = "en-US",
        include_adult: bool = False,
    ) -> SearchResults:
        del year, page, language, include_adult
        self.searches += 1
        if not self.confident:
            # Two films that tie on title and are decades apart — exactly the shape
            # `MatchingEngine` calls ambiguous, and exactly `Death on the Nile`'s.
            return SearchResults(
                page=1,
                total_pages=1,
                total_results=2,
                results=[
                    SearchResult(
                        id=1,
                        title=self.title,
                        original_title=self.title,
                        overview=query,
                        release_date="1978-09-29",
                        popularity=9.0,
                    ),
                    SearchResult(
                        id=2,
                        title=self.title,
                        original_title=self.title,
                        overview=query,
                        release_date="2022-02-11",
                        popularity=8.0,
                    ),
                ],
            )
        return SearchResults(
            page=1,
            total_pages=1,
            total_results=1,
            results=[
                SearchResult(
                    id=self.tmdb_id,
                    title=self.title,
                    original_title=self.title,
                    overview=query,
                    release_date=f"{self.year}-01-01",
                    poster_path="/poster.jpg",
                    popularity=42.0,
                )
            ],
        )

    async def get_movie_full(self, tmdb_id: int) -> TmdbMovie:
        self.fetches += 1
        return TmdbMovie(
            id=tmdb_id,
            title=self.title,
            original_title=self.title,
            overview="",
            release_date=f"{self.year}-01-01",
            runtime=140,
            poster_path="/poster.jpg",
        )


async def test_a_film_the_april_import_never_identified_is_filled_in_and_reported(
    db: AsyncSession, person: Profile
) -> None:
    """The criterion: **`tmdb_id`, year, poster, runtime and cast filled, each reported.**

    This is the half of the import worth more than the watch rows. **396 distinct films**
    would be identified on a live run — over half the 754 the April import never resolved
    — because the diary names a film the collection holds only as a bare title
    (`DECISIONS.md` #160).
    """
    unidentified = await _film(db, "Collector, The")
    assert unidentified.tmdb_id is None and unidentified.year is None

    tmdb = _StubTmdb(title="The Collector", tmdb_id=29259, year="1965")
    report = await run_import(
        db,
        person,
        [_entry("111", "The Collector", year=1965)],
        dry_run=False,
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert report.matched_unidentified == 1
    assert report.identified == [("The Collector", 29259)]

    await db.refresh(unidentified)
    assert unidentified.tmdb_id == 29259
    assert unidentified.year == 1965
    assert unidentified.poster_path == "/poster.jpg"
    assert unidentified.runtime_minutes == 140
    assert report.written == 1


async def test_an_unconfident_tmdb_match_leaves_the_row_alone_and_says_so(
    db: AsyncSession, person: Profile
) -> None:
    """**Identification rewrites a row that already exists**, so a guess is expensive and
    silent. `MatchingEngine` reports a tie between films decades apart as ambiguous, and
    the importer refuses it rather than taking TMDB's popularity ordering as an answer —
    the same rule Batch 4's collection import follows (`DECISIONS.md` #31).

    **The entry has no year**, which is what makes this a genuine tie: with no year to
    score against, two same-titled films 44 years apart get identical confidence and the
    leader's position comes from popularity alone. A diary row *with* a year resolves
    instead — see the test below, which is the common case.

    **The watch is still written.** Failing to identify the film is not a reason to lose
    the record that somebody watched it.
    """
    unidentified = await _film(db, "Death on the Nile [1978]")

    tmdb = _StubTmdb(title="Death on the Nile", tmdb_id=1, year="1978", confident=False)
    report = await run_import(
        db,
        person,
        [_entry("111", "Death on the Nile")],
        dry_run=False,
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert report.identified == []
    assert len(report.identification_failures) == 1
    assert "left unidentified" in report.identification_failures[0]
    assert tmdb.fetches == 0

    await db.refresh(unidentified)
    assert unidentified.tmdb_id is None
    assert report.written == 1


async def test_the_diary_year_resolves_a_tie_tmdb_alone_could_not(
    db: AsyncSession, person: Profile
) -> None:
    """**The diary's year is the thing TMDB search does not have**, and it settles most of
    these.

    Two *Death on the Nile*s, 44 years apart, are ambiguous on title alone. The diary row
    says 1978, so the 1978 film scores an exact year match and the 2022 one a mismatch —
    not a tie, and identification proceeds. **Every row in both real diaries carries a
    Year**, measured, so this is the common path and the test above is the edge.
    """
    unidentified = await _film(db, "Death on the Nile [1978]")

    tmdb = _StubTmdb(title="Death on the Nile", tmdb_id=1, year="1978", confident=False)
    report = await run_import(
        db,
        person,
        [_entry("111", "Death on the Nile", year=1978)],
        dry_run=False,
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert report.identified == [("Death on the Nile", 1)]
    assert report.identification_failures == []
    await db.refresh(unidentified)
    assert unidentified.tmdb_id == 1


async def test_a_dry_run_never_touches_tmdb(db: AsyncSession, person: Profile) -> None:
    """A rehearsal that spent TMDB calls and rewrote nothing would be neither dry nor free."""
    await _film(db, "Collector, The")
    tmdb = _StubTmdb(title="The Collector", tmdb_id=29259, year="1965")

    report = await run_import(
        db,
        person,
        [_entry("111", "The Collector", year=1965)],
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert report.matched_unidentified == 1
    assert tmdb.searches == 0
    assert tmdb.fetches == 0
    assert report.written == 0


# ---------------------------------------------------------------------------
# Batch 40 — identification survives the already-imported skip
#
# Step 1 of `OWNER-ACTIONS.md` 1i ran on 2026-09-15 without `--identify`, writing all
# 1,555 watches. Every entry then short-circuited on its viewing id *above* the match, so
# the identification branch became unreachable: `--identify` reported a clean run and
# identified nothing. Nothing here caught it, because every S8 test identified on a
# **first** run — the one case where the two halves are separable (`DECISIONS.md` #197).
# ---------------------------------------------------------------------------


async def test_identification_reaches_a_film_whose_watches_are_already_imported(
    db: AsyncSession, person: Profile
) -> None:
    """The regression, in the order it actually happened: watches first, identify second.

    This is the only test in this file whose first run writes without identifying, and it
    is the sequence the live database is in.
    """
    unidentified = await _film(db, "Collector, The")
    entries = [_entry("111", "The Collector", year=1965)]

    first = await run_import(db, person, entries, dry_run=False)
    assert first.written == 1
    await db.refresh(unidentified)
    assert unidentified.tmdb_id is None

    tmdb = _StubTmdb(title="The Collector", tmdb_id=29259, year="1965")
    second = await run_import(
        db,
        person,
        entries,
        dry_run=False,
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert second.already_imported == 1
    assert second.identified == [("The Collector", 29259)]
    assert second.written == 0, "the skip must still suppress the watch row"
    assert await _watch_count(db, person) == 1

    await db.refresh(unidentified)
    assert unidentified.tmdb_id == 29259
    assert unidentified.year == 1965
    assert unidentified.runtime_minutes == 140


async def test_an_already_imported_entry_is_not_counted_as_a_row_to_write(
    db: AsyncSession, person: Profile
) -> None:
    """`would_write` must keep meaning "rows a real run would insert".

    Hoisting the match above the skip makes every entry reach the counters, so the two
    that feed `would_write` are guarded and `identifiable` is not. Without that, a re-run
    would claim it was about to write 1,555 watches it will not write.
    """
    await _film(db, "Collector, The")
    entries = [_entry("111", "The Collector", year=1965)]
    await run_import(db, person, entries, dry_run=False)

    report = await run_import(db, person, entries)

    assert report.already_imported == 1
    assert report.matched_unidentified == 0
    assert report.matched_identified == 0
    assert report.would_write == 0
    assert len(report.identifiable) == 1, "still one film needing a tmdb_id"


async def test_a_dry_run_reports_the_films_it_would_identify_without_touching_tmdb(
    db: AsyncSession, person: Profile
) -> None:
    """`identifiable` is the rehearsal, and it stays free.

    A dry run spends no TMDB calls, so it can say how many films it would identify and
    what they are called locally, but not what any of them becomes. Keeping that true is
    why `identifiable` is filled from the row rather than from a search.
    """
    await _film(db, "Collector, The")
    await _film(db, "39 Steps The (Robert Donat)")
    entries = [
        _entry("111", "The Collector", year=1965),
        _entry("222", "The 39 Steps", year=1935),
    ]
    await run_import(db, person, entries, dry_run=False)
    tmdb = _StubTmdb(title="The Collector", tmdb_id=29259, year="1965")

    report = await run_import(
        db,
        person,
        entries,
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert sorted(report.identifiable.values()) == ["39 Steps The (Robert Donat)", "Collector, The"]
    assert report.identified == []
    assert tmdb.searches == 0
    assert tmdb.fetches == 0
    assert report.written == 0


async def test_a_film_watched_more_than_once_is_put_to_tmdb_only_once(
    db: AsyncSession, person: Profile
) -> None:
    """One film is many entries — 2,322 of them cover 1,101 films.

    Identifying per *entry* rather than per *film* would multiply the live run's ~800 TMDB
    calls by the rewatch rate. It never showed up before because a successful
    identification sets `tmdb_id` and so hides itself from the next entry.
    """
    await _film(db, "Collector, The")
    entries = [
        _entry("111", "The Collector", year=1965),
        _entry("222", "The Collector", year=1965, rewatch=True, watched=date(2026, 9, 2)),
        _entry("333", "The Collector", year=1965, rewatch=True, watched=date(2026, 9, 3)),
    ]
    tmdb = _StubTmdb(title="The Collector", tmdb_id=29259, year="1965")

    report = await run_import(
        db,
        person,
        entries,
        dry_run=False,
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert tmdb.searches == 1
    assert tmdb.fetches == 1
    assert report.identified == [("The Collector", 29259)]
    assert report.written == 3, "all three watches still land"


async def test_a_film_tmdb_cannot_resolve_is_not_retried_for_every_watch(
    db: AsyncSession, person: Profile
) -> None:
    """A *failed* identification leaves `tmdb_id` NULL, so it still looks like work to do.

    That is the case the `tmdb_id` check cannot close by itself, and the one that costs
    the most calls: the films with no confident match are exactly the messy-titled ones
    someone watched repeatedly.
    """
    await _film(db, "Death on the Nile [1978]")
    entries = [
        _entry("111", "Death on the Nile"),
        _entry("222", "Death on the Nile", rewatch=True, watched=date(2026, 9, 2)),
    ]
    tmdb = _StubTmdb(title="Death on the Nile", tmdb_id=1, year="1978", confident=False)

    report = await run_import(
        db,
        person,
        entries,
        dry_run=False,
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert tmdb.searches == 1, "one refusal is enough; the second watch changes nothing"
    assert report.identified == []
    assert len(report.identification_failures) == 1
    assert report.written == 2


async def test_a_later_watch_follows_a_film_that_identification_merged_away(
    db: AsyncSession, person: Profile
) -> None:
    """The index is built before the loop and a merge deletes a row inside it.

    `apply_identification` merges when the collection already holds the TMDB id — here the
    same film sits in the sheet twice, once identified and once as a bare title. The
    second entry still matches the deleted row through the stale index, so the watch would
    be written against a row that no longer exists.
    """
    survivor = await _film(db, "Le Collectionneur", year=1965, tmdb_id=29259)
    doomed = await _film(db, "Collector, The")
    entries = [
        _entry("111", "The Collector", year=1965),
        _entry("222", "The Collector", year=1965, rewatch=True, watched=date(2026, 9, 2)),
    ]
    tmdb = _StubTmdb(title="The Collector", tmdb_id=29259, year="1965")

    report = await run_import(
        db,
        person,
        entries,
        dry_run=False,
        engine=MatchingEngine(tmdb),  # type: ignore[arg-type]
    )

    assert report.written == 2
    assert tmdb.searches == 1, "the merged-away row must not be put to TMDB again"

    rows = list(await db.scalars(select(WatchLog.movie_id).where(WatchLog.user_id == person.id)))
    assert rows == [survivor.id, survivor.id], "both watches hang off the surviving row"
    assert await db.get(Movie, doomed.id) is None
