"""TV series identified from TMDB, against Postgres — Batch Y3. These run in CI.

**What this proves:** a title is identified as a TMDB series from its page, by either person,
with the series' own id in ``tmdb_tv_id`` and never in ``tmdb_id``; it fills in the metadata,
cast and creators, keeps the title it replaced, and is audited with the series' id under its
own key. A film corrected to a series clears the film's id, and back. Identifying a second
row as a series the collection already holds merges them. The Identify films page undoes a
series' identification, and its queue and counts leave a series out. "Still to identify"
lists a series set aside, the candidates offer TMDB's series beside its films, and a series'
streaming offers come from TMDB's series providers.

**What it does not:** TMDB itself. The series payload here follows TMDB's published shape;
the cloud session that built Y3 had no TMDB key to capture a real one (#273).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyLookup, MovieTitleAlias
from src.models.movie import Movie, MovieCredit
from src.models.profile import Profile, UserRole
from src.routers.movies import get_tmdb_client
from src.services.identification import IdentifyError, identify_film, undo_identification
from src.services.identify.queue import queue
from src.tmdb.models import (
    ExternalIds,
    Genre,
    SearchResult,
    SearchResults,
    TvCastMember,
    TvCreator,
    TvCredits,
    TvCrewJob,
    TvCrewMember,
    TvRole,
    TvSearchResult,
    TvSearchResults,
    TvShow,
    WatchProvider,
    WatchProviderCountry,
    WatchProviders,
)
from src.tmdb.models import Movie as TmdbMovie


def _ids() -> tuple[int, int]:
    """A film id and a series id no other test uses, so the unique indexes cannot collide."""
    base = 8_000_000 + uuid.uuid4().int % 900_000
    return base, base + 1


def _series(tv_id: int, name: str = "Band of Brothers") -> TvShow:
    return TvShow(
        id=tv_id,
        name=name,
        original_name=name,
        overview="Easy Company, from Toccoa to the Eagle's Nest.",
        first_air_date="2001-09-09",
        last_air_date="2001-11-04",
        number_of_seasons=1,
        number_of_episodes=10,
        vote_average=8.6,
        vote_count=4100,
        poster_path="/series.jpg",
        backdrop_path="/series-backdrop.jpg",
        genres=[Genre(id=10768, name="War & Politics"), Genre(id=18, name="Drama")],
        created_by=[TvCreator(id=31, name="Erik Jendresen")],
        aggregate_credits=TvCredits(
            cast=[
                TvCastMember(
                    id=11,
                    name="Damian Lewis",
                    order=0,
                    roles=[TvRole(character="Maj. Richard Winters", episode_count=10)],
                ),
                TvCastMember(id=12, name="Ron Livingston", order=1, roles=[]),
            ],
            crew=[
                TvCrewMember(
                    id=41,
                    name="Michael Kamen",
                    department="Sound",
                    jobs=[TvCrewJob(job="Original Music Composer", episode_count=10)],
                ),
                TvCrewMember(id=42, name="An Episode Director", jobs=[TvCrewJob(job="Director")]),
            ],
        ),
        external_ids=ExternalIds(imdb_id="tt0185906"),
    )


def _film(tmdb_id: int, title: str = "Band of Brothers") -> TmdbMovie:
    return TmdbMovie(
        id=tmdb_id,
        title=title,
        original_title=title,
        overview="An obscure film of the same name.",
        release_date="1998-01-01",
        runtime=88,
        vote_count=3,
        genres=[Genre(id=18, name="Drama")],
    )


class FakeTmdb:
    """TMDB for one test: the series and films it knows, and what it was asked."""

    def __init__(self, *, film_id: int, tv_id: int) -> None:
        self.film_id, self.tv_id = film_id, tv_id
        self.asked: list[str] = []

    async def search_movie(self, query: str, year: int | None = None, **_: Any) -> SearchResults:
        self.asked.append(f"film:{query}")
        return SearchResults(
            results=[
                SearchResult(
                    id=self.film_id,
                    title="Band of Brothers",
                    original_title="Band of Brothers",
                    release_date="1998-01-01",
                    vote_count=3,
                )
            ]
        )

    async def search_tv(self, query: str, **_: Any) -> TvSearchResults:
        self.asked.append(f"tv:{query}")
        return TvSearchResults(
            results=[
                TvSearchResult(id=self.tv_id + 50, name="Brothers", first_air_date="2009-01-01"),
                TvSearchResult(
                    id=self.tv_id,
                    name="Band of Brothers",
                    first_air_date="2001-09-09",
                    vote_count=4100,
                    popularity=90.0,
                    overview="Easy Company.",
                    poster_path="/series.jpg",
                ),
            ]
        )

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        return _film(movie_id)

    async def get_tv_full(self, tv_id: int, language: str = "en-US") -> TvShow:
        if tv_id != self.tv_id:
            request = httpx.Request("GET", f"https://api.themoviedb.org/3/tv/{tv_id}")
            raise httpx.HTTPStatusError(
                "not found", request=request, response=httpx.Response(404, request=request)
            )
        return _series(tv_id)

    async def get_watch_providers(self, movie_id: int) -> WatchProviders:
        self.asked.append(f"film-providers:{movie_id}")
        return WatchProviders()

    async def get_tv_watch_providers(self, tv_id: int) -> WatchProviders:
        self.asked.append(f"tv-providers:{tv_id}")
        netflix = WatchProvider(provider_id=8, provider_name="Netflix", logo_path="/n.png")
        return WatchProviders(
            results={"GB": WatchProviderCountry(link="https://tmdb.example/tv", flatrate=[netflix])}
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


async def _person(db: AsyncSession, role: UserRole) -> Profile:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"Y3 {role.value} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=role,
    )
    db.add(person)
    await db.flush()
    return person


async def _owned(db: AsyncSession, title: str, *, tmdb_id: int | None = None) -> Movie:
    film = Movie(
        id=uuid.uuid4(), tmdb_id=tmdb_id, title=title, original_title=title, media_type="film"
    )
    db.add(film)
    await db.flush()
    db.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=film.id,
            formats=["blu_ray"],
            section="Front",
            shelf="2nd",
            location="Front 2nd shelf",
        )
    )
    await db.flush()
    return film


async def _set_aside_tv(db: AsyncSession, film: Movie) -> None:
    film.is_tv, film.media_type = True, "tv"
    db.add(
        IdentifyLookup(
            id=uuid.uuid4(), movie_id=film.id, status="set_aside", set_aside_as="tv", candidates=[]
        )
    )
    await db.flush()


@dataclass
class Api:
    """The app as one person at a time, with TMDB stood in."""

    client: AsyncClient
    tmdb: FakeTmdb
    mark: Profile
    craig: Profile
    asking: list[Profile]

    def as_person(self, person: Profile) -> None:
        self.asking[0] = person


@pytest_asyncio.fixture
async def api(db: AsyncSession) -> AsyncIterator[Api]:
    mark = await _person(db, UserRole.viewer)
    craig = await _person(db, UserRole.admin)
    film_id, tv_id = _ids()
    tmdb = FakeTmdb(film_id=film_id, tv_id=tv_id)
    asking = [mark]

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        # Every request shares this session, so a route's rollback expires the profile the
        # next request is handed. A real request loads its own; this reloads it.
        await db.refresh(asking[0])
        return asking[0]

    async def override_tmdb() -> AsyncIterator[FakeTmdb]:
        yield tmdb

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield Api(client, tmdb, mark, craig, asking)
    finally:
        app.dependency_overrides.clear()


async def _audits(db: AsyncSession, film_id: uuid.UUID) -> list[AdminAction]:
    return list(
        (
            await db.scalars(
                select(AdminAction)
                .where(AdminAction.target_table == "movies", AdminAction.target_id == str(film_id))
                .order_by(AdminAction.created_at)
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Identifying a series from its page
# ---------------------------------------------------------------------------


async def test_mark_identifies_a_set_aside_series_from_its_page(db: AsyncSession, api: Api) -> None:
    """Broadchurch's case: set aside as TV by T9, now listed, offered as a series, and
    identified with the series' id in its own column."""
    shelf = await _owned(db, "Band of Brothers (Complete Series)")
    await _set_aside_tv(db, shelf)

    waiting = await api.client.get("/api/v1/movies", params={"toIdentify": True, "perPage": 2000})
    assert str(shelf.id) in {item["id"] for item in waiting.json()["items"]}

    offered = await api.client.get(f"/api/v1/movies/{shelf.id}/candidates")
    assert offered.status_code == 200
    series = offered.json()["seriesCandidates"]
    # The exact title first, scored as a film is, and searched with the cleaned title.
    assert [(c["tmdbId"], c["mediaType"], c["year"]) for c in series][0] == (
        api.tmdb.tv_id,
        "tv",
        2001,
    )
    assert "tv:Band of Brothers" in api.tmdb.asked
    assert all(c["mediaType"] == "film" for c in offered.json()["candidates"])

    chosen = await api.client.post(
        f"/api/v1/movies/{shelf.id}/identify", json={"tmdbId": api.tmdb.tv_id, "mediaType": "tv"}
    )
    assert chosen.status_code == 200
    body = chosen.json()
    assert body["id"] == str(shelf.id)
    assert (body["identified"], body["mediaType"], body["title"], body["year"]) == (
        True,
        "tv",
        "Band of Brothers",
        2001,
    )
    assert body["imdbId"] == "tt0185906"
    assert body["runtimeMinutes"] is None
    assert [member["personName"] for member in body["cast"]] == ["Damian Lewis", "Ron Livingston"]
    assert body["cast"][0]["characterName"] == "Maj. Richard Winters"
    assert {(c["personName"], c["role"]) for c in body["crew"]} == {
        ("Erik Jendresen", "writer"),
        ("Michael Kamen", "composer"),
    }

    await db.refresh(shelf)
    assert (shelf.tmdb_id, shelf.tmdb_tv_id, shelf.is_tv) == (None, api.tmdb.tv_id, True)
    # War & Politics is filed under War too, so the Archive's genre filter finds it.
    assert shelf.genre_ids == [10768, 10752, 18]
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == shelf.id))
    assert lookup is not None
    assert (lookup.status, lookup.media_type, lookup.tmdb_id, lookup.set_aside_as) == (
        "identified",
        "tv",
        api.tmdb.tv_id,
        None,
    )
    alias = await db.scalar(
        select(MovieTitleAlias.title).where(MovieTitleAlias.movie_id == shelf.id)
    )
    assert alias == "Band of Brothers (Complete Series)"
    audit = (await _audits(db, shelf.id))[-1]
    assert audit.user_id == api.mark.id
    assert audit.changes["tmdbTvId"] == api.tmdb.tv_id
    assert audit.changes["mediaType"] == "tv"
    assert "tmdbId" not in audit.changes

    waiting = await api.client.get("/api/v1/movies", params={"toIdentify": True, "perPage": 2000})
    assert str(shelf.id) not in {item["id"] for item in waiting.json()["items"]}


