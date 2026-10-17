"""Mark's 16 Oct points against Postgres — Batch Y5 (#277). These run in CI.

**What this proves:** the add form's search lists TMDB's series apart from its films, reading a
second page so BBC's *Life* is offered for "Life"; a disc is added to a series by its series
id, made from TMDB's record the first time and found the second, which meets the duplicate
prompt; "Move only this copy" offers series, moves a copy to one as Mark, settles the doubt
naming it, and Craig's undo puts it back and removes the series it made; the film page's doubt
carries the title to search; every full fetch stores the keywords, and ``keywordId`` filters by
them (Film Noir is 9807), for a saved collection too; the backfill fills only null rows still the
film it read, and its dry run writes nothing; and a disc TMDB lacks is added by its title,
filed as not a film by whoever added it, kept off "Still to identify", and found again by a
second copy.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt, IdentifyLookup
from src.models.movie import Movie, MovieCredit
from src.models.profile import Profile, UserRole
from src.routers.movies import get_tmdb_client
from src.services import keyword_backfill
from src.services.identify.doubts import raise_doubt
from src.tmdb.models import (
    Genre,
    Keyword,
    MovieKeywords,
    SearchResult,
    SearchResults,
    TvCastMember,
    TvCreator,
    TvCredits,
    TvKeywords,
    TvSearchResult,
    TvSearchResults,
    TvShow,
)
from src.tmdb.models import Movie as TmdbMovie

NOIR = 9807


def _ids() -> tuple[int, int, int]:
    """A film id, a series id and a namesake series id no other test uses."""
    base = 7_000_000 + uuid.uuid4().int % 900_000
    return base, base + 1, base + 2


def _film_record(
    tmdb_id: int, title: str = "Life", *, keywords: list[int] | None = None
) -> TmdbMovie:
    return TmdbMovie(
        id=tmdb_id,
        title=title,
        original_title=title,
        overview=f"{title}, the film.",
        release_date="2017-03-23",
        runtime=104,
        vote_count=6000,
        genres=[Genre(id=878, name="Science Fiction")],
        keywords=(
            MovieKeywords(keywords=[Keyword(id=k, name=str(k)) for k in keywords])
            if keywords is not None
            else None
        ),
    )


def _series_record(tv_id: int, name: str = "Life") -> TvShow:
    return TvShow(
        id=tv_id,
        name=name,
        original_name=name,
        overview="David Attenborough on how living things survive.",
        first_air_date="2009-10-12",
        vote_count=180,
        genres=[Genre(id=99, name="Documentary")],
        created_by=[TvCreator(id=51, name="A Producer")],
        aggregate_credits=TvCredits(
            cast=[TvCastMember(id=52, name="David Attenborough", order=0, roles=[])]
        ),
        keywords=TvKeywords(results=[Keyword(id=221, name="nature documentary")]),
    )


class FakeTmdb:
    """TMDB for one test. "Life" has a namesake series on page one and BBC's on page two, as
    TMDB answered on 16 Oct; everything it fetched is recorded."""

    def __init__(self, *, film_id: int, tv_id: int, namesake_id: int) -> None:
        self.film_id, self.tv_id, self.namesake_id = film_id, tv_id, namesake_id
        self.film_keywords: list[int] | None = [NOIR]
        self.pages: list[int] = []

    async def search_movie(self, query: str, **_: Any) -> SearchResults:
        return SearchResults(
            results=[
                SearchResult(
                    id=self.film_id,
                    title="Life",
                    original_title="Life",
                    release_date="2017-03-23",
                    vote_count=6000,
                )
            ]
        )

    async def search_tv(self, query: str, page: int = 1, **_: Any) -> TvSearchResults:
        self.pages.append(page)
        if page == 1:
            shows = [
                TvSearchResult(
                    id=self.namesake_id, name="Life", first_air_date="2007-09-26", vote_count=280
                ),
                *[
                    TvSearchResult(
                        id=self.namesake_id + 100 + n, name=f"Life Goes On {n}", vote_count=n
                    )
                    for n in range(19)
                ],
            ]
        else:
            shows = [
                TvSearchResult(id=self.namesake_id + 200 + n, name=f"This Life {n}", vote_count=n)
                for n in range(7)
            ]
            shows.append(
                TvSearchResult(
                    id=self.tv_id,
                    name="Life",
                    first_air_date="2009-10-12",
                    vote_count=180,
                    overview="David Attenborough on how living things survive.",
                )
            )
        return TvSearchResults(page=page, results=shows, total_pages=2, total_results=40)

    async def get_movie(self, movie_id: int, **_: Any) -> TmdbMovie:
        return _film_record(movie_id, keywords=self.film_keywords)

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        return _film_record(movie_id, keywords=self.film_keywords)

    async def get_tv_full(self, tv_id: int, language: str = "en-US") -> TvShow:
        if tv_id not in (self.tv_id, self.namesake_id):
            request = httpx.Request("GET", f"https://api.themoviedb.org/3/tv/{tv_id}")
            raise httpx.HTTPStatusError(
                "not found", request=request, response=httpx.Response(404, request=request)
            )
        return _series_record(tv_id)


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@dataclass
class Desk:
    client: AsyncClient
    craig: Profile
    mark: Profile
    tmdb: FakeTmdb
    user: list[Profile] = field(default_factory=list)

    def as_(self, person: Profile) -> None:
        self.user[:] = [person]


async def _person(db: AsyncSession, role: UserRole) -> Profile:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"Y5 {role.value} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=role,
    )
    db.add(person)
    await db.flush()
    return person


@pytest_asyncio.fixture
async def desk(db: AsyncSession) -> AsyncIterator[Desk]:
    craig = await _person(db, UserRole.admin)
    mark = await _person(db, UserRole.viewer)
    film_id, tv_id, namesake_id = _ids()
    tmdb = FakeTmdb(film_id=film_id, tv_id=tv_id, namesake_id=namesake_id)
    user: list[Profile] = [mark]

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        await db.refresh(user[0])
        return user[0]

    async def override_tmdb() -> AsyncIterator[FakeTmdb]:
        yield tmdb

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield Desk(client, craig, mark, tmdb, user)
    finally:
        app.dependency_overrides.clear()


async def _film(
    db: AsyncSession, title: str, *, tmdb_id: int | None = None, **fields: Any
) -> Movie:
    film = Movie(id=uuid.uuid4(), tmdb_id=tmdb_id, title=title, original_title=title, **fields)
    db.add(film)
    await db.flush()
    return film


async def _disc(db: AsyncSession, film: Movie, fmt: str = "blu_ray") -> CollectionItem:
    disc = CollectionItem(id=uuid.uuid4(), movie_id=film.id, formats=[fmt])
    db.add(disc)
    await db.flush()
    return disc


# ---------------------------------------------------------------------------
# Series on the add form
# ---------------------------------------------------------------------------


async def test_the_add_form_lists_series_apart_and_reads_a_second_page(
    db: AsyncSession, desk: Desk
) -> None:
    held = await _film(db, "Life", tmdb_tv_id=desk.tmdb.namesake_id, media_type="tv", is_tv=True)
    await db.commit()

    response = await desk.client.get("/api/v1/tmdb/search", params={"q": "Life"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [(r["tmdbId"], r["mediaType"]) for r in body["results"]] == [(desk.tmdb.film_id, "film")]
    series = body["series"]
    assert len(series) == 5
    assert all(entry["mediaType"] == "tv" for entry in series)
    # Both series called exactly "Life" come first; BBC's was on TMDB's second page.
    assert {series[0]["tmdbId"], series[1]["tmdbId"]} == {desk.tmdb.namesake_id, desk.tmdb.tv_id}
    assert desk.tmdb.pages == [1, 2]
    by_id = {entry["tmdbId"]: entry for entry in series}
    assert by_id[desk.tmdb.namesake_id]["inCollection"] is True
    assert by_id[desk.tmdb.namesake_id]["movieId"] == str(held.id)
    assert by_id[desk.tmdb.tv_id]["inCollection"] is False


async def test_a_disc_is_added_to_a_series_made_once_then_found_with_the_duplicate_prompt(
    db: AsyncSession, desk: Desk
) -> None:
    tv_id = desk.tmdb.tv_id
    first = await desk.client.post(
        "/api/v1/collection", json={"tmdbTvId": tv_id, "formats": ["blu_ray"]}
    )
    assert first.status_code == 201, first.text
    series = await db.scalar(select(Movie).where(Movie.tmdb_tv_id == tv_id))
    assert series is not None
    assert (series.tmdb_id, series.is_tv, series.media_type, series.title) == (
        None,
        True,
        "tv",
        "Life",
    )
    assert series.tmdb_keyword_ids == [221]
    names = set(
        (
            await db.scalars(
                select(MovieCredit.person_name).where(MovieCredit.movie_id == series.id)
            )
        ).all()
    )
    assert names == {"David Attenborough", "A Producer"}
    assert first.json()["movieId"] == str(series.id)

    check = await desk.client.get(
        "/api/v1/collection/duplicate-check", params={"tmdbTvId": tv_id, "format": "dvd"}
    )
    assert check.json()["isDuplicate"] is True
    refused = await desk.client.post(
        "/api/v1/collection", json={"tmdbTvId": tv_id, "formats": ["dvd"]}
    )
    assert refused.status_code == 409
    again = await desk.client.post(
        "/api/v1/collection",
        json={"tmdbTvId": tv_id, "formats": ["dvd"], "confirmDuplicate": "another_copy"},
    )
    assert again.status_code == 201, again.text
    assert again.json()["movieId"] == str(series.id)

    # A trashed series is restored by a disc added to it, as a film is.
    for disc in (
        await db.scalars(select(CollectionItem).where(CollectionItem.movie_id == series.id))
    ).all():
        await db.delete(disc)
    series.deleted_at = series.updated_at
    await db.commit()
    restored = await desk.client.post(
        "/api/v1/collection", json={"tmdbTvId": tv_id, "formats": ["dvd"]}
    )
    assert restored.status_code == 201, restored.text
    await db.refresh(series)
    assert series.deleted_at is None


async def test_a_body_naming_two_films_or_a_blank_title_is_refused(desk: Desk) -> None:
    both = await desk.client.post(
        "/api/v1/collection", json={"tmdbId": 1, "tmdbTvId": 2, "formats": ["dvd"]}
    )
    blank = await desk.client.post("/api/v1/collection", json={"title": "   ", "formats": ["dvd"]})
    none = await desk.client.get("/api/v1/collection/duplicate-check")
    assert (both.status_code, blank.status_code, none.status_code) == (422, 422, 422)


# ---------------------------------------------------------------------------
# "Move only this copy" to a series
# ---------------------------------------------------------------------------


async def _life_in_doubt(
    db: AsyncSession, desk: Desk
) -> tuple[Movie, CollectionItem, IdentifyDoubt]:
    """Life (2017) holding its 4K and BBC's Life on Blu-ray, which the re-check doubts."""
    film = await _film(db, "Life", tmdb_id=desk.tmdb.film_id, year=2017, media_type="film")
    await _disc(db, film, "uhd_4k")
    wrong = await _disc(db, film, "blu_ray")
    doubt = await raise_doubt(
        db,
        film,
        source="recheck",
        note="T9 reads the sheet's row as a TV series.",
        evidence=[],
        collection_item_id=wrong.id,
        candidates=[],
        search_hint="Life",
    )
    assert doubt is not None
    await db.commit()
    return film, wrong, doubt


