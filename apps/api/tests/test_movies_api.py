"""Postgres-backed contract tests for Batch 5's read and identify surface."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie, MovieCredit
from src.models.profile import Profile, UserRole
from src.routers.movies import get_tmdb_client
from src.tmdb.models import (
    CastMember,
    Credits,
    CrewMember,
    Genre,
    SearchResult,
    SearchResults,
)
from src.tmdb.models import (
    Movie as TmdbMovie,
)

pytestmark = pytest.mark.asyncio


def _tmdb_movie(tmdb_id: int = 550) -> TmdbMovie:
    return TmdbMovie(
        id=tmdb_id,
        title="The Identified Film",
        original_title="The Identified Film",
        overview="A quetzalcoatlus crosses an impossible ocean.",
        release_date="1999-10-15",
        runtime=139,
        tagline="Metadata makes it visible.",
        vote_average=8.4,
        vote_count=26280,
        poster_path="/identified.jpg",
        backdrop_path="/identified-backdrop.jpg",
        genres=[Genre(id=18, name="Drama")],
        imdb_id="tt0137523",
        credits=Credits(
            cast=[
                CastMember(
                    id=1,
                    name="Visible Actor",
                    character="The Collector",
                    order=0,
                    profile_path="/actor.jpg",
                    credit_id="cast-1",
                )
            ],
            crew=[
                CrewMember(
                    id=2,
                    name="Stanley Kubrick",
                    job="Director",
                    department="Directing",
                    credit_id="crew-1",
                )
            ],
        ),
    )


class FakeTmdbClient:
    async def search_movie(
        self,
        query: str,
        year: int | None = None,
        page: int = 1,
        language: str = "en-US",
        include_adult: bool = False,
    ) -> SearchResults:
        del year, page, language, include_adult
        return SearchResults(
            page=1,
            total_pages=1,
            total_results=1,
            results=[
                SearchResult(
                    id=550,
                    title="The Identified Film",
                    original_title="The Identified Film",
                    overview=f"Candidate overview for {query}",
                    release_date="1999-10-15",
                    poster_path="/candidate.jpg",
                    popularity=10,
                )
            ],
        )

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        del language
        return _tmdb_movie(movie_id)


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def client(api_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    viewer = Profile(
        id=uuid.uuid4(),
        display_name="Batch Five Viewer",
        pin_hash=None,
        role=UserRole.viewer,
    )

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user() -> Profile:
        return viewer

    async def override_tmdb() -> AsyncIterator[FakeTmdbClient]:
        yield FakeTmdbClient()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


async def _add_owned_movie(
    session: AsyncSession,
    *,
    title: str,
    tmdb_id: int | None,
    formats: list[str] | None = None,
    year: int | None = None,
    overview: str | None = None,
    genres: list[dict[str, Any]] | None = None,
) -> tuple[Movie, CollectionItem]:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=year,
        overview=overview,
        genres=genres,
        genre_ids=[genre["id"] for genre in genres] if genres else None,
        media_type="film",
    )
    session.add(movie)
    # The models deliberately expose no ORM relationship — read paths do explicit,
    # bounded queries — so establish the FK target before inserting its copy.
    await session.flush()
    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=formats or ["blu_ray"],
        location="Front 2nd shelf",
        section="Front",
        shelf="2nd",
        condition="good",
    )
    session.add(item)
    await session.flush()
    return movie, item


async def test_list_is_paginated_camel_case_and_counts_copies(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie, _ = await _add_owned_movie(
        api_session,
        title="A Batch Five Film",
        tmdb_id=910001,
        formats=["4k_uhd"],
        year=2001,
        genres=[{"id": 18, "name": "Drama"}],
    )
    api_session.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=["dvd"],
            condition="good",
        )
    )
    await api_session.flush()

    response = await client.get(
        "/api/v1/movies",
        params={"genreId": 18, "year": 2001, "format": "4k_uhd", "perPage": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "totalMovies", "totalItems", "page", "perPage", "pages"}
    assert body["totalMovies"] == 1
    # The filtered item count answers how many 4K objects match, while the card still
    # shows that the selected film has two copies in total.
    assert body["totalItems"] == 1
    assert body["items"][0]["id"] == str(movie.id)
    assert body["items"][0]["copyCount"] == 2
    assert body["items"][0]["bestFormatOwned"] == "4k_uhd"
    assert "tmdb_id" not in body["items"][0]


async def test_detail_and_copies_show_metadata_and_location(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie, item = await _add_owned_movie(
        api_session,
        title="Located Film",
        tmdb_id=910002,
        overview="Visible detail metadata.",
    )
    movie.top_cast_summary = [
        {
            "tmdb_person_id": 3,
            "name": "An Actor",
            "character_name": "Someone",
            "profile_path": "/profile.jpg",
        }
    ]
    api_session.add(
        MovieCredit(
            id=uuid.uuid4(),
            movie_id=movie.id,
            person_name="An Actor",
            tmdb_person_id=3,
            role="cast",
            character_name="Someone",
            display_order=0,
        )
    )
    await api_session.flush()

    detail = await client.get(f"/api/v1/movies/{movie.id}")
    copies = await client.get(f"/api/v1/movies/{movie.id}/copies")

    assert detail.status_code == 200
    assert detail.json()["overview"] == "Visible detail metadata."
    assert detail.json()["cast"][0]["profilePath"] == "/profile.jpg"
    assert copies.status_code == 200
    assert copies.json()[0]["id"] == str(item.id)
    assert copies.json()[0]["location"] == "Front 2nd shelf"
    assert copies.json()[0]["formats"] == ["blu_ray"]


async def test_search_uses_the_database_search_document(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie, _ = await _add_owned_movie(
        api_session,
        title="A Plain Title",
        tmdb_id=910003,
        overview="A quokka solves the mystery.",
    )

    response = await client.get("/api/v1/search", params={"q": "quokka"})

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(movie.id)
    assert response.json()["query"] == "quokka"


async def test_candidates_include_the_information_needed_to_choose(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie, _ = await _add_owned_movie(
        api_session,
        title="Unidentified shelf title",
        tmdb_id=None,
    )

    response = await client.get(
        f"/api/v1/movies/{movie.id}/candidates",
        params={"query": "A better title"},
    )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["tmdbId"] == 550
    assert candidate["year"] == 1999
    assert candidate["posterPath"] == "/candidate.jpg"
    assert candidate["overview"] == "Candidate overview for A better title"


async def test_viewer_can_identify_and_search_new_metadata(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie, _ = await _add_owned_movie(
        api_session,
        title="Unidentified shelf title",
        tmdb_id=None,
    )

    identified = await client.post(
        f"/api/v1/movies/{movie.id}/identify",
        json={"tmdbId": 550},
    )

    assert identified.status_code == 200
    body = identified.json()
    assert body["id"] == str(movie.id)
    assert body["identified"] is True
    assert body["posterPath"] == "/identified.jpg"
    assert body["overview"] == "A quetzalcoatlus crosses an impossible ocean."
    assert body["cast"][0]["personName"] == "Visible Actor"

    search = await client.get("/api/v1/search", params={"q": "quetzalcoatlus"})
    assert search.status_code == 200
    assert [item["id"] for item in search.json()["items"]] == [str(movie.id)]


async def test_correcting_to_an_existing_film_merges_the_copies(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    wrong, _ = await _add_owned_movie(
        api_session,
        title="Wrong sibling",
        tmdb_id=910004,
    )
    correct, _ = await _add_owned_movie(
        api_session,
        title="Existing correct film",
        tmdb_id=550,
        formats=["dvd"],
    )

    response = await client.post(
        f"/api/v1/movies/{wrong.id}/identify",
        json={"tmdbId": 550},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(correct.id)
    assert response.json()["copyCount"] == 2
    assert await api_session.get(Movie, wrong.id) is None
    moved = (
        (
            await api_session.execute(
                select(CollectionItem).where(CollectionItem.movie_id == correct.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(moved) == 2
