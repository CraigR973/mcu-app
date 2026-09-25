"""Identifying the unmatched films against Postgres — Batch T9. These run in CI.

**What this proves:** an identification is audited with the title it replaced, keeps that
title as an alias, and can be undone; a merge carries everything that points at a film —
discs, watches, wanted rows, movie-night suggestions and votes, calendar entries, barcode
lookups and deals — drops a duplicate vote rather than failing, never lands on a film in the
Trash, and is undone row for row; the live run applies a plan film by film, leaves alone a
film that changed after the dry run, queues rather than merges when the collection gained
the film since, and records the dry run's Brave searches where T7's ceiling counts them;
the dry run writes nothing; the Identify films page's routes do what their buttons say and
only for an admin; a valuation taken before an identification falls due; T7's second look
reconsiders a disc whose film has gained a year; and the refresh importer finds a film by the
title identification replaced.

**What it does not:** TMDB or Brave. The matcher's decisions are ``test_identify_matcher.py``.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.ebay.pricing import ASKING_PRICES
from src.main import app
from src.models.admin_action import AdminAction
from src.models.barcode import BarcodeLookup
from src.models.collection_item import CollectionItem
from src.models.deal import Deal
from src.models.identify import IdentifyLookup, IdentifyRun, MovieTitleAlias
from src.models.movie import Movie
from src.models.movie_night import MovieNightSession, MovieNightSuggestion, MovieNightVote
from src.models.profile import Profile, UserRole
from src.models.release_calendar import ReleaseCalendarEntry
from src.models.specs_backfill import SpecCandidate, SpecLookup, SpecRun
from src.models.valuation import DiscValuation
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.routers.movies import get_tmdb_client
from src.scripts.import_collection import LiveFilmIndex
from src.services.identification import (
    IdentifyError,
    MergeNeeded,
    identify_film,
    undo_identification,
)
from src.services.identify.apply import apply_plan, start_run
from src.services.identify.matcher import Identifier, Proposal
from src.services.identify.plan import (
    PLAN_VERSION,
    Disc,
    Item,
    MergeTarget,
    Offered,
    Plan,
    make_plan,
)
from src.services.specs import backfill
from src.services.valuation import count_due
from src.tmdb.models import CastMember, Credits, CrewMember, SearchResults
from src.tmdb.models import Movie as TmdbMovie

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 9, 25, 12, 0)


def _record(tmdb_id: int, title: str, year: int, *, director: str = "A Director") -> TmdbMovie:
    return TmdbMovie(
        id=tmdb_id,
        title=title,
        original_title=title,
        overview=f"{title}, as TMDB describes it.",
        release_date=f"{year}-06-01",
        runtime=101,
        vote_count=500,
        vote_average=7.1,
        credits=Credits(
            cast=[
                CastMember(id=1, name="A Star", character="Lead", order=0, credit_id="c1"),
            ],
            crew=[
                CrewMember(
                    id=2, name=director, job="Director", department="Directing", credit_id="d1"
                ),
            ],
        ),
    )


class FakeTmdb:
    """TMDB's full records, by id. Counts the fetches; searches find nothing."""

    def __init__(self, records: dict[int, TmdbMovie]) -> None:
        self.records = records
        self.fetched: list[int] = []

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        del language
        self.fetched.append(movie_id)
        return self.records[movie_id]

    async def search_movie(
        self,
        query: str,
        year: int | None = None,
        page: int = 1,
        language: str = "en-US",
        include_adult: bool = False,
    ) -> SearchResults:
        del query, year, page, language, include_adult
        return SearchResults()


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


async def _person(db: AsyncSession, role: UserRole = UserRole.admin) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"T9 {role.value} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=role,
    )
    db.add(profile)
    await db.flush()
    return profile


async def _film(
    db: AsyncSession, title: str, *, tmdb_id: int | None = None, year: int | None = None
) -> Movie:
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=year,
        media_type="film",
    )
    db.add(film)
    await db.flush()
    return film


