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
from datetime import date
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

pytestmark = pytest.mark.asyncio

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
    """Mark's client. Reads everything; writes nothing."""
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
        json=_body(movieId=str(movie.id), purchasePrice="12.99", purchaseSource="Fopp"),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["movieId"] == str(movie.id)
    assert body["section"] == "Front"
    assert body["shelf"] == "2nd"
    assert body["locationLabel"] == "Front 2nd"
    assert body["purchasePrice"] == "12.99"

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


async def test_a_viewer_cannot_write(
    viewer_client: AsyncClient,
    api_session: AsyncSession,
) -> None:
    movie = await _a_film(api_session, title="Not Yours To Edit", tmdb_id=930011)
    item = await _a_disc(api_session, movie)

    assert (
        await viewer_client.post("/api/v1/collection", json=_body(movieId=str(movie.id)))
    ).status_code == 403
    assert (
        await viewer_client.put(f"/api/v1/collection/{item.id}", json=_body())
    ).status_code == 403
    assert (await viewer_client.delete(f"/api/v1/collection/{item.id}")).status_code == 403
    assert (await viewer_client.get("/api/v1/trash")).status_code == 403
    assert (await viewer_client.get("/api/v1/admin/audit")).status_code == 403


async def test_create_requires_exactly_one_film_reference(client: AsyncClient) -> None:
    neither = await client.post("/api/v1/collection", json=_body())
    both = await client.post(
        "/api/v1/collection", json=_body(movieId=str(uuid.uuid4()), tmdbId=NEW_TMDB_ID)
    )
    assert neither.status_code == 422
    assert both.status_code == 422


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
