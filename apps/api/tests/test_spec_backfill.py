"""The Blu-ray.com backfill against Postgres — Batch T7. These run in CI.

**What this proves:** a single UK match is accepted, fetched and stored with its source;
several editions wait for Craig and nothing is fetched for them; a page the matcher chose
must show the film's year; Craig's own choice is fetched as he made it; a 403 halts the
whole integration and it stays halted; searches stop at the batch's budget and the month's
ceiling, and the next batch carries on; the 10 Sep specs are copied across only when the
search confirms their page is the UK edition; the queue, the coverage, the button and the
Archive's filter switch. Batch T10: a queued disc whose film was identified since its search
is searched once more, first and inside the budget, and a disc Craig decided, one searched
since, one whose words are unchanged, one whose page failed its year check and one whose
film is still unidentified are not.

**What it does not:** a live search or a live fetch. Brave is a scripted searcher, and
Blu-ray.com is the two captured pages (Fight Club, 1999; Blade Runner 2049 4K, 2017).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
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
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.specs_backfill import SpecCandidate, SpecLookup, SpecRun
from src.services.specs import backfill
from src.services.specs.backfill import (
    MONTHLY_SEARCH_CEILING,
    NOT_CONFIGURED,
    accept_page,
    coverage,
    editions_to_fill,
    fill_editions,
    start_run,
    work_run,
)
from src.services.specs.runner import get_state
from src.services.specs.search import SearchHit

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
    """Blu-ray.com: the captured pages by path, pages that moved, or a refusal."""

    def __init__(
        self,
        pages: dict[str, str],
        *,
        status: int = 200,
        moved: dict[str, str] | None = None,
        refusing: frozenset[str] = frozenset(),
    ) -> None:
        self.pages = pages
        self.status = status
        #: Path → where a `301` sends it (Batch U1).
        self.moved = moved or {}
        #: Paths answered with a `429`.
        self.refusing = refusing
        self.requested: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requested.append(str(request.url))
        if self.status != 200:
            return httpx.Response(self.status, text="refused")
        path = request.url.path
        if path in self.moved:
            return httpx.Response(301, headers={"Location": self.moved[path]})
        if path in self.refusing:
            return httpx.Response(429, text="slow down")
        page = self.pages.get(path)
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
    # Batch X9 (CT46-03): the page names the film's own title, so the film may be the wrong
    # one. That goes to Identify as a doubt, rather than asking for another page.
    assert (lookup.note or "").endswith(
        "The film may be the wrong one: it waits on Identify films."
    )
    doubt = await db.scalar(select(IdentifyDoubt).where(IdentifyDoubt.movie_id == film.id))
    assert doubt is not None
    assert (doubt.source, doubt.status, doubt.collection_item_id) == ("specs", "open", disc.id)
    assert (doubt.search_hint, doubt.page_url) == ("Fight Club 1999", FIGHT_CLUB_UK)


async def test_another_years_page_for_an_unidentified_film_asks_for_another_page(
    db: AsyncSession,
) -> None:
    """No identification to doubt: the film is in Identify's queue already (X9)."""
    film = await _film(db, "Fight Club", year=2021, tmdb_id=None)
    disc = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/6715/": FIGHT_CLUB_PAGE})

    run = await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK}), site)

    assert (run.fetched, run.sent_back) == (1, 1)
    lookup = await _lookup(db, disc)
    assert lookup.note == (
        "The page is for a 1999 film and this one is from 2021, so its specs were not used. "
        "Pick the right page."
    )
    assert await db.scalar(select(IdentifyDoubt).where(IdentifyDoubt.movie_id == film.id)) is None


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


async def _queued_with(
    db: AsyncSession, film: Movie, note: str, hits: list[tuple[str, str]]
) -> SpecLookup:
    disc = await _disc(db, film, "blu_ray")
    lookup = SpecLookup(
        id=uuid.uuid4(), collection_item_id=disc.id, status="needs_you", note=note, attempts=0
    )
    db.add(lookup)
    await db.flush()
    for rank, (url, title) in enumerate(hits):
        db.add(
            SpecCandidate(
                id=uuid.uuid4(), lookup_id=lookup.id, url=url, title=title, rank=rank, matches=True
            )
        )
    await db.commit()
    return lookup


