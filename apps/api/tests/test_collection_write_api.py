"""Postgres-backed contract tests for Batch 7's write surface.

Structured by acceptance criterion — §3.1, §3.2, §3.5, §3.11 and `DECISIONS.md` #5 —
because that is what `batch-verify` has to report against.

These cannot run on the development machine: there is no local Postgres and no Docker
(`STATUS.md` gotcha 15), and ``admin_actions`` does not exist on Neon until this batch's
migration deploys. They run against the Postgres 17 service in CI.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem
from src.models.movie import Movie, MovieCredit
from src.models.profile import Profile, UserRole
from src.routers.movies import get_tmdb_client
from src.tmdb.models import (
    CastMember,
    Credits,
    CrewMember,
    Genre,
    SearchResult,
    SearchResults,
)
from src.tmdb.models import (
    Movie as TmdbMovie,
)

NEW_TMDB_ID = 920001


def _tmdb_movie(tmdb_id: int) -> TmdbMovie:
    return TmdbMovie(
        id=tmdb_id,
        title="A Newly Bought Film",
        original_title="A Newly Bought Film",
        overview="Bought on a Saturday and catalogued the same afternoon.",
        release_date="1994-09-23",
        runtime=142,
        tagline="Added by hand.",
        vote_average=8.7,
        vote_count=1000,
        poster_path="/bought.jpg",
        backdrop_path="/bought-backdrop.jpg",
        genres=[Genre(id=18, name="Drama")],
        imdb_id="tt0111161",
        credits=Credits(
            cast=[
                CastMember(
                    id=11,
                    name="Bought Actor",
                    character="The Buyer",
                    order=0,
                    profile_path="/buyer.jpg",
                    credit_id="cast-11",
                )
            ],
            crew=[
                CrewMember(
                    id=12,
                    name="Frank Darabont",
                    job="Director",
                    department="Directing",
                    credit_id="crew-12",
                )
            ],
        ),
    )


class FakeTmdbClient:
    async def search_movie(
        self,
        query: str,
        year: int | None = None,
        page: int = 1,
        language: str = "en-US",
        include_adult: bool = False,
    ) -> SearchResults:
        del year, page, language, include_adult
        return SearchResults(
            page=1,
            total_pages=1,
            total_results=1,
            results=[
                SearchResult(
                    id=NEW_TMDB_ID,
                    title="A Newly Bought Film",
                    original_title="A Newly Bought Film",
                    overview=f"Search hit for {query}",
                    release_date="1994-09-23",
                    poster_path="/bought.jpg",
                    popularity=42,
                )
            ],
        )

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        del language
        return _tmdb_movie(movie_id)


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
        display_name=f"Batch Seven {role.value.title()} {uuid.uuid4().hex[:8]}",
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


#: Which profile a request is acting as. A header rather than a per-client override
#: because ``app.dependency_overrides`` is global to the application: two clients
#: installing their own ``get_current_user`` meant whichever fixture was built last
#: silently decided the actor for *both*, and the admin's writes came back 403. Found
#: in CI, and it would have made the "viewer sees it immediately" criterion untestable.
ACTOR_HEADER = "x-test-actor"


@pytest_asyncio.fixture
async def overrides(
    api_session: AsyncSession, admin: Profile, viewer: Profile
) -> AsyncIterator[None]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user(request: Request) -> Profile:
        return admin if request.headers.get(ACTOR_HEADER) == "admin" else viewer

    async def override_tmdb() -> AsyncIterator[FakeTmdbClient]:
        yield FakeTmdbClient()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
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
    """An admin's client — the only role this surface accepts."""
    del overrides
    async with _client_as("admin") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def viewer_client(overrides: None) -> AsyncIterator[AsyncClient]:
    """Mark's client. Reads everything; adds, edits and deletes discs (#155, #264)."""
    del overrides
    async with _client_as("viewer") as http_client:
        yield http_client


async def _a_film(
    session: AsyncSession,
    *,
    title: str = "An Owned Film",
    tmdb_id: int | None = 930001,
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=1994,
        media_type="film",
    )
    session.add(movie)
    await session.flush()
    return movie


async def _a_disc(
    session: AsyncSession,
    movie: Movie,
    *,
    formats: list[str] | None = None,
    section: str | None = "Front",
    shelf: str | None = "2nd",
    condition: str | None = "good",
) -> CollectionItem:
    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=formats or ["blu_ray"],
        location=f"{section} {shelf} shelf" if shelf else section,
        section=section,
        shelf=shelf,
        condition=condition,
    )
    session.add(item)
    await session.flush()
    return item


def _body(**overrides: Any) -> dict[str, Any]:
    """A valid create/update body, with the editable field set spelled out."""
    payload: dict[str, Any] = {
        "formats": ["blu_ray"],
        "location": "Front 2nd shelf",
        "condition": "good",
        "hasPlaybackIssues": False,
    }
    payload.update(overrides)
    return payload