async def _disc(db: AsyncSession, film: Movie, *formats: str, **fields: Any) -> CollectionItem:
    disc = CollectionItem(
        id=uuid.uuid4(), movie_id=film.id, formats=list(formats or ["blu_ray"]), **fields
    )
    db.add(disc)
    await db.flush()
    return disc


def _tmdb_ids() -> tuple[int, int, int]:
    """TMDB ids no other test uses, so the unique index cannot collide."""
    base = 9_000_000 + uuid.uuid4().int % 900_000
    return base, base + 1, base + 2


async def _audits(db: AsyncSession, film: Movie) -> list[AdminAction]:
    return list(
        (
            await db.scalars(
                select(AdminAction)
                .where(AdminAction.target_table == "movies", AdminAction.target_id == str(film.id))
                .order_by(AdminAction.created_at)
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# One identification, audited and undone
# ---------------------------------------------------------------------------


async def test_an_identification_is_audited_keeps_its_old_title_and_can_be_undone(
    db: AsyncSession,
) -> None:
    craig = await _person(db)
    tmdb_id, _, _ = _tmdb_ids()
    film = await _film(db, "Peepiing Tom")
    await _disc(db, film, "dvd")

    done = await identify_film(
        db, film, _record(tmdb_id, "Peeping Tom", 1960), by=craig.id, how="picked"
    )

    assert done.merged is False
    assert done.film.id == film.id
    assert (film.title, film.year, film.tmdb_id) == ("Peeping Tom", 1960, tmdb_id)
    alias = await db.scalar(select(MovieTitleAlias).where(MovieTitleAlias.movie_id == film.id))
    assert alias is not None and alias.title == "Peepiing Tom"
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == film.id))
    assert lookup is not None
    assert (lookup.status, lookup.how, lookup.replaced_title) == (
        "identified",
        "picked",
        "Peepiing Tom",
    )
    (audit,) = await _audits(db, film)
    assert audit.user_id == craig.id
    assert audit.changes is not None
    assert audit.changes["title"] == {"from": "Peepiing Tom", "to": "Peeping Tom"}

    restored = await undo_identification(db, audit.id, by=craig.id)

    assert restored.id == film.id
    assert (film.title, film.year, film.tmdb_id) == ("Peepiing Tom", None, None)
    assert (
        await db.scalar(select(MovieTitleAlias).where(MovieTitleAlias.movie_id == film.id))
    ) is None
    assert lookup.status == "needs_you"
    # One transaction, so both rows carry the same timestamp: compare them as a set.
    assert sorted(a.changes["kind"] for a in await _audits(db, film) if a.changes) == [
        "identify",
        "undo_identify",
    ]
    with pytest.raises(IdentifyError):
        await undo_identification(db, audit.id, by=craig.id)


# ---------------------------------------------------------------------------
# Merges
# ---------------------------------------------------------------------------


async def _night(db: AsyncSession, host: Profile) -> MovieNightSession:
    night = MovieNightSession(id=uuid.uuid4(), created_by=host.id, filters={}, status="open")
    db.add(night)
    await db.flush()
    return night


async def test_a_merge_moves_everything_that_points_at_the_film_and_undoes_row_for_row(
    db: AsyncSession,
) -> None:
    craig = await _person(db)
    mark = await _person(db, UserRole.viewer)
    tmdb_id, _, _ = _tmdb_ids()
    kept = await _film(db, "Misery", tmdb_id=tmdb_id, year=1990)
    loose = await _film(db, "Misery (the other row)")
    shelf = await _disc(db, loose, "blu_ray")
    binned = await _disc(db, loose, "dvd", deleted_at=NOW)
    watch = WatchLog(
        id=uuid.uuid4(), movie_id=loose.id, user_id=craig.id, watched_at=date(2026, 9, 1)
    )
    wanted = WantedItem(id=uuid.uuid4(), movie_id=loose.id)
    db.add_all([watch, wanted])
    night = await _night(db, craig)
    kept_suggestion = MovieNightSuggestion(
        id=uuid.uuid4(), session_id=night.id, movie_id=kept.id, title="Misery"
    )
    loose_suggestion = MovieNightSuggestion(
        id=uuid.uuid4(), session_id=night.id, movie_id=loose.id, title="Misery (the other row)"
    )
    db.add_all([kept_suggestion, loose_suggestion])
    await db.flush()
    craig_on_kept = MovieNightVote(
        id=uuid.uuid4(), session_id=night.id, user_id=craig.id, movie_id=kept.id, liked=True
    )
    craig_on_loose = MovieNightVote(
        id=uuid.uuid4(),
        session_id=night.id,
        user_id=craig.id,
        movie_id=loose.id,
        suggestion_id=loose_suggestion.id,
        liked=False,
    )
    mark_on_loose = MovieNightVote(
        id=uuid.uuid4(),
        session_id=night.id,
        user_id=mark.id,
        movie_id=loose.id,
        suggestion_id=loose_suggestion.id,
        liked=True,
    )
    release = ReleaseCalendarEntry(
        id=uuid.uuid4(),
        movie_id=loose.id,
        title="Misery",
        release_type="4k_uhd_release",
        release_date=date(2026, 11, 1),
    )
    code = BarcodeLookup(
        id=uuid.uuid4(),
        barcode=f"50{uuid.uuid4().int % 10**11:011d}",
        movie_id=loose.id,
        title="Misery",
        source="manual",
    )
    deal = Deal(
        id=uuid.uuid4(),
        movie_id=loose.id,
        retailer_name_snapshot="A shop",
        title_snapshot="Misery 4K",
        url=f"https://example.com/misery/{uuid.uuid4().hex}",
        price=Decimal("9.99"),
    )
    db.add_all([craig_on_kept, craig_on_loose, mark_on_loose, release, code, deal])
    await db.flush()

    with pytest.raises(MergeNeeded):
        await identify_film(db, loose, _record(tmdb_id, "Misery", 1990), by=craig.id, how="picked")

    done = await identify_film(
        db, loose, _record(tmdb_id, "Misery", 1990), by=craig.id, how="picked", allow_merge=True
    )

    assert done.merged is True and done.film.id == kept.id
    assert await db.get(Movie, loose.id) is None
    for model, row_id in (
        (CollectionItem, shelf.id),
        (CollectionItem, binned.id),
        (WatchLog, watch.id),
        (WantedItem, wanted.id),
        (ReleaseCalendarEntry, release.id),
        (BarcodeLookup, code.id),
        (Deal, deal.id),
        (MovieNightVote, mark_on_loose.id),
    ):
        moved = await db.scalar(select(model.movie_id).where(model.id == row_id))
        assert moved == kept.id, model.__tablename__
    # Craig's second vote on the same film in the same night is the duplicate; his first stands.
    assert await db.get(MovieNightVote, craig_on_loose.id) is None
    assert await db.get(MovieNightVote, craig_on_kept.id) is not None
    # The same night's second suggestion of the film goes, and Mark's vote joins the first.
    assert await db.get(MovieNightSuggestion, loose_suggestion.id) is None
    assert (
        await db.scalar(
            select(MovieNightVote.suggestion_id).where(MovieNightVote.id == mark_on_loose.id)
        )
        == kept_suggestion.id
    )
    alias = await db.scalar(
        select(MovieTitleAlias.title).where(MovieTitleAlias.movie_id == kept.id)
    )
    assert alias == "Misery (the other row)"

    (audit,) = [a for a in await _audits(db, kept) if a.changes and a.changes["kind"] == "identify"]
    restored = await undo_identification(db, audit.id, by=craig.id)

    assert restored.id == loose.id
    assert restored.title == "Misery (the other row)" and restored.tmdb_id is None
    for model, row_id in (
        (CollectionItem, shelf.id),
        (CollectionItem, binned.id),
        (WatchLog, watch.id),
        (WantedItem, wanted.id),
        (ReleaseCalendarEntry, release.id),
        (BarcodeLookup, code.id),
        (Deal, deal.id),
        (MovieNightVote, mark_on_loose.id),
    ):
        back = await db.scalar(select(model.movie_id).where(model.id == row_id))
        assert back == loose.id, model.__tablename__
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == loose.id))
    assert lookup is not None and lookup.status == "needs_you"


