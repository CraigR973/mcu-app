"""Real-Postgres ingestion and authenticated reads, without live provider requests."""

import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
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
from src.services.cinemas import programme as reads
from src.services.cinemas import refresh, store
from src.services.cinemas.domain import Showing, Snapshot, SourceError, local_start
from src.services.cinemas.metadata import Candidate, Metadata, ReleaseEvent, fingerprint
from src.services.cinemas.parsers import parse_cinematimes
from src.services.cinemas.venues import BY_SLUG, VENUES
from tests.test_cinema_sources import body
from tests.test_collection_write_api import admin as admin
from tests.test_collection_write_api import api_session as api_session
from tests.test_collection_write_api import client as client
from tests.test_collection_write_api import overrides as overrides
from tests.test_collection_write_api import viewer as viewer

NOW = datetime(2026, 11, 2, 8)
DAY = date(2026, 11, 2)
VENUE = BY_SLUG["odeon-braehead"]


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    for module in (reads, store, refresh):
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


def showing(key="one", **changes):
    row = Showing(
        key,
        "film-one",
        "A Film",
        local_start("2026-11-02T20:00:00"),
        "https://www.odeon.co.uk/ticketing/seat-picker/?showtimeId=615-1234",
        "2026-11-02T20:00:00",
    )
    return replace(row, **changes)


def snapshot(*rows, **changes):
    return Snapshot(rows=list(rows), observed_dates={DAY}, observed_utc=NOW, **changes)


async def enable(db):
    row = await db.get(CinemaVenue, VENUE.id)
    row.collection_enabled = True
    await db.flush()


def looked_up(row, venue=VENUE, *, tmdb_id, title=None, released, uk=(), directors=()):
    """The TMDB record AC3's lookup would store for ``row``: one exact-title candidate."""
    return {
        (venue.source, row.film_key): Metadata(
            source=venue.source,
            film_key=row.film_key,
            fingerprint=fingerprint(row),
            fetched_utc=NOW,
            state="candidate",
            candidates=[
                Candidate(
                    tmdb_id=tmdb_id,
                    title=title or row.title,
                    original_title=title or row.title,
                    primary_release_date=date.fromisoformat(released),
                    gb_theatrical=[ReleaseEvent(date=date.fromisoformat(d), type=3) for d in uk],
                    directors=list(directors),
                )
            ],
        )
    }


async def read(db, user):
    return await reads.programme(db, user.id, DAY, DAY, [VENUE.id])


async def test_seeded_nine_disabled_and_api_no_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get("/api/v1/cinemas/programme")
    assert response.status_code == 401


async def test_api_window_validation_and_explicit_empty_coverage(client):
    response = await client.get("/api/v1/cinemas/programme?dateFrom=2026-11-02&dateTo=2026-11-15")
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["venues"]) == 9
    assert data["films"] == [] and not data["selectionComplete"]
    assert all(not v["collectionEnabled"] for v in data["venues"])
    assert all(c["status"] == "notEnabled" for v in data["venues"] for c in v["coverage"])
    assert data["generatedAtUtc"].endswith("Z")
    for query in [
        "dateFrom=2026-11-02&dateTo=2026-11-16",
        "dateFrom=2026-11-03&dateTo=2026-11-02",
        "venueIds=" + str(uuid.uuid4()),
        "releaseCategory=olderOnly",
    ]:
        assert (await client.get("/api/v1/cinemas/programme?" + query)).status_code == 422


