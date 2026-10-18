"""The release calendar, asked by release type, and keeping itself fresh — Batch T5.

**Every property the old `/movie/upcoming` ingestion was tested for is kept here**, ported
to the discover-by-release-type source (Batches 17 and S6 wrote the originals): a film seen
on two pages is written once, a date that moves is updated in place, a page that fails keeps
the pages before it, the earliest disc date wins, VHS is not a release. What is new: disc
releases are not genre-filtered, and the calendar refreshes itself, once, when it is read
and stale.

TMDB is faked. The fake's shape is TMDB's: discover returns *films*, and each film's own GB
dates come from its release dates, because the date on a discover result is the premiere.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utc_today, utcnow
from src.database import get_db
from src.main import app
from src.models.profile import Profile, UserRole
from src.models.release_calendar import CalendarRefreshState, ReleaseCalendarEntry
from src.routers import calendar as calendar_router
from src.services.calendar import claim_refresh, ingest_releases, refresh_calendar
from src.tmdb.models import (
    CountryReleaseDates,
    ReleaseDate,
    ReleaseDates,
    SearchResult,
    SearchResults,
)

DISCS = "5"
CINEMA = "2|3"


class FakeDiscover:
    """TMDB's discover-by-release-type, and each film's GB release dates."""

    def __init__(
        self,
        pages: dict[str, dict[int, list[SearchResult]]],
        dates: dict[int, list[ReleaseDate]] | None = None,
        *,
        fail_page: tuple[str, int] | None = None,
        release_dates_raise: bool = False,
    ) -> None:
        self.pages = pages
        self.dates = dates or {}
        self.fail_page = fail_page
        self.release_dates_raise = release_dates_raise
        self.asked: list[tuple[str, int]] = []

    async def discover_by_release_type(
        self,
        *,
        region: str,
        release_types: str,
        date_from: date,
        date_to: date,
        page: int = 1,
        language: str = "en-US",
    ) -> SearchResults:
        del region, date_from, date_to, language
        self.asked.append((release_types, page))
        if self.fail_page == (release_types, page):
            raise RuntimeError("TMDB is down")
        pages = self.pages.get(release_types, {})
        results = pages.get(page, [])
        return SearchResults(
            page=page,
            total_pages=max(pages, default=0),
            total_results=len(results),
            results=results,
        )

    async def get_release_dates(self, movie_id: int) -> ReleaseDates:
        if self.release_dates_raise:
            raise RuntimeError("TMDB said no")
        return ReleaseDates(
            id=movie_id,
            results=[
                CountryReleaseDates(iso_3166_1="GB", release_dates=self.dates.get(movie_id, []))
            ],
        )


def _film(
    tmdb_id: int, title: str, premiere: date | None = None, *, genres: list[int] | None = None
) -> SearchResult:
    return SearchResult(
        id=tmdb_id,
        title=title,
        original_title=title,
        overview=f"About {title}.",
        release_date=(premiere or utc_today() - timedelta(days=200)).isoformat(),
        poster_path=f"/{tmdb_id}.jpg",
        genre_ids=genres if genres is not None else [53],
    )


def _on(day: date, kind: int, note: str = "") -> ReleaseDate:
    return ReleaseDate(release_date=f"{day.isoformat()}T00:00:00.000Z", type=kind, note=note)


def _in(days: int) -> date:
    return utc_today() + timedelta(days=days)


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _rows(db: AsyncSession, tmdb_id: int) -> list[ReleaseCalendarEntry]:
    return list(
        (
            await db.execute(
                select(ReleaseCalendarEntry).where(ReleaseCalendarEntry.tmdb_id == tmdb_id)
            )
        ).scalars()
    )


# ── Ported from Batches 17 and S6 ────────────────────────────────────────────


async def test_the_same_film_on_two_pages_is_written_once(db: AsyncSession) -> None:
    """TMDB's paginated lists are re-sorted between requests; the first live run hit it."""
    twice = _film(9_700_001, "A Disc On Two Pages")
    fake = FakeDiscover(
        {DISCS: {1: [twice], 2: [twice, _film(9_700_002, "Another Disc")]}},
        {9_700_001: [_on(_in(20), 5, "Blu-ray")], 9_700_002: [_on(_in(25), 5, "Blu-ray")]},
    )

    result = await ingest_releases(db, fake)

    assert result.errors == []
    assert len(await _rows(db, 9_700_001)) == 1
    assert len(await _rows(db, 9_700_002)) == 1