async def test_nothing_merges_into_a_film_in_the_trash(db: AsyncSession) -> None:
    craig = await _person(db)
    tmdb_id, _, _ = _tmdb_ids()
    trashed = await _film(db, "Halloween", tmdb_id=tmdb_id, year=1978)
    trashed.deleted_at = NOW
    loose = await _film(db, "Halloween")
    await _disc(db, loose)
    await db.flush()

    with pytest.raises(IdentifyError, match="Trash"):
        await identify_film(
            db,
            loose,
            _record(tmdb_id, "Halloween", 1978),
            by=craig.id,
            how="picked",
            allow_merge=True,
        )


# ---------------------------------------------------------------------------
# The dry run and the live run
# ---------------------------------------------------------------------------


class _NoTmdb:
    """A dry run whose answers are scripted asks TMDB nothing."""


class _Scripted(Identifier):
    """The matcher's answers, fixed per title, so the plan's bookkeeping is what is tested."""

    def __init__(self, answers: dict[str, Proposal]) -> None:
        super().__init__(_NoTmdb())
        self.answers = answers

    async def identify(self, parsed: Any, *, held: Any = None) -> Proposal:
        return self.answers.get(parsed.raw, Proposal("ask", reason="Not scripted."))


async def test_the_dry_run_writes_nothing(db: AsyncSession) -> None:
    film = await _film(db, "Dry Run Film")
    await _disc(db, film)
    before = [
        await db.scalar(select(func.count()).select_from(model))
        for model in (Movie, IdentifyLookup, AdminAction, MovieTitleAlias)
    ]

    plan = await make_plan(db, _Scripted({}), now=NOW, only={"Dry Run Film"})

    after = [
        await db.scalar(select(func.count()).select_from(model))
        for model in (Movie, IdentifyLookup, AdminAction, MovieTitleAlias)
    ]
    assert before == after
    assert [item.title for item in plan.items] == ["Dry Run Film"]
    assert Plan.from_dict(json.loads(plan.to_json())).items[0].title == "Dry Run Film"


