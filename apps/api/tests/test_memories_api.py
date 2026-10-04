"""Date-controlled contract tests for Batch 37's watch memories."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog


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
async def viewer(api_session: AsyncSession) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Viewer {uuid.uuid4().hex[:8]}",
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

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


async def _movie(session: AsyncSession, title: str) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        media_type="film",
    )
    session.add(movie)
    await session.flush()
    return movie


async def _watch(
    session: AsyncSession,
    movie: Movie,
    user: Profile,
    watched_at: date,
    rating: Decimal | None = None,
    *,
    deleted: bool = False,
) -> WatchLog:
    watch = WatchLog(
        id=uuid.uuid4(),
        movie_id=movie.id,
        user_id=user.id,
        watched_at=watched_at,
        personal_rating=rating,
        deleted_at=datetime(2026, 9, 9) if deleted else None,
    )
    session.add(watch)
    await session.flush()
    return watch


async def test_on_this_day_surfaces_a_watch_from_one_year_ago(
    client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The phase acceptance criterion, independent of the wall clock."""
    from src.routers import memories

    today = date(2026, 9, 9)
    monkeypatch.setattr(memories, "utc_today", lambda: today)
    anniversary = await _movie(api_session, "A September Memory")
    wrong_day = await _movie(api_session, "Not Today")
    other_person = Profile(id=uuid.uuid4(), display_name="Other person", role=UserRole.viewer)
    api_session.add(other_person)
    await api_session.flush()
    anniversary_watch = await _watch(
        api_session, anniversary, viewer, date(2025, 9, 9), Decimal("4.5")
    )
    await _watch(api_session, wrong_day, viewer, date(2025, 9, 8), Decimal("5.0"))
    await _watch(api_session, wrong_day, other_person, date(2024, 9, 9), Decimal("5.0"))

    response = await client.get("/api/v1/memories/on-this-day")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(anniversary_watch.id),
            "movieId": str(anniversary.id),
            "movieTitle": "A September Memory",
            "posterPath": None,
            "watchedAt": "2025-09-09",
            "yearsAgo": 1,
            "personalRating": 4.5,
        }
    ]


async def test_memories_exclude_soft_deleted_watches_and_movies(
    client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.routers import memories

    monkeypatch.setattr(memories, "utc_today", lambda: date(2026, 9, 9))
    deleted_watch = await _movie(api_session, "Removed Watch")
    deleted_movie = await _movie(api_session, "Removed Film")
    deleted_movie.deleted_at = datetime(2026, 9, 9)
    await _watch(api_session, deleted_watch, viewer, date(2025, 9, 9), deleted=True)
    await _watch(api_session, deleted_movie, viewer, date(2025, 9, 9))

    response = await client.get("/api/v1/memories/on-this-day")

    assert response.status_code == 200
    assert response.json() == []


async def test_rewatch_suggestions_are_highly_rated_and_not_recent(
    client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.routers import memories

    monkeypatch.setattr(memories, "utc_today", lambda: date(2026, 9, 9))
    eligible = await _movie(api_session, "Worth Revisiting")
    recent = await _movie(api_session, "Watched Too Recently")
    low_rated = await _movie(api_session, "Not Highly Rated")
    await _watch(api_session, eligible, viewer, date(2026, 2, 28), Decimal("4.5"))
    await _watch(api_session, recent, viewer, date(2025, 1, 1), Decimal("5.0"))
    await _watch(api_session, recent, viewer, date(2026, 8, 1), Decimal("5.0"))
    await _watch(api_session, low_rated, viewer, date(2025, 1, 1), Decimal("3.5"))

    response = await client.get("/api/v1/memories/rewatch-suggestions")

    assert response.status_code == 200
    assert response.json() == [
        {
            "movieId": str(eligible.id),
            "movieTitle": "Worth Revisiting",
            "posterPath": None,
            "lastWatchedAt": "2026-02-28",
            "personalRating": 4.5,
        }
    ]


async def test_rewatch_suggestion_filters_are_validated(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/memories/rewatch-suggestions?months=0")).status_code == 422
    assert (
        await client.get("/api/v1/memories/rewatch-suggestions?minRating=5.1")
    ).status_code == 422
