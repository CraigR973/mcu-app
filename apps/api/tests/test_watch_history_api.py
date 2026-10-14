"""Batch S5's sync — snag 10a, `DECISIONS.md` #156, #158, #159, #176.

Postgres-backed, so these skip here and run in CI. **No live fetch**: the feed is served
from the fixture through a stubbed transport, which is what lets the sync be tested
unattended while the first *real* fetch stays an owner action.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.importer import run_import
from src.services.letterboxd.sync import SyncNotConfigured, sync_watch_history

FEED = (Path(__file__).parent / "fixtures" / "letterboxd_diary_rss.xml").read_text(encoding="utf-8")


def _feed_client(body: str = FEED, status_code: int = 200) -> httpx.AsyncClient:
    """An httpx client that answers any request with the fixture feed.

    The sync takes its client as an argument precisely so this is possible without
    monkeypatching a module global — and so the one live request in the batch has exactly
    one place it can come from.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert "letterboxd.com" in str(request.url)
        return httpx.Response(status_code, text=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def person(db: AsyncSession) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Syncer {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
        letterboxd_username="CraigR973",
    )
    db.add(profile)
    await db.flush()
    return profile


@pytest_asyncio.fixture
async def client(db: AsyncSession, person: Profile) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user(request: Request) -> Profile:
        del request
        return person

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http
    finally:
        app.dependency_overrides.clear()


async def _film(db: AsyncSession, title: str, year: int | None, tmdb_id: int | None) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
    )
    db.add(movie)
    await db.flush()
    return movie


async def _watches(db: AsyncSession, person: Profile) -> int:
    return int(
        (
            await db.execute(select(func.count(WatchLog.id)).where(WatchLog.user_id == person.id))
        ).scalar_one()
    )


# ---------------------------------------------------------------------------
# The sync
# ---------------------------------------------------------------------------


async def test_a_sync_writes_the_viewings_of_films_they_own(
    db: AsyncSession, person: Profile
) -> None:
    pressure = await _film(db, "Pressure", 2026, 111111)
    get_out = await _film(db, "Get Out", 2017, 419430)

    result = await sync_watch_history(db, person, client=_feed_client())

    assert result.run.entries == 4  # the list item is not a viewing
    # Pressure and Get Out on the owned films; The Collector on a film row of its own
    # (Batch X5, #269); Fast & Furious carries no TMDB id and matches no title.
    assert result.run.written == 3
    assert result.run.not_in_collection == 1
    assert result.run.error is None
    assert result.run.finished_at_utc is not None
    owned = select(WatchLog.movie_id).where(WatchLog.user_id == person.id)
    on_owned = {row for row in await db.scalars(owned)}
    assert {pressure.id, get_out.id} <= on_owned


async def test_a_second_sync_writes_nothing(db: AsyncSession, person: Profile) -> None:
    """The feed re-serves the same 50 entries every time, so this is the ordinary case
    rather than an edge one: **on a healthy weekly sync, almost everything is already
    imported.**"""
    await _film(db, "Pressure", 2026, 111111)

    first = await sync_watch_history(db, person, client=_feed_client())
    second = await sync_watch_history(db, person, client=_feed_client())

    # Pressure on the owned film; Get Out and The Collector on films of their own (X5).
    assert first.run.written == 3
    assert second.run.written == 0
    assert second.run.already_imported == 3
    assert await _watches(db, person) == 3


async def test_a_viewing_already_imported_from_the_file_is_not_written_again(
    db: AsyncSession, person: Profile
) -> None:
    """**S5's headline criterion, and S8 is what makes it free** (`DECISIONS.md` #176).

    The feed's `<guid>` is `letterboxd-watch-900000001`; the diary CSV's `ViewingId` for
    the same viewing is `900000001`. `watch_log.letterboxd_viewing_id` stores the bare
    number, so the file and the feed cannot double-count — and there is no second matcher
    or writer in which they could disagree.
    """
    await _film(db, "Pressure", 2026, 111111)

    # Exactly what S8's file import would have written for this viewing.
    await run_import(
        db,
        person,
        [
            DiaryEntry(
                viewing_id="900000001",
                watched_at=date(2026, 9, 9),
                title="Pressure",
                year=2026,
                rating=None,
                is_rewatch=False,
            )
        ],
        dry_run=False,
    )
    assert await _watches(db, person) == 1

    result = await sync_watch_history(db, person, client=_feed_client())

    # The file's Pressure is not written again; Get Out and The Collector are new (X5).
    assert result.run.written == 2
    assert result.run.already_imported == 1
    pressure_rows = select(func.count(WatchLog.id)).where(
        WatchLog.user_id == person.id, WatchLog.letterboxd_viewing_id == "900000001"
    )
    assert await db.scalar(pressure_rows) == 1


async def test_a_null_rating_is_written_as_null(db: AsyncSession, person: Profile) -> None:
    """**Mark rates nothing — 0 of 50 entries** (`DECISIONS.md` #159). The fixture's
    *Collector* entry carries no `memberRating` at all, which is an ordinary entry."""
    await _film(db, "The Collector", 1965, 29259)
    await sync_watch_history(db, person, client=_feed_client())

    row = (
        await db.scalars(
            select(WatchLog).where(
                WatchLog.user_id == person.id, WatchLog.letterboxd_viewing_id == "900000003"
            )
        )
    ).one()
    assert row.personal_rating is None
    assert row.tmdb_id == 29259  # Batch X5: the feed's own id, kept on the watch