async def test_idempotence_reschedule_and_failed_observation_preserves_rows(
    api_session,
    run,
    admin,
):
    db = api_session
    first = await store.promote(db, VENUE, snapshot(showing()), DAY, DAY, run.id)
    assert first["added"] == 1
    existing = await db.scalar(select(CinemaScreening).where(CinemaScreening.venue_id == VENUE.id))
    identity = existing.id
    second = await store.promote(db, VENUE, snapshot(showing()), DAY, DAY, run.id)
    assert second["added"] == 0 and second["updated"] == 1
    moved = showing(start=local_start("2026-11-02T21:00:00"), source_local="2026-11-02T21:00:00")
    await store.promote(db, VENUE, snapshot(moved), DAY, DAY, run.id)
    assert existing.id == identity and existing.starts_utc.hour == 21
    await enable(db)
    fresh = await read(db, admin)
    assert fresh.films[0].showings[0].bookingUrl
    await store.promote(db, VENUE, snapshot(failed=True, errors=["HTTP 403"]), DAY, DAY, run.id)
    assert existing.confirmation == "confirmed" and existing.last_seen_utc == NOW
    failed = await read(db, admin)
    assert failed.films[0].showings[0].bookingUrl is None
    coverage = next(v for v in failed.venues if v.id == VENUE.id).coverage[0]
    assert coverage.status == "failed" and coverage.lastSuccessUtc == NOW


async def test_real_missing_braehead_showings_are_unconfirmed_not_cancelled(api_session, run):
    old = parse_cinematimes(body("cinematimes-braehead.html"), VENUE)
    new = parse_cinematimes(body("cinematimes-braehead-next.html"), VENUE)
    for s in (old, new):
        s.rows = [r for r in s.rows if r.start.date() == DAY]
        s.observed_dates = {DAY}
        s.observed_utc = NOW
    await store.promote(api_session, VENUE, old, DAY, DAY, run.id)
    result = await store.promote(api_session, VENUE, new, DAY, DAY, run.id)
    missing = list(
        (
            await api_session.scalars(
                select(CinemaScreening).where(
                    CinemaScreening.venue_id == VENUE.id,
                    CinemaScreening.confirmation == "unconfirmed",
                )
            )
        ).all()
    )
    assert result["unconfirmed"] == len(missing) == 4
    assert result["cancelled"] == result["withdrawn"] == 0
    assert sorted(r.starts_utc.strftime("%H:%M") for r in missing) == [
        "12:20",
        "15:00",
        "17:40",
        "20:20",
    ]


async def test_complete_absence_withdraws_and_explicit_cancellation_suppresses(
    api_session, run, admin
):
    await store.promote(api_session, VENUE, snapshot(showing()), DAY, DAY, run.id)
    partial = await store.promote(api_session, VENUE, snapshot(), DAY, DAY, run.id)
    assert partial["unconfirmed"] == 1
    again = await store.promote(api_session, VENUE, snapshot(), DAY, DAY, run.id)
    assert again["unconfirmed"] == 0
    reviewed = prepared()
    reviewed.snapshots[VENUE.slug].complete_dates = {DAY}
    prediction = await refresh.preview(api_session, reviewed)
    assert prediction["changes"][VENUE.slug]["withdrawn"] == 1
    result = await store.promote(
        api_session, VENUE, snapshot(complete_dates={DAY}), DAY, DAY, run.id
    )
    assert result["withdrawn"] == 1 and result["cancelled"] == 0
    await enable(api_session)
    assert (await read(api_session, admin)).films == []
    for changes in [{"cancelled": True}, {"expired": True}]:
        await store.promote(api_session, VENUE, snapshot(showing(**changes)), DAY, DAY, run.id)
        assert (await read(api_session, admin)).films == []


async def test_stale_upstream_and_observation_age_disable_booking_without_reset(
    api_session,
    run,
    admin,
    monkeypatch,
):
    await store.promote(api_session, VENUE, snapshot(showing()), DAY, DAY, run.id)
    await enable(api_session)
    record = await api_session.scalar(
        select(CinemaCoverage).where(CinemaCoverage.venue_id == VENUE.id)
    )
    record.upstream_utc = NOW - timedelta(hours=37)
    await api_session.flush()
    result = await read(api_session, admin)
    assert result.films[0].showings[0].upstreamAge == "stale"
    assert result.films[0].showings[0].bookingUrl is None
    record.upstream_utc = None
    row = await api_session.scalar(
        select(CinemaScreening).where(CinemaScreening.venue_id == VENUE.id)
    )
    row.last_seen_utc = NOW - timedelta(hours=31)
    await api_session.flush()
    result = await read(api_session, admin)
    assert result.films[0].showings[0].observationStale
    assert result.films[0].showings[0].bookingUrl is None
    stale = snapshot(showing())
    stale.observed_utc = NOW - timedelta(hours=31)
    with pytest.raises(SourceError, match="stale"):
        await store.promote(api_session, VENUE, stale, DAY, DAY, run.id)


