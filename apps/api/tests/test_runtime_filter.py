"""Batch T3, snag 2 — the Archive filters by runtime, and so does a saved collection.

A film with no runtime is excluded whenever either bound is set: the rating filter's rule,
and the only reading that claims nothing unknown. The saved-collection half matters because
a saved collection *is* a saved filter-bar state — the two must mean the same thing.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.schemas.collections import SmartCollectionFilters

# ── The saved vocabulary — no database ───────────────────────────────────────


def test_a_saved_collection_accepts_a_runtime_range() -> None:
    filters = SmartCollectionFilters(runtimeMin=90, runtimeMax=120)
    assert filters.stored() == {"runtimeMin": 90, "runtimeMax": 120}


def test_a_saved_collection_refuses_a_backwards_runtime_range() -> None:
    with pytest.raises(ValidationError, match="runtimeMin must not be more than runtimeMax"):
        SmartCollectionFilters(runtimeMin=150, runtimeMax=90)


# ── The routes, against Postgres ─────────────────────────────────────────────

MARKER = f"Runtime Probe {uuid.uuid4().hex[:6]}"


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def films(api_session: AsyncSession) -> dict[str, uuid.UUID]:
    """Four owned films: 90, 120 and 150 minutes, and one nothing knows the length of."""
    ids: dict[str, uuid.UUID] = {}
    for name, runtime in (("short", 90), ("middle", 120), ("long", 150), ("unknown", None)):
        movie = Movie(
            id=uuid.uuid4(),
            tmdb_id=None,
            title=f"{MARKER} {name}",
            original_title=f"{MARKER} {name}",
            media_type="film",
            year=1990,
            genre_ids=[18],
            runtime_minutes=runtime,
        )
        api_session.add(movie)
        await api_session.flush()
        api_session.add(CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["blu_ray"]))
        ids[name] = movie.id
    await api_session.flush()
    return ids


@pytest_asyncio.fixture
async def client(api_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"Runtime {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
    )
    api_session.add(person)
    await api_session.flush()

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user() -> Profile:
        return person

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


async def _titles(client: AsyncClient, **params: int) -> set[str]:
    response = await client.get("/api/v1/movies", params={"perPage": 2000, **params})
    assert response.status_code == 200, response.text
    return {
        item["title"].removeprefix(f"{MARKER} ")
        for item in response.json()["items"]
        if item["title"].startswith(MARKER)
    }


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"runtimeMin": 100, "runtimeMax": 130}, {"middle"}),
        ({"runtimeMin": 120}, {"middle", "long"}),
        ({"runtimeMax": 120}, {"short", "middle"}),
        ({}, {"short", "middle", "long", "unknown"}),
    ],
)
async def test_the_archive_filters_by_runtime(
    client: AsyncClient, films: dict[str, uuid.UUID], params: dict[str, int], expected: set[str]
) -> None:
    del films
    assert await _titles(client, **params) == expected


async def test_a_backwards_runtime_range_is_refused(client: AsyncClient) -> None:
    response = await client.get("/api/v1/movies", params={"runtimeMin": 150, "runtimeMax": 90})
    assert response.status_code == 422


async def test_a_saved_collection_means_what_the_filter_bar_means(
    client: AsyncClient, films: dict[str, uuid.UUID]
) -> None:
    created = await client.post(
        "/api/v1/smart-collections",
        json={"name": "Under 100 minutes", "filters": {"runtimeMax": 100}},
    )
    assert created.status_code == 201, created.text
    assert created.json()["filters"]["runtimeMax"] == 100

    results = await client.get(
        f"/api/v1/smart-collections/{created.json()['id']}/results", params={"perPage": 2000}
    )
    assert results.status_code == 200, results.text
    ids = {item["id"] for item in results.json()["items"]}
    assert str(films["short"]) in ids
    assert not ids & {str(films["middle"]), str(films["long"]), str(films["unknown"])}