def _item(film: Movie, outcome: str, **fields: Any) -> Item:
    return Item(
        movie_id=str(film.id),
        title=film.title,
        discs=[Disc("blu_ray", None, "Front")],
        watches=0,
        outcome=outcome,
        **fields,
    )


def _offered(tmdb_id: int, title: str, year: int) -> Offered:
    return Offered(
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        poster_path=None,
        overview="",
        votes=10,
        origin="search",
        notes=["A note"],
    )


async def test_the_live_run_applies_the_plan_film_by_film(db: AsyncSession) -> None:
    first, second, third = _tmdb_ids()
    typo = await _film(db, "Colditz Sory, the")
    doubtful = await _film(db, "Argo")
    series = await _film(db, "Dynasties")
    renamed = await _film(db, "Renamed Since")
    gained = await _film(db, "Gained Since")
    for film in (typo, doubtful, series, renamed, gained):
        await _disc(db, film)
    await _film(db, "The Gained Film", tmdb_id=third, year=2001)
    plan = Plan(
        version=PLAN_VERSION,
        made_utc=NOW.isoformat(),
        films=5,
        tmdb_calls=40,
        brave_searches=3,
        brave_budget=60,
        items=[
            _item(
                typo,
                "identify",
                chosen=_offered(first, "The Colditz Story", 1955),
                evidence=["The title matches, allowing for a typo."],
            ),
            _item(
                doubtful,
                "ask",
                reason="TMDB holds another film of this title (2004).",
                chosen=_offered(second, "Argo", 2012),
                candidates=[_offered(second, "Argo", 2012)],
            ),
            _item(series, "set_aside", set_aside_as="tv", reason="A TV series."),
            _item(renamed, "identify", chosen=_offered(first, "The Colditz Story", 1955)),
            _item(gained, "identify", chosen=_offered(third, "The Gained Film", 2001)),
        ],
    )
    plan.items[3].title = "The Title The Dry Run Saw"
    tmdb = FakeTmdb(
        {
            first: _record(first, "The Colditz Story", 1955),
            third: _record(third, "The Gained Film", 2001),
        }
    )

    run = await start_run(db, plan)
    run = await apply_plan(db, plan, tmdb, run=run, clock=lambda: NOW)

    assert (run.status, run.identified, run.queued, run.set_aside, run.unchanged, run.failed) == (
        "finished",
        1,
        2,
        1,
        1,
        0,
    )
    assert run.searches == 3
    assert (typo.title, typo.tmdb_id) == ("The Colditz Story", first)
    asked = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == doubtful.id))
    assert asked is not None and asked.status == "needs_you"
    assert asked.candidates[0]["tmdb_id"] == second
    assert asked.proposed_tmdb_id == second
    aside = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == series.id))
    assert aside is not None and aside.set_aside_as == "tv"
    assert series.is_tv is True and series.media_type == "tv"
    assert renamed.tmdb_id is None
    waiting = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == gained.id))
    assert waiting is not None and waiting.status == "needs_you"
    assert "merges the two" in (waiting.note or "")
    assert gained.tmdb_id is None
    # The dry run's Brave searches now count against the ceiling T7's batches share.
    assert await backfill.searches_this_month(db, now=NOW) >= 3


