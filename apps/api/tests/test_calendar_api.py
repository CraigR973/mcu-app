"""The release calendar and its public feed — §7.3, §7.4.

**Most of this file is about the unauthenticated endpoint**, because `/calendar.ics` is the
first thing in this application that answers without a bearer token. The URL is the
credential, so the tests that matter are the ones about what happens to a wrong one, a
revoked one, and a leaked one.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, timedelta

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utc_today
from src.database import get_db
from src.main import app
from src.models.profile import Profile, UserRole
from src.models.release_calendar import CalendarFeedToken, ReleaseCalendarEntry
from src.services.calendar import hash_feed_token, ingest_upcoming, new_feed_token
from src.tmdb.models import SearchResult, SearchResults

pytestmark = pytest.mark.asyncio

ACTOR_HEADER = "x-test-actor"


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _profile(session: AsyncSession, role: UserRole) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Batch Seventeen {role.value.title()} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=role,
    )
    session.add(profile)
    await session.flush()
    return profile


@pytest_asyncio.fixture
async def admin(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, UserRole.admin)


@pytest_asyncio.fixture
async def viewer(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, UserRole.viewer)


@pytest_asyncio.fixture
async def overrides(
    api_session: AsyncSession, admin: Profile, viewer: Profile
) -> AsyncIterator[None]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user(request: Request) -> Profile:
        return admin if request.headers.get(ACTOR_HEADER) == "admin" else viewer

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
    async with _client_as("admin") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def viewer_client(overrides: None) -> AsyncIterator[AsyncClient]:
    del overrides
    async with _client_as("viewer") as http_client:
        yield http_client


async def _entry(
    session: AsyncSession,
    title: str,
    *,
    when: date | None = None,
    kind: str = "theatrical",
    tmdb_id: int | None = None,
) -> ReleaseCalendarEntry:
    row = ReleaseCalendarEntry(
        id=uuid.uuid4(),
        title=title,
        release_type=kind,
        release_date=when or (utc_today() + timedelta(days=7)),
        region="GB",
        tmdb_id=tmdb_id,
        overview=f"About {title}.",
    )
    session.add(row)
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# §7.4 — the public feed. The security half.
# ---------------------------------------------------------------------------


async def test_the_feed_needs_no_bearer_token_but_needs_the_right_one(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """The URL is the credential — that is the whole design, and the whole risk."""
    await _entry(api_session, "A Film In The Feed")
    subscribed = await client.post("/api/v1/calendar/subscribe")
    assert subscribed.status_code == 200, subscribed.text
    path = subscribed.json()["path"]
    assert "/api/v1/calendar.ics?token=" in path
    del admin

    # No Authorization header anywhere in this request.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anonymous:
        app.dependency_overrides[get_db] = _db_override(api_session)
        try:
            served = await anonymous.get(path)
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert served.status_code == 200, served.text
    assert served.headers["content-type"].startswith("text/calendar")
    assert "A Film In The Feed" in served.text


def _db_override(session: AsyncSession):  # type: ignore[no-untyped-def]
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield session

    return override_db


async def test_the_token_is_never_stored_in_plaintext(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """A database leak must not yield working feed URLs.

    The same reasoning as `refresh_tokens.token_hash`, and the reason this is not simply a
    UUID column: the URL is as sensitive as a refresh token, so it is stored like one.
    """
    subscribed = await client.post("/api/v1/calendar/subscribe")
    token = subscribed.json()["path"].split("token=", 1)[1]

    row = (
        await api_session.execute(
            select(CalendarFeedToken).where(CalendarFeedToken.user_id == admin.id)
        )
    ).scalar_one()
    assert row.token_hash != token
    assert row.token_hash == hash_feed_token(token)
    assert len(row.token_hash) == 64


async def test_a_wrong_token_and_a_revoked_token_answer_identically(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Both 404, same body.

    A 401, or a different message for "this used to work", would confirm to someone
    guessing that a token had once existed. There is no user to tell apart from an
    attacker here — the whole point is that nobody signs in.
    """
    await _entry(api_session, "A Film Nobody Should See")
    first = (await client.post("/api/v1/calendar/subscribe")).json()["path"]
    # Subscribing again rotates, revoking the first link.
    await client.post("/api/v1/calendar/subscribe")

    never_existed = f"/api/v1/calendar.ics?token={new_feed_token()}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anonymous:
        app.dependency_overrides[get_db] = _db_override(api_session)
        try:
            revoked_response = await anonymous.get(first)
            unknown_response = await anonymous.get(never_existed)
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert revoked_response.status_code == unknown_response.status_code == 404
    assert revoked_response.json() == unknown_response.json()