async def test_the_sync_does_not_identify_films(db: AsyncSession, person: Profile) -> None:
    """Every feed entry carries a TMDB id, and the sync deliberately does not use it to
    rewrite `movies`.

    Identification is the operation S8 put in the owner's hands — it overwrites ~397 rows.
    A button that did it quietly, repeatedly and on a schedule would take that decision
    back without asking.
    """
    unidentified = await _film(db, "Collector, The", None, None)
    await sync_watch_history(db, person, client=_feed_client())

    await db.refresh(unidentified)
    assert unidentified.tmdb_id is None
    # Since Batch X5 the feed never falls back to a title (CT46-02): the viewing goes on a
    # film row carrying its own TMDB id, not on the unidentified one. Identifying that row
    # later merges the two.
    collector = select(WatchLog).where(
        WatchLog.user_id == person.id, WatchLog.letterboxd_viewing_id == "900000003"
    )
    row = (await db.scalars(collector)).one()
    assert row.movie_id != unidentified.id
    film = await db.get(Movie, row.movie_id)
    assert film is not None and film.tmdb_id == 29259


async def test_a_failed_fetch_records_the_failure_rather_than_vanishing(
    db: AsyncSession, person: Profile
) -> None:
    """**A sync that failed and left no trace is indistinguishable from one that never
    ran** — which is the expensive confusion, given the 50-entry cap."""
    result = await sync_watch_history(db, person, client=_feed_client(body="nope", status_code=503))

    assert result.run.error is not None
    assert result.run.finished_at_utc is not None
    assert result.run.written == 0
    assert await _watches(db, person) == 0


async def test_a_full_feed_is_flagged_as_a_cadence_warning(
    db: AsyncSession, person: Profile
) -> None:
    """50 entries back means entries may already have fallen off the end. Not a failure —
    a statement that the interval is too long (`DECISIONS.md` #159)."""
    items = "".join(
        f"<item><guid>letterboxd-watch-{9000000 + i}</guid>"
        f"<title>Film {i}, 2020</title>"
        f"<letterboxd:watchedDate>2026-09-0{i % 9 + 1}</letterboxd:watchedDate>"
        f"</item>"
        for i in range(50)
    )
    feed = (
        '<?xml version="1.0"?><rss xmlns:letterboxd="https://letterboxd.com">'
        f"<channel>{items}</channel></rss>"
    )
    result = await sync_watch_history(db, person, client=_feed_client(body=feed))
    assert result.feed_was_full is True


async def test_someone_with_no_username_is_told_rather_than_fetched_for(
    db: AsyncSession, person: Profile
) -> None:
    person.letterboxd_username = None
    await db.flush()
    with pytest.raises(SyncNotConfigured):
        await sync_watch_history(db, person, client=_feed_client())


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------


async def test_status_reports_when_the_sync_last_ran(
    client: AsyncClient, db: AsyncSession, person: Profile
) -> None:
    """The criterion: **the UI states when the sync last ran.** The 50-entry cap is what
    makes that a correctness property rather than a nicety."""
    before = (await client.get("/api/v1/watch-history/status")).json()
    assert before["lastSync"] is None
    assert before["letterboxdUsername"] == "CraigR973"
    assert before["watchCount"] == 0

    await _film(db, "Pressure", 2026, 111111)
    await sync_watch_history(db, person, client=_feed_client())

    after = (await client.get("/api/v1/watch-history/status")).json()
    assert after["lastSync"]["startedAt"]
    # Pressure, and Get Out and The Collector on films of their own (X5).
    assert after["lastSync"]["written"] == 3
    assert after["watchCount"] == 3


async def test_syncing_without_a_username_is_a_409_not_a_500(
    client: AsyncClient, db: AsyncSession, person: Profile
) -> None:
    person.letterboxd_username = None
    await db.flush()
    response = await client.post("/api/v1/watch-history/sync")
    assert response.status_code == 409
    assert "username" in response.json()["detail"].lower()


async def test_a_viewer_can_set_their_own_username_and_sync(
    client: AsyncClient, person: Profile
) -> None:
    """Caller-scoped, not admin-gated. Each person has their own diary, and there is no
    version of this where one of them administers the other's viewing history."""
    assert person.role == UserRole.viewer
    response = await client.put(
        "/api/v1/watch-history/username", json={"letterboxdUsername": "markr973"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["letterboxdUsername"] == "markr973"


async def test_a_username_that_could_not_name_a_diary_is_refused(client: AsyncClient) -> None:
    """Refused at the wire, at the column, and again in the URL builder. The value is
    interpolated into a URL, and "validated on the way in" is not a property a URL builder
    should assume."""
    response = await client.put(
        "/api/v1/watch-history/username", json={"letterboxdUsername": "craig/../mark"}
    )
    assert response.status_code == 422