async def test_a_copy_moves_to_a_series_as_mark_and_craig_undoes_it(
    db: AsyncSession, desk: Desk
) -> None:
    film, wrong, doubt = await _life_in_doubt(db, desk)

    page = await desk.client.get(f"/api/v1/movies/{film.id}")
    assert page.status_code == 200, page.text
    [shown] = page.json()["identificationDoubts"]
    assert (shown["searchHint"], shown["collectionItemId"]) == ("Life", str(wrong.id))

    found = await desk.client.get(
        f"/api/v1/identify/films/{film.id}/search", params={"query": "Life"}
    )
    assert found.status_code == 200, found.text
    offered = {c["tmdbId"]: c for c in found.json()["seriesCandidates"]}
    assert offered[desk.tmdb.tv_id]["mediaType"] == "tv"
    assert all(c["mediaType"] == "film" for c in found.json()["candidates"])

    moved = await desk.client.post(
        f"/api/v1/identify/copies/{wrong.id}/move",
        json={"tmdbId": desk.tmdb.tv_id, "mediaType": "tv"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["created"] is True
    series = await db.scalar(select(Movie).where(Movie.tmdb_tv_id == desk.tmdb.tv_id))
    assert series is not None and series.is_tv
    await db.refresh(wrong)
    await db.refresh(doubt)
    assert wrong.movie_id == series.id
    assert doubt.status == "moved" and doubt.decided_by == desk.mark.id
    audit = await db.get(AdminAction, uuid.UUID(moved.json()["actionId"]))
    assert audit is not None and audit.user_id == desk.mark.id
    assert audit.changes["to"]["tmdbTvId"] == desk.tmdb.tv_id
    assert audit.changes["from"]["tmdbId"] == desk.tmdb.film_id

    again = await desk.client.post(
        f"/api/v1/identify/copies/{wrong.id}/move",
        json={"tmdbId": desk.tmdb.tv_id, "mediaType": "tv"},
    )
    assert again.status_code == 409
    assert "already on that series" in again.json()["detail"]

    desk.as_(desk.craig)
    undone = await desk.client.post(f"/api/v1/identify/recent/{moved.json()['actionId']}/undo")
    assert undone.status_code == 200, undone.text
    await db.refresh(wrong)
    await db.refresh(doubt)
    assert wrong.movie_id == film.id
    assert doubt.status == "open"
    assert await db.scalar(select(Movie).where(Movie.tmdb_tv_id == desk.tmdb.tv_id)) is None


async def test_a_copy_moves_to_the_series_the_collection_already_holds(
    db: AsyncSession, desk: Desk
) -> None:
    film, wrong, _ = await _life_in_doubt(db, desk)
    held = await _film(db, "Life", tmdb_tv_id=desk.tmdb.tv_id, media_type="tv", is_tv=True)
    await db.commit()

    moved = await desk.client.post(
        f"/api/v1/identify/copies/{wrong.id}/move",
        json={"tmdbId": desk.tmdb.tv_id, "mediaType": "tv"},
    )

    assert moved.status_code == 200, moved.text
    assert (moved.json()["movieId"], moved.json()["created"]) == (str(held.id), False)
    # A move without a media type is a film's, as an app cached before Y5 meant it.
    back = await desk.client.post(
        f"/api/v1/identify/copies/{wrong.id}/move", json={"tmdbId": desk.tmdb.film_id}
    )
    assert back.status_code == 200, back.text
    assert back.json()["movieId"] == str(film.id)


# ---------------------------------------------------------------------------
# Film Noir
# ---------------------------------------------------------------------------


async def test_a_disc_added_by_tmdb_id_stores_the_films_keywords(
    db: AsyncSession, desk: Desk
) -> None:
    added = await desk.client.post(
        "/api/v1/collection", json={"tmdbId": desk.tmdb.film_id, "formats": ["dvd"]}
    )
    assert added.status_code == 201, added.text
    film = await db.get(Movie, uuid.UUID(added.json()["movieId"]))
    assert film is not None and film.tmdb_keyword_ids == [NOIR]


async def test_the_keyword_filter_finds_film_noir_and_a_saved_collection_keeps_it(
    db: AsyncSession, desk: Desk
) -> None:
    base, _, _ = _ids()
    noir = await _film(db, "Out of the Past", tmdb_id=base + 10, tmdb_keyword_ids=[NOIR, 818])
    other = await _film(db, "Brief Encounter", tmdb_id=base + 11, tmdb_keyword_ids=[818])
    unknown = await _film(db, "The Big Combo", tmdb_id=base + 12)
    for film in (noir, other, unknown):
        await _disc(db, film)
    await db.commit()

    listed = await desk.client.get(
        "/api/v1/movies", params={"keywordId": str(NOIR), "perPage": "2000"}
    )
    assert listed.status_code == 200, listed.text
    ids = {item["id"] for item in listed.json()["items"]}
    assert str(noir.id) in ids
    assert not ids & {str(other.id), str(unknown.id)}

    saved = await desk.client.post(
        "/api/v1/smart-collections",
        json={"name": f"Noir {uuid.uuid4().hex[:6]}", "filters": {"keywordId": NOIR}},
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["filters"]["keywordId"] == NOIR
    films = await desk.client.get(
        f"/api/v1/smart-collections/{saved.json()['id']}/results", params={"perPage": "2000"}
    )
    assert films.status_code == 200, films.text
    in_collection = {item["id"] for item in films.json()["items"]}
    assert str(noir.id) in in_collection and str(other.id) not in in_collection


# ---------------------------------------------------------------------------
# The backfill
# ---------------------------------------------------------------------------


class FakeKeywords:
    def __init__(self, by_film: dict[int, list[int]], by_series: dict[int, list[int]]) -> None:
        self.by_film, self.by_series = by_film, by_series
        self.asked: list[str] = []

    async def get_movie_keywords(self, movie_id: int) -> MovieKeywords:
        self.asked.append(f"movie:{movie_id}")
        if movie_id not in self.by_film:
            request = httpx.Request(
                "GET", f"https://api.themoviedb.org/3/movie/{movie_id}/keywords"
            )
            raise httpx.HTTPStatusError(
                "not found", request=request, response=httpx.Response(404, request=request)
            )
        return MovieKeywords(keywords=[Keyword(id=k) for k in self.by_film[movie_id]])

    async def get_tv_keywords(self, tv_id: int) -> TvKeywords:
        self.asked.append(f"tv:{tv_id}")
        return TvKeywords(results=[Keyword(id=k) for k in self.by_series[tv_id]])


async def test_the_backfill_fills_null_rows_still_the_film_and_its_dry_run_writes_nothing(
    db: AsyncSession,
) -> None:
    base, _, _ = _ids()
    tag = uuid.uuid4().hex[:6]
    noir = await _film(db, f"Y5 {tag} Noir", tmdb_id=base + 20)
    plain = await _film(db, f"Y5 {tag} Plain", tmdb_id=base + 21)
    gone = await _film(db, f"Y5 {tag} Gone", tmdb_id=base + 22)
    series = await _film(db, f"Y5 {tag} Series", tmdb_tv_id=base + 23, is_tv=True)
    switched = await _film(db, f"Y5 {tag} Switched", tmdb_id=base + 24)
    done = await _film(db, f"Y5 {tag} Done", tmdb_id=base + 25, tmdb_keyword_ids=[1])
    await _film(db, f"Y5 {tag} Unidentified")
    await db.flush()
    source = FakeKeywords(
        {base + 20: [NOIR, 5], base + 21: [], base + 24: [NOIR]}, {base + 23: [221]}
    )

    found = [t for t in await keyword_backfill.targets(db) if t.title.startswith(f"Y5 {tag}")]
    assert {t.movie_id for t in found} == {noir.id, plain.id, gone.id, series.id, switched.id}
    assert done.id not in {t.movie_id for t in found}

    dry = await keyword_backfill.run(source, found, apply=False)
    assert len(dry.fetched) == 4 and [t.movie_id for t in dry.missing] == [gone.id]
    for film in (noir, plain, series):
        await db.refresh(film)
        assert film.tmdb_keyword_ids is None

    # Identified as another film while the run read TMDB: its list is not written.
    switched.tmdb_id = base + 26
    await db.flush()

    async def commit(
        batch: Sequence[keyword_backfill.Target], outcome: keyword_backfill.Outcome
    ) -> None:
        await keyword_backfill.write(db, batch, outcome)
        await db.flush()

    applied = await keyword_backfill.run(source, found, apply=True, commit=commit)
    assert (applied.written, applied.changed) == (3, 1)
    assert {t.movie_id for t in applied.noir} == {noir.id, switched.id}
    for film in (noir, plain, gone, series, switched):
        await db.refresh(film)
    assert noir.tmdb_keyword_ids == [NOIR, 5]
    assert plain.tmdb_keyword_ids == []
    assert series.tmdb_keyword_ids == [221]
    assert gone.tmdb_keyword_ids is None
    assert switched.tmdb_keyword_ids is None


# ---------------------------------------------------------------------------
# A disc added by its title
# ---------------------------------------------------------------------------

DAY_IN_THE_LIFE = "A Day in the Life: Four Portraits of Post-War Britain"


async def test_a_disc_tmdb_lacks_is_added_by_its_title_and_kept_off_still_to_identify(
    db: AsyncSession, desk: Desk
) -> None:
    title = f"{DAY_IN_THE_LIFE} {uuid.uuid4().hex[:6]}"
    added = await desk.client.post(
        "/api/v1/collection", json={"title": f"  {title} ", "formats": ["blu_ray"]}
    )
    assert added.status_code == 201, added.text
    film = await db.get(Movie, uuid.UUID(added.json()["movieId"]))
    assert film is not None
    assert (film.title, film.tmdb_id, film.tmdb_tv_id, film.media_type) == (
        title,
        None,
        None,
        "other",
    )
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == film.id))
    assert lookup is not None
    assert (lookup.status, lookup.set_aside_as, lookup.decided_by) == (
        "set_aside",
        "not_film",
        desk.mark.id,
    )
    audit = await db.scalar(
        select(AdminAction).where(
            AdminAction.target_table == "movies", AdminAction.target_id == str(film.id)
        )
    )
    assert audit is not None and audit.user_id == desk.mark.id
    assert audit.changes["kind"] == "set_aside"

    waiting = await desk.client.get(
        "/api/v1/movies", params={"toIdentify": "true", "perPage": "2000"}
    )
    assert str(film.id) not in {item["id"] for item in waiting.json()["items"]}
    page = await desk.client.get(f"/api/v1/movies/{film.id}")
    assert (page.json()["identified"], page.json()["setAsideAs"]) == (False, "not_film")

    # A second copy, typed differently, finds the same title and meets the duplicate prompt.
    shouted = title.upper().replace(" ", "  ")
    check = await desk.client.get(
        "/api/v1/collection/duplicate-check", params={"title": shouted, "format": "dvd"}
    )
    assert check.json()["isDuplicate"] is True
    assert check.json()["movieId"] == str(film.id)
    refused = await desk.client.post(
        "/api/v1/collection", json={"title": shouted, "formats": ["dvd"]}
    )
    assert refused.status_code == 409
    second = await desk.client.post(
        "/api/v1/collection",
        json={"title": shouted, "formats": ["dvd"], "confirmDuplicate": "another_copy"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["movieId"] == str(film.id)
