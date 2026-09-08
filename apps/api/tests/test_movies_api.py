"""Postgres-backed contract tests for Batch 5's read and identify surface."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
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
from src.models.watch_log import WatchLog
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
async def viewer(api_session: AsyncSession) -> Profile:
    """A persisted profile.

    Batch 5 could get away with an unsaved object because nothing referenced it.
    ``watch_log.user_id`` is a real foreign key, so the row has to exist.
    """
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Batch Six Viewer {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
    )
    api_session.add(profile)
    await api_session.flush()
    return profile


@pytest_asyncio.fixture
async def client(api_session: AsyncSession, viewer: Profile) -> AsyncIterator[AsyncClient]:
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
    section: str | None = "Front",
    shelf: str | None = "2nd",
    location: str | None = "Front 2nd shelf",
    tmdb_rating: float | None = None,
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
        tmdb_rating=Decimal(str(tmdb_rating)) if tmdb_rating is not None else None,
    )
    session.add(movie)
    # The models deliberately expose no ORM relationship — read paths do explicit,
    # bounded queries — so establish the FK target before inserting its copy.
    await session.flush()
    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=formats or ["blu_ray"],
        location=location,
        section=section,
        shelf=shelf,
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


# ---------------------------------------------------------------------------
# Batch 6 — location filters, facets and watched status
# ---------------------------------------------------------------------------


async def test_section_and_shelf_filter_answers_the_front_2nd_shelf_question(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """§6.2's promise, unimplementable since April: "everything on the Front 2nd shelf"."""
    wanted, _ = await _add_owned_movie(
        api_session,
        title="On The Front Second Shelf",
        tmdb_id=920001,
        section="Front",
        shelf="2nd",
        location="Front 2nd Shelf",
    )
    await _add_owned_movie(
        api_session,
        title="On A Different Front Shelf",
        tmdb_id=920002,
        section="Front",
        shelf="5th",
        location="Front 5th Shelf",
    )
    await _add_owned_movie(
        api_session,
        title="On The Back Second Shelf",
        tmdb_id=920003,
        section="Back",
        shelf="2nd",
        location="Back 2nd Shelf",
    )

    response = await client.get(
        "/api/v1/movies", params={"section": "Front", "shelf": "2nd", "perPage": 200}
    )

    assert response.status_code == 200
    body = response.json()
    titles = [item["title"] for item in body["items"]]
    assert "On The Front Second Shelf" in titles
    assert "On A Different Front Shelf" not in titles
    assert "On The Back Second Shelf" not in titles

    # The result carries where the disc is, which is the whole point of asking.
    match = next(item for item in body["items"] if item["id"] == str(wanted.id))
    assert match["locations"] == [{"section": "Front", "shelf": "2nd", "label": "Front 2nd"}]