async def test_a_second_look_settles_what_the_sharper_matcher_can(db: AsyncSession) -> None:
    """Up was left for Craig on 24 Sep with four UK editions; one of them is plain PIXAR."""
    film = await _film(db, "Up", year=1999, tmdb_id=990_014_160)
    plain = "https://www.blu-ray.com/movies/Up-Blu-ray/3/"
    lookup = await _queued_with(
        db,
        film,
        "4 UK editions match. Pick the one on the shelf.",
        [
            (
                "https://www.blu-ray.com/movies/Up-Blu-ray/1/",
                "Up Blu-ray (PIXAR / Combi Pack) (United Kingdom)",
            ),
            (plain, "Up Blu-ray (PIXAR) (United Kingdom)"),
        ],
    )
    # A batch starts only when there is something to search for or fetch.
    await _disc(db, await _film(db, "Filler Film", year=2000, tmdb_id=990_009_999), "blu_ray")
    brave = FakeBrave()
    site = FakeBlurayCom({"/movies/Up-Blu-ray/3/": FIGHT_CLUB_PAGE})

    run = await _run(db, brave, site)

    # Up was settled from its stored results: only the filler was searched.
    assert brave.queries == ["site:blu-ray.com Filler Film Blu-ray United Kingdom"]
    assert (run.accepted, run.applied) == (1, 1)
    await db.refresh(lookup)
    assert (lookup.status, lookup.how, lookup.accepted_url) == ("done", "auto", plain)


async def test_a_page_that_failed_its_year_check_is_not_chosen_again(db: AsyncSession) -> None:
    film = await _film(db, "Up", year=2009, tmdb_id=990_014_160)
    lookup = await _queued_with(
        db,
        film,
        "The page is for a 1999 film and this one is from 2009, so its specs were not used.",
        [("https://www.blu-ray.com/movies/Up-Blu-ray/3/", "Up Blu-ray (PIXAR) (United Kingdom)")],
    )
    await _disc(db, await _film(db, "Filler Film", year=2000, tmdb_id=990_009_999), "blu_ray")
    site = FakeBlurayCom({})

    await _run(db, FakeBrave(), site, now=NOW)

    await db.refresh(lookup)
    assert lookup.status == "needs_you"
    assert site.requested == []


# ---------------------------------------------------------------------------
# Pages that moved — Batch U1, `DECISIONS.md` #219
# ---------------------------------------------------------------------------

FIGHT_CLUB_UK_PATH = "/movies/Fight-Club-Blu-ray/6715/"
#: The same release, 6715, under a new name, as Dr. Strangelove's page was renamed on 26 Sep.
FIGHT_CLUB_RENAMED_PATH = "/movies/Fight-Club-10th-Anniversary-Blu-ray/6715/"
FIGHT_CLUB_RENAMED = "https://www.blu-ray.com" + FIGHT_CLUB_RENAMED_PATH


async def _accepted(
    db: AsyncSession,
    film: Movie,
    url: str,
    *,
    how: str = "auto",
    attempts: int = 0,
    decided: datetime = NOW - timedelta(hours=18),
) -> tuple[CollectionItem, SpecLookup]:
    """A disc whose page an earlier batch accepted, and which has not loaded yet."""
    disc = await _disc(db, film, "blu_ray")
    lookup = SpecLookup(
        id=uuid.uuid4(),
        collection_item_id=disc.id,
        status="accepted",
        accepted_url=url,
        how=how,
        decided_utc=decided,
        note="One UK page matched the film and format.",
        attempts=attempts,
        last_error="Redirect response '301 Moved Permanently'" if attempts else None,
    )
    db.add(lookup)
    await db.commit()
    return disc, lookup


