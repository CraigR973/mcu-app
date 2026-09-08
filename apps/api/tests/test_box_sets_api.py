"""Postgres-backed contract tests for Batch 12's box sets — §11.3 and §11.4.

Structured by acceptance criterion, because that is what `batch-verify` reports against:

- §11.3 — *"Admin creates 'Columbia Noir Vol 4' with 4 items"*
- §11.4 — *"Browsing box sets shows all with status"*

``box_sets`` starts empty in every environment, so unlike the collection tests these can
assert on totals without the live-data collisions `STATUS.md`'s Now block describes — each
test runs inside a transaction that is rolled back, and no real rows exist to intrude.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.box_set import BOX_SETS_TABLE, BoxSet
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole

pytestmark = pytest.mark.asyncio

ACTOR_HEADER = "x-test-actor"


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


async def _profile(session: AsyncSession, role: UserRole) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Batch Twelve {role.value.title()} {uuid.uuid4().hex[:8]}",
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
    """One global override that picks the actor from a header.

    Per Batch 7's comment on the same fixture: ``app.dependency_overrides`` is global to
    the application, so two clients each installing their own ``get_current_user`` means
    whichever was built last silently decides the actor for both.
    """

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


async def _disc(session: AsyncSession, title: str) -> CollectionItem:
    """One film and one disc of it, filed somewhere real."""
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        media_type="film",
        year=1955,
    )
    session.add(movie)
    await session.flush()
    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=["blu_ray"],
        location="Top small cabinet",
        section="Top Small Cabinet",
        condition="good",
    )
    session.add(item)
    await session.flush()
    return item


#: The four films of the acceptance criterion's own example, taken from the real
#: "Columbia Noir #4" rows in the live catalogue.
COLUMBIA_NOIR_4 = [
    "A Bullet Is Waiting",
    "Chicago Syndicate",
    "The Brothers Rico",
    "Walk a Crooked Mile",
]


# ---------------------------------------------------------------------------
# §11.3 — "Admin creates 'Columbia Noir Vol 4' with 4 items"
# ---------------------------------------------------------------------------


async def test_admin_creates_columbia_noir_vol_4_with_four_items(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    discs = [await _disc(api_session, title) for title in COLUMBIA_NOIR_4]

    response = await client.post(
        "/api/v1/box-sets",
        json={
            "name": "Columbia Noir Vol 4",
            "label": "Indicator",
            "volumeNumber": 4,
            "expectedCount": 4,
            "itemIds": [str(disc.id) for disc in discs],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Columbia Noir Vol 4"
    assert body["ownedCount"] == 4
    assert body["expectedCount"] == 4
    assert body["isComplete"] is True
    assert [item["movieTitle"] for item in body["items"]] == COLUMBIA_NOIR_4
    # Disc numbers follow the order they were chosen in — the order on the spines.
    assert [item["discNumber"] for item in body["items"]] == [1, 2, 3, 4]


async def test_creating_a_set_records_an_audit_row(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    disc = await _disc(api_session, "A Filed Disc")
    response = await client.post(
        "/api/v1/box-sets", json={"name": "Audited Set", "itemIds": [str(disc.id)]}
    )
    assert response.status_code == 201, response.text

    entry = (
        await api_session.execute(
            select(AdminAction).where(
                AdminAction.target_table == BOX_SETS_TABLE,
                AdminAction.target_id == response.json()["id"],
            )
        )
    ).scalar_one()
    assert entry.action_type == "create"
    assert entry.user_id == admin.id
    assert entry.changes is not None
    assert entry.changes["name"] == "Audited Set"
    assert entry.changes["item_count"] == 1


async def test_a_viewer_cannot_create_a_box_set(
    viewer_client: AsyncClient, api_session: AsyncSession
) -> None:
    await _disc(api_session, "Not Yours To File")
    response = await viewer_client.post("/api/v1/box-sets", json={"name": "Mark's Set"})
    assert response.status_code == 403


async def test_items_can_be_added_and_removed_after_creation(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    first, second = [await _disc(api_session, t) for t in ("First Disc", "Second Disc")]
    created = await client.post("/api/v1/box-sets", json={"name": "Growing Set"})
    set_id = created.json()["id"]

    added = await client.post(
        f"/api/v1/box-sets/{set_id}/items",
        json={"collectionItemId": str(first.id), "discNumber": 1},
    )
    assert added.status_code == 201, added.text
    assert added.json()["ownedCount"] == 1

    again = await client.post(
        f"/api/v1/box-sets/{set_id}/items", json={"collectionItemId": str(first.id)}
    )
    assert again.status_code == 409

    await client.post(f"/api/v1/box-sets/{set_id}/items", json={"collectionItemId": str(second.id)})
    removed = await client.request("DELETE", f"/api/v1/box-sets/{set_id}/items/{first.id}")
    assert removed.status_code == 200, removed.text
    assert removed.json()["ownedCount"] == 1
    assert [i["movieTitle"] for i in removed.json()["items"]] == ["Second Disc"]


async def test_a_set_cannot_hold_a_disc_that_does_not_exist(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/box-sets", json={"name": "Imaginary Set", "itemIds": [str(uuid.uuid4())]}
    )
    assert response.status_code == 422
    assert "not found" in response.json()["detail"]


async def test_the_same_disc_twice_in_one_create_is_refused(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    disc = await _disc(api_session, "A Single Disc")
    response = await client.post(
        "/api/v1/box-sets",
        json={"name": "Double Counted", "itemIds": [str(disc.id), str(disc.id)]},
    )
    # Refused at validation rather than at the composite primary key, so the error
    # names the mistake instead of surfacing a constraint violation.
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# §11.3 — series linking
# ---------------------------------------------------------------------------


async def test_a_volume_links_to_its_series_and_the_series_lists_its_volumes(
    client: AsyncClient,
) -> None:
    series = await client.post("/api/v1/box-sets", json={"name": "Columbia Noir"})
    series_id = series.json()["id"]

    volume = await client.post(
        "/api/v1/box-sets",
        json={"name": "Columbia Noir Vol 4", "volumeNumber": 4, "seriesId": series_id},
    )
    assert volume.status_code == 201, volume.text
    assert volume.json()["seriesName"] == "Columbia Noir"

    detail = await client.get(f"/api/v1/box-sets/{series_id}")
    assert [v["name"] for v in detail.json()["volumes"]] == ["Columbia Noir Vol 4"]


async def test_series_nesting_is_refused_at_one_level(client: AsyncClient) -> None:
    series = await client.post("/api/v1/box-sets", json={"name": "A Series"})
    volume = await client.post(
        "/api/v1/box-sets", json={"name": "A Volume", "seriesId": series.json()["id"]}
    )

    grandchild = await client.post(
        "/api/v1/box-sets", json={"name": "A Sub-Volume", "seriesId": volume.json()["id"]}
    )
    assert grandchild.status_code == 422
    assert "one level deep" in grandchild.json()["detail"]


async def test_a_series_with_volumes_cannot_itself_become_a_volume(
    client: AsyncClient,
) -> None:
    """The back door into a two-level chain: edit the parent rather than the child."""
    other = await client.post("/api/v1/box-sets", json={"name": "Another Series"})
    series = await client.post("/api/v1/box-sets", json={"name": "A Parent Series"})
    await client.post(
        "/api/v1/box-sets", json={"name": "Its Volume", "seriesId": series.json()["id"]}
    )

    response = await client.put(
        f"/api/v1/box-sets/{series.json()['id']}",
        json={"name": "A Parent Series", "seriesId": other.json()["id"]},
    )
    assert response.status_code == 422
    assert "volumes of its own" in response.json()["detail"]


async def test_a_set_cannot_be_its_own_series(client: AsyncClient) -> None:
    created = await client.post("/api/v1/box-sets", json={"name": "Ouroboros"})
    set_id = created.json()["id"]
    response = await client.put(
        f"/api/v1/box-sets/{set_id}", json={"name": "Ouroboros", "seriesId": set_id}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# §11.4 — "Browsing box sets shows all with status"
# ---------------------------------------------------------------------------


async def test_browsing_box_sets_shows_all_of_them_with_completion_status(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    three_of_four = [await _disc(api_session, f"Boxed Film {n}") for n in range(3)]
    await client.post(
        "/api/v1/box-sets",
        json={
            "name": "A Partly Owned Set",
            "expectedCount": 4,
            "itemIds": [str(d.id) for d in three_of_four],
        },
    )
    complete_disc = await _disc(api_session, "The Only Disc In Its Box")
    await client.post(
        "/api/v1/box-sets",
        json={
            "name": "A Complete Set",
            "expectedCount": 1,
            "itemIds": [str(complete_disc.id)],
        },
    )
    await client.post("/api/v1/box-sets", json={"name": "A Set Of Unknown Size"})

    response = await client.get("/api/v1/box-sets")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    by_name = {item["name"]: item for item in body["items"]}

    # "3 of 4", which is §11.4's own wording for the thing being shown.
    partial = by_name["A Partly Owned Set"]
    assert (partial["ownedCount"], partial["expectedCount"]) == (3, 4)
    assert partial["isComplete"] is False

    assert by_name["A Complete Set"]["isComplete"] is True

    # Not False. A set whose size nobody recorded is unmeasured, not incomplete —
    # rendering it as incomplete would put a permanent red mark against it.
    unknown = by_name["A Set Of Unknown Size"]
    assert unknown["expectedCount"] is None
    assert unknown["isComplete"] is None


async def test_a_viewer_can_browse_box_sets(
    client: AsyncClient, viewer_client: AsyncClient, api_session: AsyncSession
) -> None:
    disc = await _disc(api_session, "A Shared Disc")
    await client.post(
        "/api/v1/box-sets", json={"name": "Readable By Mark", "itemIds": [str(disc.id)]}
    )
    response = await viewer_client.get("/api/v1/box-sets")
    assert response.status_code == 200
    assert [i["name"] for i in response.json()["items"]] == ["Readable By Mark"]


async def test_a_disc_in_the_trash_stops_counting_towards_completion(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Soft-deleting a disc must move a set from complete to incomplete.

    The membership row survives — the disc can come back out of the trash — so counting
    memberships rather than live discs would report "4 of 4" for a box three of whose
    discs are in the bin.
    """
    discs = [await _disc(api_session, f"Perishable {n}") for n in range(2)]
    created = await client.post(
        "/api/v1/box-sets",
        json={
            "name": "A Set That Loses A Disc",
            "expectedCount": 2,
            "itemIds": [str(d.id) for d in discs],
        },
    )
    assert created.json()["isComplete"] is True

    deleted = await client.request("DELETE", f"/api/v1/collection/{discs[0].id}")
    assert deleted.status_code == 200, deleted.text

    after = await client.get(f"/api/v1/box-sets/{created.json()['id']}")
    assert after.json()["ownedCount"] == 1
    assert after.json()["isComplete"] is False
    assert [i["movieTitle"] for i in after.json()["items"]] == ["Perishable 1"]