async def test_a_date_that_moves_is_updated_in_place(db: AsyncSession) -> None:
    """Running twice must be safe, and a moved date moves the event rather than adding one."""
    film = _film(9_700_011, "A Film Whose Date Moves")
    await ingest_releases(
        db, FakeDiscover({CINEMA: {1: [film]}}, {9_700_011: [_on(_in(10), 3)]}), genre_ids={53}
    )
    result = await ingest_releases(
        db, FakeDiscover({CINEMA: {1: [film]}}, {9_700_011: [_on(_in(13), 3)]}), genre_ids={53}
    )

    assert result.updated == 1
    (row,) = await _rows(db, 9_700_011)
    assert row.release_date == _in(13)


async def test_cinema_dates_keep_the_genres_of_interest(db: AsyncSession) -> None:
    thriller = _film(9_700_021, "A Thriller", genres=[53])
    documentary = _film(9_700_022, "A Documentary", genres=[99])
    fake = FakeDiscover(
        {CINEMA: {1: [thriller, documentary]}},
        {9_700_021: [_on(_in(10), 3)], 9_700_022: [_on(_in(10), 3)]},
    )

    await ingest_releases(db, fake, genre_ids={53})

    assert len(await _rows(db, 9_700_021)) == 1
    assert await _rows(db, 9_700_022) == []


async def test_disc_releases_are_not_genre_filtered(db: AsyncSession) -> None:
    """New in T5: a collector's disc calendar is about the discs, whatever the genre."""
    documentary = _film(9_700_023, "A Documentary On Disc", genres=[99])
    fake = FakeDiscover({DISCS: {1: [documentary]}}, {9_700_023: [_on(_in(30), 5, "4K Ultra HD")]})

    await ingest_releases(db, fake, genre_ids={53})

    assert [row.release_type for row in await _rows(db, 9_700_023)] == ["4k_uhd_release"]


async def test_a_date_already_past_or_beyond_the_horizon_is_not_written(db: AsyncSession) -> None:
    film = _film(9_700_031, "Out Of The Window")
    fake = FakeDiscover(
        {DISCS: {1: [film]}},
        {9_700_031: [_on(_in(-30), 5, "Blu-ray"), _on(_in(400), 5, "Blu-ray")]},
    )

    result = await ingest_releases(db, fake, horizon_days=183)

    assert await _rows(db, 9_700_031) == []
    assert result.physical_found == 0


async def test_a_failing_page_keeps_the_pages_before_it(db: AsyncSession) -> None:
    fake = FakeDiscover(
        {DISCS: {1: [_film(9_700_041, "From Page One")], 2: [_film(9_700_042, "From Page Two")]}},
        {9_700_041: [_on(_in(20), 5, "Blu-ray")], 9_700_042: [_on(_in(20), 5, "Blu-ray")]},
        fail_page=(DISCS, 2),
    )

    result = await ingest_releases(db, fake)

    assert any("page 2" in message for message in result.errors)
    assert len(await _rows(db, 9_700_041)) == 1


