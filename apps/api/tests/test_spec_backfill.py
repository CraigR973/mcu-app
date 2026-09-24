"""The Blu-ray.com backfill against Postgres — Batch T7. These run in CI.

**What this proves:** a single UK match is accepted, fetched and stored with its source;
several editions wait for Craig and nothing is fetched for them; a page the matcher chose
must show the film's year; Craig's own choice is fetched as he made it; a 403 halts the
whole integration and it stays halted; searches stop at the batch's budget and the month's
ceiling, and the next batch carries on; the 10 Sep specs are copied across only when the
search confirms their page is the UK edition; the queue, the coverage, the button and the
Archive's filter switch.

**What it does not:** a live search or a live fetch. Brave is a scripted searcher, and
Blu-ray.com is the two captured pages (Fight Club, 1999; Blade Runner 2049 4K, 2017).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.config import settings
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.specs_backfill import SpecCandidate, SpecLookup, SpecRun
from src.services.specs import backfill
from src.services.specs.backfill import (
    MONTHLY_SEARCH_CEILING,
    NOT_CONFIGURED,
    accept_page,
    coverage,
    start_run,
    work_run,
)
from src.services.specs.runner import get_state
from src.services.specs.search import SearchHit

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 9, 24, 2, 0)
FIXTURES = Path(__file__).parent / "fixtures"
FIGHT_CLUB_PAGE = (FIXTURES / "bluray_com_release_page.html").read_text()
BLADE_RUNNER_PAGE = (FIXTURES / "bluray_com_release_page_4k.html").read_text()

FIGHT_CLUB_UK = "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/6715/"
FIGHT_CLUB_US = "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/5587/"
BLADE_RUNNER_UK_4K = "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/248418/"


def hit(url: str, title: str) -> SearchHit:
    return SearchHit(url=url, title=title, description="")


class FakeBrave:
    """Answers by the film named in the query, counts every call, never retries."""

    attempts_per_search = 1

    def __init__(
        self, answers: dict[str, list[SearchHit]] | None = None, *, configured: bool = True
    ):
        self.answers = answers or {}
        self.queries: list[str] = []
        self.search_calls = 0
        self._configured = configured

    @property
    def configured(self) -> bool:
        return self._configured

    async def search(self, query: str, *, count: int = 20, country: str = "GB") -> list[SearchHit]:
        del count, country
        self.search_calls += 1
        self.queries.append(query)
        for film, hits in self.answers.items():
            if f" {film} " in f" {query} ":
                return hits
        return []


class FakeBlurayCom:
    """Blu-ray.com: the captured pages by path, or a refusal."""

    def __init__(self, pages: dict[str, str], *, status: int = 200) -> None:
        self.pages = pages
        self.status = status
        self.requested: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requested.append(str(request.url))
        if self.status != 200:
            return httpx.Response(self.status, text="refused")
        page = self.pages.get(request.url.path)
        return httpx.Response(200, text=page) if page else httpx.Response(404, text="none")

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        # The counts below are exact, so the shared test database must hold no owned discs.
        assert (await coverage(session)).discs == 0, "owned discs leaked into the test DB"
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


async def _film(db: AsyncSession, title: str, *, year: int | None, tmdb_id: int | None) -> Movie:
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=year,
        media_type="film",
    )
    db.add(film)
    await db.flush()
    return film


async def _disc(db: AsyncSession, film: Movie, *formats: str, **fields: Any) -> CollectionItem:
    disc = CollectionItem(id=uuid.uuid4(), movie_id=film.id, formats=list(formats), **fields)
    db.add(disc)
    await db.flush()
    return disc


async def _run(
    db: AsyncSession,
    brave: FakeBrave,
    site: FakeBlurayCom,
    *,
    now: datetime = NOW,
) -> SpecRun:
    outcome = await start_run(db, trigger="job", search_configured=brave.configured, now=now)
    assert outcome.reason == "started", outcome
    assert outcome.run is not None
    async with site.client() as client:
        return await work_run(
            db, outcome.run.id, searcher=brave, client=client, clock=lambda: now, pause=0
        )


async def _lookup(db: AsyncSession, disc: CollectionItem) -> SpecLookup:
    lookup = await db.scalar(select(SpecLookup).where(SpecLookup.collection_item_id == disc.id))
    assert lookup is not None
    return lookup


FIGHT_CLUB_ONE_UK = [
    hit(FIGHT_CLUB_UK, "Fight Club Blu-ray (United Kingdom)"),
    hit(FIGHT_CLUB_US, "Fight Club Blu-ray (10th Anniversary Edition)"),
]
FIGHT_CLUB_THREE_UK = [
    hit(
        "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/114797/",
        "Fight Club Blu-ray (MetalPak) (United Kingdom)",
    ),
    hit(FIGHT_CLUB_UK, "Fight Club Blu-ray (10th Anniversary Edition) (United Kingdom)"),
    hit(
        "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/41252/",
        "Fight Club Blu-ray (Play Exclusive SteelBook) (United Kingdom)",
    ),
]


# ---------------------------------------------------------------------------
# One batch
# ---------------------------------------------------------------------------


async def test_one_uk_page_is_accepted_fetched_and_stored_with_its_source(
    db: AsyncSession,
) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    brave = FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK})
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/6715/": FIGHT_CLUB_PAGE})

    run = await _run(db, brave, site)

    assert brave.queries == ["site:blu-ray.com Fight Club Blu-ray United Kingdom"]
    assert site.requested == [FIGHT_CLUB_UK]
    assert (run.status, run.searches, run.accepted, run.fetched, run.applied) == (
        "finished",
        1,
        1,
        1,
        1,
    )
    await db.refresh(disc)
    assert disc.specs_source_url == FIGHT_CLUB_UK
    assert disc.specs_fetched_at_utc == NOW
    assert disc.video_specs and disc.audio_specs
    lookup = await _lookup(db, disc)
    assert (lookup.status, lookup.how, lookup.accepted_url) == ("done", "auto", FIGHT_CLUB_UK)
    assert (await get_state(db)).fetch_count >= 1


async def test_several_uk_editions_wait_for_craig_and_nothing_is_fetched(
    db: AsyncSession,
) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/6715/": FIGHT_CLUB_PAGE})

    run = await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_THREE_UK}), site)

    assert site.requested == []
    assert (run.queued, run.fetched) == (1, 0)
    lookup = await _lookup(db, disc)
    assert lookup.status == "needs_you"
    assert "3 UK editions" in (lookup.note or "")
    offered = (
        await db.scalars(select(SpecCandidate).where(SpecCandidate.lookup_id == lookup.id))
    ).all()
    assert {candidate.url for candidate in offered if candidate.matches} >= {FIGHT_CLUB_UK}


async def test_a_chosen_page_showing_another_year_goes_back_to_craig(db: AsyncSession) -> None:
    """The remake guard: the captured Fight Club page says 1999, this film says 2021."""
    film = await _film(db, "Fight Club", year=2021, tmdb_id=990_000_551)
    disc = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/6715/": FIGHT_CLUB_PAGE})

    run = await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK}), site)

    assert (run.fetched, run.applied, run.sent_back) == (1, 0, 1)
    await db.refresh(disc)
    assert disc.specs_source_url is None
    lookup = await _lookup(db, disc)
    assert (lookup.status, lookup.accepted_url) == ("needs_you", None)
    assert "1999" in (lookup.note or "") and "2021" in (lookup.note or "")


async def test_craigs_own_choice_is_fetched_as_he_made_it(db: AsyncSession) -> None:
    """No year to check against, so it waits for him; his pasted page is then used."""
    craig = await _person(db, UserRole.admin)
    film = await _film(db, "Fight Club (Brad Pitt)", year=None, tmdb_id=None)
    disc = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/6715/": FIGHT_CLUB_PAGE})
    brave = FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK})

    first = await _run(db, brave, site)
    lookup = await _lookup(db, disc)
    assert (first.queued, lookup.status) == (1, "needs_you")

    await accept_page(
        db, lookup.id, "https://blu-ray.com/movies/Fight-Club-Blu-ray/6715", by=craig.id
    )
    second = await _run(db, brave, site, now=NOW + timedelta(days=1))

    assert (second.fetched, second.applied) == (1, 1)
    await db.refresh(lookup)
    assert (lookup.status, lookup.how, lookup.accepted_url) == ("done", "confirmed", FIGHT_CLUB_UK)


async def test_a_403_halts_the_integration_and_it_stays_halted(db: AsyncSession) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({}, status=403)

    run = await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK}), site)

    assert run.status == "halted"
    assert (await get_state(db)).halted is True
    lookup = await _lookup(db, disc)
    assert lookup.status == "accepted"  # untouched, for whenever an owner decision resumes it
    later = await start_run(db, trigger="job", search_configured=True, now=NOW + timedelta(days=1))
    assert (later.reason, later.run) == ("halted", None)


async def test_a_4k_box_gets_the_uk_4k_page_and_its_hdr(db: AsyncSession) -> None:
    film = await _film(db, "Blade Runner 2049", year=2017, tmdb_id=990_335_984)
    disc = await _disc(db, film, "4k_uhd", "blu_ray")
    hits = [
        hit(
            BLADE_RUNNER_UK_4K,
            "Blade Runner 2049 4K Blu-ray (4K Ultra HD + Blu-ray) (United Kingdom)",
        ),
        hit(
            "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/338923/",
            "Blade Runner 2049 4K Blu-ray (SteelBook) (United Kingdom)",
        ),
        hit(
            "https://www.blu-ray.com/movies/Blade-Runner-2049-Blu-ray/190522/",
            "Blade Runner 2049 Blu-ray (United Kingdom)",
        ),
    ]
    site = FakeBlurayCom({"/movies/Blade-Runner-2049-4K-Blu-ray/248418/": BLADE_RUNNER_PAGE})

    run = await _run(db, FakeBrave({"Blade Runner 2049": hits}), site)

    assert (run.accepted, run.applied) == (1, 1)
    await db.refresh(disc)
    assert disc.specs_source_url == BLADE_RUNNER_UK_4K
    assert (disc.video_specs or {}).get("resolution") == "2160p"


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


async def test_searches_stop_at_the_batch_budget_and_the_next_batch_carries_on(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backfill, "SEARCHES_PER_RUN", 2)
    for index in range(3):
        film = await _film(db, f"Budget Film {index}", year=2000, tmdb_id=990_001_000 + index)
        await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({})

    first = await _run(db, FakeBrave(), site)
    assert (first.status, first.searches, first.searched, first.no_match) == (
        "budget_spent",
        2,
        2,
        2,
    )

    brave = FakeBrave()
    second = await _run(db, brave, site, now=NOW + timedelta(days=1))
    assert brave.queries == ["site:blu-ray.com Budget Film 2 Blu-ray United Kingdom"]
    assert second.status == "finished"


async def test_the_months_ceiling_caps_a_batch(db: AsyncSession) -> None:
    film = await _film(db, "Ceiling Film", year=2000, tmdb_id=990_002_000)
    await _disc(db, film, "blu_ray")
    await _disc(db, await _film(db, "Ceiling Two", year=2000, tmdb_id=990_002_001), "blu_ray")
    db.add(
        SpecRun(
            id=uuid.uuid4(),
            trigger="job",
            status="finished",
            started_utc=NOW - timedelta(days=1),
            heartbeat_utc=NOW - timedelta(days=1),
            finished_utc=NOW - timedelta(days=1),
            search_budget=150,
            searches=MONTHLY_SEARCH_CEILING - 1,
            fetch_budget=150,
        )
    )
    await db.commit()

    run = await _run(db, FakeBrave(), FakeBlurayCom({}))

    assert (run.search_budget, run.searches, run.status) == (1, 1, "budget_spent")


# ---------------------------------------------------------------------------
# The 10 Sep specs
# ---------------------------------------------------------------------------


async def _trashed_with_specs(
    db: AsyncSession, film: Movie, url: str, region: str
) -> CollectionItem:
    return await _disc(
        db,
        film,
        "blu_ray",
        deleted_at=datetime(2026, 9, 18, 10, 17),
        video_specs={"codec": "MPEG-4 AVC", "resolution": "1080p"},
        audio_specs=[{"format": "DTS-HD MA", "channels": "5.1", "language": "English"}],
        region_code=region,
        specs_source_url=url,
        specs_fetched_at_utc=datetime(2026, 9, 10, 8, 37),
    )


async def test_old_specs_are_copied_when_the_search_confirms_their_page_is_uk(
    db: AsyncSession,
) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    await _trashed_with_specs(db, film, FIGHT_CLUB_UK, "B")
    live = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({})

    run = await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK}), site)

    assert (run.restored, run.fetched) == (1, 0)
    assert site.requested == []
    await db.refresh(live)
    assert (live.region_code, live.specs_source_url) == ("B", FIGHT_CLUB_UK)
    assert live.specs_fetched_at_utc == datetime(2026, 9, 10, 8, 37)
    lookup = await _lookup(db, live)
    assert (lookup.status, lookup.how) == ("done", "restored")


async def test_old_specs_from_a_us_page_are_not_copied(db: AsyncSession) -> None:
    """Kick-Ass and Up were region A on 10 Sep: US pages. The UK page is fetched instead."""
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    await _trashed_with_specs(db, film, FIGHT_CLUB_US, "A")
    live = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/6715/": FIGHT_CLUB_PAGE})

    run = await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK}), site)

    assert (run.restored, run.accepted, run.applied) == (0, 1, 1)
    await db.refresh(live)
    assert live.specs_source_url == FIGHT_CLUB_UK
    assert live.region_code != "A"


async def test_an_old_page_the_search_did_not_see_is_offered_to_craig(db: AsyncSession) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    await _trashed_with_specs(db, film, FIGHT_CLUB_US, "A")
    live = await _disc(db, film, "blu_ray")

    await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_THREE_UK}), FakeBlurayCom({}))

    lookup = await _lookup(db, live)
    assert lookup.status == "needs_you"
    restored = await db.scalar(
        select(SpecCandidate).where(
            SpecCandidate.lookup_id == lookup.id, SpecCandidate.origin == "restored"
        )
    )
    assert restored is not None and restored.url == FIGHT_CLUB_US
    assert "10 Sep" in (lookup.note or "")


# ---------------------------------------------------------------------------
# Without a key
# ---------------------------------------------------------------------------


async def test_without_a_key_a_batch_still_fetches_what_craig_chose(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    lookup = SpecLookup(id=uuid.uuid4(), collection_item_id=disc.id, status="needs_you", attempts=0)
    db.add(lookup)
    await db.commit()
    await accept_page(db, lookup.id, FIGHT_CLUB_UK, by=craig.id)
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/6715/": FIGHT_CLUB_PAGE})

    run = await _run(db, FakeBrave(configured=False), site)

    assert (run.searches, run.applied, run.status) == (0, 1, "finished")
    assert run.last_error == NOT_CONFIGURED


async def test_without_a_key_and_nothing_chosen_no_batch_starts(db: AsyncSession) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    await _disc(db, film, "blu_ray")
    outcome = await start_run(db, trigger="job", search_configured=False, now=NOW)
    assert (outcome.reason, outcome.run) == ("nothing_due", None)


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------


async def _person(db: AsyncSession, role: UserRole) -> Profile:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"{role.value} {uuid.uuid4().hex[:6]}",
        role=role,
        pin_hash="test-pin-hash",
    )
    db.add(person)
    await db.flush()
    return person


def _as(db: AsyncSession, person: Profile) -> AsyncClient:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return person

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _queued(db: AsyncSession) -> tuple[CollectionItem, SpecLookup]:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray", location="Front 4th shelf")
    await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_THREE_UK}), FakeBlurayCom({}))
    return disc, await _lookup(db, disc)


async def test_the_queue_lists_the_disc_with_its_candidates(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    disc, lookup = await _queued(db)

    async with _as(db, craig) as client:
        response = await client.get("/api/v1/specs/queue")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    (item,) = body["items"]
    assert (item["lookupId"], item["filmTitle"], item["year"]) == (
        str(lookup.id),
        "Fight Club",
        1999,
    )
    assert item["location"] == "Front 4th shelf"
    assert item["status"] == "needs_you"
    assert {candidate["url"] for candidate in item["candidates"]} >= {FIGHT_CLUB_UK}
    assert all(candidate["country"] == "United Kingdom" for candidate in item["candidates"])
    assert disc.id == uuid.UUID(item["collectionItemId"])


async def test_mark_cannot_see_or_decide_the_queue(db: AsyncSession) -> None:
    mark = await _person(db, UserRole.viewer)
    _disc_row, lookup = await _queued(db)
    async with _as(db, mark) as client:
        assert (await client.get("/api/v1/specs/queue")).status_code == 403
        skipped = await client.post(f"/api/v1/specs/queue/{lookup.id}/skip")
    assert skipped.status_code == 403


async def test_craig_picks_a_page_and_nothing_is_fetched_until_the_next_batch(
    db: AsyncSession,
) -> None:
    craig = await _person(db, UserRole.admin)
    _disc_row, lookup = await _queued(db)

    async with _as(db, craig) as client:
        picked = await client.post(
            f"/api/v1/specs/queue/{lookup.id}/accept", json={"url": FIGHT_CLUB_UK}
        )
        again = await client.post(
            f"/api/v1/specs/queue/{lookup.id}/accept", json={"url": FIGHT_CLUB_UK}
        )
        searched = await client.post(
            f"/api/v1/specs/queue/{lookup.id}/accept",
            json={"url": "https://www.blu-ray.com/search/?q=fight+club"},
        )

    assert picked.status_code == 200, picked.text
    assert picked.json() == {
        "lookupId": str(lookup.id),
        "status": "accepted",
        "acceptedUrl": FIGHT_CLUB_UK,
        "how": "confirmed",
    }
    assert again.status_code == 409
    assert searched.status_code == 422


async def test_craig_can_skip_a_disc(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    _disc_row, lookup = await _queued(db)
    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/specs/queue/{lookup.id}/skip")
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"
    assert (await coverage(db)).skipped == 1


async def test_coverage_counts_every_blu_ray_and_4k_disc(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    await _queued(db)
    film = await _film(db, "Blade Runner 2049", year=2017, tmdb_id=990_335_984)
    await _disc(db, film, "4k_uhd", "blu_ray")
    await _disc(db, film, "dvd")  # DVDs are out of scope

    async with _as(db, craig) as client:
        response = await client.get("/api/v1/specs/backfill")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["coverage"] == {
        "discs": 2,
        "withSpecs": 0,
        "accepted": 0,
        "needsYou": 1,
        "noMatch": 0,
        "skipped": 0,
        "notSearched": 1,
    }
    assert body["run"]["status"] == "finished"
    assert body["monthlyCeiling"] == MONTHLY_SEARCH_CEILING


@pytest.fixture
def background(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    import src.routers.specs as specs_router

    started: list[uuid.UUID] = []

    async def record(run_id: uuid.UUID) -> None:
        started.append(run_id)

    monkeypatch.setattr(specs_router, "continue_run_in_background", record)
    return started


async def test_the_button_claims_a_batch_and_runs_it_after_the_response(
    db: AsyncSession, background: list[uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "brave_search_api_key", "a-key")
    craig = await _person(db, UserRole.admin)
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    await _disc(db, film, "blu_ray")

    async with _as(db, craig) as client:
        first = await client.post("/api/v1/specs/backfill/run")
        second = await client.post("/api/v1/specs/backfill/run")

    assert first.json()["outcome"] == "started"
    run_id = uuid.UUID(first.json()["run"]["id"])
    run = await db.get(SpecRun, run_id)
    assert run is not None and (run.trigger, run.started_by) == ("admin", craig.id)
    assert background == [run_id]
    assert second.json()["outcome"] == "running"


async def test_the_archive_is_told_whether_any_disc_has_specs(db: AsyncSession) -> None:
    mark = await _person(db, UserRole.viewer)
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")

    async with _as(db, mark) as client:
        before = (await client.get("/api/v1/collection/facets")).json()["discsWithSpecs"]
        disc.specs_source_url = FIGHT_CLUB_UK
        await db.flush()
        after = (await client.get("/api/v1/collection/facets")).json()["discsWithSpecs"]

    assert (before, after) == (0, 1)
    assert await db.scalar(select(func.count()).select_from(SpecLookup)) == 0
