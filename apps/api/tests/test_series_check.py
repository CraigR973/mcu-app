"""Finding the series matched as films — Batch Y3.

**What this proves:** the rule names Band of Brothers (a series with 4,100 votes against a
film with 3) and leaves Fargo alone (a film better known than half its namesake series'
votes); a disc grouped "TV" or a replaced spreadsheet title in T9's series words is enough on
its own; a title TMDB fails on is noted, not fatal; the report links each film's page and
escapes what it prints. Against Postgres, the reads take only identified films still on the
shelf, never a series or a film in the Trash, and the SQL the HTTPS path sends is the same
query, row for row.

**What it does not:** TMDB, or the live database. The script runs on the Mac or over HTTPS.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.clock import utcnow
from src.models.collection_item import CollectionItem
from src.models.identify import MovieTitleAlias
from src.models.movie import Movie
from src.scripts.find_series_as_films import as_sql
from src.services.identify.series_check import (
    CheckResult,
    IdentifiedFilm,
    Suspect,
    assemble,
    check,
    films_query,
    groupings_query,
    judge,
    render_csv,
    render_html,
    replaced_titles_query,
)
from src.tmdb.models import TvSearchResult, TvSearchResults


def _film(
    title: str,
    votes: int,
    *,
    replaced_titles: tuple[str, ...] = (),
    groupings: tuple[str, ...] = (),
) -> IdentifiedFilm:
    return IdentifiedFilm(
        movie_id=uuid.uuid4(),
        title=title,
        year=1998,
        tmdb_id=777,
        votes=votes,
        replaced_titles=replaced_titles,
        groupings=groupings,
    )


def _found(*shows: tuple[str, int]) -> TvSearchResults:
    return TvSearchResults(
        results=[
            TvSearchResult(id=4000 + i, name=name, vote_count=votes, first_air_date="2001-09-09")
            for i, (name, votes) in enumerate(shows)
        ]
    )


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


def test_a_far_better_known_series_of_the_same_title_is_a_suspect() -> None:
    suspect = judge(
        _film("Band of Brothers", 3), _found(("Brothers", 900), ("Band of Brothers", 4100))
    )

    assert suspect is not None
    assert (suspect.series.name, suspect.series.vote_count) == ("Band of Brothers", 4100)
    assert suspect.reasons == ("TMDB's series has 4,100 votes; the film it was matched to has 3.",)


def test_a_film_better_known_than_its_namesake_series_is_left_alone() -> None:
    assert judge(_film("Fargo", 7000), _found(("Fargo", 4000))) is None
    # Known at all: a series with a handful of votes says nothing.
    assert judge(_film("Obscure", 1), _found(("Obscure", 40))) is None
    # Only the same title counts, not a longer one that contains it.
    assert judge(_film("Brothers", 2), _found(("Band of Brothers", 4100))) is None


def test_a_tv_grouping_or_a_series_spreadsheet_title_is_enough_alone() -> None:
    grouped = judge(_film("Broadchurch", 900, groupings=("TV",)), _found(("Broadchurch", 1200)))
    assert grouped is not None
    assert grouped.reasons == ("Craig grouped it under 'TV'.",)

    replaced = judge(
        _film("11.22.63", 900, replaced_titles=("11.22.63 (Complete Series)",)),
        _found(("11.22.63", 1000)),
    )
    assert replaced is not None
    assert replaced.reasons == (
        "Its spreadsheet title, '11.22.63 (Complete Series)': 'Complete Series' in the title.",
    )


class FakeSeriesSearch:
    def __init__(self, answers: dict[str, TvSearchResults], failing: set[str]) -> None:
        self.answers, self.failing = answers, failing
        self.asked: list[str] = []

    async def search_tv(self, query: str) -> TvSearchResults:
        self.asked.append(query)
        if query in self.failing:
            raise httpx.ConnectError("TMDB is down")
        return self.answers.get(query, TvSearchResults())


async def test_the_check_asks_for_each_title_notes_failures_and_puts_the_strongest_first() -> None:
    films = [
        _film("Band of Brothers", 3),
        _film("The Pacific", 20, groupings=("TV",)),
        _film("Down", 5),
        _film("Fargo", 7000),
    ]
    tmdb = FakeSeriesSearch(
        {
            "Band of Brothers": _found(("Band of Brothers", 4100)),
            "The Pacific": _found(("The Pacific", 2000)),
            "Fargo": _found(("Fargo", 4000)),
        },
        failing={"Down"},
    )

    result = await check(films, tmdb)

    assert tmdb.asked == ["Band of Brothers", "The Pacific", "Down", "Fargo"]
    assert (result.looked_at, result.failed) == (3, ["Down"])
    # Two reasons outrank one; then the larger gap in votes.
    assert [s.film.title for s in result.suspects] == ["The Pacific", "Band of Brothers"]


def test_the_report_links_each_films_page_and_escapes_what_it_prints() -> None:
    film = _film("Band <of> Brothers", 3)
    series = TvSearchResult(id=4613, name="Band of Brothers", vote_count=4100)
    result = CheckResult(
        looked_at=1, suspects=[Suspect(film, series, ("A <b>reason</b>.",))], failed=[]
    )

    page = render_html(result, app_url="https://mcu.example/")
    sheet = render_csv(result, app_url="https://mcu.example")

    assert f"https://mcu.example/movies/{film.movie_id}" in page
    assert "https://www.themoviedb.org/tv/4613" in page
    assert "Band &lt;of&gt; Brothers" in page and "A &lt;b&gt;reason&lt;/b&gt;." in page
    assert "Nothing here has been changed." in page
    assert sheet.splitlines()[0].startswith("film page,title,film year,film votes,series")
    assert f"https://mcu.example/movies/{film.movie_id}" in sheet


def test_rows_read_over_https_are_postgres_text_and_are_read_as_such() -> None:
    movie_id = str(uuid.uuid4())
    films = assemble(
        [[movie_id, "Band of Brothers", "1998", "777", None]],
        [[movie_id, "Band of Brothers (Complete Series)"]],
        [[movie_id, "TV"]],
    )

    assert films == [
        IdentifiedFilm(
            movie_id=uuid.UUID(movie_id),
            title="Band of Brothers",
            year=1998,
            tmdb_id=777,
            votes=0,
            replaced_titles=("Band of Brothers (Complete Series)",),
            groupings=("TV",),
        )
    ]


# ---------------------------------------------------------------------------
# The reads, against Postgres
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _movie(
    db: AsyncSession, title: str, *, tmdb_id: int | None, grouping: str | None = None
) -> Movie:
    movie = Movie(id=uuid.uuid4(), tmdb_id=tmdb_id, title=title, original_title=title)
    db.add(movie)
    await db.flush()
    db.add(
        CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["dvd"], sub_category=grouping)
    )
    await db.flush()
    return movie


async def test_the_reads_take_identified_films_on_the_shelf_and_https_sends_the_same(
    db: AsyncSession,
) -> None:
    base = 7_000_000 + uuid.uuid4().int % 900_000
    film = await _movie(db, "Y3 Band of Brothers", tmdb_id=base, grouping="TV")
    db.add(MovieTitleAlias(id=uuid.uuid4(), movie_id=film.id, title="Y3 BoB (Complete Series)"))
    series = await _movie(db, "Y3 A Series Already", tmdb_id=None)
    series.tmdb_tv_id = base + 1
    trashed = await _movie(db, "Y3 In The Trash", tmdb_id=base + 2)
    trashed.deleted_at = utcnow()
    unmatched = await _movie(db, "Y3 Not Matched", tmdb_id=None)
    shelfless = Movie(id=uuid.uuid4(), tmdb_id=base + 3, title="Y3 No Disc", original_title="x")
    db.add(shelfless)
    await db.flush()

    films = assemble(
        (await db.execute(films_query())).all(),
        (await db.execute(replaced_titles_query())).all(),
        (await db.execute(groupings_query())).all(),
    )
    mine = {f.movie_id: f for f in films if f.title.startswith("Y3 ")}

    assert set(mine) == {film.id}
    assert mine[film.id].replaced_titles == ("Y3 BoB (Complete Series)",)
    assert mine[film.id].groupings == ("TV",)
    assert {series.id, trashed.id, unmatched.id, shelfless.id}.isdisjoint(mine)

    # The HTTPS path sends each query as one statement, values written in: the same rows.
    for query in (films_query(), replaced_titles_query(), groupings_query()):
        through_text = (await db.execute(text(as_sql(query)))).all()
        assert sorted(map(tuple, through_text), key=str) == sorted(
            map(tuple, (await db.execute(query)).all()), key=str
        )
