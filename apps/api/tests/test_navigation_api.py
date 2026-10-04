"""Batch S3's self-hiding menu — snag 5, `DECISIONS.md` #154.

**Both states are tested, and that is the point of the file.** A hide that never un-hides
is the failure mode here: it looks correct on this database, where all four tables are
empty, and stays wrong forever. So every destination is asserted twice — zero, then one.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.box_set import BoxSet
from src.models.collection_item import CollectionItem
from src.models.deal import Deal
from src.models.loan import Loan
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.smart_collection import SmartCollection

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
        display_name=f"Batch S3 {role.value.title()} {uuid.uuid4().hex[:8]}",
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


async def _sections(client: AsyncClient) -> dict[str, int]:
    response = await client.get("/api/v1/nav/sections")
    assert response.status_code == 200, response.text
    body: dict[str, int] = response.json()
    return body


async def _disc(session: AsyncSession) -> CollectionItem:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=f"A Film {uuid.uuid4().hex[:8]}",
        original_title="A Film",
        media_type="film",
        year=2087,
    )
    session.add(movie)
    await session.flush()
    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=["blu_ray"],
        location="Front 2nd shelf",
        section="Front",
        shelf="2nd",
        condition="good",
    )
    session.add(item)
    await session.flush()
    return item


# ---------------------------------------------------------------------------
# Empty — the state this database is actually in
# ---------------------------------------------------------------------------


async def test_every_section_is_zero_on_an_empty_database(client: AsyncClient) -> None:
    """The measured state of live Neon on 2026-09-14: all four tables empty.

    This is the half that is easy to get right and easy to be fooled by — a broken
    endpoint returning zeros looks identical to a correct one here, which is exactly why
    the other half of this file exists.
    """
    assert await _sections(client) == {"boxSets": 0, "collections": 0, "deals": 0, "loans": 0}


# ---------------------------------------------------------------------------
# Non-empty — the state a hide-that-never-un-hides would fail
# ---------------------------------------------------------------------------


async def test_a_box_set_makes_its_section_non_empty(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    api_session.add(BoxSet(id=uuid.uuid4(), name="A Box Set"))
    await api_session.flush()
    assert (await _sections(client))["boxSets"] == 1


async def test_a_soft_deleted_box_set_does_not_count(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """A set in the trash is in the trash, not in the menu.

    Without this the destination would reappear for something the person deliberately
    removed, and lead to a page that does not list it.
    """
    from datetime import datetime

    api_session.add(BoxSet(id=uuid.uuid4(), name="A Deleted Set", deleted_at=datetime(2026, 9, 9)))
    await api_session.flush()
    assert (await _sections(client))["boxSets"] == 0


async def test_a_collection_counts_only_for_the_person_who_owns_it(
    client: AsyncClient, viewer_client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """Smart collections are per-user, so the count has to be too.

    A shared count would show Mark a Collections destination holding nothing but Craig's,
    which is the same "leads nowhere" problem wearing a different hat.
    """
    api_session.add(SmartCollection(id=uuid.uuid4(), user_id=admin.id, name="Craig's", filters={}))
    await api_session.flush()

    assert (await _sections(client))["collections"] == 1
    assert (await _sections(viewer_client))["collections"] == 0


async def test_a_deal_makes_its_section_non_empty(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    api_session.add(
        Deal(
            id=uuid.uuid4(),
            retailer_name_snapshot="A Shop",
            title_snapshot="A Film",
            url=f"https://example.invalid/{uuid.uuid4().hex}",
            price=Decimal("9.99"),
        )
    )
    await api_session.flush()
    assert (await _sections(client))["deals"] == 1


async def test_a_dismissed_deal_does_not_count(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The same filter `GET /deals` applies.

    If the two disagreed the menu would offer a page that then rendered empty — the item
    right about the table and wrong about the page.
    """
    from src.clock import utcnow

    api_session.add(
        Deal(
            id=uuid.uuid4(),
            retailer_name_snapshot="A Shop",
            title_snapshot="A Film",
            url=f"https://example.invalid/{uuid.uuid4().hex}",
            price=Decimal("9.99"),
            dismissed_at_utc=utcnow(),
        )
    )
    await api_session.flush()
    assert (await _sections(client))["deals"] == 0


async def test_a_loan_makes_its_section_non_empty(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    item = await _disc(api_session)
    api_session.add(
        Loan(
            id=uuid.uuid4(),
            collection_item_id=item.id,
            borrower_name="Mark",
            lent_date=date(2026, 9, 1),
        )
    )
    await api_session.flush()
    assert (await _sections(client))["loans"] == 1


async def test_a_returned_loan_still_counts(client: AsyncClient, api_session: AsyncSession) -> None:
    """`GET /loans` lists returned loans alongside open ones, so the menu must too.

    Filtering on `returned_date` here would make the destination vanish the moment the
    last disc came back, taking the history with it.
    """
    item = await _disc(api_session)
    api_session.add(
        Loan(
            id=uuid.uuid4(),
            collection_item_id=item.id,
            borrower_name="Mark",
            lent_date=date(2026, 9, 1),
            returned_date=date(2026, 9, 5),
        )
    )
    await api_session.flush()
    assert (await _sections(client))["loans"] == 1


async def test_a_viewer_may_read_the_menu_shape(viewer_client: AsyncClient) -> None:
    """Not admin-gated: all four destinations are visible to a viewer, and the menu is
    drawn for whoever is signed in."""
    response = await viewer_client.get("/api/v1/nav/sections")
    assert response.status_code == 200, response.text
