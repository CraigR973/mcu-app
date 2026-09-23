"""Batch T2 — one search: "seen it, and when", films beyond the shelf, and a film card.

TMDB is faked, as in `test_discovery_api.py`. What is pinned here is what this app decides:
that an owned film never appears as a stranger, that an unidentified owned film is flagged
rather than hidden, which results get a streaming lookup, and that each person sees their
own last watch.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.matching.engine import canonical_title
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.routers import discovery
from src.routers.discovery import _cached_streaming_names, _lookalike, _Unidentified
from src.routers.movies import get_tmdb_client
from src.tmdb.models import (
    CastMember,
    Credits,
    CrewMember,
    Genre,
    SearchResult,
    SearchResults,
    WatchProvider,
    WatchProviderCountry,
    WatchProviders,
)
from src.tmdb.models import Movie as TmdbMovie

# ── Titles, compared — no database ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Mummy, The (Brendan Fraser)", ("the mummy", None)),
        ("The Mummy", ("the mummy", None)),
        ("African Queen, The", ("the african queen", None)),
        ("Heat (1995)", ("heat", 1995)),
        ("Blade Runner: The Final Cut", ("blade runner", None)),
    ],
)
def test_two_spellings_of_one_title_compare_equal(
    raw: str, expected: tuple[str, int | None]
) -> None:
    assert canonical_title(raw) == expected


def _unidentified(title: str, year: int | None = None) -> _Unidentified:
    canonical, title_year = canonical_title(title)
    return _Unidentified(uuid.uuid4(), title, canonical, year or title_year)


def test_an_unidentified_owned_film_is_recognised_under_its_tmdb_title() -> None:
    films = [_unidentified("African Queen, The")]
    assert _lookalike(films, "The African Queen", 1951) is films[0]


def test_a_known_year_that_disagrees_is_not_a_lookalike() -> None:
    films = [_unidentified("Mummy, The", year=1999)]
    assert _lookalike(films, "The Mummy", 1932) is None
    assert _lookalike(films, "The Mummy", 1999) is films[0]


def test_a_different_title_is_not_a_lookalike() -> None:
    assert _lookalike([_unidentified("Heat")], "Heathers", 1989) is None


# ── The streaming lookup's cache — no database ───────────────────────────────


def _providers(*names: str) -> WatchProviders:
    return WatchProviders(
        results={
            "GB": WatchProviderCountry(
                link="https://www.themoviedb.org/movie/1/watch?locale=GB",
                flatrate=[
                    WatchProvider(provider_id=i, provider_name=name, logo_path="/logo.jpg")
                    for i, name in enumerate(names, start=1)
                ],
            )
        }
    )


class CountingProviders:
    def __init__(self, providers: WatchProviders, fail: bool = False) -> None:
        self.providers = providers
        self.fail = fail
        self.calls = 0

    async def get_watch_providers(self, movie_id: int) -> WatchProviders:
        del movie_id
        self.calls += 1
        if self.fail:
            raise httpx.ConnectError("TMDB is down")
        return self.providers


@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    discovery._streaming_cache.clear()


async def test_a_films_streaming_line_is_looked_up_once_while_somebody_types() -> None:
    tmdb = CountingProviders(_providers("Netflix"))
    for _ in range(3):
        assert await _cached_streaming_names(tmdb, 603, "GB") == ["Netflix"]
    assert tmdb.calls == 1


async def test_a_failed_lookup_is_not_cached() -> None:
    tmdb = CountingProviders(_providers("Netflix"), fail=True)
    assert await _cached_streaming_names(tmdb, 603, "GB") is None
    tmdb.fail = False
    assert await _cached_streaming_names(tmdb, 603, "GB") == ["Netflix"]
    assert tmdb.calls == 2


# ── The routes, against Postgres ─────────────────────────────────────────────


def _result(tmdb_id: int, title: str, release: str = "1995-12-15") -> SearchResult:
    return SearchResult(
        id=tmdb_id,
        title=title,
        original_title=title,
        overview=f"About {title}.",
        release_date=release,
        poster_path=f"/{tmdb_id}.jpg",
    )


class FakeTmdb:
    def __init__(
        self,
        results: list[SearchResult] | None = None,
        providers: WatchProviders | None = None,
        film: TmdbMovie | None = None,
        fail: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.providers = providers or WatchProviders()
        self.film = film
        self.fail = fail
        self.provider_lookups: list[int] = []

    async def search_movie(self, query: str, **_: object) -> SearchResults:
        del query
        if self.fail:
            raise self.fail
        return SearchResults(results=self.results, total_results=len(self.results))

    async def get_watch_providers(self, movie_id: int) -> WatchProviders:
        self.provider_lookups.append(movie_id)
        return self.providers

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        del movie_id, language
        if self.fail:
            raise self.fail
        assert self.film is not None
        return self.film


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _person(session: AsyncSession, name: str) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"{name} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
        streaming_region="GB",
    )
    session.add(profile)
    await session.flush()
    return profile


async def _film(
    session: AsyncSession,
    title: str,
    tmdb_id: int | None,
    *,
    disc: bool = True,
    year: int | None = 1995,
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
        genre_ids=[80],
    )
    session.add(movie)
    await session.flush()
    if disc:
        session.add(CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["blu_ray"]))
        await session.flush()
    return movie


async def _watched(session: AsyncSession, person: Profile, movie: Movie, when: date) -> None:
    session.add(WatchLog(id=uuid.uuid4(), movie_id=movie.id, user_id=person.id, watched_at=when))
    await session.flush()


def _install(session: AsyncSession, person: Profile, tmdb: FakeTmdb | None = None) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield session

    async def override_user() -> Profile:
        return person

    async def override_tmdb() -> AsyncIterator[FakeTmdb]:
        yield tmdb or FakeTmdb()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_each_person_sees_their_own_last_watch(api_session: AsyncSession) -> None:
    craig = await _person(api_session, "Craig")
    mark = await _person(api_session, "Mark")
    film = await _film(api_session, "Zebra Crossing Nocturne", 920071)
    await _watched(api_session, craig, film, date(2025, 3, 12))
    await _watched(api_session, craig, film, date(2024, 1, 2))
    await _watched(api_session, mark, film, date(2023, 7, 4))
    unseen = await _film(api_session, "Zebra Crossing Matinee", 920072)

    for person, expected in ((craig, "2025-03-12"), (mark, "2023-07-04")):
        _install(api_session, person)
        async with _client() as client:
            response = await client.get("/api/v1/search", params={"q": "Zebra Crossing"})
        assert response.status_code == 200
        by_id = {item["id"]: item for item in response.json()["items"]}
        assert by_id[str(film.id)]["lastWatchedAt"] == expected
        assert by_id[str(film.id)]["watched"] is True
        assert by_id[str(unseen.id)]["lastWatchedAt"] is None
        assert by_id[str(unseen.id)]["watched"] is False


async def test_beyond_the_shelf_never_repeats_an_owned_film(api_session: AsyncSession) -> None:
    person = await _person(api_session, "Craig")
    owned = await _film(api_session, "Heat", 949)
    tmdb = FakeTmdb(results=[_result(949, "Heat"), _result(10_001, "Heat Wave")])
    _install(api_session, person, tmdb)

    async with _client() as client:
        response = await client.get("/api/v1/search/beyond", params={"q": "heat"})

    assert response.status_code == 200
    ids = [item["tmdbId"] for item in response.json()["items"]]
    assert ids == [10_001]
    assert owned.tmdb_id not in ids


async def test_a_film_with_no_disc_links_to_its_own_page_and_history(
    api_session: AsyncSession,
) -> None:
    person = await _person(api_session, "Mark")
    sold = await _film(api_session, "Misery", 1700, disc=False, year=1990)
    await _watched(api_session, person, sold, date(2024, 10, 31))
    _install(api_session, person, FakeTmdb(results=[_result(1700, "Misery", "1990-11-30")]))

    async with _client() as client:
        response = await client.get("/api/v1/search/beyond", params={"q": "misery"})

    (item,) = response.json()["items"]
    assert item["movieId"] == str(sold.id)
    assert item["lastWatchedAt"] == "2024-10-31"


async def test_an_unidentified_owned_film_is_flagged_not_hidden(
    api_session: AsyncSession,
) -> None:
    person = await _person(api_session, "Craig")
    shelf = await _film(api_session, "African Queen, The", None, year=None)
    _install(
        api_session, person, FakeTmdb(results=[_result(488, "The African Queen", "1951-12-23")])
    )

    async with _client() as client:
        response = await client.get("/api/v1/search/beyond", params={"q": "african queen"})

    (item,) = response.json()["items"]
    assert item["tmdbId"] == 488
    assert item["maybeOwned"] == {"movieId": str(shelf.id), "title": "African Queen, The"}


async def test_only_the_first_few_results_get_a_streaming_lookup(
    api_session: AsyncSession,
) -> None:
    person = await _person(api_session, "Craig")
    results = [_result(20_000 + i, f"Streaming Test {i}") for i in range(8)]
    tmdb = FakeTmdb(results=results, providers=_providers("Netflix", "MUBI"))
    _install(api_session, person, tmdb)

    async with _client() as client:
        response = await client.get("/api/v1/search/beyond", params={"q": "streaming test"})

    items = response.json()["items"]
    assert len(tmdb.provider_lookups) == discovery.STREAMING_LOOKUPS
    assert items[0]["streamingOn"] == ["Netflix", "MUBI"]
    assert items[0]["streamingChecked"] is True
    assert items[-1]["streamingChecked"] is False
    assert items[-1]["streamingOn"] == []


async def test_tmdb_being_down_is_a_state_not_an_error(api_session: AsyncSession) -> None:
    person = await _person(api_session, "Craig")
    _install(api_session, person, FakeTmdb(fail=httpx.ConnectError("down")))

    async with _client() as client:
        response = await client.get("/api/v1/search/beyond", params={"q": "heat"})

    assert response.status_code == 200
    assert response.json() == {"query": "heat", "items": [], "unavailable": True}


def _tmdb_film(tmdb_id: int = 11_050) -> TmdbMovie:
    return TmdbMovie.model_validate(
        {
            "id": tmdb_id,
            "title": "The Card Player",
            "original_title": "The Card Player",
            "overview": "A film nobody here owns.",
            "release_date": "2004-01-02",
            "runtime": 103,
            "poster_path": "/card.jpg",
            "genres": [Genre(id=53, name="Thriller").model_dump()],
            "credits": Credits(
                cast=[
                    CastMember(id=2, name="Second Billed", character="B", order=1, credit_id="c2"),
                    CastMember(id=1, name="Top Billed", character="A", order=0, credit_id="c1"),
                ],
                crew=[
                    CrewMember(
                        id=3,
                        name="Dario Argento",
                        job="Director",
                        department="Directing",
                        credit_id="c3",
                    )
                ],
            ).model_dump(),
            "watch/providers": WatchProviders(
                results={
                    "GB": WatchProviderCountry(
                        link="https://www.themoviedb.org/movie/11050/watch?locale=GB",
                        flatrate=[
                            WatchProvider(
                                provider_id=8, provider_name="Netflix", logo_path="/logo.jpg"
                            )
                        ],
                        rent=[
                            WatchProvider(
                                provider_id=2, provider_name="Apple TV", logo_path="/logo.jpg"
                            )
                        ],
                    )
                }
            ).model_dump(),
        }
    )


async def test_the_film_card_describes_a_stranger(api_session: AsyncSession) -> None:
    person = await _person(api_session, "Craig")
    _install(api_session, person, FakeTmdb(film=_tmdb_film()))

    async with _client() as client:
        response = await client.get("/api/v1/films/tmdb/11050")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "The Card Player"
    assert body["year"] == 2004
    assert body["cast"] == ["Top Billed", "Second Billed"]
    assert body["directors"] == ["Dario Argento"]
    assert [(offer["providerName"], offer["kind"]) for offer in body["offers"]] == [
        ("Netflix", "flatrate"),
        ("Apple TV", "rent"),
    ]
    assert body["owned"] is False
    assert body["wanted"] is False
    assert body["movieId"] is None


async def test_the_film_card_knows_an_owned_and_a_wanted_film(api_session: AsyncSession) -> None:
    person = await _person(api_session, "Craig")
    owned = await _film(api_session, "The Card Player", 11_050)
    wanted = await _film(api_session, "The Card Player II", 11_051, disc=False)
    api_session.add(WantedItem(id=uuid.uuid4(), movie_id=wanted.id, added_by=person.id))
    await api_session.flush()

    _install(api_session, person, FakeTmdb(film=_tmdb_film(11_050)))
    async with _client() as client:
        first = (await client.get("/api/v1/films/tmdb/11050")).json()
    _install(api_session, person, FakeTmdb(film=_tmdb_film(11_051)))
    async with _client() as client:
        second = (await client.get("/api/v1/films/tmdb/11051")).json()

    assert first["owned"] is True
    assert first["movieId"] == str(owned.id)
    assert second["owned"] is False
    assert second["wanted"] is True


async def test_the_film_card_passes_on_tmdbs_not_found(api_session: AsyncSession) -> None:
    person = await _person(api_session, "Craig")
    request = httpx.Request("GET", "https://api.themoviedb.org/3/movie/1")
    missing = httpx.HTTPStatusError(
        "missing", request=request, response=httpx.Response(404, request=request)
    )
    _install(api_session, person, FakeTmdb(fail=missing))

    async with _client() as client:
        response = await client.get("/api/v1/films/tmdb/1")

    assert response.status_code == 404
