"""AC4: At the cinema, film first — the fortnight's films and listings, and one film's showings.

Real Postgres, rows written the way the refresh writes them (`store.promote`), no provider.
"""

import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.models.cinema import (
    CinemaCoverage,
    CinemaFilm,
    CinemaRefreshRun,
    CinemaScreening,
    CinemaVenue,
)
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.watch_log import WatchLog
from src.services.cinemas import films as reads
from src.services.cinemas import programme, refresh, store
from src.services.cinemas.domain import Snapshot, local_start
from src.services.cinemas.venues import BY_SLUG
from tests.test_cinemas import looked_up, showing
from tests.test_collection_write_api import admin as admin
from tests.test_collection_write_api import api_session as api_session
from tests.test_collection_write_api import client as client
from tests.test_collection_write_api import overrides as overrides
from tests.test_collection_write_api import viewer as viewer

NOW = datetime(2026, 11, 2, 8)
DAY = date(2026, 11, 2)
ODEON = BY_SLUG["odeon-braehead"]
VUE = BY_SLUG["vue-st-enoch"]
GFT = BY_SLUG["gft"]


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    for module in (reads, programme, store, refresh):
        monkeypatch.setattr(module, "utcnow", lambda: NOW)


@pytest_asyncio.fixture
async def run(api_session: AsyncSession):
    row = CinemaRefreshRun(
        id=uuid.uuid4(),
        trigger="test",
        adapter_version="ab6-1",
        status="running",
        started_utc=NOW,
        heartbeat_utc=NOW,
        lease_expires_utc=NOW + timedelta(minutes=10),
        request_count=0,
        bytes_received=0,
        report={},
    )
    api_session.add(row)
    await api_session.flush()
    return row


def at(day: date, hour: int = 20) -> datetime:
    return local_start(f"{day.isoformat()}T{hour:02d}:00:00")


async def promote(db, run, venue, rows, lookups=None, *, days=1):
    """One venue's listing of ``days`` days from today, as the refresh would store it."""
    end = DAY + timedelta(days=days - 1)
    observed = {DAY + timedelta(days=i) for i in range(days)}
    snapshot = Snapshot(rows=list(rows), observed_dates=observed, observed_utc=NOW)
    await store.promote(db, venue, snapshot, DAY, end, run.id, lookups)
    row = await db.get(CinemaVenue, venue.id)
    row.collection_enabled = True
    await db.flush()


async def test_both_reads_need_a_signed_in_person():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.get("/api/v1/cinemas/films")).status_code == 401
        assert (await http.get("/api/v1/cinemas/films/tmdb-603")).status_code == 401


async def test_an_empty_programme_still_names_the_fortnight_and_every_cinema(client):
    response = await client.get("/api/v1/cinemas/films")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["window"] == {"dateFrom": "2026-11-02", "dateTo": "2026-11-15"}
    assert data["thisWeekTo"] == "2026-11-08"
    # Every cinema named even with nothing listed; the Omniplex not until its first enable (AE4).
    assert len(data["venues"]) == 9
    assert "omniplex-glasgow-renfrew-street" not in {v["slug"] for v in data["venues"]}
    assert all(len(v["coverage"]) == 14 for v in data["venues"])
    assert data["films"] == [] and data["complete"] is False
    for key in ("nonsense", "tmdb-", "listing-123", "tmdb-603; drop"):
        assert (await client.get(f"/api/v1/cinemas/films/{key}")).status_code == 404
    # A film never listed, and a listing that does not exist, are not found either.
    assert (await client.get("/api/v1/cinemas/films/tmdb-424242")).status_code == 404
    assert (await client.get(f"/api/v1/cinemas/films/listing-{uuid.uuid4()}")).status_code == 404


async def test_one_film_at_two_chains_under_two_titles_is_one_film_with_both_cinemas(
    api_session: AsyncSession, run, admin: Profile, viewer: Profile
):
    """AC3's identity joins the chains; the film reads by TMDB's title, its poster and run."""
    db = api_session
    plain = showing(
        "odeon-1",
        film_key="shared",
        title="Shared Film",
        start=at(DAY),
        source_release=date(1986, 3, 1),
    )
    decorated = showing(
        "vue-1",
        film_key="vue-shared",
        title="Shared Film (40th Anniversary)",
        start=at(DAY + timedelta(days=9), 18),
        booking="https://www.myvue.com/book-tickets/summary/10097/1",
    )
    uk = ("1986-03-01",)
    await promote(
        db, run, ODEON, [plain], looked_up(plain, tmdb_id=991300, released="1986-01-01", uk=uk)
    )
    await promote(
        db,
        run,
        VUE,
        [decorated],
        looked_up(
            decorated, VUE, tmdb_id=991300, title="Shared Film", released="1986-01-01", uk=uk
        ),
        days=10,
    )
    result = await reads.films(db, admin.id)
    [card] = result.films
    assert card.key == "tmdb-991300" and card.kind == "film" and card.tmdbId == 991300
    assert card.title == "Shared Film" and card.identityStatus == "verified"
    assert card.sourceTitles == ["Shared Film", "Shared Film (40th Anniversary)"]
    assert card.originalYear == 1986 and card.yearConfidence == "verified"
    assert {(s.venueId, s.localDate) for s in card.slots} == {
        (ODEON.id, DAY),
        (VUE.id, DAY + timedelta(days=9)),
    }
    # Each showing keeps its own run and reason: the anniversary label is the cinema's.
    reasons = {s.venueId: (s.releaseCategory, s.runReason) for s in card.slots}
    assert reasons[ODEON.id] == ("olderFilm", "UK release 1986 · rerun")
    assert reasons[VUE.id] == (
        "olderFilm",
        "UK release 1986 · the cinema calls it an anniversary showing · rerun",
    )
    detail = await reads.film(db, viewer.id, "tmdb-991300")
    assert [s.venueId for s in detail.showings] == [ODEON.id, VUE.id]
    assert detail.film.title == "Shared Film" and detail.alsoListed == []