async def test_deleting_a_set_hides_it_and_leaves_the_discs_alone(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    disc = await _disc(api_session, "A Disc That Outlives Its Box")
    created = await client.post(
        "/api/v1/box-sets", json={"name": "A Doomed Set", "itemIds": [str(disc.id)]}
    )
    set_id = created.json()["id"]

    response = await client.request("DELETE", f"/api/v1/box-sets/{set_id}")
    assert response.status_code == 204

    assert (await client.get("/api/v1/box-sets")).json()["total"] == 0
    assert (await client.get(f"/api/v1/box-sets/{set_id}")).status_code == 404

    # Soft, not hard — recoverable once §13.5's Trash widens to this table in Batch 15.
    row = await api_session.get(BoxSet, uuid.UUID(set_id))
    assert row is not None and row.deleted_at is not None

    # And the disc is untouched: deleting a grouping destroys nothing physical.
    survivor = await api_session.get(CollectionItem, disc.id)
    assert survivor is not None and survivor.deleted_at is None


async def test_editing_a_set_records_only_the_fields_that_moved(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    created = await client.post("/api/v1/box-sets", json={"name": "Before", "expectedCount": 3})
    set_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/box-sets/{set_id}", json={"name": "After", "expectedCount": 3}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "After"

    entry = (
        await api_session.execute(
            select(AdminAction).where(
                AdminAction.target_table == BOX_SETS_TABLE,
                AdminAction.target_id == set_id,
                AdminAction.action_type == "update",
            )
        )
    ).scalar_one()
    assert entry.changes == {"name": {"from": "Before", "to": "After"}}
