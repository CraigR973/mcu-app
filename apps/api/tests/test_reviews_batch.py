"""Batch V9's reviews batch and the pages that show reviews — against Postgres (CI).

Brave is a stand-in that answers with Brave's real answers for Dog Soldiers (3 Oct), and
Blu-ray.com is a mock transport serving the two captured pages, so every request the batch
makes is visible and counted. Nothing here reaches either site.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.reviews import FilmReview, ReviewRun
from src.models.specs_backfill import SpecCandidate, SpecLookup
from src.models.specs_state import SpecsIntegrationState
from src.models.wanted import WantedItem
from src.routers.movies import get_tmdb_client
from src.services.reviews import batch
from src.services.specs.backfill import searches_this_month
from src.services.specs.search import BraveError, SearchHit, hits_from_payload

FIXTURES = Path(__file__).parent / "fixtures"
REVIEW_PAGE = (FIXTURES / "bluray_com_review_page_4k.html").read_text(encoding="utf-8")
NO_REVIEW_PAGE = (FIXTURES / "bluray_com_release_page_no_review.html").read_text(encoding="utf-8")
BRAVE = {
    "bluray_com": hits_from_payload(
        json.loads((FIXTURES / "brave_bluray_com_dog_soldiers_4k.json").read_text(encoding="utf-8"))
    ),
    "avforums": hits_from_payload(
        json.loads((FIXTURES / "brave_avforums_dog_soldiers_4k.json").read_text(encoding="utf-8"))
    ),
}

US_4K = "https://www.blu-ray.com/movies/Dog-Soldiers-4K-Blu-ray/314666/"
UK_4K = "https://www.blu-ray.com/movies/Dog-Soldiers-4K-Blu-ray/315545/"
AVFORUMS_4K = "https://www.avforums.com/reviews/dog-soldiers-4k-blu-ray-review-dolby-vision.20024/"
NOW = datetime(2026, 10, 3, 2, 30)


class FakeBrave:
    """Brave, answering with its real 3 Oct answers, or failing."""

    def __init__(self, answers: dict[str, list[SearchHit]] | None = None, *, fail: bool = False):
        self.answers = BRAVE if answers is None else answers
        self.fail = fail
        self.search_calls = 0
        self.queries: list[str] = []

    @property
    def configured(self) -> bool:
        return True

    @property
    def attempts_per_search(self) -> int:
        return 1

    async def search(self, query: str, *, count: int = 20, country: str = "GB") -> list[SearchHit]:
        del count, country
        self.search_calls += 1
        self.queries.append(query)
        if self.fail:
            raise BraveError("Brave search failed (HTTP 402)", 402)
        return self.answers["avforums" if "avforums" in query else "bluray_com"]


class Site:
    """Blu-ray.com, serving the captured pages, recording each request."""

    def __init__(self, pages: dict[str, httpx.Response] | None = None) -> None:
        self.pages = pages or {
            US_4K: httpx.Response(200, text=REVIEW_PAGE),
            UK_4K: httpx.Response(200, text=NO_REVIEW_PAGE),
        }
        self.asked: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.asked.append(url)
        reply = self.pages.get(url)
        return reply if reply is not None else httpx.Response(404, text="not here")

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _film(db: AsyncSession, title: str = "Dog Soldiers", year: int | None = 2002) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
    )
    db.add(movie)
    await db.flush()
    return movie


async def _want(db: AsyncSession, movie: Movie, fmt: str | None = "4k_uhd") -> WantedItem:
    want = WantedItem(
        id=uuid.uuid4(), movie_id=movie.id, preferred_format=fmt, currency="GBP", is_active=True
    )
    db.add(want)
    await db.flush()
    return want


async def _owned(db: AsyncSession, movie: Movie, formats: list[str], spec_page: str | None) -> None:
    db.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=formats,
            specs_source_url=spec_page,
            specs_fetched_at_utc=NOW if spec_page else None,
        )
    )
    await db.flush()


async def _reviews(db: AsyncSession, film: Movie | uuid.UUID) -> dict[str, FilmReview]:
    """A film's review rows by site and format. Pass the id after a batch that may roll
    back: a rollback expires every loaded object, and reading one in an async session fails."""
    movie_id = film if isinstance(film, uuid.UUID) else film.id
    rows = (await db.execute(select(FilmReview).where(FilmReview.movie_id == movie_id))).scalars()
    return {f"{row.site}:{row.format_code}": row for row in rows}


async def _nightly(db: AsyncSession, brave: FakeBrave, site: Site, **kwargs: object) -> ReviewRun:
    run = await batch.start_run(db, trigger="job", now=NOW)
    assert run is not None
    async with site.client() as client:
        return await batch.work_run(
            db,
            run,
            searcher=brave,
            client=client,
            clock=lambda: NOW,
            pause=0,
            **kwargs,  # type: ignore[arg-type]
        )


class TestTheNightlyBatch:
    async def test_a_want_is_searched_on_both_sites_and_blu_ray_com_s_scores_read(
        self, db: AsyncSession
    ) -> None:
        movie = await _film(db)
        await _want(db, movie, "4k_uhd")
        brave, site = FakeBrave(), Site()

        run = await _nightly(db, brave, site)

        rows = await _reviews(db, movie)
        scored = rows["bluray_com:4k_uhd"]
        assert scored.status == "scored"
        assert scored.url == US_4K
        assert scored.found_via == "brave"
        assert scored.scores == [
            {"heading": "Movie", "score": 3.5},
            {"heading": "Video 4K", "score": 4.0},
            {"heading": "Video 2K", "score": 4.5},
            {"heading": "Audio", "score": 3.5},
            {"heading": "Extras", "score": 5.0},
            {"heading": "Overall", "score": 4.0},
        ]
        assert (scored.overall, scored.out_of, scored.scores_read_utc) == (Decimal("4.0"), 5, NOW)
        link = rows["avforums:4k_uhd"]
        assert (link.status, link.url, link.scores) == ("found", AVFORUMS_4K, None)
        assert link.description and "Dolby Vision" in link.description
        # Two searches, one page read: finding sent neither site anything.
        assert (run.status, run.searches, run.found, run.fetched, run.scored) == (
            "finished",
            2,
            2,
            1,
            1,
        )
        assert site.asked == [US_4K]
        assert await searches_this_month(db, now=NOW) == 2

    async def test_a_page_without_the_review_is_followed_to_the_edition_that_has_it(
        self, db: AsyncSession
    ) -> None:
        """An owned disc's spec page is the UK release, which links the US 4K (#241)."""
        movie = await _film(db)
        await _owned(db, movie, ["4k_uhd"], UK_4K)
        brave, site = FakeBrave(), Site()

        run = await _nightly(db, brave, site)

        row = (await _reviews(db, movie))["bluray_com:4k_uhd"]
        assert (row.status, row.found_via, row.url, row.found_url) == (
            "scored",
            "spec_page",
            US_4K,
            UK_4K,
        )
        assert row.overall == Decimal("4.0")
        assert site.asked == [UK_4K, US_4K]
        # Owned films need no search.
        assert brave.search_calls == 0
        assert (run.fetched, run.scored) == (2, 1)

    async def test_another_year_s_page_is_not_used(self, db: AsyncSession) -> None:
        movie = await _film(db, year=1990)
        await _owned(db, movie, ["4k_uhd"], UK_4K)
        site = Site()

        await _nightly(db, FakeBrave(), site)

        row = (await _reviews(db, movie))["bluray_com:4k_uhd"]
        assert row.status == "mismatch"
        assert (
            row.note
            == "The page is for a 2002 film and this one is from 1990, so its review was not used."
        )
        assert site.asked == [UK_4K], "nothing followed from another film's page"

    async def test_a_review_of_the_films_own_title_in_another_year_raises_a_doubt(
        self, db: AsyncSession
    ) -> None:
        """Batch X9 (CT46-03): the page may be right and the identified film wrong."""
        movie = await _film(db, year=1990)
        movie.tmdb_id = 990_046_001
        disc = CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=["4k_uhd"],
            specs_source_url=UK_4K,
            specs_fetched_at_utc=NOW,
        )
        db.add(disc)
        await db.flush()
        lookup = SpecLookup(
            id=uuid.uuid4(),
            collection_item_id=disc.id,
            status="done",
            accepted_url=UK_4K,
            how="auto",
            attempts=0,
        )
        db.add(lookup)
        await db.flush()
        db.add(
            SpecCandidate(
                id=uuid.uuid4(),
                lookup_id=lookup.id,
                url=UK_4K,
                title="Dog Soldiers 4K Blu-ray (United Kingdom)",
                rank=1,
                matches=True,
            )
        )
        await db.flush()

        await _nightly(db, FakeBrave(), Site())

        assert (await _reviews(db, movie))["bluray_com:4k_uhd"].status == "mismatch"
        doubt = await db.scalar(select(IdentifyDoubt).where(IdentifyDoubt.movie_id == movie.id))
        assert doubt is not None
        assert (doubt.source, doubt.status, doubt.search_hint) == (
            "review",
            "open",
            "Dog Soldiers 2002",
        )
        assert doubt.note.startswith("Blu-ray.com's review for “Dog Soldiers” is a 2002 film")

    async def test_a_429_halts_the_whole_integration(self, db: AsyncSession) -> None:
        movie = await _film(db)
        await _owned(db, movie, ["4k_uhd"], UK_4K)
        other = await _film(db, "Dog Soldiers Again")
        await _owned(db, other, ["4k_uhd"], US_4K)
        # Both refuse, so whichever is asked first, nothing is asked after it.
        site = Site({UK_4K: httpx.Response(429), US_4K: httpx.Response(429)})

        run = await _nightly(db, FakeBrave(), site)

        state = await db.get(SpecsIntegrationState, 1)
        assert state is not None and state.halted
        assert run.status == "halted"
        assert len(site.asked) == 1, "everything stops at the first refusal"
        # Left to read after an owner decision, not given up on.
        assert {row.status for row in (await _reviews(db, movie)).values()} == {"found"}

    async def test_a_halted_integration_reads_nothing(self, db: AsyncSession) -> None:
        state = await db.get(SpecsIntegrationState, 1)
        assert state is not None
        state.halted = True
        # Batch 23's CHECK: a halt names its reason and its time.
        state.halted_reason = "Blu-ray.com answered 403"
        state.halted_at_utc = NOW
        movie = await _film(db)
        await _owned(db, movie, ["4k_uhd"], UK_4K)
        site = Site()

        run = await _nightly(db, FakeBrave(), site)

        assert site.asked == []
        assert run.status == "halted"

    async def test_the_pause_comes_before_every_request(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#110's spacing is between any two requests, the spec batch's included."""
        waits: list[float] = []

        async def pause(seconds: float) -> None:
            waits.append(seconds)

        monkeypatch.setattr(batch, "_pause", pause)
        movie = await _film(db)
        await _owned(db, movie, ["4k_uhd"], UK_4K)
        site = Site()
        run = await batch.start_run(db, trigger="job", now=NOW)
        assert run is not None
        async with site.client() as client:
            await batch.work_run(
                db, run, searcher=FakeBrave(), client=client, clock=lambda: NOW, pause=5.0
            )

        assert waits == [5.0, 5.0]
        assert site.asked == [UK_4K, US_4K]

    async def test_the_night_s_requests_are_capped(self, db: AsyncSession) -> None:
        first = await _film(db)
        await _owned(db, first, ["4k_uhd"], UK_4K)
        second = await _film(db, "Dog Soldiers Again")
        await _owned(db, second, ["4k_uhd"], US_4K)
        site = Site()

        run = await _nightly(db, FakeBrave(), site, fetches_per_run=1)

        assert run.fetched == 1
        assert len(site.asked) == 1

    async def test_an_owned_film_s_spec_page_replaces_a_search_that_found_nothing(
        self, db: AsyncSession
    ) -> None:
        """A 4K want whose search found nothing, then the 4K disc bought and specced."""
        movie = await _film(db)
        db.add(
            FilmReview(
                id=uuid.uuid4(),
                movie_id=movie.id,
                site="bluray_com",
                format_code="4k_uhd",
                status="none",
                found_via="brave",
                found_utc=NOW,
            )
        )
        await _owned(db, movie, ["4k_uhd"], UK_4K)

        await _nightly(db, FakeBrave(), Site())

        row = (await _reviews(db, movie))["bluray_com:4k_uhd"]
        assert (row.status, row.found_via, row.url) == ("scored", "spec_page", US_4K)

    async def test_a_failed_search_leaves_the_want_to_try_again(self, db: AsyncSession) -> None:
        movie = await _film(db)
        movie_id = movie.id
        await _want(db, movie, "4k_uhd")

        run = await _nightly(db, FakeBrave(fail=True), Site())

        # Brave's failure rolled the session back, so the film is read by id.
        assert await _reviews(db, movie_id) == {}
        assert run.status == "stopped"
        assert run.last_error == "Dog Soldiers: Brave search failed (HTTP 402)"
        assert run.searches == 1, "the failed request was billed and counted"
        due = await batch.wants_to_search(db, now=NOW)
        assert [(want.title, site) for want, site in due] == [
            ("Dog Soldiers", "bluray_com"),
            ("Dog Soldiers", "avforums"),
        ]

    async def test_an_unexpected_failure_mid_run_is_recorded_rather_than_left_running(
        self, db: AsyncSession
    ) -> None:
        """X9's guard (CR43-02's class): every run loop has a failure-injection test. A run
        the process lost would read "running" until it was abandoned; this one says why."""

        class ExplodingBrave(FakeBrave):
            async def search(
                self, query: str, *, count: int = 20, country: str = "GB"
            ) -> list[SearchHit]:
                self.search_calls += 1
                raise RuntimeError("Brave's client fell over")

        movie = await _film(db)
        await _want(db, movie, "4k_uhd")
        run = await batch.start_run(db, trigger="job", now=NOW)
        assert run is not None
        run_id = run.id

        with pytest.raises(RuntimeError, match="fell over"):
            async with Site().client() as client:
                await batch.work_run(
                    db, run, searcher=ExplodingBrave(), client=client, clock=lambda: NOW, pause=0
                )

        stopped = await db.get(ReviewRun, run_id)
        assert stopped is not None
        await db.refresh(stopped)
        assert (stopped.status, stopped.last_error, stopped.searches) == (
            "stopped",
            "RuntimeError: Brave's client fell over",
            1,
        )

    async def test_nothing_found_is_recorded_and_searched_again_after_a_month(
        self, db: AsyncSession
    ) -> None:
        movie = await _film(db)
        await _want(db, movie, None)

        await _nightly(db, FakeBrave({"bluray_com": [], "avforums": []}), Site())

        rows = await _reviews(db, movie)
        assert {key: row.status for key, row in rows.items()} == {
            "bluray_com:None": "none",
            "avforums:None": "none",
        }
        assert await batch.wants_to_search(db, now=NOW + timedelta(days=29)) == []
        assert len(await batch.wants_to_search(db, now=NOW + timedelta(days=31))) == 2

    async def test_the_month_s_own_cap_holds(self, db: AsyncSession) -> None:
        movie = await _film(db)
        await _want(db, movie, "4k_uhd")
        db.add(
            ReviewRun(
                id=uuid.uuid4(),
                trigger="want_added",
                status="finished",
                started_utc=NOW - timedelta(days=1),
                heartbeat_utc=NOW - timedelta(days=1),
                searches=batch.MONTHLY_REVIEW_SEARCHES,
            )
        )
        await db.flush()
        brave = FakeBrave()

        run = await _nightly(db, brave, Site())

        assert brave.search_calls == 0
        assert run.searches == 0
        assert await _reviews(db, movie) == {}

    async def test_a_film_just_wanted_is_searched_at_once_and_read_overnight(
        self, db: AsyncSession
    ) -> None:
        movie = await _film(db)
        await _want(db, movie, "4k_uhd")
        brave = FakeBrave()

        run = await batch.search_for_want(db, movie.id, searcher=brave, clock=lambda: NOW)

        assert run is not None and (run.trigger, run.status, run.searches) == (
            "want_added",
            "finished",
            2,
        )
        rows = await _reviews(db, movie)
        assert {key: row.status for key, row in rows.items()} == {
            "bluray_com:4k_uhd": "found",
            "avforums:4k_uhd": "found",
        }


# ---------------------------------------------------------------------------
# The pages that show them
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin(db: AsyncSession) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"V9 admin {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.admin,
    )
    db.add(profile)
    await db.flush()
    return profile


