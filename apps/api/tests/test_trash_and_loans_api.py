"""Batch 15's trash, permanent delete and lending — §13.5, §13.6, §12.5.

**The permanent delete is the first irreversible operation in this application**, so the
tests that matter most are not the happy path. They are: that it genuinely destroys the row
rather than soft-deleting it again; that an *ordinary* delete is still soft afterwards; and
that the mechanism which makes the first possible cannot leak into the second.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from typing import Any

import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utc_today
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.box_set import BoxSet
from src.models.collection_item import CollectionItem
from src.models.loan import Loan
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import Retailer, WantedItem
from src.models.watch_log import WatchLog
from src.services import trash as trash_service

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
        display_name=f"Batch Fifteen {role.value.title()} {uuid.uuid4().hex[:8]}",
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


async def _disc(session: AsyncSession, title: str) -> tuple[Movie, CollectionItem]:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
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
        notes="A note that must survive a restore",
        sub_category="A set",
    )
    session.add(item)
    await session.flush()
    return movie, item


# ---------------------------------------------------------------------------
# §13.5 — the trash, per table
# ---------------------------------------------------------------------------


async def test_deleted_rows_from_every_table_appear_in_one_shape(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """§13.5's "list soft-deleted items per table".

    Six tables. Batch 15 shipped four; `wanted_list` and `retailers` joined when Batch 18
    built §3.5 and §3.16. `gift_links` was a seventh from Batch 27 until **Batch S1 removed
    the feature** — the table held 0 rows, so nothing left the bin that was ever in it.
    Batch 15 deliberately left the names it could not serve *refused* rather than answering
    an empty page for tables that did not exist, which is why this list has only ever
    contained tables that are real.
    """
    movie, item = await _disc(api_session, "A Deleted Disc")
    item.deleted_at = datetime(2026, 9, 9)

    watched = WatchLog(
        id=uuid.uuid4(),
        movie_id=movie.id,
        user_id=admin.id,
        watched_at=date(2026, 9, 1),
        deleted_at=datetime(2026, 9, 9),
    )
    box_set = BoxSet(id=uuid.uuid4(), name="A Deleted Box Set", deleted_at=datetime(2026, 9, 9))
    api_session.add_all([watched, box_set])
    await api_session.flush()

    items = (await client.get("/api/v1/trash/all?table=collection_items")).json()
    assert any(row["label"] == "A Deleted Disc" for row in items["items"])
    # Every table's count comes back with every page, for the tabs.
    assert {c["table"] for c in items["counts"]} == {
        "collection_items",
        "watch_log",
        "movies",
        "box_sets",
        "wanted_list",
        "retailers",
    }

    watches = (await client.get("/api/v1/trash/all?table=watch_log")).json()
    assert any(row["label"] == "A Deleted Disc" for row in watches["items"])

    sets = (await client.get("/api/v1/trash/all?table=box_sets")).json()
    assert any(row["label"] == "A Deleted Box Set" for row in sets["items"])


async def test_a_table_with_no_trash_is_refused_rather_than_answered_empty(
    client: AsyncClient,
) -> None:
    """Answering "nothing here" for a table with no bin is how a missing feature passes
    for a working one.

    The example used to be ``wanted_list``, which **Batch 18 built** — so it is now a
    supported tab, and this test moved to a table that genuinely has no trash.
    ``smart_collections`` hard-deletes by design (`DECISIONS.md` #55: a saved collection
    owns no data, so there is nothing for a bin to hold), and ``profiles`` is not
    something a trash page should ever restore.
    """
    for absent in ("smart_collections", "profiles", "loans", "not_a_table"):
        response = await client.get(f"/api/v1/trash/all?table={absent}")
        assert response.status_code == 422, absent
        assert "Unknown table" in response.json()["detail"]


async def test_restoring_brings_a_disc_back_with_full_state(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§13.5's acceptance, and the word that matters is *full*.

    A restore clears the tombstone and nothing else. If it were a re-create, the notes,
    the sub-category and the shelf would all have to be re-supplied — and whatever was not
    would come back subtly different from what was deleted.
    """
    _, item = await _disc(api_session, "A Disc With History")
    item.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()

    response = await client.post(f"/api/v1/trash/collection_items/{item.id}/restore-row")
    assert response.status_code == 204, response.text

    await api_session.refresh(item)
    assert item.deleted_at is None
    assert item.notes == "A note that must survive a restore"
    assert item.sub_category == "A set"
    assert (item.section, item.shelf) == ("Front", "2nd")