async def test_a_film_matched_by_mistake_is_corrected_to_the_series_and_back(
    db: AsyncSession, api: Api
) -> None:
    """Band of Brothers, 15 Oct: matched to an obscure film of the same name. Correcting it
    clears the film's id, and correcting it back clears the series'."""
    shelf = await _owned(db, "Band of Brothers", tmdb_id=api.tmdb.film_id)
    db.add(MovieCredit(id=uuid.uuid4(), movie_id=shelf.id, person_name="Old Cast", role="cast"))
    await db.flush()

    as_series = await api.client.post(
        f"/api/v1/movies/{shelf.id}/identify", json={"tmdbId": api.tmdb.tv_id, "mediaType": "tv"}
    )
    assert as_series.status_code == 200
    await db.refresh(shelf)
    assert (shelf.tmdb_id, shelf.tmdb_tv_id, shelf.media_type) == (None, api.tmdb.tv_id, "tv")
    names = set(
        await db.scalars(select(MovieCredit.person_name).where(MovieCredit.movie_id == shelf.id))
    )
    assert "Old Cast" not in names and "Damian Lewis" in names

    as_film = await api.client.post(
        f"/api/v1/movies/{shelf.id}/identify", json={"tmdbId": api.tmdb.film_id}
    )
    assert as_film.status_code == 200
    await db.refresh(shelf)
    assert (shelf.tmdb_id, shelf.tmdb_tv_id, shelf.media_type, shelf.is_tv) == (
        api.tmdb.film_id,
        None,
        "film",
        False,
    )


