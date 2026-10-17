"""Postgres-backed contract tests for Batch 12's smart collections — §11.5, §3.23.

§11.5's acceptance: *"Creating 'Unwatched 4Ks from 2010s' lists correct films and updates
live"*. Three separate claims, tested separately — that the collection can be created,
that its results are the right films, and that they change without the collection being
touched.

**Why the fixtures live in the 2080s.** The live database holds real unwatched 4K films
from the 2010s, so a test asserting "these are the results" for that literal decade would
be asserting something about 1,857 real rows that a future disc could falsify —
`STATUS.md`'s Now block is the record of four tests that failed exactly that way. The
decade is shifted to one no real disc can occupy; the *shape* of the filter (format +
decade + unwatched) is the criterion's own, and
:func:`test_results_agree_exactly_with_the_same_filters_on_the_movies_endpoint` covers the
literal 2010s case without claiming to know what is in it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.smart_collection import SmartCollection
from src.models.watch_log import WatchLog

ACTOR_HEADER = "x-test-actor"

#: A decade with no real discs in it. See the module docstring.
FIXTURE_DECADE = 2080

UNWATCHED_4K_FILTERS = {
    "format": "4k_uhd",
    "decadeFrom": FIXTURE_DECADE,
    "decadeTo": FIXTURE_DECADE,
    "watched": False,
}


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


async def _profile(session: AsyncSession, label: str) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Batch Twelve {label} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
    )
    session.add(profile)
    await session.flush()
    return profile


@pytest_asyncio.fixture
async def owner(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, "Owner")


@pytest_asyncio.fixture
async def other(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, "Other")


@pytest_asyncio.fixture
async def overrides(
    api_session: AsyncSession, owner: Profile, other: Profile
) -> AsyncIterator[None]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user(request: Request) -> Profile:
        return other if request.headers.get(ACTOR_HEADER) == "other" else owner

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def _client_as(actor: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={ACTOR_HEADER: actor},
    )


@pytest_asyncio.fixture
async def client(overrides: None) -> AsyncIterator[AsyncClient]:
    del overrides
    async with _client_as("owner") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def other_client(overrides: None) -> AsyncIterator[AsyncClient]:
    del overrides
    async with _client_as("other") as http_client:
        yield http_client


async def _film(
    session: AsyncSession,
    title: str,
    *,
    year: int,
    formats: list[str],
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
    )
    session.add(movie)
    await session.flush()
    session.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=formats,
            location="Front 1st shelf",
            section="Front",
            shelf="1st",
            condition="good",
        )
    )
    await session.flush()
    return movie


async def _create(client: AsyncClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": f"Unwatched 4Ks from the {FIXTURE_DECADE}s",
        "icon": "sparkles",
        "filters": UNWATCHED_4K_FILTERS,
    }
    payload.update(overrides)
    response = await client.post("/api/v1/smart-collections", json=payload)
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


# ---------------------------------------------------------------------------
# §11.5 — "lists correct films"
# ---------------------------------------------------------------------------


async def test_a_saved_collection_lists_exactly_the_films_its_filters_describe(
    client: AsyncClient, api_session: AsyncSession, owner: Profile
) -> None:
    wanted = await _film(
        api_session, "An Unwatched 4K", year=FIXTURE_DECADE + 1, formats=["4k_uhd"]
    )
    # One near miss per criterion, so a filter that silently stopped applying shows up
    # as a specific extra film rather than as a count that is merely too high.
    await _film(api_session, "A 4K From The Wrong Decade", year=2075, formats=["4k_uhd"])
    await _film(
        api_session, "A Blu-ray Of The Right Age", year=FIXTURE_DECADE + 2, formats=["blu_ray"]
    )
    seen = await _film(
        api_session, "A 4K Already Watched", year=FIXTURE_DECADE + 3, formats=["4k_uhd"]
    )
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=seen.id,
            user_id=owner.id,
            watched_at=date(2026, 1, 1),
        )
    )
    await api_session.flush()

    collection = await _create(client)
    results = await client.get(f"/api/v1/smart-collections/{collection['id']}/results")

    assert results.status_code == 200, results.text
    body = results.json()
    assert [item["title"] for item in body["items"]] == ["An Unwatched 4K"]
    assert body["totalMovies"] == 1
    assert body["collection"]["name"] == collection["name"]
    del wanted


async def test_results_update_live_without_the_collection_being_touched(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§3.23: *"Evaluated at query time — no materialisation."*

    The collection row is not written to between the two reads. If results were
    materialised at save time, the second call would still say one film.
    """
    await _film(api_session, "The First 4K", year=FIXTURE_DECADE + 1, formats=["4k_uhd"])
    collection = await _create(client)

    first = await client.get(f"/api/v1/smart-collections/{collection['id']}/results")
    assert first.json()["totalMovies"] == 1

    await _film(api_session, "A Later Purchase", year=FIXTURE_DECADE + 4, formats=["4k_uhd"])

    second = await client.get(f"/api/v1/smart-collections/{collection['id']}/results")
    assert second.json()["totalMovies"] == 2
    assert sorted(item["title"] for item in second.json()["items"]) == [
        "A Later Purchase",
        "The First 4K",
    ]
    # And the saved row itself never changed.
    assert second.json()["collection"]["updatedAt"] == collection["updatedAt"]