async def test_a_listing_keeps_to_its_own_chain_and_gathers_a_film_listed_once_per_showing(
    api_session: AsyncSession, run, admin: Profile
):
    """GFT lists some films once per showing. Its rows of one title and the same facts read as
    one listing; another chain's listing of that title, and a linked film of it, stay apart
    (#327, #342)."""
    db = api_session
    gft = [
        showing(f"gft-{n}", film_key=f"showing:{n}", title="Lonely Title", start=at(DAY, 14 + n))
        for n in range(3)
    ]
    await promote(db, run, GFT, gft)
    elsewhere = showing("odeon-lonely", film_key="lonely", title="Lonely Title", start=at(DAY, 21))
    await promote(db, run, ODEON, [elsewhere])
    linked = showing("vue-lonely", film_key="vue-lonely", title="Lonely Title", start=at(DAY, 22))
    await promote(
        db,
        run,
        VUE,
        [linked],
        looked_up(linked, VUE, tmdb_id=991310, released="2026-10-20", uk=("2026-10-23",)),
    )
    result = await reads.films(db, admin.id)
    assert len(result.films) == 3, [(c.key, c.title) for c in result.films]
    gft_listing = next(c for c in result.films if c.slots[0].venueId == GFT.id)
    assert gft_listing.kind == "listing" and gft_listing.identityStatus == "unverified"
    assert gft_listing.identityReason == "not yet looked up on TMDB"
    assert len(gft_listing.slots) == 1 and len(gft_listing.slots[0].startsAtUtc) == 3
    ids = sorted(
        str(f.id)
        for f in (await db.scalars(select(CinemaFilm).where(CinemaFilm.source == "gft"))).all()
    )
    assert gft_listing.key == f"listing-{ids[0]}"
    assert gft_listing.posterPath is None and gft_listing.originalYear is None
    assert all(
        s.releaseCategory == "unclassified" and s.runReason is None for s in gft_listing.slots
    )
    film = next(c for c in result.films if c.kind == "film")
    assert film.key == "tmdb-991310"
    # Any of GFT's rows opens the whole listing, and its page points at the namesakes.
    for row_id in ids:
        detail = await reads.film(db, admin.id, f"listing-{row_id}")
        assert detail.film.key == gft_listing.key and len(detail.showings) == 3
    assert {a.key for a in detail.alsoListed} == {
        "tmdb-991310",
        next(c.key for c in result.films if c.slots[0].venueId == ODEON.id),
    }


async def test_events_review_and_conflicts_are_listings_with_their_state(
    api_session: AsyncSession, run, admin: Profile
):
    db = api_session
    event = showing("event", film_key="event", title="National Theatre Live: Hamlet")
    double = showing("double", film_key="double", title="One + Two")
    conflict = showing(
        "conflict", film_key="conflict", title="Muddled", evidence={"conflict": True}
    )
    named = showing("named", film_key="named", title="Named Film", tmdb_id=991320)
    await promote(
        db,
        run,
        ODEON,
        [event, double, conflict, named],
        looked_up(named, tmdb_id=991321, title="Another Film", released="2024-01-01"),
    )
    result = {c.title: c for c in (await reads.films(db, admin.id)).films}
    assert result["National Theatre Live: Hamlet"].kind == "event"
    assert result["One + Two"].kind == "event"
    assert result["Muddled"].kind == "listing" and result["Muddled"].identityStatus == "conflict"
    waiting = result["Named Film"]
    assert waiting.kind == "listing" and waiting.identityStatus == "review"
    assert waiting.identityReason == "the cinema's own id was not found"
    assert all(c.key.startswith("listing-") for c in result.values())


