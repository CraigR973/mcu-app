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
from src.services.calendar import hash_feed_token, new_feed_token

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


async def _feed(session: AsyncSession, path: str):  # type: ignore[no-untyped-def]
    """Fetch a feed path the way a calendar app does: no Authorization header at all."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anonymous:
        app.dependency_overrides[get_db] = _db_override(session)
        try:
            return await anonymous.get(path)
        finally:
            app.dependency_overrides.pop(get_db, None)


async def _one_of_each(session: AsyncSession) -> None:
    """A 4K, a Blu-ray, a sale and a cinema date next week, as Releases' two calendars hold."""
    await _entry(session, "A Disc In 4K", kind="4k_uhd_release", tmdb_id=7001)
    await _entry(session, "A Disc On Blu-ray", kind="blu_ray_release", tmdb_id=7002)
    await _entry(session, "A Winter Sale", kind="sale_event")
    await _entry(session, "A Film At The Pictures", kind="theatrical", tmdb_id=7003)


async def test_one_press_gives_a_feed_per_calendar_with_the_same_token(
    client: AsyncClient,
) -> None:
    """AC7 (#344): the token is still one per person, so the three links come together."""
    body = (await client.post("/api/v1/calendar/subscribe")).json()
    token = body["path"].split("token=", 1)[1]
    assert body["path"] == f"/api/v1/calendar.ics?token={token}"
    assert body["discPath"] == f"/api/v1/calendar.ics?token={token}&calendar=disc"
    assert body["cinemaPath"] == f"/api/v1/calendar.ics?token={token}&calendar=cinema"


