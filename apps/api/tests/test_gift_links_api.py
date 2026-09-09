"""Batch 27's gift links — §12.1, §12.2, §3.21, §6.26.

**Most of this file is about what the public page does *not* do**, because that is where the
risk is. `GET /api/v1/gift/{slug}` is the application's second unauthenticated endpoint, and
the ledger singles this batch out as needing its own security review: an unguessable slug,
an answer that reveals nothing when it is wrong, and a response that carries a wanted list
and nothing else.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.gift_link import GiftLink, new_slug
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import Retailer, WantedItem

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
        display_name=f"Batch TwentySeven {role.value.title()} {uuid.uuid4().hex[:8]}",
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


@contextlib.asynccontextmanager
async def _anonymous(api_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """A visitor with no session at all.

    ``get_current_user`` is overridden to **raise 401** rather than being removed. Simply
    dropping it would leave the admin override in place, and then an endpoint that
    *required* auth would still answer — so the test would prove nothing about "no auth
    required". Raising is what an absent bearer token actually does.

    It also restores the previous overrides rather than clearing them: the first version
    called ``app.dependency_overrides.clear()``, which wiped the admin client's auth for
    the rest of the test and produced a 401 on the *next* admin request.
    """

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def no_credentials() -> Profile:
        raise HTTPException(status_code=401, detail="Not authenticated")

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = no_credentials
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as visitor:
            yield visitor
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def _wanted(
    session: AsyncSession,
    title: str,
    *,
    price: str | None = None,
    fmt: str | None = None,
    owned: bool = False,
    active: bool = True,
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        media_type="film",
        year=2087,
        poster_path=f"/{uuid.uuid4().hex[:6]}.jpg",
    )
    session.add(movie)
    await session.flush()
    if owned:
        session.add(CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["dvd"]))
    session.add(
        WantedItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            preferred_format=fmt,
            max_price=Decimal(price) if price else None,
            currency="GBP",
            is_active=active,
            added_at=utcnow(),
        )
    )
    await session.flush()
    return movie


# ---------------------------------------------------------------------------
# §12.1 — creating a link
# ---------------------------------------------------------------------------


async def test_creating_a_link_and_visiting_the_slug_renders_the_list(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§12.1's acceptance, word for word."""
    await _wanted(api_session, "A Film Someone Might Buy Me")

    created = await client.post(
        "/api/v1/gift-links", json={"title": "Christmas 2026", "isActive": True}
    )
    assert created.status_code == 201, created.text
    slug = created.json()["slug"]
    assert created.json()["path"] == f"/gift/{slug}"

    async with _anonymous(api_session) as visitor:
        page = await visitor.get(f"/api/v1/gift/{slug}")

    assert page.status_code == 200, page.text
    assert page.json()["title"] == "Christmas 2026"
    assert any(f["title"] == "A Film Someone Might Buy Me" for f in page.json()["films"])


async def test_the_slug_is_long_enough_not_to_be_guessed(client: AsyncClient) -> None:
    """§6.26's worked example is `/gift/a8f3b2c1` — eight hex characters, **32 bits**.

    That is four billion possibilities: enumerable by anyone willing to spend an afternoon,
    and what would be enumerated is a named person's wish list. `token_urlsafe(16)` is 128
    bits.
    """
    created = await client.post("/api/v1/gift-links", json={"title": "Long Enough"})
    slug = created.json()["slug"]
    assert len(slug) >= 20, slug
    assert set(slug) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


async def test_two_links_never_share_a_slug(client: AsyncClient) -> None:
    slugs = {
        (await client.post("/api/v1/gift-links", json={"title": f"List {n}"})).json()["slug"]
        for n in range(5)
    }
    assert len(slugs) == 5