async def test_the_reader_s_own_watch_and_the_collection_ride_on_the_film(
    api_session: AsyncSession, run, admin: Profile, viewer: Profile
):
    db = api_session
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=991330,
        title="Owned Classic",
        original_title="Owned Classic",
        year=1975,
        poster_path="/owned.jpg",
        runtime_minutes=124,
    )
    db.add(movie)
    await db.flush()
    db.add(WatchLog(movie_id=movie.id, user_id=admin.id, watched_at=DAY))
    db.add(CollectionItem(movie_id=movie.id, formats=["blu_ray"], added_by=admin.id))
    row = showing(
        title="Owned Classic (4K Restoration)", identity_facts={"director": "Ann Director"}
    )
    await promote(
        db,
        run,
        ODEON,
        [row],
        looked_up(
            row,
            tmdb_id=991330,
            title="Owned Classic",
            released="1975-06-20",
            uk=("1975-12-26",),
            directors=("Ann Director",),
        ),
    )
    for user, watched in [(admin, True), (viewer, False)]:
        [card] = (await reads.films(db, user.id)).films
        assert card.key == "tmdb-991330" and card.movieId == movie.id
        assert card.owned is True and card.watched is watched
        assert card.posterPath == "/owned.jpg" and card.runtimeMinutes == 124
        assert card.originalYear == 1975
    # The catalogue film's own address opens the same film.
    detail = await reads.film(db, admin.id, f"movie-{movie.id}")
    assert detail.film.key == "tmdb-991330" and len(detail.showings) == 1


async def test_the_fortnight_runs_from_today_to_the_thirteenth_day_after_and_skips_the_started(
    api_session: AsyncSession, run, admin: Profile
):
    db = api_session
    rows = [
        showing("started", film_key="f", title="Window Film", start=at(DAY, 7)),
        showing("today", film_key="f", title="Window Film", start=at(DAY, 20)),
        showing("last", film_key="f", title="Window Film", start=at(DAY + timedelta(days=13))),
        showing(
            "beyond", film_key="f", title="Window Film", start=at(DAY + timedelta(days=13), 21)
        ),
    ]
    await promote(db, run, ODEON, rows, days=14)
    # A showing stored for the day after the fortnight waits for tomorrow's read.
    beyond = (
        await db.scalars(select(CinemaScreening).where(CinemaScreening.source_key == "beyond"))
    ).one()
    beyond.local_date = DAY + timedelta(days=14)
    beyond.starts_utc = beyond.starts_utc + timedelta(days=1)
    await db.flush()
    [card] = (await reads.films(db, admin.id)).films
    assert sorted(t for s in card.slots for t in s.startsAtUtc) == [
        datetime(2026, 11, 2, 20),
        datetime(2026, 11, 15, 20),
    ]


async def test_ticket_links_follow_the_programme_rules_on_the_film_page(
    api_session: AsyncSession, run, admin: Profile
):
    db = api_session
    row = showing(title="Rule Film")
    other = replace(
        row, key="vue-rule", booking="https://www.myvue.com/book-tickets/summary/10097/2"
    )
    lookup = {"tmdb_id": 991340, "released": "2026-10-20", "uk": ("2026-10-23",)}
    await promote(db, run, ODEON, [row], looked_up(row, **lookup))
    await promote(db, run, VUE, [other], looked_up(other, VUE, **lookup))
    coverage = (
        await db.scalars(
            select(CinemaCoverage).where(
                CinemaCoverage.venue_id == VUE.id, CinemaCoverage.local_date == DAY
            )
        )
    ).one()
    coverage.status = "failed"
    await db.flush()
    detail = await reads.film(db, admin.id, "tmdb-991340")
    links = {s.venueId: s.bookingUrl for s in detail.showings}
    assert links[ODEON.id] == row.booking and links[VUE.id] is None
    assert next(v for v in detail.venues if v.id == VUE.id).coverage[0].status == "failed"
    assert detail.showings[0].categoryReason == "UK release 23 Oct 2026 · first run"


async def test_a_listing_s_address_opens_the_film_once_it_is_linked(
    api_session: AsyncSession, run, admin: Profile, monkeypatch
):
    """The page's address is stable (#341): a listing linked by a later morning's lookup
    opens as the film, and a film with nothing in the fortnight still opens by its name."""
    db = api_session
    row = showing(title="Later Linked")
    await promote(db, run, ODEON, [row])
    [listing] = (await reads.films(db, admin.id)).films
    assert listing.kind == "listing" and listing.identityReason == "not yet looked up on TMDB"
    await promote(
        db,
        run,
        ODEON,
        [row],
        looked_up(row, tmdb_id=991350, released="2026-10-20", uk=("2026-10-23",)),
    )
    detail = await reads.film(db, admin.id, listing.key)
    assert detail.film.key == "tmdb-991350" and detail.film.kind == "film"
    assert len(detail.showings) == 1
    # Once its showings are past, the film still opens, saying nothing is listed now.
    monkeypatch.setattr(reads, "utcnow", lambda: NOW + timedelta(days=1))
    later = await reads.film(db, admin.id, "tmdb-991350")
    assert later.showings == [] and later.film.title == "Later Linked"
    assert (await reads.film(db, admin.id, listing.key)).film.key == "tmdb-991350"