async def test_results_agree_exactly_with_the_same_filters_on_the_movies_endpoint(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The anti-drift criterion, and the reason ``movie_page`` was extracted.

    A saved collection is a saved filter-bar state. If the two ever disagreed, the
    disagreement would be invisible — both would return a plausible page of films. This
    runs the *literal* "Unwatched 4Ks from the 2010s" of §11.5's wording against the real
    catalogue and asserts only that the two routes answer identically, which is true
    whatever the live data happens to hold.
    """
    await _film(api_session, "A 2010s 4K Fixture", year=2015, formats=["4k_uhd"])

    collection = await _create(
        client,
        name="Unwatched 4Ks from the 2010s",
        filters={"format": "4k_uhd", "decadeFrom": 2010, "decadeTo": 2010, "watched": False},
    )
    via_collection = await client.get(
        f"/api/v1/smart-collections/{collection['id']}/results?perPage=200"
    )
    via_movies = await client.get(
        "/api/v1/movies?format=4k_uhd&decadeFrom=2010&decadeTo=2010&watched=false&perPage=200"
    )

    assert via_collection.status_code == 200 and via_movies.status_code == 200
    left, right = via_collection.json(), via_movies.json()
    assert left["totalMovies"] == right["totalMovies"]
    assert left["totalItems"] == right["totalItems"]
    assert left["items"] == right["items"]
    assert left["totalMovies"] >= 1


async def test_the_watched_filter_is_about_the_person_reading_it(
    client: AsyncClient, other_client: AsyncClient, api_session: AsyncSession, owner: Profile
) -> None:
    """Watched-status is the one genuinely per-person fact in this app.

    The collection is private to its owner, so this is really a check that the results
    endpoint scopes the ``EXISTS`` to the caller rather than to whoever logged a watch.
    """
    film = await _film(
        api_session, "Watched By One Of Us", year=FIXTURE_DECADE + 5, formats=["4k_uhd"]
    )
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=film.id,
            user_id=owner.id,
            watched_at=date(2026, 1, 1),
        )
    )
    await api_session.flush()

    mine = await _create(client)
    assert (await client.get(f"/api/v1/smart-collections/{mine['id']}/results")).json()[
        "totalMovies"
    ] == 0

    theirs = await _create(other_client)
    assert (await other_client.get(f"/api/v1/smart-collections/{theirs['id']}/results")).json()[
        "totalMovies"
    ] == 1


# ---------------------------------------------------------------------------
# The filter blob is a query, so what may be stored is closed
# ---------------------------------------------------------------------------


async def test_an_unknown_filter_key_is_refused_rather_than_stored_and_ignored(
    client: AsyncClient,
) -> None:
    """A key that survived into JSONB and was then dropped at evaluation would produce a
    collection listing the wrong films with total confidence."""
    response = await client.post(
        "/api/v1/smart-collections",
        json={"name": "Sneaky", "filters": {"format": "4k_uhd", "orderBy": "1; DROP TABLE"}},
    )
    assert response.status_code == 422


async def test_an_unknown_section_is_refused(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/smart-collections",
        json={"name": "Nowhere", "filters": {"section": "The Attic"}},
    )
    assert response.status_code == 422


async def test_an_unknown_icon_is_refused(client: AsyncClient) -> None:
    """The icon is rendered as a component name, so the vocabulary is closed."""
    response = await client.post(
        "/api/v1/smart-collections", json={"name": "Bad Icon", "icon": "skull-and-crossbones"}
    )
    assert response.status_code == 422


async def test_a_half_decade_is_refused(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/smart-collections",
        json={"name": "Mid-decade", "filters": {"decadeFrom": 2015}},
    )
    assert response.status_code == 422


async def test_the_column_stores_only_the_constrained_fields(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Two different shapes on purpose, so neither is an accident.

    **The column holds only what the collection constrains.** A stored blob full of
    nulls invites a reader — a future migration, a hand-written query, a person looking
    at the row — to treat ``watched: null`` as "unwatched", and it makes the saved query
    harder to read than the sentence it came from.

    **The wire carries every key.** A client is parsing this through a zod schema and
    then rendering it into a form; an explicit ``null`` says "this filter is off" without
    the client having to distinguish absent from unset.
    """
    collection = await _create(client)
    stored = await api_session.get(SmartCollection, uuid.UUID(str(collection["id"])))
    assert stored is not None
    assert stored.filters == {
        "format": "4k_uhd",
        "decadeFrom": FIXTURE_DECADE,
        "decadeTo": FIXTURE_DECADE,
        "watched": False,
    }

    assert collection["filters"] == {
        "genreId": None,
        # Batch Y5: the vocabulary gained a TMDB keyword (Film Noir), and the wire carries it.
        "keywordId": None,
        "year": None,
        "format": "4k_uhd",
        "section": None,
        "shelf": None,
        "decadeFrom": FIXTURE_DECADE,
        "decadeTo": FIXTURE_DECADE,
        "minRating": None,
        # Batch T3: the vocabulary gained runtime, and the wire carries every key.
        "runtimeMin": None,
        "runtimeMax": None,
        "watched": False,
    }


# ---------------------------------------------------------------------------
# Ownership, pinning and the rest of CRUD
# ---------------------------------------------------------------------------


async def test_a_collection_is_private_to_its_owner(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    mine = await _create(client)

    assert (await other_client.get("/api/v1/smart-collections")).json()["total"] == 0
    # 404 rather than 403: whether that id exists in someone else's sidebar is not
    # something this response should confirm.
    assert (
        await other_client.get(f"/api/v1/smart-collections/{mine['id']}/results")
    ).status_code == 404
    assert (
        await other_client.request("DELETE", f"/api/v1/smart-collections/{mine['id']}")
    ).status_code == 404


async def test_editing_changes_the_filters_and_the_results_follow(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    await _film(api_session, "A 4K", year=FIXTURE_DECADE + 1, formats=["4k_uhd"])
    await _film(api_session, "A DVD", year=FIXTURE_DECADE + 1, formats=["dvd"])
    collection = await _create(client)

    updated = await client.put(
        f"/api/v1/smart-collections/{collection['id']}",
        json={
            "name": "Unwatched DVDs instead",
            "icon": "disc",
            "filters": {**UNWATCHED_4K_FILTERS, "format": "dvd"},
            "sortBy": "year",
            "sortOrder": "desc",
            "isPinned": True,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["isPinned"] is True

    results = await client.get(f"/api/v1/smart-collections/{collection['id']}/results")
    assert [item["title"] for item in results.json()["items"]] == ["A DVD"]


async def test_pinned_collections_are_what_the_dashboard_asks_for(
    client: AsyncClient,
) -> None:
    await _create(client, name="Pinned One", isPinned=True)
    await _create(client, name="Not Pinned", isPinned=False)

    pinned = await client.get("/api/v1/smart-collections?pinned=true")
    assert [c["name"] for c in pinned.json()["items"]] == ["Pinned One"]
    assert (await client.get("/api/v1/smart-collections")).json()["total"] == 2


async def test_two_collections_cannot_share_a_name(client: AsyncClient) -> None:
    await _create(client, name="Duplicated")
    response = await client.post(
        "/api/v1/smart-collections", json={"name": "Duplicated", "filters": {}}
    )
    assert response.status_code == 409


async def test_the_same_name_is_free_for_the_other_person(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    await _create(client, name="Favourites")
    response = await other_client.post(
        "/api/v1/smart-collections", json={"name": "Favourites", "filters": {}}
    )
    assert response.status_code == 201


async def test_deleting_removes_it(client: AsyncClient) -> None:
    collection = await _create(client)
    response = await client.request("DELETE", f"/api/v1/smart-collections/{collection['id']}")
    assert response.status_code == 204
    assert (await client.get("/api/v1/smart-collections")).json()["total"] == 0


async def test_an_empty_filter_set_is_the_whole_collection(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """ "Everything" is a legitimate saved collection, and it must not mean "nothing".

    Two fixture films rather than one, and a lower bound of 2 rather than "more than
    one". The first version asserted ``> 1`` on the strength of the 1,857 real rows a
    local run sees — exactly the environment assumption `STATUS.md`'s Now block was
    written about. It passed locally and failed in CI, whose database holds only what the
    test put in it. The bound now rests on this test's own fixtures rather than on which
    database it happens to be pointed at.
    """
    await _film(api_session, "Any Film At All", year=FIXTURE_DECADE + 1, formats=["dvd"])
    await _film(api_session, "Another Film Entirely", year=FIXTURE_DECADE + 2, formats=["dvd"])
    collection = await _create(client, name="Everything", filters={})

    results = await client.get(f"/api/v1/smart-collections/{collection['id']}/results")
    everything = await client.get("/api/v1/movies?perPage=1")
    assert results.json()["totalMovies"] == everything.json()["totalMovies"]
    assert results.json()["totalMovies"] >= 2