async def test_expired_writer_cannot_publish_and_bad_snapshot_is_atomic(api_session, run):
    run.lease_expires_utc = NOW - timedelta(seconds=1)
    await api_session.flush()
    with pytest.raises(store.LostLease):
        await store.promote(api_session, VENUE, snapshot(showing()), DAY, DAY, run.id)
    assert await api_session.scalar(select(func.count()).select_from(CinemaScreening)) == 0
    run.lease_expires_utc = NOW + timedelta(minutes=10)
    await api_session.flush()
    # The caller's transaction encloses every row of a venue, including a late error.
    invalid = showing("two", film_key="different", start=local_start("2026-11-03T20:00"))
    with pytest.raises(SourceError, match="outside"):
        async with api_session.begin_nested():
            await store.promote(api_session, VENUE, snapshot(showing(), invalid), DAY, DAY, run.id)
    assert await api_session.scalar(select(func.count()).select_from(CinemaScreening)) == 0
    assert await api_session.scalar(select(func.count()).select_from(CinemaFilm)) == 0


async def test_runs_come_from_the_uk_cinema_release_with_personal_watches_and_unknown_remakes(
    api_session: AsyncSession,
    run: CinemaRefreshRun,
    admin: Profile,
    viewer: Profile,
):
    """AC3 (#335): first run within 16 weeks of the UK release, rerun 12 months after."""
    db = api_session
    movie = Movie(
        id=uuid.uuid4(), tmdb_id=991234, title="A Film", original_title="A Film", year=2025
    )
    db.add(movie)
    await db.flush()
    db.add(WatchLog(movie_id=movie.id, user_id=admin.id, watched_at=DAY))
    db.add(CollectionItem(movie_id=movie.id, formats=["blu_ray"], added_by=admin.id))
    await db.flush()
    # The cinema's own date corroborates a film first in UK cinemas in January 2025: a rerun.
    older = showing(source_release=date(2025, 1, 10))
    new = showing("two", film_key="film-two", title="New Film")
    unknown = showing("three", film_key="remake", title="A Film")
    lookups = {
        **looked_up(older, tmdb_id=991234, released="2025-01-08", uk=("2025-01-10",)),
        **looked_up(new, tmdb_id=991235, released="2026-10-20", uk=("2026-10-23",)),
    }
    await store.promote(db, VENUE, snapshot(older, new, unknown), DAY, DAY, run.id, lookups)
    await enable(db)
    for user, watched in [(admin, True), (viewer, False)]:
        result = await read(db, user)
        assert result.categoryCounts.model_dump() == {
            "newRelease": 1,
            "olderFilm": 1,
            "unclassified": 1,
        }
        known = next(f for f in result.films if f.movieId == movie.id)
        assert known.originalYear == 2025 and known.owned and known.watched is watched
        assert known.showings[0].releaseCategory == "olderFilm"
        assert known.showings[0].categoryReason == "UK release 2025 · rerun"
        fresh = next(f for f in result.films if f.title == "New Film")
        assert fresh.showings[0].categoryReason == "UK release 23 Oct 2026 · first run"
        unidentified = next(f for f in result.films if f.identityStatus == "unverified")
        assert unidentified.movieId is unidentified.owned is unidentified.watched is None
    for category in ("newRelease", "olderFilm", "unclassified"):
        result = await reads.programme(db, admin.id, DAY, DAY, [VENUE.id], category)
        assert result.returnedShowingCount == 1
        assert sum(result.categoryCounts.model_dump().values()) == 3
        assert result.films[0].showings[0].releaseCategory == category
    # A source id that names another film than the title goes to Craig's review, unlinked.
    other = replace(older, tmdb_id=991236)
    await store.promote(
        db,
        VENUE,
        snapshot(other),
        DAY,
        DAY,
        run.id,
        looked_up(other, tmdb_id=991236, title="Another Film", released="2024-01-01"),
    )
    result = await read(db, admin)
    review = next(f for f in result.films if f.identityStatus == "review")
    assert review.movieId is None and review.showings[0].releaseCategory == "unclassified"