async def test_one_film_can_have_a_cinema_date_and_a_disc_date(db: AsyncSession) -> None:
    """Snag 2, and S6's "beside, not instead": two questions, two rows."""
    film = _film(9_700_051, "A Film In Both Lists")
    fake = FakeDiscover(
        {DISCS: {1: [film]}, CINEMA: {1: [film]}},
        {9_700_051: [_on(_in(10), 3), _on(_in(90), 5, "4k Ultra HD Blu-ray")]},
    )

    await ingest_releases(db, fake, genre_ids={53})

    kinds = {row.release_type: row.release_date for row in await _rows(db, 9_700_051)}
    assert kinds == {"theatrical": _in(10), "4k_uhd_release": _in(90)}


async def test_the_earliest_disc_date_of_one_format_wins(db: AsyncSession) -> None:
    """A re-release and a box set are both type 5; the constraint allows one row."""
    film = _film(9_700_061, "Released Twice On Disc")
    fake = FakeDiscover(
        {DISCS: {1: [film]}},
        # Later-first on purpose: the earliest must win on merit, not on payload order.
        {9_700_061: [_on(_in(60), 5, "Blu-ray Box Set"), _on(_in(30), 5, "Blu-ray")]},
    )

    await ingest_releases(db, fake)

    (row,) = await _rows(db, 9_700_061)
    assert row.release_type == "blu_ray_release"
    assert row.release_date == _in(30)


async def test_vhs_is_not_a_release(db: AsyncSession) -> None:
    film = _film(9_700_071, "Only On Tape")
    fake = FakeDiscover({DISCS: {1: [film]}}, {9_700_071: [_on(_in(20), 5, "VHS")]})

    await ingest_releases(db, fake)

    assert await _rows(db, 9_700_071) == []


async def test_a_failed_date_lookup_is_recorded_and_writes_nothing_for_that_film(
    db: AsyncSession,
) -> None:
    fake = FakeDiscover({DISCS: {1: [_film(9_700_081, "Not Discussed")]}}, release_dates_raise=True)

    result = await ingest_releases(db, fake)

    assert any("release_dates" in message for message in result.errors)
    assert await _rows(db, 9_700_081) == []


async def test_a_cinema_date_is_never_read_as_a_disc_date(db: AsyncSession) -> None:
    """Only the discs list may produce disc rows: a type-5 date on a film found through the
    cinema list alone is not in the window TMDB was asked about, so it is not claimed."""
    film = _film(9_700_091, "Cinema Only")
    fake = FakeDiscover(
        {CINEMA: {1: [film]}}, {9_700_091: [_on(_in(10), 3), _on(_in(40), 5, "Blu-ray")]}
    )

    await ingest_releases(db, fake, genre_ids={53})

    assert [row.release_type for row in await _rows(db, 9_700_091)] == ["theatrical"]


# ── The calendar keeps itself fresh ──────────────────────────────────────────


async def _state(db: AsyncSession) -> CalendarRefreshState:
    state = await db.get(CalendarRefreshState, 1)
    assert state is not None, "migration 035 seeds the one row"
    await db.refresh(state)
    return state


async def _set_state(db: AsyncSession, started: datetime | None, finished: datetime | None) -> None:
    await db.execute(
        update(CalendarRefreshState)
        .where(CalendarRefreshState.id == 1)
        .values(last_started_utc=started, last_finished_utc=finished)
    )
    await db.flush()


async def test_a_stale_calendar_can_be_claimed_once(db: AsyncSession) -> None:
    now = utcnow()
    await _set_state(db, now - timedelta(days=2), now - timedelta(days=2))

    assert await claim_refresh(db, now=now) is True
    assert await claim_refresh(db, now=now) is False, "a second reader must not start a second run"


async def test_a_fresh_calendar_is_not_refreshed_unless_forced(db: AsyncSession) -> None:
    now = utcnow()
    await _set_state(db, now - timedelta(hours=2), now - timedelta(hours=2))

    assert await claim_refresh(db, now=now) is False
    assert await claim_refresh(db, now=now, force=True) is True