async def _audit_rows(session: AsyncSession, target_id: uuid.UUID) -> list[AdminAction]:
    return list(
        (
            await session.execute(
                select(AdminAction)
                .where(AdminAction.target_id == str(target_id))
                .order_by(AdminAction.created_at, AdminAction.id)
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# §3.1 — Admin adds a movie; viewer immediately sees it
# ---------------------------------------------------------------------------


async def test_admin_adds_a_disc_and_the_viewer_sees_it(
    client: AsyncClient,
    viewer_client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Added By Hand", tmdb_id=930010)

    created = await client.post(
        "/api/v1/collection",
        json=_body(
            movieId=str(movie.id),
            barcode="5-051892-211475",
            purchasePrice="12.99",
            purchaseSource="Fopp",
        ),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["movieId"] == str(movie.id)
    assert body["section"] == "Front"
    assert body["shelf"] == "2nd"
    assert body["locationLabel"] == "Front 2nd"
    assert body["purchasePrice"] == "12.99"

    # Phase 3.4 is a scan-to-add flow, so the physical row must retain the normalised
    # code. Without this, the confirmation cache answers next time but duplicate detection
    # incorrectly says the exact disc is not already owned.
    written = await api_session.get(CollectionItem, uuid.UUID(body["id"]))
    assert written is not None
    assert written.barcode == "5051892211475"

    # The viewer's read of the same film shows the disc without any further write.
    seen = await viewer_client.get(f"/api/v1/movies/{movie.id}/copies")
    assert seen.status_code == 200
    assert [copy["id"] for copy in seen.json()] == [body["id"]]


async def test_adding_from_tmdb_creates_the_film_and_its_credits(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    response = await client.post(
        "/api/v1/collection", json=_body(tmdbId=NEW_TMDB_ID, formats=["4k_uhd"])
    )
    assert response.status_code == 201, response.text
    movie_id = uuid.UUID(response.json()["movieId"])

    movie = await api_session.get(Movie, movie_id)
    assert movie is not None
    assert movie.tmdb_id == NEW_TMDB_ID
    assert movie.title == "A Newly Bought Film"
    assert movie.year == 1994

    credits = (
        (await api_session.execute(select(MovieCredit).where(MovieCredit.movie_id == movie_id)))
        .scalars()
        .all()
    )
    assert {credit.role for credit in credits} == {"cast", "director"}


async def test_adding_a_tmdb_film_already_in_the_catalogue_reuses_its_row(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """``movies.tmdb_id`` is unique — a second row would fail, or split one film in two."""
    existing = await _a_film(api_session, title="Already Here", tmdb_id=NEW_TMDB_ID)

    response = await client.post("/api/v1/collection", json=_body(tmdbId=NEW_TMDB_ID))

    assert response.status_code == 201, response.text
    assert response.json()["movieId"] == str(existing.id)


async def test_a_viewer_may_add_edit_move_and_delete_a_disc(
    viewer_client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
) -> None:
    """**Batch Y1 moved the line again, and this test is still where the line lives.**

    #155 let Mark add a disc and kept editing and deleting as Craig's. That left Mark able
    to add a disc he could not correct, or move when it changed shelf, so `DECISIONS.md`
    #264 (superseding #37) gives him both. What keeps the line sharp now is attribution:
    each change is an audit row naming Mark, and getting a disc back from the Trash stays
    Craig's (the next test).
    """
    # Two films on purpose. Adding a *second* copy of a film that already has one is a
    # duplicate and answers 409 before it ever reaches the role check.
    fresh = await _a_film(api_session, title="Marks To Add", tmdb_id=930201)
    movie = await _a_film(api_session, title="Marks To Move", tmdb_id=930011)
    item = await _a_disc(api_session, movie, section="Front", shelf="2nd")

    added = await viewer_client.post("/api/v1/collection", json=_body(movieId=str(fresh.id)))
    assert added.status_code == 201, added.text

    moved = await viewer_client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(section="Craig's house", shelf=None, location=None, edition="Steelbook"),
    )
    assert moved.status_code == 200, moved.text
    assert (moved.json()["section"], moved.json()["shelf"]) == ("Craig's house", None)
    assert moved.json()["edition"] == "Steelbook"

    deleted = await viewer_client.delete(f"/api/v1/collection/{item.id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deletedAt"] is not None

    entries = await _audit_rows(api_session, item.id)
    assert [(entry.action_type, entry.user_id) for entry in entries] == [
        ("update", viewer.id),
        ("delete", viewer.id),
    ]


async def test_a_viewer_cannot_bring_a_deleted_disc_back(
    client: AsyncClient,
    viewer_client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """#264 widens deleting, not the Trash: restoring stays Craig's, as #155 kept it."""
    movie = await _a_film(api_session, title="Marks Mistake", tmdb_id=930202)
    item = await _a_disc(api_session, movie)
    assert (await viewer_client.delete(f"/api/v1/collection/{item.id}")).status_code == 200

    refused = await viewer_client.post(f"/api/v1/trash/collection_items/{item.id}/restore")
    assert refused.status_code == 403

    restored = await client.post(f"/api/v1/trash/collection_items/{item.id}/restore")
    assert restored.status_code == 200, restored.text


async def test_the_admin_only_tools_still_refuse_a_viewer(viewer_client: AsyncClient) -> None:
    """Batch S4's other criterion: **403**, for the tools that do not move.

    #155 widens Mark's reach; it does not remove the distinction. Trash, the audit log and
    changing retailers are Craig's in the sense the Admin page's own label means, and a
    batch about *reach* is exactly when a boundary quietly stops being enforced.

    **Retailers is where the criterion is looser than the code, and the code is right.**
    The ledger says "Retailers still refuses a viewer", which is true of the *page* —
    `/retailers` is `AdminShell` — but `GET /api/v1/retailers` has been `CurrentUser`
    since Batch 18, deliberately and with its reason written down: *"reads are open to
    both people — Mark can reasonably want to see what is being looked for"*. Every
    **write** is admin-only, which is the boundary this asserts. S4 changed none of it.
    """
    assert (await viewer_client.get("/api/v1/trash")).status_code == 403
    assert (await viewer_client.get("/api/v1/admin/audit")).status_code == 403
    assert (
        await viewer_client.post(
            "/api/v1/retailers",
            json={"name": "Marks Shop", "baseUrl": "https://example.invalid"},
        )
    ).status_code == 403
    assert (await viewer_client.post("/api/v1/retailers/seed")).status_code == 403


async def test_a_viewer_can_reach_every_step_of_the_add_flow(
    viewer_client: AsyncClient, api_session: AsyncSession
) -> None:
    """**The API moves with the UI, never after it** — #155.

    A page that stops hiding a button whose endpoint still 403s is worse than no change at
    all, so the criterion is the *whole flow*, not the final POST. Search for the film,
    check for a duplicate, then add: any one of the three still refusing a viewer would
    leave Mark with an add page that fails somewhere in the middle.
    """
    movie = await _a_film(api_session, title="A Film Mark Can Add", tmdb_id=930012)

    duplicate = await viewer_client.get(
        f"/api/v1/collection/duplicate-check?movieId={movie.id}&format=blu_ray"
    )
    assert duplicate.status_code == 200, duplicate.text

    added = await viewer_client.post("/api/v1/collection", json=_body(movieId=str(movie.id)))
    assert added.status_code == 201, added.text


async def test_create_requires_exactly_one_film_reference(client: AsyncClient) -> None:
    neither = await client.post("/api/v1/collection", json=_body())
    both = await client.post(
        "/api/v1/collection", json=_body(movieId=str(uuid.uuid4()), tmdbId=NEW_TMDB_ID)
    )
    assert neither.status_code == 422
    assert both.status_code == 422


async def test_create_refuses_a_misread_scanner_code_before_writing(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    movie = await _a_film(api_session, title="Not Added From A Misread", tmdb_id=930012)

    response = await client.post(
        "/api/v1/collection",
        json=_body(movieId=str(movie.id), barcode="5051892211476"),
    )

    assert response.status_code == 422
    rows = (
        (
            await api_session.execute(
                select(CollectionItem).where(CollectionItem.movie_id == movie.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


# ---------------------------------------------------------------------------
# §3.5 — Adding a 4K when Blu-ray exists triggers the upgrade prompt
# ---------------------------------------------------------------------------


async def test_duplicate_check_reports_an_upgrade_with_formats_and_locations(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Owned On Blu-ray", tmdb_id=930020)
    await _a_disc(api_session, movie, formats=["blu_ray"], section="Back", shelf="6th")

    response = await client.get(
        "/api/v1/collection/duplicate-check",
        params={"movieId": str(movie.id), "format": "4k_uhd"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["isDuplicate"] is True
    assert body["isUpgrade"] is True
    assert body["bestFormatOwned"] == "blu_ray"
    assert body["existingCopies"][0]["formats"] == ["blu_ray"]
    assert body["existingCopies"][0]["locationLabel"] == "Back 6th"


async def test_duplicate_check_of_an_equal_format_is_not_an_upgrade(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Owned On 4K", tmdb_id=930021)
    await _a_disc(api_session, movie, formats=["4k_uhd"])

    response = await client.get(
        "/api/v1/collection/duplicate-check",
        params={"movieId": str(movie.id), "format": "4k_uhd"},
    )

    assert response.json()["isDuplicate"] is True
    assert response.json()["isUpgrade"] is False


async def test_duplicate_check_is_clean_for_a_film_not_in_the_catalogue(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/collection/duplicate-check", params={"tmdbId": 999_999_001}
    )
    assert response.status_code == 200
    assert response.json()["isDuplicate"] is False


async def test_an_unconfirmed_duplicate_is_refused_and_carries_the_prompt(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The guard, not the courtesy — a client that skipped the preflight still stops."""
    movie = await _a_film(api_session, title="Bought Twice", tmdb_id=930022)
    await _a_disc(api_session, movie, formats=["blu_ray"])

    response = await client.post(
        "/api/v1/collection", json=_body(movieId=str(movie.id), formats=["4k_uhd"])
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["isDuplicate"] is True
    assert detail["isUpgrade"] is True
    assert detail["existingCopies"][0]["formats"] == ["blu_ray"]

    still_one = await client.get(f"/api/v1/movies/{movie.id}/copies")
    assert len(still_one.json()) == 1


async def test_a_confirmed_duplicate_is_added_and_records_why(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Upgraded", tmdb_id=930023)
    await _a_disc(api_session, movie, formats=["blu_ray"])

    response = await client.post(
        "/api/v1/collection",
        json=_body(movieId=str(movie.id), formats=["4k_uhd"], confirmDuplicate="upgrade"),
    )

    assert response.status_code == 201, response.text
    entries = await _audit_rows(api_session, uuid.UUID(response.json()["id"]))
    assert entries[0].action_type == "create"
    assert entries[0].changes is not None
    assert entries[0].changes["duplicate_reason"] == "upgrade"


# ---------------------------------------------------------------------------
# §3.2 — Changes persist; deleted items appear in trash; the audit log shows the change
# ---------------------------------------------------------------------------


async def test_an_edit_persists_and_logs_only_what_changed(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Moved Shelves", tmdb_id=930030)
    item = await _a_disc(api_session, movie, section="Front", shelf="2nd")

    response = await client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(location="Back 6th shelf", notes="Moved when the shelf was rebuilt"),
    )

    assert response.status_code == 200, response.text
    assert response.json()["section"] == "Back"
    assert response.json()["shelf"] == "6th"

    # Persisted, not merely echoed.
    reread = await client.get(f"/api/v1/movies/{movie.id}/copies")
    assert reread.json()[0]["section"] == "Back"
    assert reread.json()[0]["notes"] == "Moved when the shelf was rebuilt"

    entries = await _audit_rows(api_session, item.id)
    assert [entry.action_type for entry in entries] == ["update"]
    assert entries[0].changes is not None
    assert set(entries[0].changes) == {"location", "section", "shelf", "notes"}
    assert entries[0].changes["section"] == {"from": "Front", "to": "Back"}


async def test_an_edit_that_changes_nothing_writes_no_audit_row(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Untouched", tmdb_id=930031)
    item = await _a_disc(api_session, movie)

    response = await client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(location="Front 2nd shelf", formats=["blu_ray"], condition="good"),
    )

    assert response.status_code == 200, response.text
    assert await _audit_rows(api_session, item.id) == []


async def test_the_audit_entry_names_the_actor(
    client: AsyncClient,
    api_session: AsyncSession,
    admin: Profile,
) -> None:
    movie = await _a_film(api_session, title="Who Did This", tmdb_id=930032)
    created = await client.post("/api/v1/collection", json=_body(movieId=str(movie.id)))

    log = await client.get(
        "/api/v1/admin/audit",
        params={"targetId": created.json()["id"], "targetTable": "collection_items"},
    )

    assert log.status_code == 200
    entry = log.json()["items"][0]
    assert entry["actorId"] == str(admin.id)
    assert entry["actorName"] == admin.display_name
    assert entry["actionType"] == "create"
    assert entry["targetTable"] == "collection_items"


async def test_a_deleted_disc_leaves_the_collection_and_appears_in_the_trash(
    client: AsyncClient,
    viewer_client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Thrown Away", tmdb_id=930033)
    item = await _a_disc(api_session, movie)

    deleted = await client.delete(f"/api/v1/collection/{item.id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deletedAt"] is not None

    assert (await viewer_client.get(f"/api/v1/movies/{movie.id}/copies")).json() == []

    trash = await client.get("/api/v1/trash")
    assert trash.status_code == 200
    assert str(item.id) in [row["id"] for row in trash.json()["items"]]

    entries = await _audit_rows(api_session, item.id)
    assert [entry.action_type for entry in entries] == ["delete"]


async def test_restoring_brings_the_disc_back_with_full_state(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Restored", tmdb_id=930034)
    item = await _a_disc(api_session, movie, formats=["4k_uhd"], section="Lounge", shelf=None)
    await client.delete(f"/api/v1/collection/{item.id}")

    restored = await client.post(f"/api/v1/trash/collection_items/{item.id}/restore")

    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["deletedAt"] is None
    assert body["formats"] == ["4k_uhd"]
    assert body["section"] == "Lounge"

    assert (await client.get("/api/v1/trash")).json()["total"] == 0
    assert len((await client.get(f"/api/v1/movies/{movie.id}/copies")).json()) == 1

    entries = await _audit_rows(api_session, item.id)
    assert [entry.action_type for entry in entries] == ["delete", "restore"]


async def test_trash_rejects_a_table_this_batch_does_not_serve(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/trash", params={"table": "movies"})).status_code == 422
    assert (await client.post(f"/api/v1/trash/movies/{uuid.uuid4()}/restore")).status_code == 422


async def test_deleting_a_live_disc_twice_is_a_404(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Gone Once", tmdb_id=930035)
    item = await _a_disc(api_session, movie)

    assert (await client.delete(f"/api/v1/collection/{item.id}")).status_code == 200
    assert (await client.delete(f"/api/v1/collection/{item.id}")).status_code == 404
    # ...and a live item is not restorable, which is the same guard from the other side.
    await client.post(f"/api/v1/trash/collection_items/{item.id}/restore")
    assert (
        await client.post(f"/api/v1/trash/collection_items/{item.id}/restore")
    ).status_code == 404


# ---------------------------------------------------------------------------
# `DECISIONS.md` #5 — the log survives deletion of the target row
# ---------------------------------------------------------------------------


async def test_an_audit_entry_survives_a_hard_delete_of_its_target(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The criterion #5 exists for, proved by actually destroying the row.

    A plain ``DELETE`` cannot do it: ``collection_items_soft_delete`` rewrites one into
    an update of ``deleted_at``. The trigger is disabled for the length of the statement
    so the row is genuinely gone, which is the only way to show that nothing in
    ``admin_actions`` was blocking the delete or riding a cascade out with it.
    """
    movie = await _a_film(api_session, title="Erased", tmdb_id=930040)
    created = await client.post("/api/v1/collection", json=_body(movieId=str(movie.id)))
    item_id = uuid.UUID(created.json()["id"])
    assert len(await _audit_rows(api_session, item_id)) == 1

    await api_session.execute(
        text("ALTER TABLE collection_items DISABLE TRIGGER collection_items_soft_delete")
    )
    await api_session.execute(text("DELETE FROM collection_items WHERE id = :id"), {"id": item_id})
    await api_session.execute(
        text("ALTER TABLE collection_items ENABLE TRIGGER collection_items_soft_delete")
    )

    gone = await api_session.get(CollectionItem, item_id)
    assert gone is None

    survivors = await _audit_rows(api_session, item_id)
    assert len(survivors) == 1
    assert survivors[0].action_type == "create"
    assert survivors[0].target_id == str(item_id)

    # Still readable through the API, not merely present in the table.
    log = await client.get("/api/v1/admin/audit", params={"targetId": str(item_id)})
    assert log.json()["total"] == 1


# ---------------------------------------------------------------------------
# §3.11 — Marking a disc as damaged updates the UI and logs the change
# ---------------------------------------------------------------------------


async def test_marking_a_disc_damaged_stamps_the_time_and_logs_it(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Scratched", tmdb_id=930050)
    item = await _a_disc(api_session, movie, condition="good")

    response = await client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(
            condition="damaged",
            hasPlaybackIssues=True,
            playbackNotes="Freezes about an hour in",
        ),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["condition"] == "damaged"
    assert body["conditionUpdatedAt"] is not None
    assert body["hasPlaybackIssues"] is True

    entries = await _audit_rows(api_session, item.id)
    assert entries[0].changes is not None
    assert entries[0].changes["condition"] == {"from": "good", "to": "damaged"}
    assert entries[0].changes["has_playback_issues"] == {"from": False, "to": True}


async def test_the_condition_timestamp_only_moves_when_the_condition_does(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Same Condition", tmdb_id=930051)
    item = await _a_disc(api_session, movie, condition="good")

    first = await client.put(f"/api/v1/collection/{item.id}", json=_body(condition="acceptable"))
    stamped = first.json()["conditionUpdatedAt"]
    assert stamped is not None

    second = await client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(condition="acceptable", notes="Only the note moved"),
    )
    assert second.json()["conditionUpdatedAt"] == stamped


async def test_condition_history_covers_every_disc_of_a_film_including_deleted_ones(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """§3.11's "condition history visible on detail page", which is per film, not per disc."""
    movie = await _a_film(api_session, title="Two Copies", tmdb_id=930052)
    first = await _a_disc(api_session, movie, formats=["dvd"])
    second = await _a_disc(api_session, movie, formats=["blu_ray"])

    await client.put(f"/api/v1/collection/{first.id}", json=_body(condition="damaged"))
    await client.put(
        f"/api/v1/collection/{second.id}", json=_body(formats=["blu_ray"], condition="new")
    )
    await client.delete(f"/api/v1/collection/{second.id}")

    history = await client.get("/api/v1/admin/audit", params={"movieId": str(movie.id)})

    assert history.status_code == 200
    body = history.json()
    assert body["total"] == 3
    assert {row["targetId"] for row in body["items"]} == {str(first.id), str(second.id)}
    assert [row["actionType"] for row in body["items"]][0] == "delete"  # newest first


async def test_audit_history_for_a_film_with_no_discs_is_empty(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="No Discs", tmdb_id=930053)
    response = await client.get("/api/v1/admin/audit", params={"movieId": str(movie.id)})
    assert response.status_code == 200
    assert response.json()["total"] == 0


# ---------------------------------------------------------------------------
# Location, formats and the derived-field triggers
# ---------------------------------------------------------------------------


async def test_a_typed_location_is_filed_by_the_same_rules_as_an_imported_one(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """Including `STATUS.md` gotcha 17 — a bare digit in a box-set title is not a shelf."""
    movie = await _a_film(api_session, title="Boxed Set", tmdb_id=930060)

    response = await client.post(
        "/api/v1/collection",
        json=_body(
            movieId=str(movie.id),
            location="Top small cabinet (Arrow 4 Film Noir Classics Vol 2)",
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["section"] == "Top Small Cabinet"
    assert response.json()["shelf"] is None


async def test_explicit_pickers_win_over_the_typed_text(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Picker Wins", tmdb_id=930061)

    response = await client.post(
        "/api/v1/collection",
        json=_body(movieId=str(movie.id), location=None, section="Back", shelf="3rd"),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["section"], body["shelf"]) == ("Back", "3rd")
    # `location` is composed rather than left empty — every other surface falls back to it.
    assert body["location"] == "Back 3rd shelf"


async def test_a_new_shelf_replaces_text_that_still_names_the_old_one(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """Mark's 12 Angry Men, 13 Oct: the shelf changed, the text did not, and the film page
    showed both. An older app on a phone still sends the old text, so the API fixes it."""
    movie = await _a_film(api_session, title="Twelve Shelves", tmdb_id=930350)
    item = await _a_disc(api_session, movie, section="Front", shelf="3rd")

    response = await client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(location="Front 3rd shelf", section="Front", shelf="4th"),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["section"], body["shelf"]) == ("Front", "4th")
    assert body["location"] == "Front 4th shelf"


async def test_text_that_names_the_same_place_is_kept_as_written(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The imported "Front 4th Shelf", capital S, still names Front 4th: left alone."""
    movie = await _a_film(api_session, title="Kept As Written", tmdb_id=930351)
    item = await _a_disc(api_session, movie, section="Front", shelf="4th")

    response = await client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(location="Front 4th Shelf", section="Front", shelf="4th"),
    )

    assert response.status_code == 200, response.text
    assert response.json()["location"] == "Front 4th Shelf"


async def test_a_disc_can_be_moved_to_craigs_house_from_the_picker(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """Batch V4. Through the API to Postgres, so the CHECK is the one that allows it."""
    movie = await _a_film(api_session, title="Lent Long Term", tmdb_id=930063)

    response = await client.post(
        "/api/v1/collection",
        json=_body(movieId=str(movie.id), section="Craig's house", shelf=None, location=None),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["section"], body["shelf"]) == ("Craig's house", None)
    assert body["location"] == "Craig's house"


@pytest.mark.parametrize("typed", ["Craigs house", "Craig\u2019s house"])
async def test_typing_craigs_house_files_the_disc_there(
    client: AsyncClient,
    api_session: AsyncSession,
    typed: str,
) -> None:
    movie = await _a_film(api_session, title=f"Typed {typed}", tmdb_id=None)

    response = await client.post(
        "/api/v1/collection",
        json=_body(movieId=str(movie.id), location=typed, section=None, shelf=None),
    )

    assert response.status_code == 201, response.text
    assert response.json()["section"] == "Craig's house"
    assert response.json()["location"] == typed


async def test_an_unknown_section_is_refused_before_it_reaches_the_check_constraint(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Nowhere", tmdb_id=930062)
    response = await client.post(
        "/api/v1/collection",
        json=_body(movieId=str(movie.id), section="Attic", shelf=None, location=None),
    )
    assert response.status_code == 422
    assert "Unknown section" in response.json()["detail"]


async def test_an_unknown_or_repeated_format_is_refused(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """An unrecognised code does not error in the trigger — it silently ranks 99."""
    movie = await _a_film(api_session, title="Laserdisc", tmdb_id=930063)
    unknown = await client.post(
        "/api/v1/collection", json=_body(movieId=str(movie.id), formats=["laserdisc"])
    )
    repeated = await client.post(
        "/api/v1/collection", json=_body(movieId=str(movie.id), formats=["dvd", "dvd"])
    )
    empty = await client.post("/api/v1/collection", json=_body(movieId=str(movie.id), formats=[]))
    assert unknown.status_code == 422
    assert repeated.status_code == 422
    assert empty.status_code == 422


async def test_a_future_purchase_date_is_refused(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Not Yet Bought", tmdb_id=930064)
    response = await client.post(
        "/api/v1/collection",
        json=_body(movieId=str(movie.id), purchaseDate=str(date(2999, 1, 1))),
    )
    assert response.status_code == 422


async def test_adding_and_deleting_a_disc_moves_the_films_best_format_owned(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The write surface has to keep the Batch 4 triggers correct, not just the rows."""
    movie = await _a_film(api_session, title="Format Ladder", tmdb_id=930070)
    await _a_disc(api_session, movie, formats=["dvd"])
    await api_session.refresh(movie)
    assert movie.best_format_owned == "dvd"

    added = await client.post(
        "/api/v1/collection",
        json=_body(movieId=str(movie.id), formats=["4k_uhd"], confirmDuplicate="upgrade"),
    )
    await api_session.refresh(movie)
    assert movie.best_format_owned == "4k_uhd"

    await client.delete(f"/api/v1/collection/{added.json()['id']}")
    await api_session.refresh(movie)
    assert movie.best_format_owned == "dvd"

    await client.post(f"/api/v1/trash/collection_items/{added.json()['id']}/restore")
    await api_session.refresh(movie)
    assert movie.best_format_owned == "4k_uhd"


async def test_purchase_price_survives_the_round_trip_as_written(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """A price is money, so it must not come back as a binary float."""
    movie = await _a_film(api_session, title="Priced", tmdb_id=930071)
    created = await client.post(
        "/api/v1/collection", json=_body(movieId=str(movie.id), purchasePrice="19.99")
    )

    assert created.json()["purchasePrice"] == "19.99"
    item = await api_session.get(CollectionItem, uuid.UUID(created.json()["id"]))
    assert item is not None
    assert item.purchase_price == Decimal("19.99")


# ---------------------------------------------------------------------------
# §3.1's movie search
# ---------------------------------------------------------------------------


async def test_tmdb_search_flags_films_the_catalogue_already_has(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    response = await client.get("/api/v1/tmdb/search", params={"q": "newly bought"})
    assert response.status_code == 200
    assert response.json()["results"][0]["inCollection"] is False
    assert response.json()["results"][0]["movieId"] is None

    known = await _a_film(api_session, title="A Newly Bought Film", tmdb_id=NEW_TMDB_ID)

    again = await client.get("/api/v1/tmdb/search", params={"q": "newly bought"})
    result = again.json()["results"][0]
    assert result["inCollection"] is True
    assert result["movieId"] == str(known.id)


# ---------------------------------------------------------------------------
# Batch 8 — an offline edit must not overwrite a newer change
# ---------------------------------------------------------------------------


async def test_a_stale_edit_is_refused_and_shows_what_it_would_have_overwritten(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The criterion phase 13.9's "last-write-wins" would have failed.

    An edit queued offline carries the ``updatedAt`` it was based on. If the disc has
    moved on since — someone else edited it, or the same person did from another device —
    flushing the queue must not silently win.
    """
    movie = await _a_film(api_session, title="Edited Twice", tmdb_id=930080)
    item = await _a_disc(api_session, movie, section="Front", shelf="2nd")

    original = (await client.get(f"/api/v1/movies/{movie.id}/copies")).json()[0]
    stale_base = original["updatedAt"]

    # Someone else moves the disc while our edit sits in the queue.
    moved = await client.put(f"/api/v1/collection/{item.id}", json=_body(location="Back 6th shelf"))
    assert moved.status_code == 200, moved.text

    late = await client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(location="Lounge", baseUpdatedAt=stale_base),
    )

    assert late.status_code == 409
    detail = late.json()["detail"]
    assert detail["code"] == "STALE_EDIT"
    # The response carries the row it refused to clobber, so the client can say what
    # the newer change actually was rather than only that the flush failed.
    assert detail["current"]["section"] == "Back"

    still = (await client.get(f"/api/v1/movies/{movie.id}/copies")).json()[0]
    assert still["section"] == "Back"


async def test_an_edit_based_on_the_current_version_is_accepted(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The queue's happy path: nothing else touched the disc, so the edit lands."""
    movie = await _a_film(api_session, title="Edited Once", tmdb_id=930081)
    item = await _a_disc(api_session, movie)

    current = (await client.get(f"/api/v1/movies/{movie.id}/copies")).json()[0]

    response = await client.put(
        f"/api/v1/collection/{item.id}",
        json=_body(
            location="Lounge", section="Lounge", shelf=None, baseUpdatedAt=current["updatedAt"]
        ),
    )

    assert response.status_code == 200, response.text
    assert response.json()["section"] == "Lounge"
    # And the version moved, so replaying the same queued edit would now be refused.
    assert response.json()["updatedAt"] != current["updatedAt"]


async def test_an_edit_with_no_base_version_still_works(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """``baseUpdatedAt`` is optional — an online edit that just read the row needs no guard."""
    movie = await _a_film(api_session, title="No Base", tmdb_id=930082)
    item = await _a_disc(api_session, movie)

    response = await client.put(f"/api/v1/collection/{item.id}", json=_body(notes="Fine"))

    assert response.status_code == 200, response.text
    assert response.json()["notes"] == "Fine"


async def test_an_edit_advances_the_version_within_one_transaction(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The property the stale-edit guard rests on.

    ``NOW()`` is the *transaction* start time in Postgres, so the trigger used to stamp
    an identical ``updated_at`` however many times a row was updated — and a concurrency
    token that does not advance cannot detect anything. Migration ``009`` moves it to
    ``clock_timestamp()``. This test is written deliberately inside one transaction,
    because that is where the old behaviour was indistinguishable from working.
    """
    movie = await _a_film(api_session, title="Versioned", tmdb_id=930084)
    item = await _a_disc(api_session, movie)

    first = await client.put(f"/api/v1/collection/{item.id}", json=_body(notes="One"))
    second = await client.put(f"/api/v1/collection/{item.id}", json=_body(notes="Two"))

    assert first.json()["updatedAt"] < second.json()["updatedAt"]


async def test_the_wire_timestamp_round_trips_exactly(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """Microseconds included.

    The conflict check compares an inbound string against a Postgres timestamp. If the
    serialisation lost precision, an edit based on the current version would read as
    stale — or worse, a genuinely stale one would read as current.
    """
    movie = await _a_film(api_session, title="Precise", tmdb_id=930083)
    item = await _a_disc(api_session, movie)

    seen = (await client.get(f"/api/v1/movies/{movie.id}/copies")).json()[0]["updatedAt"]
    assert seen.endswith("Z")

    accepted = await client.put(
        f"/api/v1/collection/{item.id}", json=_body(notes="Round trip", baseUpdatedAt=seen)
    )
    assert accepted.status_code == 200, accepted.text


async def test_a_purchase_date_of_today_is_accepted_from_a_timezone_ahead_of_utc(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The same local-timezone defect the watch log carried, on the same day's fix.

    Both guards asked ``date.today()``, which reads the server's timezone. A disc bought
    this evening and catalogued just after midnight in London is dated the 9th while UTC
    still says the 8th; refusing it would be the app arguing with the person's calendar.
    """
    movie = await _a_film(api_session, title="A Disc Bought Tonight", tmdb_id=930_777)

    response = await client.post(
        "/api/v1/collection",
        json=_body(
            movieId=str(movie.id),
            purchaseDate=(datetime.now(UTC).date() + timedelta(days=1)).isoformat(),
        ),
    )

    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# Batch 29 — §4.2 format upgrade, §4.4 listing status
# ---------------------------------------------------------------------------


class TestListingStatus:
    """§4.4: *"Marking sold removes from active views, remains in audit/trash"*.

    Every assertion here is against the **HTTP surface**, because "active views" is a
    property of what the endpoints return rather than of a predicate in isolation —
    `test_listing_status.py` covers the predicate.
    """

    async def test_listing_a_disc_for_sale_leaves_it_in_the_collection(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """§4.2 marks the old disc `listed_for_sale`, and it must stay on the shelf.

        Hiding it at the moment of listing would make "I advertised it" and "I lost it"
        look identical, and the disc is still in the house until somebody buys it.
        """
        movie = await _a_film(api_session, title="An Upgraded Film", tmdb_id=930101)
        disc = await _a_disc(api_session, movie, formats=["blu_ray"])

        response = await client.put(
            f"/api/v1/collection/{disc.id}/listing",
            json={"status": "listed_for_sale", "listingPrice": "9.99"},
        )
        assert response.status_code == 200
        assert response.json()["listingStatus"] == "listed_for_sale"
        assert response.json()["listingPrice"] == "9.99"

        copies = await client.get(f"/api/v1/movies/{movie.id}/copies")
        assert [copy["id"] for copy in copies.json()] == [str(disc.id)]

    async def test_marking_sold_removes_it_from_every_active_view(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """The criterion itself, checked across the surfaces that mean "what I own"."""
        movie = await _a_film(api_session, title="A Sold Film", tmdb_id=930102)
        disc = await _a_disc(api_session, movie, formats=["blu_ray"])

        before = await client.get(f"/api/v1/movies/{movie.id}")
        assert before.json()["copyCount"] == 1

        sold = await client.put(
            f"/api/v1/collection/{disc.id}/listing",
            json={"status": "sold", "listingPrice": "12.50"},
        )
        assert sold.status_code == 200

        # The film's own page: no owned copies, and the count agrees with the list.
        copies = await client.get(f"/api/v1/movies/{movie.id}/copies")
        assert copies.json() == []
        detail = await client.get(f"/api/v1/movies/{movie.id}")
        assert detail.json()["copyCount"] == 0

        # And the film drops out of the browse list, which filters on owning a disc.
        listing = await client.get("/api/v1/movies", params={"q": "A Sold Film"})
        assert str(movie.id) not in [row["id"] for row in listing.json()["items"]]

    async def test_a_sold_disc_is_still_reachable_and_still_knows_what_it_fetched(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """ "Removes from active views" must not mean "unreachable".

        `includeSold` is the one surface allowed to show it — and the row is **not**
        soft-deleted, which matters in ninety days: §6.30 auto-purges the trash, so a
        sold disc routed through `deleted_at` would be permanently destroyed a quarter
        later along with the record of the sale.
        """
        movie = await _a_film(api_session, title="A Recorded Sale", tmdb_id=930103)
        disc = await _a_disc(api_session, movie, formats=["blu_ray"])
        await client.put(
            f"/api/v1/collection/{disc.id}/listing",
            json={"status": "sold", "listingPrice": "12.50"},
        )

        with_sold = await client.get(
            f"/api/v1/movies/{movie.id}/copies", params={"includeSold": "true"}
        )
        rows = with_sold.json()
        assert [row["id"] for row in rows] == [str(disc.id)]
        assert rows[0]["listingStatus"] == "sold"
        assert rows[0]["listingPrice"] == "12.50"

        stored = await api_session.get(CollectionItem, disc.id)
        assert stored is not None
        assert stored.deleted_at is None, "a sale is not a deletion"

    async def test_the_transition_is_written_to_the_audit_log(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """ "Remains in audit" — §13.6's log is where a sold disc stays visible."""
        movie = await _a_film(api_session, title="An Audited Sale", tmdb_id=930104)
        disc = await _a_disc(api_session, movie, formats=["blu_ray"])

        await client.put(
            f"/api/v1/collection/{disc.id}/listing", json={"status": "listed_for_sale"}
        )
        await client.put(f"/api/v1/collection/{disc.id}/listing", json={"status": "sold"})

        entries = (
            (
                await api_session.execute(
                    select(AdminAction)
                    .where(AdminAction.target_id == str(disc.id))
                    .order_by(AdminAction.created_at)
                )
            )
            .scalars()
            .all()
        )
        # `update`, not a bespoke `listing_sold`: §3.20's action vocabulary is a closed
        # CHECK, and widening it is its own decision. The transition is legible in the
        # diff, which is what the audit page renders.
        assert [entry.action_type for entry in entries] == ["update", "update"]

        moves = [(entry.changes or {}).get("listing_status", {}) for entry in entries]
        assert moves[0] == {"from": "in_collection", "to": "listed_for_sale"}
        assert moves[1] == {"from": "listed_for_sale", "to": "sold"}

        # The row also reads as a sentence on its own rather than needing the one before
        # it to be understood.
        assert (entries[1].changes or {})["previous_listing_status"] == "listed_for_sale"

    async def test_putting_a_disc_back_clears_the_advert(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """A live link to a dead listing outliving the sale it described is the failure
        this prevents."""
        movie = await _a_film(api_session, title="A Withdrawn Listing", tmdb_id=930105)
        disc = await _a_disc(api_session, movie, formats=["blu_ray"])

        await client.put(
            f"/api/v1/collection/{disc.id}/listing",
            json={
                "status": "listed_for_sale",
                "listingPrice": "9.99",
                "ebayListingUrl": "https://www.ebay.co.uk/itm/123",
            },
        )
        back = await client.put(
            f"/api/v1/collection/{disc.id}/listing", json={"status": "in_collection"}
        )

        assert back.json()["listingStatus"] == "in_collection"
        assert back.json()["ebayListingUrl"] is None
        assert back.json()["listingPrice"] is None

    async def test_a_sold_disc_is_no_longer_a_duplicate(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """You cannot own two of something you have sold one of.

        This is the same rule as the views, reaching the place it matters most: §3.5's
        prompt would otherwise warn about a clash with a disc that is in someone else's
        house.
        """
        movie = await _a_film(api_session, title="A Replaced Film", tmdb_id=930106)
        disc = await _a_disc(api_session, movie, formats=["blu_ray"])

        clash = await client.get(
            "/api/v1/collection/duplicate-check",
            params={"movieId": str(movie.id), "format": "blu_ray"},
        )
        assert clash.json()["isDuplicate"] is True

        await client.put(f"/api/v1/collection/{disc.id}/listing", json={"status": "sold"})

        after = await client.get(
            "/api/v1/collection/duplicate-check",
            params={"movieId": str(movie.id), "format": "blu_ray"},
        )
        assert after.json()["isDuplicate"] is False

    async def test_a_viewer_can_list_a_superseded_disc_for_sale(
        self, viewer_client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """**Batch S4 moved this, and it was not in the criterion's list.**

        `DECISIONS.md` #155 names `/collection/add` and the two eBay endpoints. Following
        the *button* rather than the criterion found a third: "List for sale" prices via
        eBay and then lands here, so with this left admin-only Mark would have seen the
        upgrade prompt, fetched the price, pressed the button and got a 403 — the precise
        failure #155 calls worse than no change at all.

        This used to assert 403 under the name "a viewer cannot sell a disc". The word
        *sell* was doing too much work: it is one endpoint covering both "I have listed
        this" and "this is gone", and the first is half of the flow snag 7 is about.
        """
        movie = await _a_film(api_session, title="Marks To List", tmdb_id=930107)
        disc = await _a_disc(api_session, movie, formats=["blu_ray"])

        response = await viewer_client.put(
            f"/api/v1/collection/{disc.id}/listing",
            json={"status": "listed_for_sale", "listingPrice": "12.99"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["listingStatus"] == "listed_for_sale"

    async def test_an_unknown_status_is_refused_before_it_reaches_the_check_constraint(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        movie = await _a_film(api_session, title="A Bad Transition", tmdb_id=930108)
        disc = await _a_disc(api_session, movie, formats=["blu_ray"])

        response = await client.put(
            f"/api/v1/collection/{disc.id}/listing", json={"status": "lost_in_a_move"}
        )
        assert response.status_code == 422


class TestUpgradePath:
    """§4.2: *"Upgrade path completes in ≤ 3 taps; old item marked `listed_for_sale`"*."""

    async def test_the_upgrade_path_is_three_requests_and_the_old_disc_ends_up_listed(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """The criterion counts *taps*, which the API can only bound from below: a flow
        that needs four requests cannot be done in three taps.

        The three are: confirm the upgrade on the add form, save the new disc, list the
        old one. There is no fourth — in particular, listing the old disc does not need a
        separate "fetch a price" round trip, because §4.1's estimate is what pre-fills the
        number and the admin either accepts it or types over it.
        """
        movie = await _a_film(api_session, title="An Upgrade In Three", tmdb_id=930109)
        old = await _a_disc(api_session, movie, formats=["blu_ray"])

        # 1 + 2: the duplicate prompt answers "it's an upgrade", and the disc is saved.
        added = await client.post(
            "/api/v1/collection",
            json={
                **_body(formats=["4k_uhd"]),
                "movieId": str(movie.id),
                "confirmDuplicate": "upgrade",
            },
        )
        assert added.status_code == 201

        # 3: the old disc goes up for sale at the suggested price.
        listed = await client.put(
            f"/api/v1/collection/{old.id}/listing",
            json={"status": "listed_for_sale", "listingPrice": "9.99"},
        )
        assert listed.status_code == 200
        assert listed.json()["listingStatus"] == "listed_for_sale"

        # Both discs are still owned — the upgrade has not happened until it sells.
        copies = await client.get(f"/api/v1/movies/{movie.id}/copies")
        statuses = {row["id"]: row["listingStatus"] for row in copies.json()}
        assert statuses[str(old.id)] == "listed_for_sale"
        assert statuses[added.json()["id"]] == "in_collection"

    async def test_the_reason_a_second_copy_was_allowed_is_still_recorded(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """Batch 7 wrote `duplicate_reason` into the audit *for this batch* — "upgrade is
        the input phase 4.2's sale tracking will want, and it is unrecoverable if only the
        click knew". This asserts the debt was actually paid."""
        movie = await _a_film(api_session, title="A Recorded Upgrade", tmdb_id=930110)
        await _a_disc(api_session, movie, formats=["blu_ray"])

        added = await client.post(
            "/api/v1/collection",
            json={
                **_body(formats=["4k_uhd"]),
                "movieId": str(movie.id),
                "confirmDuplicate": "upgrade",
            },
        )
        entry = (
            await api_session.execute(
                select(AdminAction).where(AdminAction.target_id == added.json()["id"])
            )
        ).scalar_one()
        assert entry.changes is not None
        assert entry.changes["duplicate_reason"] == "upgrade"


# ---------------------------------------------------------------------------
# Batch U2 — each copy's edition, set and corrected on the copy form
# ---------------------------------------------------------------------------


class TestEdition:
    async def test_a_disc_is_added_with_its_edition_and_the_copy_shows_it(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        movie = await _a_film(api_session, title="A SteelBook", tmdb_id=930201)

        created = await client.post(
            "/api/v1/collection",
            json=_body(movieId=str(movie.id), edition="  Zavvi Exclusive SteelBook  "),
        )

        assert created.status_code == 201, created.text
        assert created.json()["edition"] == "Zavvi Exclusive SteelBook"
        copies = await client.get(f"/api/v1/movies/{movie.id}/copies")
        assert copies.json()[0]["edition"] == "Zavvi Exclusive SteelBook"

    async def test_an_edition_is_corrected_and_cleared_and_each_change_is_logged(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        movie = await _a_film(api_session, title="A Corrected Edition", tmdb_id=930202)
        item = await _a_disc(api_session, movie)
        item.edition = "SteelBook"
        await api_session.flush()
        item_id = item.id

        corrected = await client.put(
            f"/api/v1/collection/{item_id}", json=_body(edition="Masters of Cinema")
        )
        cleared = await client.put(f"/api/v1/collection/{item_id}", json=_body(edition="   "))

        assert corrected.json()["edition"] == "Masters of Cinema"
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["edition"] is None
        changes = [entry.changes for entry in await _audit_rows(api_session, item_id)]
        assert changes == [
            {"edition": {"from": "SteelBook", "to": "Masters of Cinema"}},
            {"edition": {"from": "Masters of Cinema", "to": None}},
        ]

    async def test_an_edit_from_a_client_that_never_knew_editions_keeps_one(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """A cached app or an edit queued offline sends no `edition`; that is not "cleared"."""
        movie = await _a_film(api_session, title="An Older Client", tmdb_id=930203)
        item = await _a_disc(api_session, movie)
        item.edition = "Indicator Series"
        await api_session.flush()

        response = await client.put(
            f"/api/v1/collection/{item.id}", json=_body(notes="Edited on an old build")
        )

        assert response.status_code == 200, response.text
        assert response.json()["edition"] == "Indicator Series"
        assert response.json()["notes"] == "Edited on an old build"

    async def test_an_edition_longer_than_the_column_is_refused(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        movie = await _a_film(api_session, title="A Long Edition", tmdb_id=930204)

        response = await client.post(
            "/api/v1/collection", json=_body(movieId=str(movie.id), edition="x" * 101)
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Batch Y2 — moving many discs at once (`DECISIONS.md` #265)
# ---------------------------------------------------------------------------


async def _version(http: AsyncClient, movie: Movie) -> str:
    """The ``updatedAt`` a tray would hold for the film's only disc."""
    return str((await http.get(f"/api/v1/movies/{movie.id}/copies")).json()[0]["updatedAt"])


def _move(item: CollectionItem, base: str, **place: Any) -> dict[str, Any]:
    return {"itemId": str(item.id), "baseUpdatedAt": base, **place}


async def test_a_viewer_moves_discs_from_anywhere_to_one_place(
    viewer_client: AsyncClient,
    api_session: AsyncSession,
    viewer: Profile,
) -> None:
    """Y2's whole point: discs from different places, one request, one destination."""
    first = await _a_film(api_session, title="Moved From Front", tmdb_id=930301)
    second = await _a_film(api_session, title="Moved From Lounge", tmdb_id=930302)
    a = await _a_disc(api_session, first, section="Front", shelf="2nd")
    b = await _a_disc(api_session, second, section="Lounge", shelf=None)

    response = await viewer_client.post(
        "/api/v1/collection/move",
        json={
            "moves": [
                _move(a, await _version(viewer_client, first), section="Back", shelf="Top"),
                _move(b, await _version(viewer_client, second), section="Back", shelf="Top"),
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["moved"] == 2
    assert [result["status"] for result in body["results"]] == ["moved", "moved"]
    for result in body["results"]:
        assert (result["item"]["section"], result["item"]["shelf"]) == ("Back", "Top")
        assert result["item"]["location"] == "Back Top shelf"

    for disc, was in ((a, "Front"), (b, "Lounge")):
        entries = await _audit_rows(api_session, disc.id)
        assert [(entry.action_type, entry.user_id) for entry in entries] == [("update", viewer.id)]
        assert entries[0].changes["section"] == {"from": was, "to": "Back"}


async def test_one_stale_or_missing_disc_does_not_stop_the_rest(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """Partial success, each case on its own: moved, unchanged, stale, deleted, unknown."""
    films = [await _a_film(api_session, title=f"Partial {n}", tmdb_id=930310 + n) for n in range(4)]
    to_move = await _a_disc(api_session, films[0], section="Front", shelf="1st")
    already = await _a_disc(api_session, films[1], section="Back", shelf="Top")
    changed = await _a_disc(api_session, films[2], section="Front", shelf="1st")
    gone = await _a_disc(api_session, films[3], section="Front", shelf="1st")
    bases = [await _version(client, film) for film in films]

    # The other phone edits one disc after it was picked, and deletes another.
    edited = await client.put(f"/api/v1/collection/{changed.id}", json=_body(location="Lounge"))
    assert edited.status_code == 200, edited.text
    assert (await client.delete(f"/api/v1/collection/{gone.id}")).status_code == 200
    unknown = uuid.uuid4()

    place = {"section": "Back", "shelf": "Top"}
    response = await client.post(
        "/api/v1/collection/move",
        json={
            "moves": [
                _move(to_move, bases[0], **place),
                _move(already, bases[1], **place),
                _move(changed, bases[2], **place),
                _move(gone, bases[3], **place),
                {"itemId": str(unknown), "baseUpdatedAt": bases[0], **place},
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["moved"] == 1
    assert [result["status"] for result in body["results"]] == [
        "moved",
        "unchanged",
        "stale",
        "not_found",
        "not_found",
    ]
    # A stale disc reports where it actually is, so the screen can say so.
    assert body["results"][2]["item"]["section"] == "Lounge"
    assert body["results"][3]["item"] is None
    # Nothing was written for the disc already there, or the one changed elsewhere.
    assert [entry.action_type for entry in await _audit_rows(api_session, already.id)] == []
    assert [entry.action_type for entry in await _audit_rows(api_session, changed.id)] == ["update"]
    still = (await client.get(f"/api/v1/movies/{films[2].id}/copies")).json()[0]
    assert still["section"] == "Lounge"


async def test_move_them_back_restores_each_disc_exactly(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """The undo is the same endpoint with each disc's own previous place.

    One disc has only free text and no section — the two the importer could not file —
    so "exactly" includes the text, not just the section and shelf.
    """
    first = await _a_film(api_session, title="Undo Filed", tmdb_id=930320)
    second = await _a_film(api_session, title="Undo Unfiled", tmdb_id=930321)
    filed = await _a_disc(api_session, first, section="Front", shelf="2nd")
    unfiled = await _a_disc(api_session, second, section=None, shelf=None)
    unfiled.location = "In the car"
    await api_session.flush()

    before = {
        disc.id: (await client.get(f"/api/v1/movies/{film.id}/copies")).json()[0]
        for disc, film in ((filed, first), (unfiled, second))
    }
    forward = await client.post(
        "/api/v1/collection/move",
        json={
            "moves": [
                _move(disc, before[disc.id]["updatedAt"], section="Craig's house", shelf=None)
                for disc in (filed, unfiled)
            ]
        },
    )
    assert forward.json()["moved"] == 2, forward.text
    after = {result["itemId"]: result["item"] for result in forward.json()["results"]}

    back = await client.post(
        "/api/v1/collection/move",
        json={
            "moves": [
                _move(
                    disc,
                    after[str(disc.id)]["updatedAt"],
                    location=before[disc.id]["location"],
                    section=before[disc.id]["section"],
                    shelf=before[disc.id]["shelf"],
                )
                for disc in (filed, unfiled)
            ]
        },
    )

    assert back.json()["moved"] == 2, back.text
    for result in back.json()["results"]:
        was = before[uuid.UUID(result["itemId"])]
        now = result["item"]
        assert (now["location"], now["section"], now["shelf"]) == (
            was["location"],
            was["section"],
            was["shelf"],
        )


async def test_an_unknown_section_refuses_the_whole_move(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    """Places are resolved before any write, so a bad one never leaves half a move."""
    first = await _a_film(api_session, title="Not Half Moved", tmdb_id=930330)
    second = await _a_film(api_session, title="Nowhere Real", tmdb_id=930331)
    good = await _a_disc(api_session, first, section="Front", shelf="2nd")
    bad = await _a_disc(api_session, second, section="Front", shelf="2nd")

    response = await client.post(
        "/api/v1/collection/move",
        json={
            "moves": [
                _move(good, await _version(client, first), section="Back", shelf="Top"),
                _move(bad, await _version(client, second), section="The Moon", shelf=None),
            ]
        },
    )

    assert response.status_code == 422
    assert (await client.get(f"/api/v1/movies/{first.id}/copies")).json()[0]["section"] == "Front"
    assert await _audit_rows(api_session, good.id) == []


async def test_a_move_names_each_disc_once_and_has_a_ceiling(
    client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Twice Over", tmdb_id=930340)
    item = await _a_disc(api_session, movie)
    base = await _version(client, movie)

    twice = await client.post(
        "/api/v1/collection/move",
        json={"moves": [_move(item, base, section="Back"), _move(item, base, section="Lounge")]},
    )
    assert twice.status_code == 422

    too_many = await client.post(
        "/api/v1/collection/move",
        json={
            "moves": [
                {"itemId": str(uuid.uuid4()), "baseUpdatedAt": base, "section": "Back"}
                for _ in range(201)
            ]
        },
    )
    assert too_many.status_code == 422
    assert (await client.post("/api/v1/collection/move", json={"moves": []})).status_code == 422
