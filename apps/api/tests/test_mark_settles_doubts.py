"""Mark settles identification doubts from the film page against Postgres — Batch Y4 (#276).
These run in CI.

**What this proves:** the Archive's "In doubt" filter lists exactly the identified films with
an open doubt, each list item says so and the facets count them; the film page lists every
open doubt with the copy it names and T9's proposal; Mark keeps one, audited as him, and
Craig sees it under Recently identified with Mark's name and undoes it, which opens the doubt
again, but not once the film has changed since; Mark searches TMDB and moves one copy,
audited as him; and the rest of Identify films still refuses him.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.routers.movies import get_tmdb_client
from src.services.identify.doubts import raise_doubt
from tests.test_identify_films import FakeTmdb, _disc, _film, _person, _record, _tmdb_ids


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@dataclass
class Desk:
    """The app as either person: requests go as ``user``, Mark unless a test says Craig."""

    client: AsyncClient
    craig: Profile
    mark: Profile
    tmdb: FakeTmdb
    user: list[Profile] = field(default_factory=list)

    def as_(self, person: Profile) -> None:
        self.user[:] = [person]


@pytest_asyncio.fixture
async def desk(db: AsyncSession) -> AsyncIterator[Desk]:
    craig = await _person(db)
    mark = await _person(db, UserRole.viewer)
    tmdb = FakeTmdb({})
    user: list[Profile] = [mark]

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        await db.refresh(user[0])
        return user[0]

    async def override_tmdb() -> AsyncIterator[FakeTmdb]:
        yield tmdb

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield Desk(client, craig, mark, tmdb, user)
    finally:
        app.dependency_overrides.clear()


async def _in_doubt(
    db: AsyncSession,
    title: str,
    year: int,
    *,
    note: str = "T9 cannot tell which film the sheet's title is.",
    evidence: list[str] | None = None,
    candidates: list[dict[str, object]] | None = None,
    proposed_tmdb_id: int | None = None,
) -> tuple[Movie, CollectionItem, IdentifyDoubt]:
    """A film the re-check doubts, with the Blu-ray the doubt names."""
    tmdb_id, _, _ = _tmdb_ids()
    film = await _film(db, title, tmdb_id=tmdb_id, year=year)
    disc = await _disc(db, film, "blu_ray", sub_category="Martin Scorsese", location="Front")
    raised = await raise_doubt(
        db,
        film,
        source="recheck",
        note=note,
        evidence=evidence or [],
        collection_item_id=disc.id,
        candidates=candidates or [],
        proposed_tmdb_id=proposed_tmdb_id,
    )
    assert raised is not None
    return film, disc, raised


# ---------------------------------------------------------------------------
# Finding them
# ---------------------------------------------------------------------------


async def test_the_in_doubt_filter_lists_the_films_in_doubt_and_counts_them(
    db: AsyncSession, desk: Desk
) -> None:
    doubted, _disc_, doubt = await _in_doubt(db, "Good Fellas", 2016)
    _, sure_id, _ = _tmdb_ids()
    sure = await _film(db, "GoodFellas", tmdb_id=sure_id, year=1990)
    await _disc(db, sure, "dvd")
    unidentified = await _film(db, "Halfway House")
    await _disc(db, unidentified, "dvd")
    # A doubt left open on a film no longer identified is not one the page can settle.
    db.add(IdentifyDoubt(id=uuid.uuid4(), movie_id=unidentified.id, source="recheck", note="x"))
    await db.commit()

    params = {"perPage": "2000"}
    doubted_page = await desk.client.get("/api/v1/movies", params={**params, "inDoubt": "true"})
    rest_page = await desk.client.get("/api/v1/movies", params={**params, "inDoubt": "false"})

    assert doubted_page.status_code == 200, doubted_page.text
    listed = {item["id"]: item for item in doubted_page.json()["items"]}
    rest = {item["id"]: item for item in rest_page.json()["items"]}
    assert str(doubted.id) in listed and listed[str(doubted.id)]["inDoubt"] is True
    assert str(sure.id) not in listed and str(unidentified.id) not in listed
    assert str(sure.id) in rest and rest[str(sure.id)]["inDoubt"] is False
    assert rest[str(unidentified.id)]["inDoubt"] is False
    assert str(doubted.id) not in rest
    facets = (await desk.client.get("/api/v1/collection/facets")).json()
    assert facets["inDoubtMovieCount"] == len(listed)

    kept = await desk.client.post(f"/api/v1/identify/doubts/{doubt.id}/keep")
    assert kept.status_code == 200, kept.text
    after = await desk.client.get("/api/v1/movies", params={**params, "inDoubt": "true"})
    assert str(doubted.id) not in {item["id"] for item in after.json()["items"]}


async def test_the_film_page_lists_every_open_doubt_with_its_copy_and_t9s_proposal(
    db: AsyncSession, desk: Desk
) -> None:
    _, real, _ = _tmdb_ids()
    film, disc, first = await _in_doubt(
        db,
        "Good Fellas",
        2016,
        note="The sheet groups it under Martin Scorsese.",
        evidence=["Scorsese directed GoodFellas (1990).", "This film has 0 votes."],
        candidates=[{"tmdb_id": real, "title": "GoodFellas", "year": 1990, "votes": 12000}],
        proposed_tmdb_id=real,
    )
    await _disc(db, film, "dvd")
    second = await raise_doubt(db, film, source="specs", note="A 1990 disc page.")
    assert second is not None
    second.created_utc = first.created_utc + timedelta(seconds=1)
    await db.commit()

    detail = (await desk.client.get(f"/api/v1/movies/{film.id}")).json()

    assert detail["inDoubt"] is True
    shown = detail["identificationDoubts"]
    assert [entry["doubtId"] for entry in shown] == [str(first.id), str(second.id)]
    assert (shown[0]["collectionItemId"], shown[0]["copyLabel"]) == (
        str(disc.id),
        "Blu-ray · Martin Scorsese · Front",
    )
    assert (shown[0]["proposedTmdbId"], shown[0]["proposedTitle"], shown[0]["proposedYear"]) == (
        real,
        "GoodFellas",
        1990,
    )
    assert shown[0]["evidence"] == [
        "Scorsese directed GoodFellas (1990).",
        "This film has 0 votes.",
    ]
    assert (shown[1]["source"], shown[1]["collectionItemId"], shown[1]["proposedTitle"]) == (
        "specs",
        None,
        None,
    )
    # The single doubt an app cached before Y4 reads is the oldest.
    assert detail["identificationDoubt"]["doubtId"] == str(first.id)


# ---------------------------------------------------------------------------
# Settling them
# ---------------------------------------------------------------------------


async def test_mark_keeps_a_film_and_craig_sees_it_and_undoes_it(
    db: AsyncSession, desk: Desk
) -> None:
    film, _disc_, doubt = await _in_doubt(db, "Kiss of Death", 1947)
    await db.commit()

    kept = await desk.client.post(f"/api/v1/identify/doubts/{doubt.id}/keep")

    assert kept.status_code == 200, kept.text
    assert kept.json()["outcome"] == "kept"
    await db.refresh(doubt)
    assert (doubt.status, doubt.decided_by) == ("kept", desk.mark.id)
    audit = await db.get(AdminAction, doubt.decided_action_id)
    assert audit is not None and audit.changes is not None
    assert (audit.user_id, audit.changes["kind"]) == (desk.mark.id, "doubt_kept")
    assert (audit.changes["title"], audit.changes["year"]) == ("Kiss of Death", 1947)
    assert (await desk.client.get(f"/api/v1/movies/{film.id}")).json()["inDoubt"] is False
    assert (await desk.client.get("/api/v1/identify/recent")).status_code == 403

    desk.as_(desk.craig)
    recent = (await desk.client.get("/api/v1/identify/recent")).json()["items"]
    (entry,) = [item for item in recent if item["actionId"] == str(audit.id)]
    assert (entry["how"], entry["by"], entry["title"], entry["year"]) == (
        "kept",
        desk.mark.display_name,
        "Kiss of Death",
        1947,
    )
    assert (entry["movieId"], entry["replaced"], entry["undone"]) == (str(film.id), "", False)

    undone = await desk.client.post(f"/api/v1/identify/recent/{audit.id}/undo")

    assert undone.status_code == 200, undone.text
    await db.refresh(doubt)
    assert (doubt.status, doubt.decided_by, doubt.decided_action_id) == ("open", None, None)
    assert (await desk.client.get(f"/api/v1/movies/{film.id}")).json()["inDoubt"] is True
    recent = (await desk.client.get("/api/v1/identify/recent")).json()["items"]
    (entry,) = [item for item in recent if item["actionId"] == str(audit.id)]
    assert entry["undone"] is True
    again = await desk.client.post(f"/api/v1/identify/recent/{audit.id}/undo")
    assert again.status_code == 409


async def test_a_keep_is_not_undone_once_the_film_has_changed(db: AsyncSession, desk: Desk) -> None:
    film, _disc_, doubt = await _in_doubt(db, "Nightmare Alley", 1947)
    await db.commit()
    kept = await desk.client.post(f"/api/v1/identify/doubts/{doubt.id}/keep")
    assert kept.status_code == 200, kept.text
    await db.refresh(doubt)
    action_id = doubt.decided_action_id
    _, other, _ = _tmdb_ids()
    film.tmdb_id = other
    await db.commit()

    desk.as_(desk.craig)
    refused = await desk.client.post(f"/api/v1/identify/recent/{action_id}/undo")

    assert refused.status_code == 409
    await db.refresh(doubt)
    assert doubt.status == "kept"


async def test_mark_moves_one_copy_but_the_rest_of_identify_still_refuses_him(
    db: AsyncSession, desk: Desk
) -> None:
    """The French Connection II row held both discs of The French Connection (CT46-01)."""
    sequel_id, real_id, _ = _tmdb_ids()
    desk.tmdb.records[real_id] = _record(real_id, "The French Connection", 1971)
    real = await _film(db, "The French Connection", tmdb_id=real_id, year=1971)
    sequel = await _film(db, "French Connection II", tmdb_id=sequel_id, year=1975)
    right = await _disc(db, sequel, "dvd")
    wrong = await _disc(db, sequel, "blu_ray")
    doubt = await raise_doubt(
        db, sequel, source="recheck", note="T9 cannot tell.", collection_item_id=wrong.id
    )
    assert doubt is not None
    await db.commit()

    searched = await desk.client.get(
        f"/api/v1/identify/films/{sequel.id}/search", params={"query": "The French Connection"}
    )
    moved = await desk.client.post(
        f"/api/v1/identify/copies/{wrong.id}/move",
        json={"tmdbId": real_id, "doubtId": str(doubt.id)},
    )

    assert searched.status_code == 200, searched.text
    assert moved.status_code == 200, moved.text
    await db.refresh(wrong)
    await db.refresh(right)
    await db.refresh(doubt)
    assert (wrong.movie_id, right.movie_id) == (real.id, sequel.id)
    assert (doubt.status, doubt.decided_by) == ("moved", desk.mark.id)
    audit = await db.get(AdminAction, uuid.UUID(moved.json()["actionId"]))
    assert audit is not None and audit.user_id == desk.mark.id

    action = moved.json()["actionId"]
    assert (await desk.client.get("/api/v1/identify/doubts")).status_code == 403
    assert (await desk.client.get("/api/v1/identify/queue")).status_code == 403
    assert (await desk.client.get("/api/v1/identify/overview")).status_code == 403
    assert (await desk.client.get("/api/v1/identify/recent")).status_code == 403
    assert (await desk.client.post(f"/api/v1/identify/recent/{action}/undo")).status_code == 403
    corrected = await desk.client.post(
        f"/api/v1/identify/doubts/{doubt.id}/identify", json={"tmdbId": real_id}
    )
    assert corrected.status_code == 403