async def test_subscribing_again_rotates_the_link_and_says_so(
    client: AsyncClient,
) -> None:
    """Rotating is the only way to take back a URL that has already been pasted somewhere,
    and the response says the old one stopped working so nobody keeps two."""
    first = await client.post("/api/v1/calendar/subscribe")
    second = await client.post("/api/v1/calendar/subscribe")

    assert first.json()["replacedPrevious"] is False
    assert second.json()["replacedPrevious"] is True
    assert first.json()["path"] != second.json()["path"]


async def test_only_one_live_token_exists_per_person(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """A partial unique index, not application discipline: "exactly one working link" is
    the property the whole revoke story rests on."""
    for _ in range(3):
        await client.post("/api/v1/calendar/subscribe")

    live = (
        (
            await api_session.execute(
                select(CalendarFeedToken).where(
                    CalendarFeedToken.user_id == admin.id,
                    CalendarFeedToken.revoked_at_utc.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(live) == 1


async def test_the_feed_carries_no_personal_data(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """What keeps a leaked URL a nuisance rather than a disclosure.

    The feed is release dates for films — public facts, most of them from TMDB. Nothing in
    it says whose calendar it is, what they own, or what they have watched. Worth asserting
    rather than assuming, because the natural way to extend this feed is to start adding
    exactly those things.
    """
    await _entry(api_session, "A Public Fact")
    path = (await client.post("/api/v1/calendar/subscribe")).json()["path"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anonymous:
        app.dependency_overrides[get_db] = _db_override(api_session)
        try:
            served = await anonymous.get(path)
        finally:
            app.dependency_overrides.pop(get_db, None)

    body = served.text
    assert admin.display_name not in body
    assert str(admin.id) not in body
    for word in ("watched", "owned", "collection_items", "PIN"):
        assert word not in body


async def test_the_feed_refuses_to_be_indexed_or_cached(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """A URL that is its own credential must not end up in a search index or a shared
    cache."""
    await _entry(api_session, "A Film")
    path = (await client.post("/api/v1/calendar/subscribe")).json()["path"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anonymous:
        app.dependency_overrides[get_db] = _db_override(api_session)
        try:
            served = await anonymous.get(path)
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert served.headers["x-robots-tag"] == "noindex, nofollow"
    assert "no-store" in served.headers["cache-control"]


async def test_using_the_feed_records_when(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """So a link that has never been fetched is visible — either not set up, or leaked and
    idle, and both are worth seeing."""
    await _entry(api_session, "A Film")
    path = (await client.post("/api/v1/calendar/subscribe")).json()["path"]

    row = (
        await api_session.execute(
            select(CalendarFeedToken).where(
                CalendarFeedToken.user_id == admin.id,
                CalendarFeedToken.revoked_at_utc.is_(None),
            )
        )
    ).scalar_one()
    assert row.last_used_at_utc is None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anonymous:
        app.dependency_overrides[get_db] = _db_override(api_session)
        try:
            await anonymous.get(path)
        finally:
            app.dependency_overrides.pop(get_db, None)

    await api_session.refresh(row)
    assert row.last_used_at_utc is not None


async def test_a_short_token_is_rejected_before_any_lookup(
    api_session: AsyncSession,
) -> None:
    """A length floor on the query parameter, so a trivially short guess never reaches the
    database at all."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anonymous:
        app.dependency_overrides[get_db] = _db_override(api_session)
        try:
            response = await anonymous.get("/api/v1/calendar.ics?token=abc")
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# §7.4 — the monthly view
# ---------------------------------------------------------------------------


async def test_the_month_view_buckets_entries_by_day(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    await _entry(api_session, "First", when=date(2087, 3, 4))
    await _entry(api_session, "Second", when=date(2087, 3, 4), kind="sale_event")
    await _entry(api_session, "Elsewhere", when=date(2087, 4, 1))

    response = await client.get("/api/v1/calendar/month?month=2087-03")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert sorted(e["title"] for e in body["days"]["2087-03-04"]) == ["First", "Second"]
    assert "2087-04-01" not in body["days"]


async def test_an_empty_month_is_an_explicit_empty_map(client: AsyncClient) -> None:
    """Rather than a gap the client has to infer."""
    response = await client.get("/api/v1/calendar/month?month=2088-01")
    assert response.status_code == 200
    assert response.json()["days"] == {}
    assert response.json()["total"] == 0


async def test_a_month_that_is_not_a_month_is_refused(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/calendar/month?month=2087-13")).status_code == 422
    assert (await client.get("/api/v1/calendar/month?month=nonsense")).status_code == 422


async def test_a_viewer_can_read_the_calendar_but_not_ingest(
    viewer_client: AsyncClient, api_session: AsyncSession
) -> None:
    """Ingestion spends a shared TMDB budget and writes a table both people read."""
    await _entry(api_session, "A Film Mark Can See")
    assert (await viewer_client.get("/api/v1/calendar")).status_code == 200
    assert (await viewer_client.post("/api/v1/calendar/ingest")).status_code == 403


# ---------------------------------------------------------------------------
# §7.3 — ingestion
# ---------------------------------------------------------------------------


class _FakeUpcoming:
    """TMDB's upcoming list, with the shuffling that broke the first live run."""

    def __init__(self, pages: dict[int, list[SearchResult]]) -> None:
        self._pages = pages

    async def get_upcoming(
        self, region: str = "GB", language: str = "en-US", page: int = 1
    ) -> SearchResults:
        del region, language
        results = self._pages.get(page, [])
        return SearchResults(
            page=page, total_pages=len(self._pages), total_results=len(results), results=results
        )


def _upcoming(tmdb_id: int, title: str, when: date) -> SearchResult:
    return SearchResult(
        id=tmdb_id,
        title=title,
        original_title=title,
        overview=f"About {title}.",
        release_date=when.isoformat(),
        poster_path=f"/{tmdb_id}.jpg",
        genre_ids=[53],
    )


async def test_the_same_film_on_two_pages_is_ingested_once(
    api_session: AsyncSession,
) -> None:
    """The defect the first live ingestion hit.

    TMDB's paginated ``upcoming`` list is re-sorted between requests, so a film can appear
    on page 2 and again on page 3 of the same run. Appending blindly then violates
    ``uq_release_calendar_tmdb_type_region`` mid-insert and loses the whole batch.

    **A dry run cannot catch this** — it never writes, so it never reaches the constraint.
    `STATUS.md` gotcha 16 restated: the first real write against real data is its own test
    stage.
    """
    soon = utc_today() + timedelta(days=10)
    duplicated = _upcoming(9_100_001, "A Film On Two Pages", soon)
    fake = _FakeUpcoming({1: [duplicated], 2: [duplicated, _upcoming(9_100_002, "Another", soon)]})

    result = await ingest_upcoming(api_session, fake, region="GB", genre_ids={53}, pages=2)

    # Counted against this test's own rows, not the total: `CURATED_EVENTS` are ingested
    # too, and a total would break whenever that list changed.
    assert result.errors == []
    rows = (
        (
            await api_session.execute(
                select(ReleaseCalendarEntry).where(ReleaseCalendarEntry.tmdb_id == 9_100_001)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "the same film on two pages was ingested twice"
    both = (
        (
            await api_session.execute(
                select(ReleaseCalendarEntry).where(
                    ReleaseCalendarEntry.tmdb_id.in_([9_100_001, 9_100_002])
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(both) == 2


async def test_re_running_updates_rather_than_duplicating(
    api_session: AsyncSession,
) -> None:
    """§7.3's job is meant for a schedule, so running it twice must be safe."""
    soon = utc_today() + timedelta(days=10)
    later = soon + timedelta(days=3)
    first = _FakeUpcoming({1: [_upcoming(9_100_011, "A Film", soon)]})
    await ingest_upcoming(api_session, first, region="GB", genre_ids={53}, pages=1)

    # The release date moves — which is the entire point of a release calendar.
    moved = _FakeUpcoming({1: [_upcoming(9_100_011, "A Film", later)]})
    result = await ingest_upcoming(api_session, moved, region="GB", genre_ids={53}, pages=1)

    assert result.updated == 1
    row = (
        await api_session.execute(
            select(ReleaseCalendarEntry).where(ReleaseCalendarEntry.tmdb_id == 9_100_011)
        )
    ).scalar_one()
    # Updated in place, so a subscriber's existing event moves rather than duplicating.
    assert row.release_date == later


async def test_films_outside_the_genres_of_interest_are_skipped(
    api_session: AsyncSession,
) -> None:
    soon = utc_today() + timedelta(days=10)
    wanted = _upcoming(9_100_021, "A Thriller", soon)
    unwanted = _upcoming(9_100_022, "A Documentary", soon)
    unwanted.genre_ids = [99]

    result = await ingest_upcoming(
        api_session, _FakeUpcoming({1: [wanted, unwanted]}), region="GB", genre_ids={53}, pages=1
    )

    assert result.skipped >= 1
    ingested = {
        row.tmdb_id
        for row in (
            await api_session.execute(
                select(ReleaseCalendarEntry).where(
                    ReleaseCalendarEntry.tmdb_id.in_([9_100_021, 9_100_022])
                )
            )
        )
        .scalars()
        .all()
    }
    assert ingested == {9_100_021}


async def test_a_release_already_in_the_past_is_not_ingested(
    api_session: AsyncSession,
) -> None:
    """A calendar of things that already happened is not a calendar."""
    result = await ingest_upcoming(
        api_session,
        _FakeUpcoming(
            {1: [_upcoming(9_100_031, "Last Year's Film", utc_today() - timedelta(days=30))]}
        ),
        region="GB",
        genre_ids={53},
        pages=1,
    )
    assert result.skipped >= 1
    # Asserted against this test's own row, not `created`: `CURATED_EVENTS` are ingested
    # in the same call, so a total would break whenever that list changed.
    assert (
        await api_session.execute(
            select(ReleaseCalendarEntry).where(ReleaseCalendarEntry.tmdb_id == 9_100_031)
        )
    ).scalar_one_or_none() is None


async def test_a_failing_page_does_not_lose_the_pages_before_it(
    api_session: AsyncSession,
) -> None:
    class _BreaksOnPageTwo(_FakeUpcoming):
        async def get_upcoming(
            self, region: str = "GB", language: str = "en-US", page: int = 1
        ) -> SearchResults:
            if page == 2:
                raise RuntimeError("TMDB is down")
            return await super().get_upcoming(region=region, language=language, page=page)

    soon = utc_today() + timedelta(days=10)
    fake = _BreaksOnPageTwo({1: [_upcoming(9_100_041, "A Film From Page One", soon)]})

    result = await ingest_upcoming(api_session, fake, region="GB", genre_ids={53}, pages=3)

    assert any("page 2" in message for message in result.errors)
    assert (
        await api_session.execute(
            select(ReleaseCalendarEntry).where(ReleaseCalendarEntry.tmdb_id == 9_100_041)
        )
    ).scalar_one_or_none() is not None, "page one's row was lost with page two's failure"


async def test_a_year_outside_the_supported_range_is_refused_not_a_500(
    client: AsyncClient,
) -> None:
    """``\\d{4}`` matches "0000", and ``date(0, 1, 1)`` raises ValueError.

    Without the bound that is an unhandled 500 from a query string.
    """
    assert (await client.get("/api/v1/calendar/month?month=0000-01")).status_code == 422
    assert (await client.get("/api/v1/calendar/month?month=9999-01")).status_code == 422