async def test_a_calendar_feed_holds_that_calendar_alone(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Disc releases are 4K, Blu-ray and sale dates; cinema releases are UK cinema dates.
    Each feed is named for its calendar, so a phone holding both can tell them apart."""
    await _one_of_each(api_session)
    body = (await client.post("/api/v1/calendar/subscribe")).json()

    disc = await _feed(api_session, body["discPath"])
    assert disc.status_code == 200, disc.text
    assert "X-WR-CALNAME:MCU — Disc releases" in disc.text
    assert disc.headers["content-disposition"] == 'inline; filename="mcu-disc-releases.ics"'
    for summary in ("4K UHD: A Disc In 4K", "Blu-ray: A Disc On Blu-ray", "Sale: A Winter Sale"):
        assert summary in disc.text
    assert "A Film At The Pictures" not in disc.text

    cinema = await _feed(api_session, body["cinemaPath"])
    assert cinema.status_code == 200, cinema.text
    assert "X-WR-CALNAME:MCU — Cinema releases" in cinema.text
    assert cinema.headers["content-disposition"] == 'inline; filename="mcu-cinema-releases.ics"'
    assert "In cinemas: A Film At The Pictures" in cinema.text
    for title in ("A Disc In 4K", "A Disc On Blu-ray", "A Winter Sale"):
        assert title not in cinema.text


async def test_the_all_types_feed_installed_calendars_follow_is_unchanged(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """A link pasted into a calendar before AC7 has no ``calendar``: it still gets every
    type under the old name and file name, and ``calendar=all`` is the same feed."""
    await _one_of_each(api_session)
    path = (await client.post("/api/v1/calendar/subscribe")).json()["path"]

    served = await _feed(api_session, path)
    assert served.status_code == 200, served.text
    assert "X-WR-CALNAME:MCU — Release calendar" in served.text
    assert served.headers["content-disposition"] == 'inline; filename="mcu-release-calendar.ics"'
    for title in ("A Disc In 4K", "A Disc On Blu-ray", "A Winter Sale", "A Film At The Pictures"):
        assert title in served.text

    def events(text: str) -> list[str]:
        return sorted(line for line in text.split("\r\n") if line.startswith(("UID:", "SUMMARY:")))

    explicit = await _feed(api_session, f"{path}&calendar=all")
    assert events(explicit.text) == events(served.text)


async def test_asking_again_stops_every_calendar_feed(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Rotating is still the whole recovery story: one press revokes all three links, and
    each then answers exactly as a token that never existed."""
    await _one_of_each(api_session)
    first = (await client.post("/api/v1/calendar/subscribe")).json()
    await client.post("/api/v1/calendar/subscribe")
    unknown = await _feed(
        api_session, f"/api/v1/calendar.ics?token={new_feed_token()}&calendar=disc"
    )
    for key in ("path", "discPath", "cinemaPath"):
        revoked = await _feed(api_session, first[key])
        assert revoked.status_code == unknown.status_code == 404
        assert revoked.json() == unknown.json()


async def test_a_calendar_the_feed_does_not_have_is_refused(api_session: AsyncSession) -> None:
    response = await _feed(
        api_session, f"/api/v1/calendar.ics?token={new_feed_token()}&calendar=dvd"
    )
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


async def test_the_month_narrows_to_the_types_asked_for(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """AC7 (#344): each calendar reads its own month, and the answer says what it holds."""
    when = date(2087, 5, 6)
    await _entry(api_session, "Four K", when=when, kind="4k_uhd_release", tmdb_id=8001)
    await _entry(api_session, "Blu", when=when, kind="blu_ray_release", tmdb_id=8002)
    await _entry(api_session, "Sale", when=date(2087, 5, 9), kind="sale_event")
    await _entry(api_session, "Pictures", when=when, kind="theatrical", tmdb_id=8003)

    cinema = (await client.get("/api/v1/calendar/month?month=2087-05&types=theatrical")).json()
    assert cinema["types"] == ["theatrical"]
    assert cinema["total"] == 1
    assert [e["title"] for e in cinema["days"]["2087-05-06"]] == ["Pictures"]
    assert "2087-05-09" not in cinema["days"]

    # Asked in any order, held in the vocabulary's.
    disc = (
        await client.get(
            "/api/v1/calendar/month?month=2087-05"
            "&types=sale_event&types=blu_ray_release&types=4k_uhd_release&types=sale_event"
        )
    ).json()
    assert disc["types"] == ["4k_uhd_release", "blu_ray_release", "sale_event"]
    assert disc["total"] == 3
    assert sorted(e["title"] for e in disc["days"]["2087-05-06"]) == ["Blu", "Four K"]
    assert [e["title"] for e in disc["days"]["2087-05-09"]] == ["Sale"]


async def test_without_a_type_the_month_holds_every_type_as_before(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    await _entry(api_session, "Four K", when=date(2087, 6, 1), kind="4k_uhd_release")
    await _entry(api_session, "Pictures", when=date(2087, 6, 2), kind="theatrical")
    body = (await client.get("/api/v1/calendar/month?month=2087-06")).json()
    assert body["total"] == 2
    assert body["types"] == [
        "4k_uhd_release",
        "blu_ray_release",
        "streaming_release",
        "theatrical",
        "award_ceremony",
        "sale_event",
    ]


async def test_a_type_the_calendar_does_not_have_is_refused(client: AsyncClient) -> None:
    response = await client.get("/api/v1/calendar/month?month=2087-06&types=dvd_release")
    assert response.status_code == 422


async def test_an_entry_carries_its_tmdb_id_so_a_showing_film_can_link(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """AC7: a cinema release showing at one of the nine opens its film page, `tmdb-<id>`."""
    await _entry(api_session, "Pictures", when=date(2087, 7, 3), kind="theatrical", tmdb_id=8004)
    await _entry(api_session, "Sale", when=date(2087, 7, 3), kind="sale_event")
    body = (await client.get("/api/v1/calendar/month?month=2087-07")).json()
    by_title = {e["title"]: e for e in body["days"]["2087-07-03"]}
    assert by_title["Pictures"]["tmdbId"] == 8004
    assert by_title["Sale"]["tmdbId"] is None


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


async def test_a_year_outside_the_supported_range_is_refused_not_a_500(
    client: AsyncClient,
) -> None:
    """``\\d{4}`` matches "0000", and ``date(0, 1, 1)`` raises ValueError.

    Without the bound that is an unhandled 500 from a query string.
    """
    assert (await client.get("/api/v1/calendar/month?month=0000-01")).status_code == 422
    assert (await client.get("/api/v1/calendar/month?month=9999-01")).status_code == 422