# ---------------------------------------------------------------------------
# The Identify films page
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def page(db: AsyncSession) -> AsyncIterator[tuple[AsyncClient, Profile, FakeTmdb]]:
    craig = await _person(db)
    tmdb = FakeTmdb({})

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return craig

    async def override_tmdb() -> AsyncIterator[FakeTmdb]:
        yield tmdb

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, craig, tmdb


async def test_the_page_offers_each_waiting_film_with_what_a_choice_would_merge_into(
    db: AsyncSession, page: tuple[AsyncClient, Profile, FakeTmdb]
) -> None:
    client, _craig, _tmdb = page
    tmdb_id, other, _ = _tmdb_ids()
    held = await _film(db, "Dunkirk", tmdb_id=tmdb_id, year=1958)
    await _disc(db, held, "dvd")
    waiting = await _film(db, "Dunkirk (4K row)")
    await _disc(db, waiting, "4k_uhd", sub_category="War", location="Front")
    db.add(
        IdentifyLookup(
            id=uuid.uuid4(),
            movie_id=waiting.id,
            status="needs_you",
            note="TMDB holds another film of this title (1958).",
            candidates=[
                {"tmdb_id": other, "title": "Dunkirk", "year": 2017, "votes": 18000, "notes": []},
                {"tmdb_id": tmdb_id, "title": "Dunkirk", "year": 1958, "votes": 77, "notes": []},
            ],
            proposed_tmdb_id=other,
        )
    )
    await db.commit()

    response = await client.get("/api/v1/identify/queue", params={"limit": 50})

    assert response.status_code == 200
    (entry,) = [item for item in response.json()["items"] if item["movieId"] == str(waiting.id)]
    assert entry["discs"] == [{"label": "4K · War · Front"}]
    assert entry["proposedTmdbId"] == other
    first, second = entry["candidates"]
    assert first["inCollection"] is None
    assert second["inCollection"]["movieId"] == str(held.id)
    assert second["inCollection"]["discs"] == 1


async def test_a_choice_that_merges_needs_saying_so(
    db: AsyncSession, page: tuple[AsyncClient, Profile, FakeTmdb]
) -> None:
    client, _craig, tmdb = page
    tmdb_id, _, _ = _tmdb_ids()
    tmdb.records[tmdb_id] = _record(tmdb_id, "Goodbye, Mr. Chips", 1939)
    held = await _film(db, "Goodbye, Mr. Chips", tmdb_id=tmdb_id, year=1939)
    waiting = await _film(db, "Goodbye Mr Chips")
    await _disc(db, waiting, "dvd")
    # A refusal rolls the route's work back; the films must be committed to survive it, and
    # their ids taken now, because the rollback expires every object this session holds.
    await db.commit()
    waiting_id, held_id = waiting.id, held.id

    refused = await client.post(
        f"/api/v1/identify/films/{waiting_id}/identify", json={"tmdbId": tmdb_id}
    )
    assert refused.status_code == 409
    assert "merges" in refused.json()["detail"]

    merged = await client.post(
        f"/api/v1/identify/films/{waiting_id}/identify", json={"tmdbId": tmdb_id, "merge": True}
    )
    assert merged.status_code == 200
    assert merged.json() == {
        "movieId": str(held_id),
        "outcome": "merged",
        "title": "Goodbye, Mr. Chips",
    }