async def test_a_cabinet_is_a_section_a_filter_can_reach(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The 122 cabinet discs Batch 6 brought into the vocabulary (`DECISIONS.md` #34)."""
    await _add_owned_movie(
        api_session,
        title="In The Big Cabinet",
        tmdb_id=920010,
        section="Top Big Cabinet",
        shelf=None,
        location="Top Big Cabinet",
    )

    response = await client.get(
        "/api/v1/movies", params={"section": "Top Big Cabinet", "perPage": 200}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["title"] for item in items] == ["In The Big Cabinet"]
    # No shelf, so the label is the section alone rather than "Top Big Cabinet None".
    assert items[0]["locations"] == [
        {"section": "Top Big Cabinet", "shelf": None, "label": "Top Big Cabinet"}
    ]


async def test_unknown_section_is_refused_rather_than_silently_matching_nothing(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/movies", params={"section": "Attic"})
    assert response.status_code == 422
    assert "Attic" not in response.json()["detail"]


async def test_a_film_kept_in_two_places_reports_both(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie, _ = await _add_owned_movie(
        api_session,
        title="Owned On Disc And Digitally",
        tmdb_id=920020,
        section="Front",
        shelf="3rd",
        location="Front 3rd Shelf & E:\\Movies",
    )
    api_session.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=["download"],
            location="E:\\Movies",
            section="Digital",
            condition="good",
        )
    )
    await api_session.flush()

    response = await client.get("/api/v1/movies", params={"section": "Digital", "perPage": 200})

    assert response.status_code == 200
    match = next(item for item in response.json()["items"] if item["id"] == str(movie.id))
    # Filtering by one of its homes still shows every home it has — otherwise the card
    # would claim the disc is only in the place you happened to filter on.
    assert {location["label"] for location in match["locations"]} == {
        "Digital",
        "Front 3rd",
    }


async def test_decade_range_covers_the_pre_1970_collection(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The old single-year select started at 1970 and hid 47% of the dated collection."""
    await _add_owned_movie(api_session, title="A 1931 Film", tmdb_id=920030, year=1931)
    await _add_owned_movie(api_session, title="A 1949 Film", tmdb_id=920031, year=1949)
    await _add_owned_movie(api_session, title="A 1955 Film", tmdb_id=920032, year=1955)
    await _add_owned_movie(api_session, title="A 2019 Film", tmdb_id=920033, year=2019)

    response = await client.get(
        "/api/v1/movies",
        params={"decadeFrom": 1930, "decadeTo": 1940, "perPage": 500},
    )

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "A 1931 Film" in titles
    # Inclusive of the whole closing decade: 1949 is inside "to the 1940s".
    assert "A 1949 Film" in titles
    assert "A 1955 Film" not in titles
    assert "A 2019 Film" not in titles


async def test_decade_bounds_are_validated(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/movies", params={"decadeFrom": 1935})).status_code == 422
    inverted = await client.get("/api/v1/movies", params={"decadeFrom": 2000, "decadeTo": 1980})
    assert inverted.status_code == 422


async def test_min_rating_excludes_unrated_rather_than_treating_them_as_zero(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    await _add_owned_movie(api_session, title="Highly Rated Film", tmdb_id=920040, tmdb_rating=8.4)
    await _add_owned_movie(api_session, title="Poorly Rated Film", tmdb_id=920041, tmdb_rating=4.1)
    # Unidentified, so TMDB has told us nothing about it at all.
    await _add_owned_movie(api_session, title="Unrated Film", tmdb_id=None)

    response = await client.get("/api/v1/movies", params={"minRating": 7, "perPage": 500})

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "Highly Rated Film" in titles
    assert "Poorly Rated Film" not in titles
    assert "Unrated Film" not in titles


async def test_watched_status_is_per_user(
    client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
) -> None:
    seen, _ = await _add_owned_movie(api_session, title="Already Seen", tmdb_id=920050)
    unseen, _ = await _add_owned_movie(api_session, title="Not Yet Seen", tmdb_id=920051)

    other = Profile(
        id=uuid.uuid4(),
        display_name=f"Someone Else {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
    )
    api_session.add(other)
    await api_session.flush()

    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=seen.id,
            user_id=viewer.id,
            watched_at=date.today() - timedelta(days=3),
        )
    )
    # The other user's history must not colour this user's answer.
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=unseen.id,
            user_id=other.id,
            watched_at=date.today(),
        )
    )
    await api_session.flush()

    watched = await client.get("/api/v1/movies", params={"watched": True, "perPage": 500})
    unwatched = await client.get("/api/v1/movies", params={"watched": False, "perPage": 500})

    assert watched.status_code == 200
    watched_titles = [item["title"] for item in watched.json()["items"]]
    unwatched_titles = [item["title"] for item in unwatched.json()["items"]]
    assert "Already Seen" in watched_titles
    assert "Not Yet Seen" not in watched_titles
    assert "Not Yet Seen" in unwatched_titles
    assert "Already Seen" not in unwatched_titles

    # And the flag on the row agrees with the filter that selected it.
    assert next(item for item in watched.json()["items"] if item["id"] == str(seen.id))["watched"]


async def test_a_soft_deleted_watch_no_longer_counts_as_watched(
    client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
) -> None:
    movie, _ = await _add_owned_movie(api_session, title="Logged Then Undone", tmdb_id=920060)
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=movie.id,
            user_id=viewer.id,
            watched_at=date.today(),
            deleted_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await api_session.flush()

    response = await client.get("/api/v1/movies", params={"watched": True, "perPage": 500})

    assert response.status_code == 200
    assert str(movie.id) not in [item["id"] for item in response.json()["items"]]


async def test_search_results_carry_location_and_watched_state(
    client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
) -> None:
    """Search shares the list DTO, so it must fill the same two fields the grid reads."""
    movie, _ = await _add_owned_movie(
        api_session,
        title="Zamboni Nocturne",
        tmdb_id=920070,
        overview="A quiet film about resurfacing ice.",
        section="Back",
        shelf="4th",
        location="Back 4th Shelf",
    )
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=movie.id,
            user_id=viewer.id,
            watched_at=date.today(),
        )
    )
    await api_session.flush()

    response = await client.get("/api/v1/search", params={"q": "Zamboni"})

    assert response.status_code == 200
    match = next(item for item in response.json()["items"] if item["id"] == str(movie.id))
    assert match["locations"] == [{"section": "Back", "shelf": "4th", "label": "Back 4th"}]
    assert match["watched"] is True


async def test_facets_are_served_from_the_data(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    await _add_owned_movie(
        api_session,
        title="Facet Front Second",
        tmdb_id=920080,
        year=1954,
        section="Front",
        shelf="2nd",
    )
    await _add_owned_movie(
        api_session,
        title="Facet Cabinet",
        tmdb_id=920081,
        year=1954,
        section="Top Big Cabinet",
        shelf=None,
        location="Top Big Cabinet",
    )
    await _add_owned_movie(
        api_session,
        title="Facet Unfiled",
        tmdb_id=920082,
        section=None,
        shelf=None,
        location="(In with The Killing)",
    )
    await _add_owned_movie(api_session, title="Facet Undated", tmdb_id=None, year=None)

    response = await client.get("/api/v1/collection/facets")

    assert response.status_code == 200
    body = response.json()
    sections = {section["section"]: section for section in body["sections"]}

    assert "2nd" in [shelf["shelf"] for shelf in sections["Front"]["shelves"]]
    # A cabinet has no shelves, so it offers none rather than an empty-looking picker.
    assert sections["Top Big Cabinet"]["shelves"] == []
    assert sections["Top Big Cabinet"]["itemCount"] >= 1
    assert body["unsectionedItemCount"] >= 1

    decades = {decade["decade"] for decade in body["decades"]}
    assert 1950 in decades
    # Films with no year cannot appear in any decade, and the count says so rather
    # than leaving the totals quietly short.
    assert body["undatedMovieCount"] >= 1


async def test_identifying_a_film_keeps_the_watch_history_it_already_had(
    client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
) -> None:
    """The merge hard-deletes the source row, and ``RESTRICT`` would refuse it."""
    wrong, _ = await _add_owned_movie(api_session, title="Wrong Sibling", tmdb_id=None)
    correct, _ = await _add_owned_movie(
        api_session, title="Existing correct film", tmdb_id=550, formats=["dvd"]
    )
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=wrong.id,
            user_id=viewer.id,
            watched_at=date.today(),
        )
    )
    await api_session.flush()

    response = await client.post(f"/api/v1/movies/{wrong.id}/identify", json={"tmdbId": 550})

    assert response.status_code == 200
    assert await api_session.get(Movie, wrong.id) is None
    moved = (
        (await api_session.execute(select(WatchLog).where(WatchLog.movie_id == correct.id)))
        .scalars()
        .all()
    )
    assert len(moved) == 1