async def test_a_second_copy_of_a_series_merges_into_the_row_that_holds_it(
    db: AsyncSession, api: Api
) -> None:
    held = await _owned(db, "Band of Brothers")
    held.tmdb_tv_id, held.is_tv, held.media_type = api.tmdb.tv_id, True, "tv"
    duplicate = await _owned(db, "Band Of Brothers - DVD box")
    await db.flush()

    merged = await api.client.post(
        f"/api/v1/movies/{duplicate.id}/identify",
        json={"tmdbId": api.tmdb.tv_id, "mediaType": "tv"},
    )
    assert merged.status_code == 200
    assert merged.json()["id"] == str(held.id)
    assert merged.json()["copyCount"] == 2
    assert await db.get(Movie, duplicate.id) is None


async def test_craig_undoes_a_series_identification_from_the_identify_films_page(
    db: AsyncSession, api: Api
) -> None:
    shelf = await _owned(db, "Broadchurch Series 1-3")
    await _set_aside_tv(db, shelf)
    await api.client.post(
        f"/api/v1/movies/{shelf.id}/identify", json={"tmdbId": api.tmdb.tv_id, "mediaType": "tv"}
    )
    action = (await _audits(db, shelf.id))[-1]

    api.as_person(api.craig)
    recent = await api.client.get("/api/v1/identify/recent")
    assert str(action.id) in {row["actionId"] for row in recent.json()["items"]}
    undone = await api.client.post(f"/api/v1/identify/recent/{action.id}/undo")
    assert undone.status_code == 200

    await db.refresh(shelf)
    assert (shelf.title, shelf.tmdb_id, shelf.tmdb_tv_id) == ("Broadchurch Series 1-3", None, None)
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == shelf.id))
    assert lookup is not None
    assert (lookup.status, lookup.media_type, lookup.tmdb_id) == ("needs_you", "film", None)


