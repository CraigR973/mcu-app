"""The series pass — Batch Y3, at Craig's word on 15 Oct.

**What this proves:** the rule proposes a series only where TMDB leaves no doubt (one series of
that title, or one far better known than the rest, its first-air year agreeing with any year the
title gives), searching with the title a series is sold under; everything else is left for Mark
with what TMDB offered. A title TMDB fails on is noted. The plan survives its file, and one of
another version is refused. Against Postgres, the dry run reads exactly "Still to identify" on
the shelf, set-aside series included and "not a film" left out; the live run identifies a title
as planned (audited ``auto`` with its evidence), leaves alone one changed since, never merges,
and reports TMDB's failure without writing.

**What it does not:** TMDB. Its answers are stand-ins in TMDB's published shape (#273).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyLookup
from src.models.movie import Movie
from src.services.identify.series_pass import (
    Proposal,
    SeriesPlan,
    Waiting,
    apply_one,
    dry_run,
    propose,
    read_waiting,
    render_report,
)
from src.tmdb.models import Genre, TvSearchResult, TvSearchResults, TvShow


def _waiting(title: str, grouping: str | None = None) -> Waiting:
    return Waiting(movie_id=uuid.uuid4(), title=title, grouping=grouping)


def _found(*shows: tuple[int, str, str, int]) -> TvSearchResults:
    return TvSearchResults(
        results=[
            TvSearchResult(id=tv_id, name=name, first_air_date=aired, vote_count=votes)
            for tv_id, name, aired, votes in shows
        ]
    )


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


def test_one_series_of_the_title_is_identified_searching_as_a_series_is_sold() -> None:
    proposal = propose(
        _waiting("Broadchurch Series 1 - 3"),
        _found((1001, "Broadchurch", "2013-03-04", 1500), (7, "Church", "1990-01-01", 9)),
    )

    assert proposal.query == "Broadchurch"
    assert (proposal.outcome, proposal.tmdb_tv_id, proposal.series_year) == ("identify", 1001, 2013)
    assert proposal.reason == "TMDB has one series called 'Broadchurch'."


def test_one_series_far_better_known_than_its_namesakes_is_identified() -> None:
    proposal = propose(
        _waiting("Band of Brothers (Complete Series)"),
        _found(
            (4613, "Band of Brothers", "2001-09-09", 4100),
            (88, "Band of Brothers", "2019-01-01", 30),
        ),
    )

    assert (proposal.outcome, proposal.tmdb_tv_id) == ("identify", 4613)
    assert [o["tmdb_tv_id"] for o in proposal.offered] == [88]


def test_namesakes_alike_or_no_series_at_all_are_left_for_mark() -> None:
    alike = propose(
        _waiting("The Office"),
        _found((2996, "The Office", "2005-03-24", 3800), (2995, "The Office", "2001-07-09", 1500)),
    )
    assert alike.outcome == "ask"
    assert alike.reason == "TMDB has 2 series called 'The Office', none far better known."
    assert {o["tmdb_tv_id"] for o in alike.offered} == {2995, 2996}

    nothing = propose(_waiting("A Quiet Film"), _found((5, "Quiet Riot", "2010-01-01", 3)))
    assert nothing.outcome == "ask"
    assert "may be a film" in nothing.reason


def test_a_year_in_the_title_must_agree_with_the_series() -> None:
    dated = propose(
        _waiting("Office, The (2001)"),
        _found((2996, "The Office", "2005-03-24", 3800), (2995, "The Office", "2001-07-09", 1500)),
    )
    assert (dated.outcome, dated.tmdb_tv_id) == ("identify", 2995)

    wrong = propose(_waiting("Dynasties (1990)"), _found((80, "Dynasties", "2018-11-11", 300)))
    assert wrong.outcome == "ask"
    assert wrong.reason == "TMDB's series called 'Dynasties' did not start in or near 1990."


class FakeTmdb:
    def __init__(self, found: dict[str, TvSearchResults], *, failing: set[str]) -> None:
        self.found, self.failing = found, failing
        self.searched: list[str] = []

    async def search_tv(self, query: str) -> TvSearchResults:
        self.searched.append(query)
        if query in self.failing:
            raise httpx.ConnectError("TMDB is down")
        return self.found.get(query, TvSearchResults())

    async def get_tv_full(self, tv_id: int) -> TvShow:
        if tv_id in {int(q) for q in self.failing if q.isdigit()}:
            raise httpx.ConnectError("TMDB is down")
        return TvShow(
            id=tv_id,
            name="Broadchurch",
            first_air_date="2013-03-04",
            overview="A boy is found dead.",
            vote_count=1500,
            genres=[Genre(id=80, name="Crime")],
        )


async def test_the_dry_run_notes_a_title_tmdb_fails_on_and_keeps_its_plan(tmp_path: Path) -> None:
    tmdb = FakeTmdb(
        {"Broadchurch": _found((1001, "Broadchurch", "2013-03-04", 1500))}, failing={"Dynasties"}
    )
    plan = await dry_run(
        [_waiting("Broadchurch Series 1 - 3"), _waiting("Dynasties")],
        tmdb,
        now=datetime(2026, 10, 15, 19, tzinfo=UTC),
    )

    assert tmdb.searched == ["Broadchurch", "Dynasties"]
    assert (plan.count("identify"), plan.failed) == (1, ["Dynasties"])

    path = tmp_path / "series-plan.json"
    plan.save(path)
    assert SeriesPlan.load(path) == plan
    path.write_text(path.read_text().replace('"version": 1', '"version": 0'))
    with pytest.raises(ValueError, match="version 0"):
        SeriesPlan.load(path)


def test_the_report_lists_both_kinds_links_each_page_and_escapes() -> None:
    sure = Proposal(
        movie_id=str(uuid.uuid4()),
        title="Broadchurch <S1-3>",
        query="Broadchurch",
        outcome="identify",
        reason="TMDB has one series called 'Broadchurch'.",
        tmdb_tv_id=1001,
        series="Broadchurch",
        series_year=2013,
        votes=1500,
        set_aside_as="tv",
    )
    ask = Proposal(
        movie_id=str(uuid.uuid4()),
        title="The Office",
        query="The Office",
        outcome="ask",
        reason="TMDB has 2 series called 'The Office', none far better known.",
        offered=[{"tmdb_tv_id": 2995, "name": "The Office", "year": 2001, "votes": 1500}],
    )
    page = render_report(
        SeriesPlan(made_utc="2026-10-15T19:00:00", proposals=[sure, ask]),
        app_url="https://mcu.example/",
    )

    assert "Will be identified (1)" in page and "Left for Mark (1)" in page
    assert f"https://mcu.example/movies/{sure.movie_id}" in page
    assert "https://www.themoviedb.org/tv/2995" in page
    assert "Broadchurch &lt;S1-3&gt;" in page and "(set aside as TV)" in page


# ---------------------------------------------------------------------------
# Against Postgres
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


async def _title(
    db: AsyncSession, title: str, *, grouping: str | None = None, shelf: bool = True
) -> Movie:
    movie = Movie(id=uuid.uuid4(), title=title, original_title=title)
    db.add(movie)
    await db.flush()
    if shelf:
        db.add(
            CollectionItem(
                id=uuid.uuid4(), movie_id=movie.id, formats=["dvd"], sub_category=grouping
            )
        )
        await db.flush()
    return movie


def _aside(movie: Movie, kind: str) -> IdentifyLookup:
    return IdentifyLookup(
        id=uuid.uuid4(), movie_id=movie.id, status="set_aside", set_aside_as=kind, candidates=[]
    )


async def test_the_dry_run_reads_exactly_still_to_identify_on_the_shelf(db: AsyncSession) -> None:
    base = 6_000_000 + uuid.uuid4().int % 900_000
    plain = await _title(db, "Y3P Line of Duty - Series 1-6", grouping="TV")
    series_aside = await _title(db, "Y3P Broadchurch")
    concert = await _title(db, "Y3P A Concert")
    db.add_all([_aside(series_aside, "tv"), _aside(concert, "not_film")])
    film = await _title(db, "Y3P A Film")
    film.tmdb_id = base
    series = await _title(db, "Y3P A Series")
    series.tmdb_tv_id = base
    trashed = await _title(db, "Y3P Trashed")
    trashed.deleted_at = utcnow()
    await _title(db, "Y3P No Disc", shelf=False)
    await db.flush()

    mine = {w.title: w for w in await read_waiting(db) if w.title.startswith("Y3P ")}

    assert set(mine) == {"Y3P Line of Duty - Series 1-6", "Y3P Broadchurch"}
    assert mine["Y3P Broadchurch"].set_aside_as == "tv"
    assert mine["Y3P Line of Duty - Series 1-6"].grouping == "TV"
    assert mine["Y3P Line of Duty - Series 1-6"].movie_id == plain.id


def _planned(movie: Movie, tv_id: int) -> Proposal:
    return Proposal(
        movie_id=str(movie.id),
        title=movie.title,
        query="Broadchurch",
        outcome="identify",
        reason="TMDB has one series called 'Broadchurch'.",
        tmdb_tv_id=tv_id,
        series="Broadchurch",
    )


async def test_the_live_run_identifies_as_planned_and_leaves_anything_else(
    db: AsyncSession,
) -> None:
    tv_id = 5_000_000 + uuid.uuid4().int % 900_000
    planned = await _title(db, "Y3P Broadchurch Series 1 - 3")
    db.add(_aside(planned, "tv"))
    renamed = await _title(db, "Y3P Renamed Since")
    holder = await _title(db, "Y3P Already Holds It")
    holder.tmdb_tv_id = tv_id + 1
    duplicate = await _title(db, "Y3P Second Copy")
    failing = await _title(db, "Y3P TMDB Fails")
    await db.commit()
    tmdb = FakeTmdb({}, failing={str(tv_id + 2)})

    # The plan is made before anything runs, as the dry run's is: a rollback below expires rows.
    stale = _planned(renamed, tv_id + 3)
    stale.title = "Y3P What The Dry Run Saw"
    proposals = [
        _planned(planned, tv_id),
        stale,
        _planned(duplicate, tv_id + 1),
        _planned(failing, tv_id + 2),
    ]

    done, left, waits, failed = [await apply_one(db, tmdb, p) for p in proposals]

    assert (done.result, left.result, waits.result, failed.result) == (
        "identified",
        "unchanged",
        "waits",
        "failed",
    )
    assert waits.note == "'Y3P Already Holds It' already holds the series."
    await db.refresh(planned)
    assert (planned.tmdb_tv_id, planned.tmdb_id, planned.title) == (tv_id, None, "Broadchurch")
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == planned.id))
    assert lookup is not None
    assert (lookup.status, lookup.how, lookup.media_type) == ("identified", "auto", "tv")
    audit = await db.scalar(select(AdminAction).where(AdminAction.target_id == str(planned.id)))
    assert audit is not None
    assert audit.changes["how"] == "auto"
    assert audit.changes["evidence"][0] == "TMDB has one series called 'Broadchurch'."
    for untouched in (renamed, duplicate, failing):
        await db.refresh(untouched)
        assert (untouched.tmdb_id, untouched.tmdb_tv_id) == (None, None)