async def test_unfinished_run_disables_old_booking_even_before_coverage_write(
    api_session, run, admin
):
    await store.promote(api_session, VENUE, snapshot(showing()), DAY, DAY, run.id)
    await enable(api_session)
    run.status = "failed"
    run.started_utc = NOW + timedelta(seconds=1)
    run.report = {
        "dateFrom": DAY.isoformat(),
        "dateTo": DAY.isoformat(),
        "venueIds": [str(VENUE.id)],
    }
    await api_session.flush()
    result = await read(api_session, admin)
    assert result.films[0].showings[0].bookingUrl is None
    assert next(v for v in result.venues if v.id == VENUE.id).coverage[0].status == "failed"


async def test_an_old_film_first_in_uk_cinemas_now_a_labelled_reissue_and_a_combined_programme(
    api_session, run, admin
):
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=991250,
        title="Older original",
        original_title="Older original",
        year=1973,
    )
    api_session.add(movie)
    await api_session.flush()
    # Made in 1973, first shown in UK cinemas this autumn: a first run, whatever its age.
    first = showing(title=movie.title, source_release=DAY)
    reissue = showing(
        "reissue",
        film_key="reissue",
        title="Reissued Film (40th Anniversary 4K Restoration)",
        evidence={"returningLabel": True, "sourceUrl": VENUE.programme_url, "quote": "4K"},
    )
    combined = showing(
        "double",
        film_key="combined",
        title="One + Two",
        evidence={"combinedProgramme": True},
    )
    lookups = {
        **looked_up(first, tmdb_id=991250, released="1973-05-01", uk=("2026-10-30",)),
        **looked_up(
            reissue,
            tmdb_id=991251,
            title="Reissued Film",
            released="1986-01-01",
            uk=("1986-03-01",),
        ),
    }
    await store.promote(
        api_session, VENUE, snapshot(first, reissue, combined), DAY, DAY, run.id, lookups
    )
    result = await read(api_session, admin)
    original = next(f for f in result.films if f.movieId == movie.id)
    assert original.originalYear == 1973
    assert original.showings[0].releaseCategory == "newRelease"
    assert original.showings[0].sourceReleaseDate == DAY
    assert original.showings[0].reissue is None
    returning = next(s for f in result.films for s in f.showings if s.reissue)
    assert returning.releaseCategory == "olderFilm"
    assert (
        returning.categoryReason
        == "UK release 1986 · the cinema calls it an anniversary showing · rerun"
    )
    # A double bill is never one film.
    double = next(f for f in result.films if f.title == "One + Two")
    assert double.identityStatus == "event" and result.categoryCounts.unclassified == 1


async def test_a_source_flag_or_a_film_not_looked_up_never_links(api_session, run):
    """#335: a double bill the source flags, a listing the source says conflicts, and a film
    not yet looked up all stay unlinked, whatever the title alone would allow. Only a lookup
    can say a film was not found, or send it to Craig."""
    flagged = showing(
        "flagged", film_key="flagged", title="Flagged Pair", evidence={"combinedProgramme": True}
    )
    conflicting = showing(
        "conflicting", film_key="conflicting", title="Conflicting Film", evidence={"conflict": True}
    )
    waiting = showing("waiting", film_key="waiting", title="Waiting Film")
    named = showing("named", film_key="named", title="Named Film", tmdb_id=991270)
    lookups = {
        **looked_up(flagged, tmdb_id=991271, released="2026-10-20", uk=("2026-10-23",)),
        **looked_up(conflicting, tmdb_id=991272, released="2026-10-20", uk=("2026-10-23",)),
    }
    rows = (flagged, conflicting, waiting, named)
    await store.promote(api_session, VENUE, snapshot(*rows), DAY, DAY, run.id, lookups)
    films = {
        f.source_key: f
        for f in (
            await api_session.scalars(
                select(CinemaFilm).where(CinemaFilm.source_key.in_([r.film_key for r in rows]))
            )
        ).all()
    }
    assert films["flagged"].identity_status == "event"
    assert films["conflicting"].identity_status == "conflict"
    for key in ("waiting", "named"):
        assert films[key].identity_status == "unverified"
        assert films[key].evidence["identity"]["reason"] == "not yet looked up on TMDB"
    assert all(f.movie_id is None and f.evidence["tmdbId"] is None for f in films.values())
    showings = (
        await api_session.scalars(
            select(CinemaScreening).where(
                CinemaScreening.film_id.in_([f.id for f in films.values()])
            )
        )
    ).all()
    assert len(showings) == 4 and {s.release_category for s in showings} == {"unclassified"}