async def test_replaced_disc_can_be_restored_with_the_same_source_row(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Batch 39 leaves provenance intact, so restore must allow the replacement's row.

    A bad spreadsheet can put something different on a line which the previous sheet
    used.  Recovery means bringing the complete old item back for comparison, not
    silently clearing its source provenance or refusing at the former unique index.
    """
    movie, old_item = await _disc(api_session, "A Replaced Disc")
    source_row = 1_000_000_000 + uuid.uuid4().int % 1_000_000_000
    old_item.import_source_row = source_row
    old_item.deleted_at = datetime(2026, 9, 16)
    await api_session.flush()

    replacement = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=["4k_uhd"],
        location="Front 1st shelf",
        section="Front",
        shelf="1st",
        condition="good",
        import_source_row=source_row,
    )
    api_session.add(replacement)
    await api_session.flush()

    response = await client.post(f"/api/v1/trash/collection_items/{old_item.id}/restore-row")
    assert response.status_code == 204, response.text

    await api_session.refresh(old_item)
    assert old_item.deleted_at is None
    assert old_item.import_source_row == source_row
    assert old_item.notes == "A note that must survive a restore"


async def test_every_remaining_table_can_still_be_restored(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """Batch S1's own criterion: removing one table from the bin must not break the other six.

    `TRASH_TABLES` is a tuple that `_MODELS` mirrors and `_describe` switches on, and a
    removal touches all three. The failure mode is not a crash — it is one table quietly
    dropping out of the restore path while the other five keep working and the suite keeps
    passing. So this walks the registry itself rather than a hand-written list: a table
    added later is covered without anyone remembering to add it here, and a table lost by
    accident fails at the `KeyError` in ``_rows``.
    """
    movie, item = await _disc(api_session, "A Disc For Every Table")

    watched = WatchLog(
        id=uuid.uuid4(),
        movie_id=movie.id,
        user_id=admin.id,
        watched_at=date(2026, 9, 1),
    )
    box_set = BoxSet(id=uuid.uuid4(), name="A Box Set For Every Table")
    wanted = WantedItem(id=uuid.uuid4(), movie_id=movie.id, preferred_format="4k_uhd")
    retailer = Retailer(
        id=uuid.uuid4(),
        name=f"A Shop {uuid.uuid4().hex[:8]}",
        base_url="https://example.invalid",
        scraper_type="generic_css",
    )
    api_session.add_all([watched, box_set, wanted, retailer])
    await api_session.flush()

    rows: dict[str, Any] = {
        "collection_items": item,
        "watch_log": watched,
        "movies": movie,
        "box_sets": box_set,
        "wanted_list": wanted,
        "retailers": retailer,
    }
    # The registry is the source of truth, not this dict — if they disagree, say which
    # name is unaccounted for rather than skipping it silently.
    assert set(rows) == set(trash_service.TRASH_TABLES)

    for table, row in rows.items():
        row.deleted_at = datetime(2026, 9, 9)
        await api_session.flush()

        listed = (await client.get(f"/api/v1/trash/all?table={table}")).json()
        assert any(entry["id"] == str(row.id) for entry in listed["items"]), table

        response = await client.post(f"/api/v1/trash/{table}/{row.id}/restore-row")
        assert response.status_code == 204, f"{table}: {response.text}"

        await api_session.refresh(row)
        assert row.deleted_at is None, table


async def test_restoring_something_that_is_not_deleted_is_a_404(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    _, item = await _disc(api_session, "A Live Disc")
    response = await client.post(f"/api/v1/trash/collection_items/{item.id}/restore-row")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# §13.5 — the permanent delete. The irreversible one.
# ---------------------------------------------------------------------------


async def test_a_permanent_delete_genuinely_destroys_the_row(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The whole point, and the thing a soft-delete trigger would silently prevent.

    `003`'s `collection_items_soft_delete` rewrites every DELETE into an UPDATE. If the
    permanent delete did not get past it, this endpoint would report success having
    destroyed nothing and the row would simply still be in the trash.
    """
    _, item = await _disc(api_session, "A Disc To Be Destroyed")
    item.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()

    response = await client.request("DELETE", f"/api/v1/trash/collection_items/{item.id}/permanent")
    assert response.status_code == 204, response.text

    gone = (
        await api_session.execute(
            text("SELECT count(*) FROM collection_items WHERE id = :id"), {"id": item.id}
        )
    ).scalar_one()
    assert gone == 0, "the row is still there — the soft-delete trigger won"


async def test_an_ordinary_delete_is_still_soft_afterwards(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The hazard the whole mechanism was chosen to avoid.

    `ALTER TABLE ... DISABLE TRIGGER` is persistent and **global**: a process death between
    disabling and re-enabling would leave every delete in the app permanent, with the trash
    showing an empty page while discs vanished. `SET LOCAL` reverts at commit and at
    rollback, so a permanent delete in one transaction cannot affect the next.
    """
    _, doomed = await _disc(api_session, "Destroyed First")
    doomed.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()
    await client.request("DELETE", f"/api/v1/trash/collection_items/{doomed.id}/permanent")

    _, survivor = await _disc(api_session, "Deleted Afterwards")
    await api_session.flush()
    response = await client.request("DELETE", f"/api/v1/collection/{survivor.id}")
    assert response.status_code == 200, response.text

    await api_session.refresh(survivor)
    assert survivor.deleted_at is not None, "an ordinary delete became permanent"
    still_there = (
        await api_session.execute(
            text("SELECT count(*) FROM collection_items WHERE id = :id"), {"id": survivor.id}
        )
    ).scalar_one()
    assert still_there == 1


async def test_only_something_already_in_the_trash_can_be_destroyed(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Two deliberate steps, not one mis-tap."""
    _, item = await _disc(api_session, "A Live Disc Nobody May Destroy")
    await api_session.flush()

    response = await client.request("DELETE", f"/api/v1/trash/collection_items/{item.id}/permanent")
    assert response.status_code == 404
    assert await api_session.get(CollectionItem, item.id) is not None


async def test_the_audit_row_outlives_the_row_it_describes(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """`admin_actions.target_id` is TEXT with no foreign key exactly so this works."""
    _, item = await _disc(api_session, "A Disc Whose Record Survives It")
    item.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()

    await client.request("DELETE", f"/api/v1/trash/collection_items/{item.id}/permanent")

    entry = (
        await api_session.execute(
            select(AdminAction).where(
                AdminAction.target_id == str(item.id),
                AdminAction.action_type == "delete",
            )
        )
    ).scalar_one()
    assert entry.user_id == admin.id
    assert entry.changes == {"permanent": True}


async def test_a_film_still_holding_discs_cannot_be_destroyed(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """`movies.id` is RESTRICT from `collection_items`, and the refusal says why.

    A cascade here would take real discs and real watch history out with a tidy-up.
    """
    movie, _ = await _disc(api_session, "A Film With A Disc")
    movie.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()

    response = await client.request("DELETE", f"/api/v1/trash/movies/{movie.id}/permanent")
    assert response.status_code == 409
    assert "still referenced" in response.json()["detail"]
    assert await api_session.get(Movie, movie.id) is not None


async def test_a_viewer_cannot_destroy_anything(
    viewer_client: AsyncClient, api_session: AsyncSession
) -> None:
    _, item = await _disc(api_session, "Not Mark's To Destroy")
    item.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()

    response = await viewer_client.request(
        "DELETE", f"/api/v1/trash/collection_items/{item.id}/permanent"
    )
    assert response.status_code == 403
    assert await api_session.get(CollectionItem, item.id) is not None


async def test_the_purge_is_a_dry_run_unless_asked_otherwise(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§6.30's 90-day purge. The destructive call is the one you have to ask for.

    Defaulting to destruction would mean a forgotten query parameter permanently deletes
    rows — and §6.30 says "auto-purged", which is precisely the wording that invites it.
    """
    _, old = await _disc(api_session, "Deleted Long Ago")
    old.deleted_at = datetime(2026, 1, 1)
    _, recent = await _disc(api_session, "Deleted Yesterday")
    recent.deleted_at = datetime(2026, 9, 8)
    await api_session.flush()

    preview = (await client.post("/api/v1/trash/purge?table=collection_items")).json()
    assert preview["dryRun"] is True
    assert preview["deleted"] == 0
    assert preview["olderThanDays"] == 90
    assert await api_session.get(CollectionItem, old.id) is not None

    done = (await client.post("/api/v1/trash/purge?table=collection_items&dryRun=false")).json()
    assert done["deleted"] >= 1
    # The one deleted yesterday is well inside the window and must survive.
    assert await api_session.get(CollectionItem, recent.id) is not None


# ---------------------------------------------------------------------------
# §13.6 — the audit log's filters
# ---------------------------------------------------------------------------


async def test_five_changes_show_five_entries_with_correct_diffs(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§13.6's acceptance, word for word: "5 test changes shows 5 entries with correct diffs"."""
    movie, item = await _disc(api_session, "A Disc Edited Five Times")
    await api_session.flush()

    conditions = ["like_new", "good", "acceptable", "damaged", "new"]
    for condition in conditions:
        response = await client.put(
            f"/api/v1/collection/{item.id}",
            json={"formats": ["blu_ray"], "condition": condition},
        )
        assert response.status_code == 200, response.text

    log = (await client.get(f"/api/v1/admin/audit?movieId={movie.id}&actionType=update")).json()
    assert log["total"] == 5, log

    # Newest first, so the diffs read backwards through the list.
    moves = [entry["changes"]["condition"] for entry in log["items"]]
    assert [move["to"] for move in moves] == list(reversed(conditions))
    assert moves[-1]["from"] == "good"


async def test_the_audit_log_filters_by_who_and_when(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """§13.6's "filterable" — who and when are the questions a person actually brings."""
    _, item = await _disc(api_session, "A Disc For Filtering")
    await api_session.flush()
    await client.put(
        f"/api/v1/collection/{item.id}", json={"formats": ["dvd"], "condition": "good"}
    )

    mine = (await client.get(f"/api/v1/admin/audit?actorId={admin.id}")).json()
    assert mine["total"] >= 1

    nobody = (await client.get(f"/api/v1/admin/audit?actorId={uuid.uuid4()}")).json()
    assert nobody["total"] == 0

    future = (await client.get("/api/v1/admin/audit?since=2099-01-01T00:00:00Z")).json()
    assert future["total"] == 0


# ---------------------------------------------------------------------------
# §12.5 — the lending tracker
# ---------------------------------------------------------------------------


async def test_lending_a_disc_shows_it_in_loans(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§12.5's acceptance, first half."""
    _, item = await _disc(api_session, "A Disc Lent To A Friend")
    await api_session.flush()

    created = await client.post(
        "/api/v1/loans",
        json={
            "collectionItemId": str(item.id),
            "borrowerName": "A Friend",
            "dueDate": (utc_today() + timedelta(days=14)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["isOverdue"] is False
    assert created.json()["daysUntilDue"] == 14

    loans = (await client.get("/api/v1/loans")).json()
    mine = next(loan for loan in loans["items"] if loan["id"] == created.json()["id"])
    assert mine["movieTitle"] == "A Disc Lent To A Friend"
    assert mine["borrowerName"] == "A Friend"
    assert loans["openCount"] >= 1


async def test_an_overdue_loan_is_derived_from_the_date_not_stored(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """A stored `is_overdue` needs a job to keep it true and is wrong between runs.

    **No push is sent by this endpoint**, and none should be: the reminder fires when a
    due date passes, which is the scheduled pass's job. Batch 11 built it — see
    `test_notifications_api.py::TestOverdueLoans`. What this test covers is the state a
    reminder is sent *about*, derived rather than stored.
    """
    _, item = await _disc(api_session, "A Disc Nobody Returned")
    await api_session.flush()

    created = await client.post(
        "/api/v1/loans",
        json={
            "collectionItemId": str(item.id),
            "borrowerName": "A Forgetful Friend",
            "lentDate": (utc_today() - timedelta(days=40)).isoformat(),
            "dueDate": (utc_today() - timedelta(days=10)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["isOverdue"] is True
    assert created.json()["daysUntilDue"] == -10

    loans = (await client.get("/api/v1/loans?openOnly=true")).json()
    assert loans["overdueCount"] >= 1

    # And nothing has claimed to notify anybody.
    loan = await api_session.get(Loan, uuid.UUID(created.json()["id"]))
    assert loan is not None and loan.reminder_sent is False


async def test_a_loan_with_no_due_date_is_never_overdue(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """ "No deadline" is not "due today". Rendering it as 0 puts every open-ended loan in
    the red."""
    _, item = await _disc(api_session, "A Disc Lent Indefinitely")
    await api_session.flush()

    created = await client.post(
        "/api/v1/loans",
        json={"collectionItemId": str(item.id), "borrowerName": "A Patient Friend"},
    )
    assert created.json()["isOverdue"] is False
    assert created.json()["daysUntilDue"] is None


async def test_one_disc_cannot_be_lent_to_two_people_at_once(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Two open loans on one object give two people a claim and no way to tell which is real."""
    _, item = await _disc(api_session, "A Disc In Demand")
    await api_session.flush()

    first = await client.post(
        "/api/v1/loans",
        json={"collectionItemId": str(item.id), "borrowerName": "First Borrower"},
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/loans",
        json={"collectionItemId": str(item.id), "borrowerName": "Second Borrower"},
    )
    assert second.status_code == 409


async def test_returning_a_disc_closes_the_loan_and_frees_the_disc(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    _, item = await _disc(api_session, "A Disc That Came Back")
    await api_session.flush()

    lent = await client.post(
        "/api/v1/loans",
        json={"collectionItemId": str(item.id), "borrowerName": "An Honest Friend"},
    )
    returned = await client.put(f"/api/v1/loans/{lent.json()['id']}/return", json={})
    assert returned.status_code == 200, returned.text
    assert returned.json()["returnedDate"] == utc_today().isoformat()
    assert returned.json()["isOverdue"] is False

    # Closed, so the disc can go out again.
    again = await client.post(
        "/api/v1/loans",
        json={"collectionItemId": str(item.id), "borrowerName": "The Next Borrower"},
    )
    assert again.status_code == 201


async def test_a_loan_cannot_be_returned_twice(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    _, item = await _disc(api_session, "A Disc Returned Once")
    await api_session.flush()
    lent = await client.post(
        "/api/v1/loans",
        json={"collectionItemId": str(item.id), "borrowerName": "A Friend"},
    )
    await client.put(f"/api/v1/loans/{lent.json()['id']}/return", json={})
    again = await client.put(f"/api/v1/loans/{lent.json()['id']}/return", json={})
    assert again.status_code == 409


async def test_a_disc_cannot_come_back_before_it_went_out(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    _, item = await _disc(api_session, "A Disc With Impossible Dates")
    await api_session.flush()
    lent = await client.post(
        "/api/v1/loans",
        json={
            "collectionItemId": str(item.id),
            "borrowerName": "A Friend",
            "lentDate": utc_today().isoformat(),
        },
    )
    response = await client.put(
        f"/api/v1/loans/{lent.json()['id']}/return",
        json={"returnedDate": (utc_today() - timedelta(days=5)).isoformat()},
    )
    assert response.status_code == 422


async def test_a_viewer_can_see_loans_but_not_create_one(
    viewer_client: AsyncClient, api_session: AsyncSession
) -> None:
    """Knowing where a disc went is not an admin question, even though lending one is."""
    _, item = await _disc(api_session, "A Disc Mark Can Ask About")
    await api_session.flush()

    assert (await viewer_client.get("/api/v1/loans")).status_code == 200
    refused = await viewer_client.post(
        "/api/v1/loans",
        json={"collectionItemId": str(item.id), "borrowerName": "Mark's Friend"},
    )
    assert refused.status_code == 403


async def test_destroying_a_disc_takes_its_loan_with_it(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """`loans.collection_item_id` is CASCADE: a loan of a disc that no longer exists is
    not a fact about anything. This is the one path that fires it."""
    _, item = await _disc(api_session, "A Disc Destroyed While Out")
    await api_session.flush()
    lent = await client.post(
        "/api/v1/loans",
        json={"collectionItemId": str(item.id), "borrowerName": "A Friend"},
    )
    loan_id = uuid.UUID(lent.json()["id"])

    item.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()
    destroyed = await client.request(
        "DELETE", f"/api/v1/trash/collection_items/{item.id}/permanent"
    )
    assert destroyed.status_code == 204, destroyed.text

    assert await api_session.get(Loan, loan_id) is None


async def test_the_permanent_flag_covers_exactly_one_statement(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """A soft delete in the *same transaction* as a permanent one must still be soft.

    `SET LOCAL` lasts to the end of the transaction and a released savepoint does not undo
    it, so the flag is turned off again immediately after the DELETE. This test shares one
    session between both operations, which is the arrangement that would expose a leak —
    in production they are separate requests and separate transactions.
    """
    _, doomed = await _disc(api_session, "Destroyed In This Transaction")
    doomed.deleted_at = datetime(2026, 9, 9)
    _, survivor = await _disc(api_session, "Soft Deleted In The Same One")
    await api_session.flush()

    await client.request("DELETE", f"/api/v1/trash/collection_items/{doomed.id}/permanent")
    await api_session.execute(
        text("DELETE FROM collection_items WHERE id = :id"), {"id": survivor.id}
    )
    await api_session.flush()

    row = (
        await api_session.execute(
            text("SELECT deleted_at FROM collection_items WHERE id = :id"),
            {"id": survivor.id},
        )
    ).first()
    assert row is not None, "the row was destroyed — the permanent flag leaked"
    assert row[0] is not None