async def test_set_aside_skip_put_back_and_undo_are_one_tap_each(
    db: AsyncSession, page: tuple[AsyncClient, Profile, FakeTmdb]
) -> None:
    client, _craig, tmdb = page
    tmdb_id, _, _ = _tmdb_ids()
    tmdb.records[tmdb_id] = _record(tmdb_id, "The Titfield Thunderbolt", 1953)
    series = await _film(db, "Wild China")
    skipped = await _film(db, "Munch - Our Greatest Hits")
    typo = await _film(db, "Titfield Thuderbolt, The")
    for film in (series, skipped, typo):
        await _disc(db, film)
    await db.commit()

    assert (
        await client.post(f"/api/v1/identify/films/{series.id}/set-aside", json={"kind": "tv"})
    ).status_code == 200
    assert (await client.post(f"/api/v1/identify/films/{skipped.id}/skip")).status_code == 200
    assert series.is_tv is True
    overview = (await client.get("/api/v1/identify/overview")).json()
    assert overview["setAsideTv"] >= 1 and overview["skipped"] >= 1

    assert (await client.post(f"/api/v1/identify/films/{series.id}/put-back")).status_code == 200
    assert series.is_tv is False and series.media_type == "film"

    picked = await client.post(
        f"/api/v1/identify/films/{typo.id}/identify", json={"tmdbId": tmdb_id}
    )
    assert picked.status_code == 200 and picked.json()["outcome"] == "identified"
    recent = (await client.get("/api/v1/identify/recent")).json()["items"]
    (entry,) = [item for item in recent if item["movieId"] == str(typo.id)]
    assert (entry["replaced"], entry["title"], entry["undone"]) == (
        "Titfield Thuderbolt, The",
        "The Titfield Thunderbolt",
        False,
    )
    undone = await client.post(f"/api/v1/identify/recent/{entry['actionId']}/undo")
    assert undone.status_code == 200
    assert typo.title == "Titfield Thuderbolt, The" and typo.tmdb_id is None
    again = await client.post(f"/api/v1/identify/recent/{entry['actionId']}/undo")
    assert again.status_code == 409


async def test_only_an_admin_reaches_the_page(db: AsyncSession) -> None:
    mark = await _person(db, UserRole.viewer)

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return mark

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/identify/overview")).status_code == 403
        assert (await client.get("/api/v1/identify/queue")).status_code == 403


async def test_the_film_pages_own_identify_is_audited_too(
    db: AsyncSession, page: tuple[AsyncClient, Profile, FakeTmdb]
) -> None:
    client, craig, tmdb = page
    tmdb_id, _, _ = _tmdb_ids()
    tmdb.records[tmdb_id] = _record(tmdb_id, "Scott of the Antarctic", 1948)
    film = await _film(db, "Scott of The Antartic")
    await _disc(db, film)
    await db.commit()

    response = await client.post(f"/api/v1/movies/{film.id}/identify", json={"tmdbId": tmdb_id})

    assert response.status_code == 200
    (audit,) = await _audits(db, film)
    assert audit.user_id == craig.id
    assert audit.changes is not None and audit.changes["how"] == "film_page"


# ---------------------------------------------------------------------------
# The knock-ons
# ---------------------------------------------------------------------------


async def test_a_value_taken_before_an_identification_falls_due(db: AsyncSession) -> None:
    craig = await _person(db)
    tmdb_id, _, _ = _tmdb_ids()
    film = await _film(db, "Captain Ameica - Civil War")
    await _disc(db, film, "4k_uhd")
    db.add(
        DiscValuation(
            id=uuid.uuid4(),
            movie_id=film.id,
            format_code="4k_uhd",
            status="not_priced",
            basis=ASKING_PRICES,
            search_query="Captain Ameica Civil War 4K",
            checked_utc=datetime(2026, 9, 25, 11, 0),
        )
    )
    await db.flush()
    due_before = await count_due(db, now=datetime(2026, 9, 25, 11, 30))

    await identify_film(
        db, film, _record(tmdb_id, "Captain America: Civil War", 2016), by=craig.id, how="auto"
    )
    film.last_tmdb_sync_utc = datetime(2026, 9, 25, 11, 15)
    await db.flush()

    assert await count_due(db, now=datetime(2026, 9, 25, 11, 30)) == due_before + 1


