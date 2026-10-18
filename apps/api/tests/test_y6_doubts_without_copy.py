"""A doubt shows only while what it is about is still owned, against Postgres — Batch Y6 (#279).
These run in CI.

**The fault, 17–18 Oct:** a re-check doubt named a copy #278's plan then binned. Its film had
no owned copy left, so the Archive and the film page never showed the doubt, while Identify
films still counted it. Craig could not find it anywhere.

**What this proves:** binning or selling the copy a doubt names hides the doubt from every
surface (Identify films' list and overview, the daily check, the Archive's filter, count and
flag, the film page), whether or not the film has another copy; restoring or unselling it
shows the doubt again, unchanged and still open; a doubt naming no copy shows while the film
has a copy; and the overview, the Archive and the doubts list's film count agree, a film with
two doubts counting once.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.services.health_checks import check_identification
from src.services.identify.doubts import count_old, raise_doubt
from tests.test_identify_films import _disc, _film, _person, _tmdb_ids


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
class App:
    """The app as Craig, who alone sees Identify films and restores from the Trash."""

    client: AsyncClient
    craig: Profile


@pytest_asyncio.fixture
async def craig_app(db: AsyncSession) -> AsyncIterator[App]:
    craig = await _person(db)
    await _person(db, UserRole.viewer)

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        await db.refresh(craig)
        return craig

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield App(client, craig)
    finally:
        app.dependency_overrides.clear()


async def _doubted(
    db: AsyncSession, title: str, *, copies: int = 1, named: int | None = 0
) -> tuple[Movie, list[CollectionItem], IdentifyDoubt]:
    """An identified film with ``copies`` Blu-rays and a doubt naming copy ``named`` (none
    when ``named`` is None, as the review job raises one)."""
    tmdb_id, _, _ = _tmdb_ids()
    film = await _film(db, title, tmdb_id=tmdb_id, year=1989)
    discs = [await _disc(db, film, "blu_ray") for _ in range(copies)]
    doubt = await raise_doubt(
        db,
        film,
        source="recheck" if named is not None else "review",
        note="T9 cannot tell which film the sheet's title is.",
        collection_item_id=discs[named].id if named is not None else None,
    )
    assert doubt is not None
    await db.commit()
    return film, discs, doubt


@dataclass
class Seen:
    """What each surface says about one film and one doubt."""

    overview: int
    listed_doubt: bool
    doubts_total: int
    doubts_films: int
    archive_count: int
    archive_lists: bool
    flagged: bool
    page_doubts: list[str]
    page_flag: bool


async def _seen(client: AsyncClient, film: Movie, doubt: IdentifyDoubt) -> Seen:
    overview = (await client.get("/api/v1/identify/overview")).json()
    doubts = (await client.get("/api/v1/identify/doubts", params={"limit": 50})).json()
    facets = (await client.get("/api/v1/collection/facets")).json()
    archive = (
        await client.get("/api/v1/movies", params={"perPage": "2000", "inDoubt": "true"})
    ).json()
    every = (await client.get("/api/v1/movies", params={"perPage": "2000"})).json()
    flags = {item["id"]: item["inDoubt"] for item in every["items"]}
    page = (await client.get(f"/api/v1/movies/{film.id}")).json()
    return Seen(
        overview=overview["inDoubt"],
        listed_doubt=str(doubt.id) in {item["doubtId"] for item in doubts["items"]},
        doubts_total=doubts["total"],
        doubts_films=doubts["films"],
        archive_count=facets["inDoubtMovieCount"],
        archive_lists=str(film.id) in {item["id"] for item in archive["items"]},
        flagged=bool(flags.get(str(film.id))),
        page_doubts=[shown["doubtId"] for shown in page["identificationDoubts"]],
        page_flag=page["inDoubt"],
    )


def _hidden(seen: Seen) -> bool:
    return not (
        seen.listed_doubt
        or seen.archive_lists
        or seen.flagged
        or seen.page_doubts
        or seen.page_flag
    )


def _agree(seen: Seen) -> bool:
    return seen.overview == seen.archive_count == seen.doubts_films


# ---------------------------------------------------------------------------
# The copy goes, and comes back
# ---------------------------------------------------------------------------


async def test_a_doubt_whose_only_copy_is_binned_hides_everywhere_and_restoring_shows_it(
    db: AsyncSession, craig_app: App
) -> None:
    """The 17 Oct fault: the film the doubt is on has no owned copy left."""
    client = craig_app.client
    film, (disc,), doubt = await _doubted(db, "Time Is But a Window")
    doubt.created_utc = utcnow() - timedelta(days=15)
    await db.commit()
    now = utcnow()
    shown = await _seen(client, film, doubt)
    assert shown.listed_doubt and shown.archive_lists and shown.flagged and shown.page_flag
    assert shown.page_doubts == [str(doubt.id)] and _agree(shown)
    old_before = await count_old(db, now)

    binned = await client.delete(f"/api/v1/collection/{disc.id}")
    assert binned.status_code == 200, binned.text

    hidden = await _seen(client, film, doubt)
    assert _hidden(hidden) and _agree(hidden)
    assert hidden.overview == shown.overview - 1
    assert hidden.doubts_total == shown.doubts_total - 1
    assert await count_old(db, now) == old_before - 1
    await db.refresh(doubt)
    assert doubt.status == "open"  # nothing is written when a copy goes

    restored = await client.post(f"/api/v1/trash/collection_items/{disc.id}/restore")
    assert restored.status_code == 200, restored.text

    assert await _seen(client, film, doubt) == shown
    assert await count_old(db, now) == old_before


async def test_a_doubt_naming_a_binned_copy_hides_though_the_film_has_another(
    db: AsyncSession, craig_app: App
) -> None:
    """The doubt is about the binned disc; the film's other disc has no doubt of its own."""
    client = craig_app.client
    film, (named, other), doubt = await _doubted(db, "Ghostbusters II", copies=2)
    shown = await _seen(client, film, doubt)
    assert shown.listed_doubt and shown.archive_lists and shown.page_doubts == [str(doubt.id)]

    assert (await client.delete(f"/api/v1/collection/{named.id}")).status_code == 200

    hidden = await _seen(client, film, doubt)
    assert _hidden(hidden) and _agree(hidden)
    assert hidden.overview == shown.overview - 1
    # The film itself is still on the shelf, just not in doubt.
    page = (await client.get(f"/api/v1/movies/{film.id}")).json()
    assert page["copyCount"] == 1
    await db.refresh(other)
    assert other.deleted_at is None

    assert (
        await client.post(f"/api/v1/trash/collection_items/{named.id}/restore")
    ).status_code == 200
    assert await _seen(client, film, doubt) == shown


