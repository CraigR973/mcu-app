"""Postgres-backed contract tests for the watch log — roadmap §3.7, §6.5.

The table these exercise had no owning phase in the roadmap: §3.7 designs it, §6.5 lists
its endpoints, and Batch 37 waits on it, but nothing created it until Batch 6
(`DECISIONS.md` #35).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog

pytestmark = pytest.mark.asyncio


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


async def _profile(session: AsyncSession, name: str) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"{name} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
    )
    session.add(profile)
    await session.flush()
    return profile


@pytest_asyncio.fixture
async def viewer(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, "Watcher")


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


async def _owned_movie(session: AsyncSession, title: str) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        media_type="film",
    )
    session.add(movie)
    await session.flush()
    session.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=["blu_ray"],
            location="Front 2nd shelf",
            section="Front",
            shelf="2nd",
            condition="good",
        )
    )
    await session.flush()
    return movie


async def test_logging_a_watch_returns_it_and_defaults_to_today(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _owned_movie(api_session, "A Film Watched Tonight")

    before = datetime.now(UTC).date()
    response = await client.post("/api/v1/watch-log", json={"movieId": str(movie.id)})

    assert response.status_code == 201
    body = response.json()
    assert body["movieId"] == str(movie.id)
    assert body["movieTitle"] == "A Film Watched Tonight"
    # The UTC date, not ``date.today()``. The endpoint computes its default in UTC, so
    # comparing against the *server's local* date asserted that the machine running the
    # test happened to be on UTC — which this one is not, and which is why this line
    # failed for the hour after midnight BST and passed in CI all day.
    #
    # Bracketing the call removes the last of the flake: if the clock crosses UTC
    # midnight mid-request, both answers are correct and both are accepted.
    assert body["watchedAt"] in {before.isoformat(), datetime.now(UTC).date().isoformat()}
    assert body["isRewatch"] is False
    assert body["personalRating"] is None
    # snake_case must not leak onto the wire (`DECISIONS.md` #6).
    assert "movie_id" not in body


async def test_a_rating_and_review_round_trip(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _owned_movie(api_session, "A Film Worth Four And A Half")

    response = await client.post(
        "/api/v1/watch-log",
        json={
            "movieId": str(movie.id),
            "watchedAt": (date.today() - timedelta(days=2)).isoformat(),
            "isRewatch": True,
            "personalRating": 4.5,
            "review": "Better than remembered.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["personalRating"] == 4.5
    assert body["isRewatch"] is True
    assert body["review"] == "Better than remembered."


async def test_a_rating_between_half_stars_is_refused(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """Refused at the wire so it is a 422, not a database CHECK violation as a 500."""
    movie = await _owned_movie(api_session, "A Film Rated Oddly")

    response = await client.post(
        "/api/v1/watch-log",
        json={"movieId": str(movie.id), "personalRating": 3.7},
    )

    assert response.status_code == 422


async def test_a_rating_outside_the_scale_is_refused(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _owned_movie(api_session, "A Film Rated Off The Scale")

    for rating in (0.0, 5.5, -1):
        response = await client.post(
            "/api/v1/watch-log",
            json={"movieId": str(movie.id), "personalRating": rating},
        )
        assert response.status_code == 422, rating


async def test_a_watch_cannot_be_logged_in_the_future(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _owned_movie(api_session, "A Film Not Yet Watched")

    response = await client.post(
        "/api/v1/watch-log",
        json={
            "movieId": str(movie.id),
            "watchedAt": (date.today() + timedelta(days=30)).isoformat(),
        },
    )

    assert response.status_code == 422


async def test_logging_against_an_unknown_film_is_a_404(client: AsyncClient) -> None:
    response = await client.post("/api/v1/watch-log", json={"movieId": str(uuid.uuid4())})
    assert response.status_code == 404


async def test_the_same_film_can_be_watched_more_than_once(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """No unique key on (movie, user): rewatching is the point of a watch *log*."""
    movie = await _owned_movie(api_session, "A Film Watched Twice")

    first = await client.post(
        "/api/v1/watch-log",
        json={
            "movieId": str(movie.id),
            "watchedAt": (date.today() - timedelta(days=400)).isoformat(),
        },
    )
    second = await client.post(
        "/api/v1/watch-log",
        json={"movieId": str(movie.id), "isRewatch": True},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    listing = await client.get("/api/v1/watch-log", params={"movieId": str(movie.id)})
    assert listing.status_code == 200
    assert listing.json()["total"] == 2
    # Newest first.
    assert listing.json()["items"][0]["isRewatch"] is True


async def test_history_is_scoped_to_the_caller(
    client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
) -> None:
    """Watched-status is the one genuinely per-person thing in a shared catalogue."""
    mine = await _owned_movie(api_session, "What I Watched")
    theirs = await _owned_movie(api_session, "What They Watched")
    other = await _profile(api_session, "The Other Person")

    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=mine.id,
            user_id=viewer.id,
            watched_at=date.today(),
        )
    )
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=theirs.id,
            user_id=other.id,
            watched_at=date.today(),
        )
    )
    await api_session.flush()

    response = await client.get("/api/v1/watch-log", params={"perPage": 200})

    assert response.status_code == 200
    titles = [item["movieTitle"] for item in response.json()["items"]]
    assert "What I Watched" in titles
    assert "What They Watched" not in titles


async def test_deleting_is_soft_and_removes_it_from_the_history(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _owned_movie(api_session, "A Film Logged By Mistake")
    created = await client.post("/api/v1/watch-log", json={"movieId": str(movie.id)})
    entry_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/watch-log/{entry_id}")

    assert deleted.status_code == 204
    listing = await client.get("/api/v1/watch-log", params={"movieId": str(movie.id)})
    assert listing.json()["total"] == 0

    # Soft: the row is still there for §13.5's Trash to find.
    row = (
        await api_session.execute(select(WatchLog).where(WatchLog.id == uuid.UUID(entry_id)))
    ).scalar_one()
    assert row.deleted_at is not None


async def test_deleting_someone_elses_entry_is_a_404(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """A 404 rather than a 403 — the response should not confirm the id exists."""
    movie = await _owned_movie(api_session, "A Film Someone Else Watched")
    other = await _profile(api_session, "Not The Caller")
    entry = WatchLog(
        id=uuid.uuid4(),
        movie_id=movie.id,
        user_id=other.id,
        watched_at=date.today(),
    )
    api_session.add(entry)
    await api_session.flush()

    response = await client.delete(f"/api/v1/watch-log/{entry.id}")

    assert response.status_code == 404
    await api_session.refresh(entry)
    assert entry.deleted_at is None


async def test_todays_date_is_accepted_from_a_timezone_ahead_of_utc(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The defect the local-timezone guard hid.

    At 00:30 in London the calendar on the wall says the 9th and UTC still says the 8th.
    A guard comparing against UTC *today* would tell someone logging tonight's film that
    tonight is in the future. The ceiling is therefore the latest date that is today
    anywhere on Earth — UTC+14 — which is UTC today plus one.
    """
    movie = await _owned_movie(api_session, "A Film Watched Just After Midnight")

    response = await client.post(
        "/api/v1/watch-log",
        json={
            "movieId": str(movie.id),
            "watchedAt": (datetime.now(UTC).date() + timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 201, response.text


async def test_the_day_after_that_is_still_refused(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The ceiling is one day of slack, not an open door — no timezone is UTC+38."""
    movie = await _owned_movie(api_session, "A Film Not Watched The Day After Tomorrow")

    response = await client.post(
        "/api/v1/watch-log",
        json={
            "movieId": str(movie.id),
            "watchedAt": (datetime.now(UTC).date() + timedelta(days=2)).isoformat(),
        },
    )

    assert response.status_code == 422