async def test_a_page_renamed_on_the_site_settles_in_one_batch(db: AsyncSession) -> None:
    """Dr. Strangelove's, 26 Sep: accepted, then answered `301` to a new name for the same
    release. It had one of its three tries left over from that batch."""
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc, lookup = await _accepted(db, film, FIGHT_CLUB_UK, attempts=1)
    site = FakeBlurayCom(
        {FIGHT_CLUB_RENAMED_PATH: FIGHT_CLUB_PAGE},
        moved={FIGHT_CLUB_UK_PATH: FIGHT_CLUB_RENAMED_PATH},
    )

    run = await _run(db, FakeBrave(), site)

    assert site.requested == [FIGHT_CLUB_UK, FIGHT_CLUB_RENAMED]
    assert (run.status, run.fetched, run.applied, run.fetch_failed, run.sent_back) == (
        "finished",
        1,
        1,
        0,
        0,
    )
    await db.refresh(lookup)
    assert (lookup.status, lookup.accepted_url, lookup.last_error) == (
        "done",
        FIGHT_CLUB_RENAMED,
        None,
    )
    await db.refresh(disc)
    assert disc.specs_source_url == FIGHT_CLUB_RENAMED
    assert disc.video_specs and disc.audio_specs


async def test_craigs_own_page_that_moved_is_kept_at_its_new_address(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    film = await _film(db, "Fight Club (Brad Pitt)", year=None, tmdb_id=None)
    disc, lookup = await _accepted(db, film, FIGHT_CLUB_UK, how="pasted")
    lookup.decided_by = craig.id
    await db.commit()
    site = FakeBlurayCom(
        {FIGHT_CLUB_RENAMED_PATH: FIGHT_CLUB_PAGE},
        moved={FIGHT_CLUB_UK_PATH: FIGHT_CLUB_RENAMED},
    )

    run = await _run(db, FakeBrave(), site)

    assert run.applied == 1
    await db.refresh(lookup)
    assert (lookup.status, lookup.how, lookup.accepted_url) == (
        "done",
        "pasted",
        FIGHT_CLUB_RENAMED,
    )
    await db.refresh(disc)
    assert disc.specs_source_url == FIGHT_CLUB_RENAMED


async def test_a_page_sent_anywhere_else_goes_straight_back_to_craig(db: AsyncSession) -> None:
    """Not after three batches, and the other address is never requested."""
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc, lookup = await _accepted(db, film, FIGHT_CLUB_UK)
    site = FakeBlurayCom(
        {"/movies/Fight-Club-Blu-ray/5587/": FIGHT_CLUB_PAGE},
        moved={FIGHT_CLUB_UK_PATH: FIGHT_CLUB_US},
    )

    run = await _run(db, FakeBrave(), site)

    assert site.requested == [FIGHT_CLUB_UK]
    assert (run.fetched, run.applied, run.sent_back, run.fetch_failed) == (0, 0, 1, 0)
    await db.refresh(lookup)
    assert (lookup.status, lookup.accepted_url, lookup.how, lookup.attempts) == (
        "needs_you",
        None,
        None,
        0,
    )
    assert FIGHT_CLUB_US in (lookup.note or "")
    assert "not the same release page" in (lookup.note or "")
    await db.refresh(disc)
    assert disc.specs_source_url is None
    assert (await get_state(db)).halted is False


async def test_a_429_from_the_new_address_halts_the_integration(db: AsyncSession) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    _disc_row, lookup = await _accepted(db, film, FIGHT_CLUB_UK)
    site = FakeBlurayCom(
        {},
        moved={FIGHT_CLUB_UK_PATH: FIGHT_CLUB_RENAMED_PATH},
        refusing=frozenset({FIGHT_CLUB_RENAMED_PATH}),
    )

    run = await _run(db, FakeBrave(), site)

    assert run.status == "halted"
    assert (await get_state(db)).halted is True
    await db.refresh(lookup)
    assert (lookup.status, lookup.accepted_url) == ("accepted", FIGHT_CLUB_UK)


async def test_the_new_address_waits_its_turn_like_any_request(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#110's five seconds come before the second request, and before the next disc's."""
    import src.services.specs.runner as runner

    events: list[str] = []

    async def sleep(seconds: float) -> None:
        events.append(f"pause {seconds}")

    monkeypatch.setattr(runner, "asyncio", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(backfill, "asyncio", SimpleNamespace(sleep=sleep))
    first = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    second = await _film(db, "Fight Club Again", year=1999, tmdb_id=990_000_551)
    await _accepted(db, first, FIGHT_CLUB_UK)
    other = "https://www.blu-ray.com/movies/Fight-Club-Again-Blu-ray/7000/"
    # Fetched in the order they were accepted.
    await _accepted(db, second, other, decided=NOW - timedelta(hours=17))
    site = FakeBlurayCom(
        {
            FIGHT_CLUB_RENAMED_PATH: FIGHT_CLUB_PAGE,
            "/movies/Fight-Club-Again-Blu-ray/7000/": FIGHT_CLUB_PAGE,
        },
        moved={FIGHT_CLUB_UK_PATH: FIGHT_CLUB_RENAMED_PATH},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        events.append(f"GET {request.url}")
        return site.handler(request)

    outcome = await start_run(db, trigger="job", search_configured=False, now=NOW)
    assert outcome.run is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        run = await work_run(
            db, outcome.run.id, searcher=FakeBrave(), client=client, clock=lambda: NOW, pause=5.0
        )

    assert run.applied == 2
    assert events == [
        f"GET {FIGHT_CLUB_UK}",
        "pause 5.0",
        f"GET {FIGHT_CLUB_RENAMED}",
        "pause 5.0",
        f"GET {other}",
    ]


async def test_five_pages_sent_elsewhere_in_a_row_stop_the_batch(db: AsyncSession) -> None:
    """A site sending every page elsewhere costs five discs, not a whole batch of them."""
    for number in range(6):
        film = await _film(db, f"Moved Film {number}", year=1999, tmdb_id=990_100_000 + number)
        await _accepted(
            db, film, f"https://www.blu-ray.com/movies/Moved-Film-{number}-Blu-ray/{8000 + number}/"
        )
    site = FakeBlurayCom(
        {},
        moved={
            f"/movies/Moved-Film-{number}-Blu-ray/{8000 + number}/": "/community/login.php"
            for number in range(6)
        },
    )

    run = await _run(db, FakeBrave(), site)

    assert run.status == "stopped"
    assert len(site.requested) == 5
    assert run.sent_back == 5
    still_accepted = await db.scalar(
        select(func.count()).select_from(SpecLookup).where(SpecLookup.status == "accepted")
    )
    assert still_accepted == 1


# ---------------------------------------------------------------------------
# Searched again once the film is identified — Batch T10
# ---------------------------------------------------------------------------

NO_UK_PAGE = "No UK page matched this film's name and format. Pick one, paste a link, or skip."
FIGHT_CLUB_QUERY = "site:blu-ray.com Fight Club Blu-ray United Kingdom"
FILLER_QUERY = "site:blu-ray.com Filler Film Blu-ray United Kingdom"


async def _identified(db: AsyncSession, title: str, *, year: int, tmdb_id: int) -> Movie:
    """A film identified an hour before the batch, as T9's live run or Craig did."""
    film = await _film(db, title, year=year, tmdb_id=tmdb_id)
    film.last_tmdb_sync_utc = NOW - timedelta(hours=1)
    await db.flush()
    return film


async def _searched_earlier(
    db: AsyncSession,
    film: Movie,
    *,
    query: str,
    note: str = NO_UK_PAGE,
    searched: datetime = NOW - timedelta(days=2),
    decided_by: uuid.UUID | None = None,
    hits: tuple[tuple[str, str], ...] = (),
) -> tuple[CollectionItem, SpecLookup]:
    """A disc a batch searched and left for Craig, with what that search found."""
    disc = await _disc(db, film, "blu_ray")
    lookup = SpecLookup(
        id=uuid.uuid4(),
        collection_item_id=disc.id,
        status="needs_you",
        note=note,
        search_query=query,
        searched_utc=searched,
        decided_by=decided_by,
        attempts=0,
    )
    db.add(lookup)
    await db.flush()
    for rank, (url, title) in enumerate(hits):
        db.add(
            SpecCandidate(
                id=uuid.uuid4(),
                lookup_id=lookup.id,
                url=url,
                title=title,
                rank=rank,
                matches=False,
                origin="search",
            )
        )
    await db.commit()
    return disc, lookup


async def _filler(db: AsyncSession, title: str = "Filler Film", tmdb_id: int = 990_009_999) -> None:
    """A disc never searched, so a batch has something of its own to do."""
    await _disc(db, await _film(db, title, year=2000, tmdb_id=tmdb_id), "blu_ray")


async def test_a_disc_searched_under_a_misspelt_title_is_searched_again_once_identified(
    db: AsyncSession,
) -> None:
    """Captain Ameica, 25 Sep: its results came from the spreadsheet's spelling."""
    film = await _identified(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc, lookup = await _searched_earlier(
        db,
        film,
        query="site:blu-ray.com Fight Clubb Blu-ray United Kingdom",
        hits=(
            (
                "https://www.blu-ray.com/movies/Fight-Night-Blu-ray/1/",
                "Fight Night Blu-ray (United Kingdom)",
            ),
        ),
    )
    brave = FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK})
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/6715/": FIGHT_CLUB_PAGE})

    run = await _run(db, brave, site)

    assert brave.queries == [FIGHT_CLUB_QUERY]
    assert (run.searched, run.searched_again, run.settled_again, run.applied) == (1, 1, 1, 1)
    await db.refresh(lookup)
    await db.refresh(disc)
    assert (lookup.status, lookup.how, lookup.accepted_url) == ("done", "auto", FIGHT_CLUB_UK)
    assert (lookup.search_query, lookup.searched_utc, lookup.run_id) == (
        FIGHT_CLUB_QUERY,
        NOW,
        run.id,
    )
    assert disc.specs_source_url == FIGHT_CLUB_UK
    # The old title's result is gone; the new search's are what Craig would see.
    kept = await db.scalars(select(SpecCandidate.url).where(SpecCandidate.lookup_id == lookup.id))
    assert set(kept.all()) == {FIGHT_CLUB_UK, FIGHT_CLUB_US}


async def test_a_disc_is_searched_again_only_once(db: AsyncSession) -> None:
    film = await _identified(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    _disc_row, lookup = await _searched_earlier(
        db, film, query="site:blu-ray.com Fight Clubb Blu-ray United Kingdom"
    )
    await _filler(db)
    # Three UK editions: the second search leaves it for Craig too.
    first = await _run(db, FakeBrave({"Fight Club": FIGHT_CLUB_THREE_UK}), FakeBlurayCom({}))
    assert (first.searched_again, first.settled_again) == (1, 0)
    await db.refresh(lookup)
    assert lookup.status == "needs_you"
    assert "3 UK editions match" in (lookup.note or "")
    await _filler(db, "Second Filler", 990_009_998)

    brave = FakeBrave({"Fight Club": FIGHT_CLUB_ONE_UK})
    second = await _run(db, brave, FakeBlurayCom({}), now=NOW + timedelta(days=1))

    assert FIGHT_CLUB_QUERY not in brave.queries
    assert second.searched_again == 0


async def test_discs_not_to_search_again_are_left_as_they_are(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    before = await _identified(db, "Identified Before", year=2001, tmdb_id=990_003_001)
    # Identified an hour before the batch, but searched after that, under its own title.
    _a, searched_since = await _searched_earlier(
        db,
        before,
        query="site:blu-ray.com Identified Before Blu-ray United Kingdom",
        searched=NOW - timedelta(minutes=30),
    )
    # The kept film of a merge: identified again, but its words have not changed.
    same = await _identified(db, "Same Words", year=2002, tmdb_id=990_003_002)
    _b, same_words = await _searched_earlier(
        db, same, query="site:blu-ray.com Same Words Blu-ray United Kingdom"
    )
    # Craig chose this disc's page himself, and it would not load.
    chosen = await _identified(db, "Craigs Choice", year=2003, tmdb_id=990_003_003)
    _c, decided = await _searched_earlier(
        db,
        chosen,
        query="site:blu-ray.com Craigs Chioce Blu-ray United Kingdom",
        note="The page would not load after 3 tries.",
        decided_by=craig.id,
    )
    # Its page failed the year check: searching again could accept that page anew.
    remake = await _identified(db, "Year Checked", year=2004, tmdb_id=990_003_004)
    _d, year_failed = await _searched_earlier(
        db,
        remake,
        query="site:blu-ray.com Year Chekced Blu-ray United Kingdom",
        note="The page is for a 1960 film and this one is from 2004, so its specs were not used.",
    )
    # Still unidentified: nothing new to search under.
    unmatched = await _film(db, "Still Unmatched", year=None, tmdb_id=None)
    _e, not_identified = await _searched_earlier(
        db, unmatched, query="site:blu-ray.com Still Unmatchd Blu-ray United Kingdom"
    )
    await _filler(db)
    brave = FakeBrave()

    run = await _run(db, brave, FakeBlurayCom({}))

    assert brave.queries == [FILLER_QUERY]
    assert run.searched_again == 0
    for lookup in (searched_since, same_words, decided, year_failed, not_identified):
        searched_utc = lookup.searched_utc
        await db.refresh(lookup)
        assert (lookup.status, lookup.searched_utc) == ("needs_you", searched_utc)


async def test_discs_searched_again_come_first_and_count_in_the_budget(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backfill, "SEARCHES_PER_RUN", 1)
    film = await _identified(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    await _searched_earlier(db, film, query="site:blu-ray.com Fight Clubb Blu-ray United Kingdom")
    await _filler(db)
    brave = FakeBrave()

    run = await _run(db, brave, FakeBlurayCom({}))

    assert brave.queries == [FIGHT_CLUB_QUERY]
    assert (run.status, run.searches, run.searched_again) == ("budget_spent", 1, 1)


async def test_a_batch_starts_when_only_a_search_again_is_due(db: AsyncSession) -> None:
    film = await _identified(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    await _searched_earlier(db, film, query="site:blu-ray.com Fight Clubb Blu-ray United Kingdom")
    brave = FakeBrave()

    run = await _run(db, brave, FakeBlurayCom({}))

    assert brave.queries == [FIGHT_CLUB_QUERY]
    assert (run.searched, run.searched_again, run.no_match) == (1, 1, 1)


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


# ---------------------------------------------------------------------------
# Editions — Batch U2, `DECISIONS.md` #220
# ---------------------------------------------------------------------------

FIGHT_CLUB_STEELBOOK = "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/41252/"
HEAT_UK = "https://www.blu-ray.com/movies/Heat-Blu-ray/7000/"


def _one_uk(title: str = "Fight Club Blu-ray (MetalPak) (United Kingdom)") -> list[SearchHit]:
    """One UK edition of the film on Blu-ray, and a US one beside it."""
    return [hit(FIGHT_CLUB_UK, title), hit(FIGHT_CLUB_US, "Fight Club Blu-ray (10th Anniversary)")]


async def test_the_one_uk_edition_the_search_found_gives_the_disc_its_edition(
    db: AsyncSession,
) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom({FIGHT_CLUB_UK_PATH: FIGHT_CLUB_PAGE})

    run = await _run(db, FakeBrave({"Fight Club": _one_uk()}), site)

    assert run.applied == 1
    await db.refresh(disc)
    assert disc.edition == "MetalPak"
    # Batch X9 (CT46-05): inferred, so the copy page reads "probably" until a person confirms.
    assert disc.edition_source == "only_uk_edition"


async def test_the_plain_one_among_several_uk_editions_gives_none(db: AsyncSession) -> None:
    """#212's bet is good enough for specs, and says nothing about which box is on the shelf,
    even when the page it settles on names a publisher's line."""
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    hits = [
        hit(FIGHT_CLUB_UK, "Fight Club Blu-ray (Masters of Cinema) (United Kingdom)"),
        hit(FIGHT_CLUB_STEELBOOK, "Fight Club Blu-ray (SteelBook) (United Kingdom)"),
    ]
    site = FakeBlurayCom({FIGHT_CLUB_UK_PATH: FIGHT_CLUB_PAGE})

    run = await _run(db, FakeBrave({"Fight Club": hits}), site)

    assert (run.accepted, run.applied) == (1, 1)
    await db.refresh(disc)
    assert (disc.specs_source_url, disc.edition) == (FIGHT_CLUB_UK, None)


async def test_craigs_choice_from_the_list_gives_the_edition_he_chose(db: AsyncSession) -> None:
    craig = await _person(db, UserRole.admin)
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    brave = FakeBrave({"Fight Club": FIGHT_CLUB_THREE_UK})
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/41252/": FIGHT_CLUB_PAGE})
    await _run(db, brave, site)
    lookup = await _lookup(db, disc)
    await accept_page(db, lookup.id, FIGHT_CLUB_STEELBOOK, by=craig.id)

    run = await _run(db, brave, site, now=NOW + timedelta(days=1))

    assert run.applied == 1
    await db.refresh(disc)
    assert (disc.edition, disc.edition_source) == ("Play Exclusive SteelBook", "chosen")


async def test_a_page_craig_pasted_that_the_search_never_offered_gives_none(
    db: AsyncSession,
) -> None:
    """It is certainly the copy, but nothing says what the page is called."""
    craig = await _person(db, UserRole.admin)
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    brave = FakeBrave({"Fight Club": FIGHT_CLUB_THREE_UK})
    site = FakeBlurayCom({"/movies/Fight-Club-Blu-ray/99999/": FIGHT_CLUB_PAGE})
    await _run(db, brave, site)
    lookup = await _lookup(db, disc)
    await accept_page(
        db, lookup.id, "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/99999/", by=craig.id
    )

    run = await _run(db, brave, site, now=NOW + timedelta(days=1))

    assert run.applied == 1
    await db.refresh(lookup)
    assert lookup.how == "pasted"
    await db.refresh(disc)
    assert disc.edition is None


async def test_an_edition_already_on_the_disc_is_never_replaced(db: AsyncSession) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray", edition="Bought in Fopp, the tin one")
    site = FakeBlurayCom({FIGHT_CLUB_UK_PATH: FIGHT_CLUB_PAGE})

    await _run(db, FakeBrave({"Fight Club": _one_uk()}), site)

    await db.refresh(disc)
    assert (disc.edition, disc.edition_source) == ("Bought in Fopp, the tin one", None)


async def test_a_page_that_moved_gives_no_edition_from_its_old_name(db: AsyncSession) -> None:
    """Batch U1: a renamed page keeps its number, not necessarily what its old name said."""
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    site = FakeBlurayCom(
        {FIGHT_CLUB_RENAMED_PATH: FIGHT_CLUB_PAGE},
        moved={FIGHT_CLUB_UK_PATH: FIGHT_CLUB_RENAMED_PATH},
    )

    run = await _run(db, FakeBrave({"Fight Club": _one_uk()}), site)

    assert run.applied == 1
    await db.refresh(disc)
    assert (disc.specs_source_url, disc.edition) == (FIGHT_CLUB_RENAMED, None)


async def test_a_result_cut_short_before_its_country_leaves_the_edition_blank(
    db: AsyncSession,
) -> None:
    """ "I, Robot Blu-ray (Zavvi Exclusive SteelBook ..." was a result on 26 Sep: it could be a
    second UK edition, so the one the matcher accepted may not be the box on the shelf."""
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    hits = [
        hit(FIGHT_CLUB_UK, "Fight Club Blu-ray (MetalPak) (United Kingdom)"),
        hit(FIGHT_CLUB_STEELBOOK, "Fight Club Blu-ray (Zavvi Exclusive SteelBook ..."),
    ]
    site = FakeBlurayCom({FIGHT_CLUB_UK_PATH: FIGHT_CLUB_PAGE})

    run = await _run(db, FakeBrave({"Fight Club": hits}), site)

    assert run.applied == 1
    await db.refresh(disc)
    assert (disc.specs_source_url, disc.edition) == (FIGHT_CLUB_UK, None)


async def test_the_one_off_fills_discs_settled_before_editions_existed(db: AsyncSession) -> None:
    film = await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550)
    disc = await _disc(db, film, "blu_ray")
    await _run(
        db,
        FakeBrave({"Fight Club": _one_uk()}),
        FakeBlurayCom({FIGHT_CLUB_UK_PATH: FIGHT_CLUB_PAGE}),
    )
    # As the 430 discs settled before Batch U2 were: no edition, so nothing inferred.
    disc.edition = None
    disc.edition_source = None
    await db.commit()

    found = await editions_to_fill(db)
    written = await fill_editions(db, found)
    again = await editions_to_fill(db)

    assert [(entry.item_id, entry.kind, entry.edition) for entry in found] == [
        (disc.id, "only_uk_edition", "MetalPak")
    ]
    assert written == 1
    await db.refresh(disc)
    assert (disc.edition, disc.edition_source) == ("MetalPak", "only_uk_edition")
    assert again == []


async def test_forgetting_blu_ray_com_takes_its_editions_and_leaves_typed_ones(
    db: AsyncSession,
) -> None:
    """#110: everything derived from the site can be removed. A corrected edition is Craig's."""
    craig = await _person(db, UserRole.admin)
    fight_club = await _disc(
        db, await _film(db, "Fight Club", year=1999, tmdb_id=990_000_550), "blu_ray"
    )
    heat = await _disc(db, await _film(db, "Heat", year=1999, tmdb_id=990_000_949), "blu_ray")
    brave = FakeBrave(
        {
            "Fight Club": _one_uk(),
            "Heat": [hit(HEAT_UK, "Heat Blu-ray (SteelBook) (United Kingdom)")],
        }
    )
    site = FakeBlurayCom(
        {FIGHT_CLUB_UK_PATH: FIGHT_CLUB_PAGE, "/movies/Heat-Blu-ray/7000/": FIGHT_CLUB_PAGE}
    )
    await _run(db, brave, site)
    await db.refresh(heat)
    assert heat.edition == "SteelBook"
    # Craig's correction, as the copy form writes it: his, so no longer the job's guess.
    heat.edition = "Ultimate Hi-Def Edition"
    heat.edition_source = None
    await db.commit()
    fight_club_id, heat_id = fight_club.id, heat.id

    async with _as(db, craig) as client:
        response = await client.delete("/api/v1/specs")

    assert response.status_code == 200, response.text
    forgotten = await db.get(CollectionItem, fight_club_id)
    kept = await db.get(CollectionItem, heat_id)
    assert forgotten is not None and kept is not None
    await db.refresh(forgotten)
    await db.refresh(kept)
    assert (forgotten.specs_source_url, forgotten.edition) == (None, None)
    assert forgotten.edition_source is None
    assert (kept.specs_source_url, kept.edition) == (None, "Ultimate Hi-Def Edition")


class ExplodingBrave(FakeBrave):
    """A search that fails in a way nothing expects, as a library bug or an outage would."""

    async def search(self, query: str, *, count: int = 20, country: str = "GB") -> list[SearchHit]:
        self.search_calls += 1
        raise RuntimeError("Brave's client fell over")


async def test_an_unexpected_failure_mid_run_is_recorded_rather_than_left_running(
    db: AsyncSession,
) -> None:
    """X9's guard (CR43-02's class): every run loop has a failure-injection test. A run the
    process lost would read "running" until it was abandoned; this one says why it stopped."""
    film = await _film(db, "Exploding Film", year=2000, tmdb_id=990_003_000)
    await _disc(db, film, "blu_ray")
    outcome = await start_run(db, trigger="job", search_configured=True, now=NOW)
    assert outcome.run is not None
    run_id = outcome.run.id

    with pytest.raises(RuntimeError, match="fell over"):
        async with FakeBlurayCom({}).client() as client:
            await work_run(
                db, run_id, searcher=ExplodingBrave(), client=client, clock=lambda: NOW, pause=0
            )

    stopped = await db.get(SpecRun, run_id)
    assert stopped is not None
    assert (stopped.status, stopped.last_error) == (
        "stopped",
        "RuntimeError: Brave's client fell over",
    )
    assert stopped.searches == 1