@pytest_asyncio.fixture
async def client(db: AsyncSession, admin: Profile) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user(request: Request) -> Profile:
        del request
        return admin

    async def override_tmdb() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http
    finally:
        app.dependency_overrides.clear()


async def _scored(
    db: AsyncSession,
    movie: Movie,
    fmt: str,
    overall: str,
    *,
    scores: list[dict[str, float]] | None = None,
) -> None:
    db.add(
        FilmReview(
            id=uuid.uuid4(),
            movie_id=movie.id,
            site="bluray_com",
            format_code=fmt,
            status="scored",
            url=US_4K
            if fmt == "4k_uhd"
            else "https://www.blu-ray.com/movies/Dog-Soldiers-Blu-ray/4011/",
            found_via="spec_page",
            found_utc=NOW,
            scores=scores or [{"heading": "Overall", "score": float(overall)}],
            overall=Decimal(overall),
            out_of=5,
            scores_read_utc=NOW,
        )
    )
    await db.flush()


class TestThePagesShowTheReviews:
    async def test_a_want_shows_one_review_per_site(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        movie = await _film(db)
        await _want(db, movie, "4k_uhd")
        await _scored(db, movie, "4k_uhd", "4.0")
        db.add(
            FilmReview(
                id=uuid.uuid4(),
                movie_id=movie.id,
                site="avforums",
                format_code="4k_uhd",
                status="found",
                url=AVFORUMS_4K,
                found_via="brave",
                found_utc=NOW,
                description="The 4K image is stunning.",
            )
        )
        await db.flush()

        response = await client.get("/api/v1/wanted")

        assert response.status_code == 200, response.text
        item = next(row for row in response.json()["items"] if row["movieId"] == str(movie.id))
        assert [(review["siteName"], review["overall"]) for review in item["reviews"]] == [
            ("Blu-ray.com", 4.0),
            ("AVForums", None),
        ]
        assert item["reviews"][1]["note"].startswith("AVForums does not allow apps")

    async def test_the_film_page_shows_every_review_found(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        movie = await _film(db)
        await _scored(db, movie, "4k_uhd", "4.0")
        await _scored(db, movie, "blu_ray", "3.5")
        db.add(
            FilmReview(
                id=uuid.uuid4(),
                movie_id=movie.id,
                site="bluray_com",
                format_code="dvd",
                status="none",
                found_via="brave",
                found_utc=NOW,
            )
        )
        await db.flush()

        response = await client.get(f"/api/v1/movies/{movie.id}")

        assert response.status_code == 200, response.text
        assert [
            (review["formatCode"], review["overall"]) for review in response.json()["reviews"]
        ] == [
            ("4k_uhd", 4.0),
            ("blu_ray", 3.5),
        ]

    async def test_best_reviewed_ranks_the_shelf_by_a_format_it_is_on(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        owned_4k = await _film(db, "Owned In 4K")
        await _owned(db, owned_4k, ["4k_uhd"], None)
        await _scored(
            db,
            owned_4k,
            "4k_uhd",
            "4.5",
            scores=[
                {"heading": "Video 4K", "score": 4.0},
                {"heading": "Audio", "score": 4.5},
                {"heading": "Extras", "score": 3.5},
            ],
        )
        owned_blu_ray = await _film(db, "Owned On Blu-ray")
        await _owned(db, owned_blu_ray, ["blu_ray"], None)
        await _scored(db, owned_blu_ray, "blu_ray", "3.5")
        # A 4K review of a film owned only on DVD is not the shelf's.
        dvd_only = await _film(db, "Owned On DVD")
        await _owned(db, dvd_only, ["dvd"], None)
        await _scored(db, dvd_only, "4k_uhd", "5.0")

        response = await client.get("/api/v1/highlights")

        assert response.status_code == 200, response.text
        best = response.json()["bestReviewed"]
        assert [(film["title"], film["overall"], film["formatCode"]) for film in best] == [
            ("Owned In 4K", 4.5, "4k_uhd"),
            ("Owned On Blu-ray", 3.5, "blu_ray"),
        ]
        assert best[0]["strength"] == "sound"
        assert best[0]["scores"] == [
            {"heading": "Video 4K", "score": 4.0},
            {"heading": "Audio", "score": 4.5},
            {"heading": "Extras", "score": 3.5},
        ]

    async def test_adding_a_want_searches_for_its_reviews_after_the_response(
        self, db: AsyncSession, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        searched: list[uuid.UUID] = []

        async def record(movie_id: uuid.UUID) -> None:
            searched.append(movie_id)

        monkeypatch.setattr("src.routers.wanted.search_for_want_in_background", record)
        movie = await _film(db)

        response = await client.post(
            "/api/v1/wanted",
            json={"movieId": str(movie.id), "preferredFormat": "4k_uhd", "currency": "GBP"},
        )

        assert response.status_code == 201, response.text
        assert response.json()["reviews"] == []
        assert searched == [movie.id]