async def test_a_sold_copy_hides_its_doubt_and_unselling_shows_it(
    db: AsyncSession, craig_app: App
) -> None:
    client = craig_app.client
    film, (disc,), doubt = await _doubted(db, "The Burbs")
    shown = await _seen(client, film, doubt)

    sold = await client.put(
        f"/api/v1/collection/{disc.id}/listing", json={"status": "sold", "listingPrice": "4.00"}
    )
    assert sold.status_code == 200, sold.text
    hidden = await _seen(client, film, doubt)
    assert _hidden(hidden) and _agree(hidden)

    back = await client.put(
        f"/api/v1/collection/{disc.id}/listing", json={"status": "in_collection"}
    )
    assert back.status_code == 200, back.text
    assert await _seen(client, film, doubt) == shown


async def test_a_doubt_naming_no_copy_shows_while_the_film_has_one(
    db: AsyncSession, craig_app: App
) -> None:
    """The review job's doubts are about the film, not a disc."""
    client = craig_app.client
    film, (first, second), doubt = await _doubted(db, "Big", copies=2, named=None)
    shown = await _seen(client, film, doubt)
    assert shown.listed_doubt and shown.page_flag

    assert (await client.delete(f"/api/v1/collection/{first.id}")).status_code == 200
    still = await _seen(client, film, doubt)
    assert still.listed_doubt and still.archive_lists and still.page_doubts == [str(doubt.id)]

    assert (await client.delete(f"/api/v1/collection/{second.id}")).status_code == 200
    hidden = await _seen(client, film, doubt)
    assert _hidden(hidden) and _agree(hidden)

    assert (
        await client.post(f"/api/v1/trash/collection_items/{second.id}/restore")
    ).status_code == 200
    back = await _seen(client, film, doubt)
    assert back.listed_doubt and back.archive_lists and back.page_doubts == [str(doubt.id)]


async def test_a_copy_on_another_film_does_not_keep_the_doubt_showing(
    db: AsyncSession, craig_app: App
) -> None:
    """A doubt naming a disc that has since gone to another film is about nothing here."""
    client = craig_app.client
    film, (disc,), doubt = await _doubted(db, "Scrooged")
    elsewhere_id, _, _ = _tmdb_ids()
    elsewhere = await _film(db, "A Christmas Carol", tmdb_id=elsewhere_id, year=1951)
    await _disc(
        db, film, "dvd"
    )  # the film keeps a copy, so only the rule on the named one hides it
    disc.movie_id = elsewhere.id
    await db.commit()

    hidden = await _seen(client, film, doubt)
    assert _hidden(hidden) and _agree(hidden)


# ---------------------------------------------------------------------------
# The counts agree
# ---------------------------------------------------------------------------


async def test_the_overview_the_archive_and_the_daily_check_agree(
    db: AsyncSession, craig_app: App
) -> None:
    """Two doubts on one film count once; the daily check counts the fortnight-old films."""
    client = craig_app.client
    now = utcnow()
    other, _, other_doubt = await _doubted(db, "Weekend at Bernie's")
    before = await _seen(client, other, other_doubt)
    old_before = await count_old(db, now)
    waiting_before = dict(await check_identification(db, now))["identify:waiting"]

    film, discs, first = await _doubted(db, "Road House", copies=2)
    second = await raise_doubt(
        db,
        film,
        source="specs",
        note="A disc page for another year.",
        collection_item_id=discs[1].id,
    )
    assert second is not None
    first.created_utc = second.created_utc = now - timedelta(days=15)
    await db.commit()

    after = await _seen(client, film, first)
    assert _agree(after)
    assert after.overview == before.overview + 1
    assert after.doubts_total == before.doubts_total + 2
    assert after.doubts_films == before.doubts_films + 1
    assert await count_old(db, now) == old_before + 1
    assert await count_old(db, now) <= after.archive_count

    def waiting(message: str | None) -> int:
        return int(message.split()[0]) if message else 0

    waiting_after = dict(await check_identification(db, now))["identify:waiting"]
    assert waiting(waiting_after) == waiting(waiting_before) + 1