async def test_one_film_at_two_cinemas_groups_as_one_film_and_keeps_both_showings(
    api_session, run, admin
):
    row = showing(title="Shared Film")
    await store.promote(
        api_session,
        VENUE,
        snapshot(row),
        DAY,
        DAY,
        run.id,
        looked_up(row, tmdb_id=991260, released="2026-10-20", uk=("2026-10-23",)),
    )
    second = BY_SLUG["vue-st-enoch"]
    other = replace(row, key="vue-one")
    await store.promote(
        api_session,
        second,
        snapshot(other),
        DAY,
        DAY,
        run.id,
        looked_up(other, second, tmdb_id=991260, released="2026-10-20", uk=("2026-10-23",)),
    )
    result = await reads.programme(api_session, admin.id, DAY, DAY)
    assert len(result.films) == 1
    assert len(result.films[0].showings) == 2
    assert {s.venueId for s in result.films[0].showings} == {VENUE.id, second.id}


def prepared():
    return refresh.PreparedRun(
        prepared_utc=NOW,
        date_from=DAY,
        date_to=DAY,
        requests=9,
        decoded_bytes=100,
        snapshots={v.slug: snapshot() for v in VENUES},
    )


def test_review_artifact_digest_count_scope_and_source_age(tmp_path):
    artifact = prepared()
    path = tmp_path / "review.json"
    digest = refresh.save_artifact(artifact, path)
    assert refresh.load_artifact(path, digest, 0).row_count == 0
    with pytest.raises(SourceError, match="digest"):
        refresh.load_artifact(path, "bad", 0)
    with pytest.raises(SourceError, match="count"):
        refresh.load_artifact(path, digest, 1)
    with pytest.raises(FileExistsError):
        refresh.save_artifact(artifact, path)
    artifact.snapshots[VENUE.slug].observed_utc = NOW - timedelta(hours=31)
    with pytest.raises(SourceError, match="stale/future"):
        artifact.require_all_nine()
    artifact.snapshots.pop(VENUE.slug)
    with pytest.raises(SourceError, match="all nine"):
        artifact.require_all_nine()


async def test_admin_role_check_does_not_allow_viewer(api_session, viewer, admin):
    await refresh._admin(api_session, admin.id)
    with pytest.raises(SourceError, match="admin"):
        await refresh._admin(api_session, viewer.id)


async def test_retention_does_not_remove_recent_future_or_catalogue(api_session, run):
    await store.promote(api_session, VENUE, snapshot(showing()), DAY, DAY, run.id)
    recent = await api_session.scalar(
        select(CinemaScreening).where(CinemaScreening.venue_id == VENUE.id)
    )
    old = CinemaScreening(
        venue_id=VENUE.id,
        film_id=recent.film_id,
        source_key="expired",
        identity_strength="weak",
        local_date=DAY - timedelta(days=40),
        source_local_start="old",
        starts_utc=NOW - timedelta(days=40),
        formats=[],
        release_category="unclassified",
        category_evidence={},
        confirmation="confirmed",
        first_seen_utc=NOW - timedelta(days=50),
        last_seen_utc=NOW - timedelta(days=40),
    )
    api_session.add(old)
    await api_session.flush()
    result = await store.retain(api_session, limit=1)
    assert result["screeningsPurged"] == 1
    assert await api_session.get(CinemaScreening, recent.id) is not None
    with pytest.raises(SourceError, match="500"):
        await store.retain(api_session, limit=501)
