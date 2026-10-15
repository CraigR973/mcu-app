"""Identification in doubt against Postgres — Batch X9 (CT46-01, CT46-03). These run in CI.

**What this proves:** a doubt is raised only about a film identified as a film, once per
source and copy, and never again after Craig kept the film as it stands; a disc page or
review names the film by T9's title rule before it raises one; the Identify page lists the
doubts with the copy and the films offered, and its overview counts them; the film page says
"identification in doubt" while one is open; keeping a film sends a disc page that disagreed
back to "pick the right page"; identifying the film again settles every doubt about it,
chooses that disc page again, and is undone from the recent list, which opens the doubt
again and puts the film and its lookup back; a merge carries a film's doubts and its undo
brings them back; and the daily check counts a doubt a fortnight old.

The spec and review jobs' own hooks are in ``test_spec_backfill.py`` and
``test_reviews_batch.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.identify import IdentifyDoubt, IdentifyLookup
from src.models.profile import Profile
from src.models.specs_backfill import SpecCandidate, SpecLookup
from src.routers.movies import get_tmdb_client
from src.services.health_checks import check_identification
from src.services.identify.doubts import (
    SPECS_IN_DOUBT,
    doubt_from_page,
    names_the_film,
    raise_doubt,
)
from tests.test_identify_films import (
    FakeTmdb,
    _disc,
    _film,
    _person,
    _record,
    _tmdb_ids,
)

KWAI_PAGE = "https://www.blu-ray.com/movies/The-Bridge-on-the-River-Kwai-4K-Blu-ray/290000/"


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def page(db: AsyncSession) -> AsyncIterator[tuple[AsyncClient, Profile, FakeTmdb]]:
    craig = await _person(db)
    tmdb = FakeTmdb({})

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        await db.refresh(craig)
        return craig

    async def override_tmdb() -> AsyncIterator[FakeTmdb]:
        yield tmdb

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, craig, tmdb
    finally:
        app.dependency_overrides.clear()


async def _waiting_spec_page(db: AsyncSession, disc_id: uuid.UUID, note: str) -> SpecLookup:
    """A disc sent back by the spec job, with the search result its page was chosen from."""
    lookup = SpecLookup(
        id=uuid.uuid4(), collection_item_id=disc_id, status="needs_you", note=note, attempts=0
    )
    db.add(lookup)
    await db.flush()
    db.add(
        SpecCandidate(
            id=uuid.uuid4(),
            lookup_id=lookup.id,
            url=KWAI_PAGE,
            title="The Bridge on the River Kwai 4K Blu-ray (United Kingdom)",
            rank=1,
            matches=True,
        )
    )
    await db.flush()
    return lookup


# ---------------------------------------------------------------------------
# Raising one
# ---------------------------------------------------------------------------


def test_a_page_names_the_film_by_t9s_title_rule() -> None:
    names = ["The Bridge on the River Kwai", "Bridge on the River Kwai, The"]
    assert names_the_film("Bridge on the River Kwai", names)
    assert names_the_film("The Bridge On The River Kwai", names)
    assert not names_the_film("Kwai: The Making of a Classic", names)
    assert not names_the_film("", names)
    assert names_the_film("Kill Bill: Vol. 1", ["Kill Bill: Volume 1"])


async def test_a_doubt_is_raised_once_and_not_after_craig_kept_the_film(
    db: AsyncSession,
) -> None:
    unidentified = await _film(db, "Good Fellas")
    assert await raise_doubt(db, unidentified, source="recheck", note="Not identified.") is None

    tmdb_id, _, _ = _tmdb_ids()
    film = await _film(db, "Good Fellas", tmdb_id=tmdb_id, year=2016)
    first = await raise_doubt(db, film, source="recheck", note="The sheet says Scorsese.")
    again = await raise_doubt(db, film, source="recheck", note="And 1990.")
    assert first is not None and again is not None and first.id == again.id
    assert (again.note, again.identified_as, again.status) == ("And 1990.", tmdb_id, "open")

    craig = await _person(db)
    again.status, again.decided_by, again.decided_utc = "kept", craig.id, utcnow()
    await db.flush()
    assert await raise_doubt(db, film, source="recheck", note="Still 1990?") is None
    # Another source, or the film identified as something else, may still raise one.
    assert await raise_doubt(db, film, source="specs", note="A 1990 page.") is not None


async def test_a_page_for_the_films_own_title_in_another_year_raises_a_doubt(
    db: AsyncSession,
) -> None:
    tmdb_id, _, _ = _tmdb_ids()
    film = await _film(db, "The Bridge on the River Kwai", tmdb_id=tmdb_id, year=2007)
    disc = await _disc(db, film, "4k_uhd")

    doubt = await doubt_from_page(
        db,
        film,
        source="specs",
        page_name="The Bridge on the River Kwai",
        page_year=1957,
        page_url=KWAI_PAGE,
        collection_item_id=disc.id,
    )
    other = await doubt_from_page(
        db, film, source="review", page_name="Kwai", page_year=1957, page_url=KWAI_PAGE
    )

    assert doubt is not None and other is None
    assert doubt.note == (
        "Blu-ray.com's disc page for “The Bridge on the River Kwai” is a 1957 film, and this "
        "film is identified as 2007. The copy may be the 1957 film."
    )
    assert (doubt.search_hint, doubt.page_url, doubt.collection_item_id) == (
        "The Bridge on the River Kwai 1957",
        KWAI_PAGE,
        disc.id,
    )


# ---------------------------------------------------------------------------
# Settling one on Identify films
# ---------------------------------------------------------------------------


async def test_the_page_lists_doubts_and_the_film_page_says_so(
    db: AsyncSession, page: tuple[AsyncClient, Profile, FakeTmdb]
) -> None:
    client, _craig, _tmdb = page
    tmdb_id, real, _ = _tmdb_ids()
    held = await _film(db, "GoodFellas", tmdb_id=real, year=1990)
    await _disc(db, held, "dvd")
    film = await _film(db, "Good Fellas", tmdb_id=tmdb_id, year=2016)
    disc = await _disc(db, film, "blu_ray", sub_category="Martin Scorsese", location="Front")
    await _disc(db, film, "dvd")
    doubt = await raise_doubt(
        db,
        film,
        source="recheck",
        note="The sheet groups it under Martin Scorsese, who made GoodFellas (1990).",
        evidence=["Scorsese directed GoodFellas (1990).", "This film has 0 votes."],
        collection_item_id=disc.id,
        candidates=[{"tmdb_id": real, "title": "GoodFellas", "year": 1990, "votes": 12000}],
        proposed_tmdb_id=real,
    )
    assert doubt is not None
    await db.commit()

    listed = (await client.get("/api/v1/identify/doubts")).json()
    (entry,) = [item for item in listed["items"] if item["doubtId"] == str(doubt.id)]
    assert (entry["title"], entry["year"], entry["tmdbId"], entry["source"]) == (
        "Good Fellas",
        2016,
        tmdb_id,
        "recheck",
    )
    assert entry["discs"] == [{"label": "Blu-ray · Martin Scorsese · Front"}]
    assert (entry["copies"], entry["collectionItemId"]) == (2, str(disc.id))
    assert entry["candidates"][0]["inCollection"]["movieId"] == str(held.id)
    assert entry["searchHint"] == "Good Fellas"
    assert (await client.get("/api/v1/identify/overview")).json()["inDoubt"] >= 1

    detail = (await client.get(f"/api/v1/movies/{film.id}")).json()
    assert detail["identificationDoubt"]["note"].startswith("The sheet groups it under")
    assert (await client.get(f"/api/v1/movies/{held.id}")).json()["identificationDoubt"] is None


async def test_keeping_a_film_sends_a_disagreeing_disc_page_back_to_pick_another(
    db: AsyncSession, page: tuple[AsyncClient, Profile, FakeTmdb]
) -> None:
    client, craig, _tmdb = page
    tmdb_id, _, _ = _tmdb_ids()
    film = await _film(db, "Halloween", tmdb_id=tmdb_id, year=1978)
    disc = await _disc(db, film, "blu_ray")
    reason = "The page is for a 2018 film and this one is from 1978, so its specs were not used."
    lookup = await _waiting_spec_page(db, disc.id, f"{reason} {SPECS_IN_DOUBT}")
    doubt = await raise_doubt(
        db, film, source="specs", note="A 2018 page.", collection_item_id=disc.id
    )
    assert doubt is not None
    await db.commit()

    kept = await client.post(f"/api/v1/identify/doubts/{doubt.id}/keep")

    assert kept.status_code == 200 and kept.json()["outcome"] == "kept"
    assert (doubt.status, doubt.decided_by) == ("kept", craig.id)
    assert lookup.note == f"{reason} Pick the right page."
    audit = await db.get(AdminAction, doubt.decided_action_id)
    assert audit is not None and audit.changes is not None
    assert audit.changes["kind"] == "doubt_kept"
    assert (await client.post(f"/api/v1/identify/doubts/{doubt.id}/keep")).status_code == 409


async def test_identifying_it_again_settles_the_doubt_and_its_undo_opens_it_again(
    db: AsyncSession, page: tuple[AsyncClient, Profile, FakeTmdb]
) -> None:
    client, _craig, tmdb = page
    wrong, right, _ = _tmdb_ids()
    tmdb.records[right] = _record(right, "The Bridge on the River Kwai", 1957)
    film = await _film(db, "The Bridge on the River Kwai", tmdb_id=wrong, year=2007)
    disc = await _disc(db, film, "4k_uhd")
    lookup = await _waiting_spec_page(db, disc.id, f"A 1957 page. {SPECS_IN_DOUBT}")
    doubt = await doubt_from_page(
        db,
        film,
        source="specs",
        page_name="The Bridge on the River Kwai",
        page_year=1957,
        page_url=KWAI_PAGE,
        collection_item_id=disc.id,
    )
    assert doubt is not None
    await db.commit()
    film_id, doubt_id = film.id, doubt.id

    same = await client.post(f"/api/v1/identify/doubts/{doubt_id}/identify", json={"tmdbId": wrong})
    assert same.status_code == 409
    corrected = await client.post(
        f"/api/v1/identify/doubts/{doubt_id}/identify", json={"tmdbId": right, "searched": True}
    )

    assert corrected.status_code == 200 and corrected.json()["outcome"] == "identified"
    await db.refresh(film)
    await db.refresh(doubt)
    await db.refresh(lookup)
    assert (film.tmdb_id, film.year) == (right, 1957)
    assert doubt.status == "corrected" and doubt.decided_action_id is not None
    # The disc page that disagreed is chosen again, to be read against 1957.
    assert (lookup.status, lookup.accepted_url, lookup.how) == ("accepted", KWAI_PAGE, "auto")
    detail = (await client.get(f"/api/v1/movies/{film_id}")).json()
    assert detail["identificationDoubt"] is None

    recent = (await client.get("/api/v1/identify/recent")).json()["items"]
    (entry,) = [item for item in recent if item["movieId"] == str(film_id)]
    undone = await client.post(f"/api/v1/identify/recent/{entry['actionId']}/undo")

    assert undone.status_code == 200
    await db.refresh(film)
    await db.refresh(doubt)
    assert (film.tmdb_id, film.year) == (wrong, 2007)
    assert (doubt.status, doubt.decided_utc, doubt.decided_action_id) == ("open", None, None)
    # The film had no lookup before; the undo leaves none, rather than one asking about it.
    assert await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == film_id)) is None


async def test_a_doubt_settled_by_a_merge_goes_with_the_film_and_comes_back_on_undo(
    db: AsyncSession, page: tuple[AsyncClient, Profile, FakeTmdb]
) -> None:
    client, _craig, tmdb = page
    wrong, right, _ = _tmdb_ids()
    tmdb.records[right] = _record(right, "GoodFellas", 1990)
    held = await _film(db, "GoodFellas", tmdb_id=right, year=1990)
    await _disc(db, held, "dvd")
    film = await _film(db, "Good Fellas", tmdb_id=wrong, year=2016)
    disc = await _disc(db, film, "blu_ray")
    doubt = await raise_doubt(
        db, film, source="recheck", note="Scorsese.", collection_item_id=disc.id
    )
    assert doubt is not None
    await db.commit()
    film_id, held_id, doubt_id = film.id, held.id, doubt.id

    refused = await client.post(
        f"/api/v1/identify/doubts/{doubt_id}/identify", json={"tmdbId": right}
    )
    assert refused.status_code == 409 and "merges" in refused.json()["detail"]
    merged = await client.post(
        f"/api/v1/identify/doubts/{doubt_id}/identify", json={"tmdbId": right, "merge": True}
    )

    assert merged.json() == {"movieId": str(held_id), "outcome": "merged", "title": "GoodFellas"}
    settled = await db.get(IdentifyDoubt, doubt_id)
    assert settled is not None
    await db.refresh(settled)
    assert (settled.movie_id, settled.status) == (held_id, "corrected")

    recent = (await client.get("/api/v1/identify/recent")).json()["items"]
    (entry,) = [item for item in recent if item["replaced"] == "Good Fellas"]
    assert (
        await client.post(f"/api/v1/identify/recent/{entry['actionId']}/undo")
    ).status_code == 200

    await db.refresh(settled)
    assert (settled.movie_id, settled.status) == (film_id, "open")


async def test_the_daily_check_counts_a_doubt_a_fortnight_old(db: AsyncSession) -> None:
    tmdb_id, _, _ = _tmdb_ids()
    film = await _film(db, "The Night of the Hunter", tmdb_id=tmdb_id, year=1991)
    doubt = await raise_doubt(db, film, source="recheck", note="Laughton's grouping.")
    assert doubt is not None
    now = utcnow()
    before = dict(await check_identification(db, now))

    doubt.created_utc = now - timedelta(days=15)
    await db.flush()
    after = dict(await check_identification(db, now))

    def waiting(message: str | None) -> int:
        return int(message.split()[0]) if message else 0

    assert waiting(after["identify:waiting"]) == waiting(before["identify:waiting"]) + 1