async def test_t7s_second_look_reconsiders_a_disc_whose_film_has_gained_a_year(
    db: AsyncSession,
) -> None:
    film = await _film(db, "Fight Club")
    disc = await _disc(db, film, "blu_ray")
    run = SpecRun(
        id=uuid.uuid4(),
        trigger="job",
        status="running",
        started_utc=NOW,
        heartbeat_utc=NOW,
        search_budget=0,
        fetch_budget=0,
        searches=0,
        searched=0,
        accepted=0,
        queued=0,
        no_match=0,
        restored=0,
        fetched=0,
        applied=0,
        sent_back=0,
        fetch_failed=0,
    )
    lookup = SpecLookup(
        id=uuid.uuid4(),
        collection_item_id=disc.id,
        status="needs_you",
        note="This film has no year, so the page cannot be checked. Confirm it's the right one.",
        attempts=0,
    )
    db.add_all([run, lookup])
    await db.flush()
    db.add(
        SpecCandidate(
            id=uuid.uuid4(),
            lookup_id=lookup.id,
            url="https://www.blu-ray.com/movies/Fight-Club-Blu-ray/6715/",
            title="Fight Club Blu-ray (United Kingdom)",
            rank=0,
            matches=True,
            origin="search",
        )
    )
    await db.flush()

    assert await backfill.redecide_queue(db, run, clock=lambda: NOW) == 0
    film.year = 1999
    film.tmdb_id = _tmdb_ids()[0]
    await db.flush()

    assert await backfill.redecide_queue(db, run, clock=lambda: NOW) == 1
    assert lookup.status == "accepted"


async def test_the_refresh_finds_a_film_by_the_title_identification_replaced() -> None:
    film = uuid.uuid4()
    other = uuid.uuid4()
    index = LiveFilmIndex([(film, "Peeping Tom"), (film, "Peepiing Tom"), (other, "Peeping Toms")])

    assert index.resolve("Peepiing Tom") == (film, "title")
    assert index.resolve("Peeping Tom") == (film, "title")
    # A film that answers to one title twice is still one film, not an ambiguity.
    doubled = LiveFilmIndex([(film, "The Mummy"), (film, "The Mummy")])
    assert doubled.resolve("The Mummy") == (film, "title")


async def test_identified_films_keep_their_run_counted(db: AsyncSession) -> None:
    """The runs table holds one running run at a time, as T6's and T7's do."""
    plan = Plan(
        version=PLAN_VERSION,
        made_utc=NOW.isoformat(),
        films=0,
        tmdb_calls=0,
        brave_searches=0,
        brave_budget=0,
        items=[],
    )
    run = await start_run(db, plan)
    assert run.status == "running"
    stale = await db.get(IdentifyRun, run.id)
    assert stale is not None
    stale.heartbeat_utc = NOW - timedelta(hours=2)
    await db.flush()
    again = await start_run(db, plan)
    assert again.id != run.id
    abandoned = await db.get(IdentifyRun, run.id)
    assert abandoned is not None and abandoned.status == "abandoned"


async def test_a_merge_target_reads_back_from_the_plan() -> None:
    item = Item(
        movie_id="m",
        title="Misery",
        discs=[Disc("blu_ray", None, None)],
        watches=0,
        outcome="ask",
        merge_into=MergeTarget("x", "Misery", 1990),
    )
    plan = Plan(PLAN_VERSION, NOW.isoformat(), 1, 0, 0, 0, [item])
    again = Plan.from_dict(json.loads(plan.to_json()))
    assert again.items[0].merge_into == MergeTarget("x", "Misery", 1990)