async def test_a_run_that_started_long_ago_and_never_finished_is_taken_over(
    db: AsyncSession,
) -> None:
    now = utcnow()
    await _set_state(db, now - timedelta(hours=3), now - timedelta(days=2))

    assert await claim_refresh(db, now=now) is True


async def test_a_refresh_records_what_it_found(db: AsyncSession) -> None:
    now = utcnow()
    await _set_state(db, now - timedelta(days=2), now - timedelta(days=2))
    fake = FakeDiscover(
        {DISCS: {1: [_film(9_700_101, "Recorded Disc")]}}, {9_700_101: [_on(_in(15), 5, "4K UHD")]}
    )

    result = await refresh_calendar(db, fake, now=now)

    assert result is not None and result.physical_found == 1
    state = await _state(db)
    assert state.last_finished_utc is not None and state.last_finished_utc >= now
    assert state.last_disc_releases == 1
    assert state.last_error is None


async def test_a_refresh_also_fetches_again_the_films_whose_tmdb_data_is_150_days_old(
    db: AsyncSession,
) -> None:
    """Batch X12c (DS44-06): TMDB's terms bar caching its data over six months."""
    from src.models.movie import Movie
    from src.tmdb.models import Genre
    from src.tmdb.models import Movie as TmdbMovie

    now = utcnow()
    await _set_state(db, now - timedelta(days=2), now - timedelta(days=2))
    old = Movie(
        id=uuid.uuid4(),
        tmdb_id=9_700_901,
        title="Old Data",
        original_title="Old Data",
        media_type="film",
        overview="Stale.",
        last_tmdb_sync_utc=now - timedelta(days=200),
    )
    db.add(old)
    await db.flush()

    class WithFilms(FakeDiscover):
        failing = False

        async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
            del language
            if self.failing:
                raise RuntimeError("TMDB is down")
            return TmdbMovie(
                id=movie_id,
                title="New Data",
                original_title="New Data",
                overview="Fresh.",
                genres=[Genre(id=18, name="Drama")],
            )

    fake = WithFilms({DISCS: {1: []}}, {})
    result = await refresh_calendar(db, fake, now=now)

    assert result is not None and not result.errors
    await db.refresh(old)
    assert (old.title, old.overview) == ("New Data", "Fresh.")

    # TMDB down for the fields: the calendar still finishes, and says so.
    await _set_state(db, now - timedelta(days=2), now - timedelta(days=2))
    old.last_tmdb_sync_utc = now - timedelta(days=200)
    await db.flush()
    broken = WithFilms({DISCS: {1: []}}, {})
    broken.failing = True
    again = await refresh_calendar(db, broken, now=now)
    assert again is not None and any("TMDB is down" in e for e in again.errors)


@pytest_asyncio.fixture
async def viewer_client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    viewer = Profile(
        id=uuid.uuid4(), display_name=f"T5 {uuid.uuid4().hex[:8]}", role=UserRole.viewer
    )
    db.add(viewer)
    await db.flush()

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return viewer

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def test_reading_a_stale_calendar_starts_one_refresh(
    db: AsyncSession, viewer_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[str] = []

    async def recorder() -> None:
        started.append("refresh")

    monkeypatch.setattr(calendar_router, "refresh_calendar_if_stale", recorder)
    await _set_state(db, utcnow() - timedelta(days=2), utcnow() - timedelta(days=2))

    response = await viewer_client.get("/api/v1/calendar")

    assert response.status_code == 200
    assert started == ["refresh"]


async def test_reading_a_fresh_calendar_starts_nothing_and_says_how_fresh(
    db: AsyncSession, viewer_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[str] = []

    async def recorder() -> None:
        started.append("refresh")

    monkeypatch.setattr(calendar_router, "refresh_calendar_if_stale", recorder)
    finished = utcnow() - timedelta(hours=1)
    await _set_state(db, finished, finished)

    response = await viewer_client.get("/api/v1/calendar")

    assert started == []
    assert response.json()["refreshedAt"] is not None