async def test_undo_refuses_a_series_identified_again_since(db: AsyncSession, api: Api) -> None:
    """The undo checks the series' own id, not the film's, before putting anything back."""
    shelf = await _owned(db, "Band of Brothers")
    first = await identify_film(db, shelf, _series(api.tmdb.tv_id), by=None, how="film_page")
    other_tv = api.tmdb.tv_id + 7
    await identify_film(db, first.film, _series(other_tv, "Brothers"), by=None, how="film_page")

    with pytest.raises(IdentifyError, match="changed since"):
        await undo_identification(db, first.audit.id, by=None)


async def test_a_series_leaves_craigs_queue_and_counts_as_identified(
    db: AsyncSession, api: Api
) -> None:
    waiting = await _owned(db, "Still A Mystery Film")
    series = await _owned(db, "A Series Identified")
    series.tmdb_tv_id = api.tmdb.tv_id
    await db.flush()

    # The page shows 50 at most; the service answers for the whole queue.
    entries, _total = await queue(db, limit=100_000)
    ids = {entry.movie.id for entry in entries}
    assert waiting.id in ids
    assert series.id not in ids

    api.as_person(api.craig)
    refused = await api.client.post(
        f"/api/v1/identify/films/{series.id}/set-aside", json={"kind": "tv"}
    )
    assert refused.status_code == 409


async def test_a_series_streaming_offers_come_from_tmdbs_series_providers(
    db: AsyncSession, api: Api
) -> None:
    series = await _owned(db, "Band of Brothers")
    series.tmdb_tv_id = api.tmdb.tv_id
    await db.flush()

    offers = await api.client.get(f"/api/v1/movies/{series.id}/streaming", params={"region": "GB"})

    assert offers.status_code == 200
    assert offers.json()["unidentified"] is False
    assert [o["providerName"] for o in offers.json()["offers"]] == ["Netflix"]
    assert api.tmdb.asked[-1] == f"tv-providers:{api.tmdb.tv_id}"


async def test_a_series_tmdb_does_not_know_is_a_404_and_changes_nothing(
    db: AsyncSession, api: Api
) -> None:
    shelf = await _owned(db, "Not On TMDB")

    missing = await api.client.post(
        f"/api/v1/movies/{shelf.id}/identify",
        json={"tmdbId": api.tmdb.tv_id + 99, "mediaType": "tv"},
    )

    assert missing.status_code == 404
    assert missing.json()["detail"] == "TMDB series could not be loaded"
    await db.refresh(shelf)
    assert (shelf.tmdb_id, shelf.tmdb_tv_id) == (None, None)


async def test_a_series_card_says_so(db: AsyncSession, api: Api) -> None:
    series = await _owned(db, "Band of Brothers")
    series.tmdb_tv_id, series.media_type, series.year = api.tmdb.tv_id, "tv", 1904
    await db.flush()

    items = (await api.client.get("/api/v1/movies", params={"year": 1904})).json()["items"]

    assert [(i["identified"], i["mediaType"], i["setAsideAs"]) for i in items] == [
        (True, "tv", None)
    ]