async def test_the_slug_is_not_written_to_the_audit_log(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """It is a credential, and an audit log is read more widely and kept longer than the
    link it would leak."""
    from src.models.admin_action import AdminAction

    created = await client.post("/api/v1/gift-links", json={"title": "Not In The Log"})
    slug = created.json()["slug"]

    entry = (
        await api_session.execute(
            select(AdminAction).where(
                AdminAction.target_id == created.json()["id"],
                AdminAction.action_type == "create",
            )
        )
    ).scalar_one()
    assert slug not in str(entry.changes)


async def test_a_viewer_cannot_create_or_list_links(viewer_client: AsyncClient) -> None:
    assert (await viewer_client.get("/api/v1/gift-links")).status_code == 403
    assert (
        await viewer_client.post("/api/v1/gift-links", json={"title": "Mark's"})
    ).status_code == 403


# ---------------------------------------------------------------------------
# §12.2 — the public page, and what it must not say
# ---------------------------------------------------------------------------


async def test_the_page_never_says_what_the_recipient_already_owns(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The wanted list is the point; the collection is not being shared.

    A film can be wanted *and* owned — a DVD-to-4K upgrade is exactly that, and Batch 18
    surfaces it to the admin. It must not reach the public page: whether someone owns
    something is not what a family member needs in order to buy a present, and the
    response model is deliberately not a superset of the admin one.
    """
    # A title with no incriminating words in it — the first version was called "Owned And
    # Wanted", so the substring check found the *title* rather than a leaked field.
    await _wanted(api_session, "A Disc On Both Lists", owned=True)
    slug = (await client.post("/api/v1/gift-links", json={"title": "L"})).json()["slug"]

    async with _anonymous(api_session) as visitor:
        page = await visitor.get(f"/api/v1/gift/{slug}")

    body = page.text
    assert "ownedAlready" not in body
    assert "owned" not in body.lower()
    film = next(f for f in page.json()["films"] if f["title"] == "A Disc On Both Lists")
    assert set(film) == {
        "title",
        "year",
        "posterPath",
        "preferredFormat",
        "maxPrice",
        "currency",
        "retailerLinks",
    }


async def test_the_page_carries_no_ids_no_slug_and_no_view_count(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The public model is not a superset of the admin one, so adding a field to the admin
    view cannot leak it here."""
    await _wanted(api_session, "A Film")
    slug = (await client.post("/api/v1/gift-links", json={"title": "L"})).json()["slug"]

    async with _anonymous(api_session) as visitor:
        page = await visitor.get(f"/api/v1/gift/{slug}")

    assert set(page.json()) == {"title", "films", "total", "filterConfig"}
    body = page.text
    assert slug not in body
    for leaked in ("viewCount", "createdBy", "movieId", 'id":'):
        assert leaked not in body, leaked


async def test_a_wrong_expired_deactivated_or_deleted_slug_all_answer_identically(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Nobody on this endpoint can be told apart from someone guessing, so none of them
    learns whether a slug was ever real."""
    await _wanted(api_session, "A Film")

    expired = await client.post(
        "/api/v1/gift-links",
        json={
            "title": "Expired",
            "expiresAt": (utcnow() - timedelta(days=1)).isoformat() + "Z",
        },
    )
    deactivated = await client.post("/api/v1/gift-links", json={"title": "Off", "isActive": False})
    revoked = await client.post("/api/v1/gift-links", json={"title": "Gone"})
    await client.request("DELETE", f"/api/v1/gift-links/{revoked.json()['id']}")

    async with _anonymous(api_session) as visitor:
        responses = [
            await visitor.get(f"/api/v1/gift/{new_slug()}"),
            await visitor.get(f"/api/v1/gift/{expired.json()['slug']}"),
            await visitor.get(f"/api/v1/gift/{deactivated.json()['slug']}"),
            await visitor.get(f"/api/v1/gift/{revoked.json()['slug']}"),
        ]

    assert [r.status_code for r in responses] == [404, 404, 404, 404]
    assert len({r.text for r in responses}) == 1, "the four answers differ"


async def test_a_short_slug_never_reaches_the_database(
    api_session: AsyncSession,
) -> None:
    """A length floor on the path parameter, so a trivially short guess is refused before
    any lookup."""
    async with _anonymous(api_session) as visitor:
        response = await visitor.get("/api/v1/gift/abc")
    assert response.status_code == 422


async def test_the_page_refuses_to_be_indexed_or_cached(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    await _wanted(api_session, "A Film")
    slug = (await client.post("/api/v1/gift-links", json={"title": "L"})).json()["slug"]

    async with _anonymous(api_session) as visitor:
        page = await visitor.get(f"/api/v1/gift/{slug}")

    assert page.headers["x-robots-tag"] == "noindex, nofollow"
    assert "no-store" in page.headers["cache-control"]


async def test_only_active_wanted_entries_appear(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """ "No longer looking" is a decision, and a present bought against it is a wasted one."""
    await _wanted(api_session, "Still Looking For This", active=True)
    await _wanted(api_session, "Gave Up On This", active=False)
    slug = (await client.post("/api/v1/gift-links", json={"title": "L"})).json()["slug"]

    async with _anonymous(api_session) as visitor:
        page = await visitor.get(f"/api/v1/gift/{slug}")

    titles = [f["title"] for f in page.json()["films"]]
    assert "Still Looking For This" in titles
    assert "Gave Up On This" not in titles


async def test_a_price_filter_keeps_unpriced_entries(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """ "Under £30" is about what the *buyer* wants to spend, and an entry with no threshold
    recorded has not claimed to cost more than that."""
    await _wanted(api_session, "Cheap Enough", price="12.99")
    await _wanted(api_session, "Too Expensive", price="99.99")
    await _wanted(api_session, "No Price Recorded", price=None)

    created = await client.post(
        "/api/v1/gift-links",
        json={"title": "Under thirty", "filterConfig": {"maxPrice": "30.00"}},
    )
    async with _anonymous(api_session) as visitor:
        page = await visitor.get(f"/api/v1/gift/{created.json()['slug']}")

    titles = [f["title"] for f in page.json()["films"]]
    assert "Cheap Enough" in titles
    assert "No Price Recorded" in titles
    assert "Too Expensive" not in titles
    # §12.2's "basic filters visible to viewer".
    assert page.json()["filterConfig"]["maxPrice"] == "30.00"


async def test_a_format_filter_narrows_the_list(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    await _wanted(api_session, "A 4K Want", fmt="4k_uhd")
    await _wanted(api_session, "A DVD Want", fmt="dvd")
    created = await client.post(
        "/api/v1/gift-links",
        json={"title": "4K only", "filterConfig": {"formats": ["4k_uhd"]}},
    )
    async with _anonymous(api_session) as visitor:
        page = await visitor.get(f"/api/v1/gift/{created.json()['slug']}")

    titles = [f["title"] for f in page.json()["films"]]
    assert "A 4K Want" in titles and "A DVD Want" not in titles


async def test_an_unknown_filter_key_is_refused_at_creation(client: AsyncClient) -> None:
    """The blob is read by an unauthenticated endpoint. A key that survived into JSONB and
    was interpreted later would be a stranger-facing query built from stored input."""
    response = await client.post(
        "/api/v1/gift-links",
        json={"title": "Sneaky", "filterConfig": {"maxPrice": "10", "orderBy": "x"}},
    )
    assert response.status_code == 422


async def test_retailer_links_are_offered_for_buying(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§6.26's "direct retailer links" — the reason a family member can act on the page."""
    api_session.add(
        Retailer(
            id=uuid.uuid4(),
            name="A Shop",
            base_url="https://shop.example",
            search_url_template="https://shop.example/s?q={query}",
            scraper_config={},
            enabled=True,
            added_at=utcnow(),
        )
    )
    await _wanted(api_session, "Buy Me This")
    await api_session.flush()

    slug = (await client.post("/api/v1/gift-links", json={"title": "L"})).json()["slug"]
    async with _anonymous(api_session) as visitor:
        page = await visitor.get(f"/api/v1/gift/{slug}")

    film = next(f for f in page.json()["films"] if f["title"] == "Buy Me This")
    links = {link["name"]: link["url"] for link in film["retailerLinks"]}
    assert "A Shop" in links
    assert links["A Shop"].startswith("https://shop.example/s?q=")
    assert "Buy%20Me%20This" in links["A Shop"]


async def test_visiting_counts_a_view(client: AsyncClient, api_session: AsyncSession) -> None:
    """§6.26 step 5. The one place an unauthenticated request causes a write, which is why
    the endpoint is rate-limited."""
    await _wanted(api_session, "A Film")
    created = await client.post("/api/v1/gift-links", json={"title": "Counted"})
    assert created.json()["viewCount"] == 0

    async with _anonymous(api_session) as visitor:
        await visitor.get(f"/api/v1/gift/{created.json()['slug']}")
        await visitor.get(f"/api/v1/gift/{created.json()['slug']}")

    link = await api_session.get(GiftLink, uuid.UUID(created.json()["id"]))
    assert link is not None
    await api_session.refresh(link)
    assert link.view_count == 2
    assert link.last_viewed_at is not None


async def test_deactivating_stops_the_link_without_deleting_it(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§3.21's "can be deactivated without deleting" — the same distinction Batch 18 drew
    between `is_active` and `deleted_at`."""
    await _wanted(api_session, "A Film")
    created = await client.post("/api/v1/gift-links", json={"title": "Switchable"})
    slug = created.json()["slug"]

    off = await client.put(
        f"/api/v1/gift-links/{created.json()['id']}",
        json={"title": "Switchable", "isActive": False},
    )
    assert off.json()["isUsable"] is False

    async with _anonymous(api_session) as visitor:
        assert (await visitor.get(f"/api/v1/gift/{slug}")).status_code == 404

    # Back on, and **the same slug still works** — the link already shared with family is
    # not silently rotated.
    on = await client.put(
        f"/api/v1/gift-links/{created.json()['id']}",
        json={"title": "Switchable", "isActive": True},
    )
    assert on.json()["slug"] == slug
    async with _anonymous(api_session) as visitor:
        assert (await visitor.get(f"/api/v1/gift/{slug}")).status_code == 200


# ---------------------------------------------------------------------------
# Fixes from this batch's security review
# ---------------------------------------------------------------------------


async def test_the_retailer_query_runs_once_not_once_per_film(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The N+1 the review found.

    `_retailer_links` used to be called *inside* the per-film loop and re-read the whole
    `retailers` table each time — 50 identical queries for a 50-film list, on the
    unauthenticated endpoint. The rows do not vary by film; only the query string does.
    """
    api_session.add(
        Retailer(
            id=uuid.uuid4(),
            name=f"Counted Shop {uuid.uuid4().hex[:6]}",
            base_url="https://shop.example",
            search_url_template="https://shop.example/s?q={query}",
            scraper_config={},
            enabled=True,
            added_at=utcnow(),
        )
    )
    for n in range(4):
        await _wanted(api_session, f"Film Number {n}")
    await api_session.flush()

    slug = (await client.post("/api/v1/gift-links", json={"title": "L"})).json()["slug"]

    seen: list[str] = []
    original = AsyncSession.execute

    async def counting_execute(self, statement, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(str(statement))
        return await original(self, statement, *args, **kwargs)

    AsyncSession.execute = counting_execute  # type: ignore[method-assign]
    try:
        async with _anonymous(api_session) as visitor:
            page = await visitor.get(f"/api/v1/gift/{slug}")
    finally:
        AsyncSession.execute = original  # type: ignore[method-assign]

    assert page.status_code == 200
    assert len(page.json()["films"]) >= 4
    retailer_queries = [sql for sql in seen if "FROM retailers" in sql]
    assert len(retailer_queries) == 1, (
        f"the retailers table was queried {len(retailer_queries)} times for one page"
    )


async def test_the_view_counter_is_incremented_in_sql_not_in_python(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """`link.view_count += 1` is a read-modify-write: two family members opening the link
    at the same moment would record one view between them."""
    await _wanted(api_session, "A Film")
    created = await client.post("/api/v1/gift-links", json={"title": "Counted"})
    slug = created.json()["slug"]

    seen: list[str] = []
    original = AsyncSession.execute

    async def capturing_execute(self, statement, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(str(statement))
        return await original(self, statement, *args, **kwargs)

    AsyncSession.execute = capturing_execute  # type: ignore[method-assign]
    try:
        async with _anonymous(api_session) as visitor:
            await visitor.get(f"/api/v1/gift/{slug}")
    finally:
        AsyncSession.execute = original  # type: ignore[method-assign]

    updates = [sql for sql in seen if sql.startswith("UPDATE gift_links")]
    assert updates, "no UPDATE was issued for the view counter"
    assert "view_count + " in updates[0].replace("gift_links.view_count", "view_count"), updates[0]

    link = await api_session.get(GiftLink, uuid.UUID(created.json()["id"]))
    assert link is not None
    await api_session.refresh(link)
    assert link.view_count == 1
