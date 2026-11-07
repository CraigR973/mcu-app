"""AC6: real evaluator, durable history and preferences on disposable Postgres."""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from src.models.cinema import (
    CinemaCoverage,
    CinemaFilm,
    CinemaRefreshRun,
    CinemaScreening,
    CinemaVenue,
)
from src.models.cinema_digest import (
    CinemaDigestAppearance,
    CinemaDigestDay,
    CinemaDigestFilm,
    CinemaDigestListing,
)
from src.models.notification import Notification
from src.services.cinema_digest import evaluate as digest
from src.services.cinemas.venues import VENUES
from src.services.notifications import get_or_create_preferences
from tests.test_collection_write_api import admin as admin
from tests.test_collection_write_api import api_session as api_session
from tests.test_collection_write_api import client as client
from tests.test_collection_write_api import overrides as overrides
from tests.test_collection_write_api import viewer as viewer

NOW = datetime(2026, 11, 7, 8)


async def finished(db, now=NOW, *, failed=(), status="partial", trigger="cron"):
    run = CinemaRefreshRun(
        id=uuid.uuid4(),
        trigger=trigger,
        adapter_version="ab6-3",
        status=status,
        started_utc=now - timedelta(minutes=2),
        heartbeat_utc=now,
        lease_expires_utc=now + timedelta(minutes=10),
        finished_utc=now,
        report={
            "venues": {
                v.slug: {"failed": v.slug in failed, "observedDates": [now.date().isoformat()]}
                for v in VENUES
            }
        },
    )
    db.add(run)
    await db.flush()
    await db.execute(update(CinemaVenue).values(collection_enabled=True))
    for venue in VENUES:
        row = await db.scalar(
            select(CinemaCoverage).where(
                CinemaCoverage.venue_id == venue.id, CinemaCoverage.local_date == now.date()
            )
        )
        if row is None:
            row = CinemaCoverage(venue_id=venue.id, local_date=now.date())
            db.add(row)
        row.status, row.observed, row.complete = "partial", venue.slug not in failed, False
        row.last_attempt_utc = row.last_success_utc = now
        row.run_id = run.id
    await db.flush()
    return run


async def showing(
    db,
    venue,
    *,
    identity=950006,
    now=NOW,
    source_key=None,
    category="olderFilm",
    status="verified",
    confirmation="confirmed",
):
    key = source_key or str(uuid.uuid4())
    film = CinemaFilm(
        id=uuid.uuid4(),
        source=venue.source,
        source_key=key,
        title=f"Digest film {identity}",
        identity_status=status,
        evidence={"tmdbId": identity, "sourceFingerprint": "a" * 64},
        last_seen_utc=now,
    )
    db.add(film)
    await db.flush()
    row = CinemaScreening(
        id=uuid.uuid4(),
        venue_id=venue.id,
        film_id=film.id,
        source_key=str(uuid.uuid4()),
        identity_strength="opaque",
        local_date=now.date(),
        source_local_start=now.isoformat(),
        starts_utc=now + timedelta(hours=12),
        formats=[],
        release_category=category,
        category_evidence={
            "runReason": "UK release 1986 · rerun"
            if category == "olderFilm"
            else "UK release 2026 · first run"
        },
        confirmation=confirmation,
        first_seen_utc=now,
        last_seen_utc=now,
        source_expired=False,
    )
    db.add(row)
    await db.flush()
    return film, row


async def test_identity_dedup_preferences_three_profiles_and_retries(api_session, admin, viewer):
    db = api_session
    run = await finished(db)
    await showing(db, VENUES[0])
    await showing(db, VENUES[1])
    await showing(db, VENUES[2], identity=950007, category="newRelease")
    from src.models.profile import Profile, UserRole

    third = Profile(id=uuid.uuid4(), display_name="AC6 Third", role=UserRole.viewer, is_active=True)
    db.add(third)
    await db.flush()
    pref = await get_or_create_preferences(db, viewer.id)
    pref.cinemas_older_only = True
    disabled = await get_or_create_preferences(db, third.id)
    disabled.cinemas_enabled = False
    result = await digest.evaluate(db, run, now=NOW)
    assert result["status"] == "evaluated" and len(result["appearanceIds"]) == 2
    rows = {
        n.user_id: n
        for n in (
            await db.scalars(select(Notification).where(Notification.category == "cinemas"))
        ).all()
    }
    assert rows[admin.id].title == "2 films newly listed at your cinemas"
    assert rows[viewer.id].title == "1 older film newly listed at your cinemas"
    assert "Rerun" in rows[viewer.id].body and "First run" not in rows[viewer.id].body
    assert rows[viewer.id].url.endswith("&run=olderFilm")
    assert rows[third.id].status == "suppressed"
    assert (await digest.evaluate(db, run, now=NOW))["status"] == "already_evaluated"
    assert await db.scalar(select(func.count()).select_from(CinemaDigestDay)) == 1
    assert await db.scalar(select(func.count()).select_from(CinemaDigestAppearance)) == 2


@pytest.mark.parametrize("status", ["failed", "abandoned", "running"])
async def test_unfinished_or_failed_run_adds_nothing(api_session, status):
    run = await finished(api_session, status=status)
    await showing(api_session, VENUES[0])
    assert (await digest.evaluate(api_session, run, now=NOW))["status"] == "ineligible_run"
    assert await api_session.scalar(select(func.count()).select_from(CinemaDigestDay)) == 0


async def test_partial_run_uses_only_current_successful_venue_and_stays_frozen(api_session):
    db = api_session
    run = await finished(db, failed=(VENUES[0].slug,))
    await showing(db, VENUES[0], identity=950001)
    await showing(db, VENUES[1], identity=950002)
    # A retained row at a successful venue was not observed by this refresh.
    _, old = await showing(db, VENUES[1], identity=950003)
    old.last_seen_utc = NOW - timedelta(days=1)
    result = await digest.evaluate(db, run, now=NOW)
    assert len(result["appearanceIds"]) == 1
    [state] = (await db.scalars(select(CinemaDigestFilm))).all()
    assert state.tmdb_id == 950002
    later = await finished(db, now=NOW + timedelta(hours=1))
    await showing(db, VENUES[2], identity=950004, now=NOW + timedelta(hours=1))
    assert (await digest.evaluate(db, later, now=NOW + timedelta(hours=1)))[
        "status"
    ] == "already_evaluated"


async def test_unmatched_baseline_late_matching_and_identity_correction_are_silent(api_session):
    db = api_session
    run = await finished(db)
    film, _ = await showing(db, VENUES[0], status="unverified")
    db.add(
        CinemaDigestListing(
            source=film.source,
            source_key=film.source_key,
            source_fingerprint="a" * 64,
            cinema_film_id=film.id,
            first_observed_utc=NOW,
            last_observed_utc=NOW,
            baseline=True,
        )
    )
    film.identity_status = "verified"
    result = await digest.evaluate(db, run, now=NOW)
    assert result["appearanceIds"] == []
    assert (await db.scalar(select(CinemaDigestFilm))).baseline is True


@pytest.mark.parametrize("days,expected", [(29, False), (30, True), (31, True)])
def test_exact_return_boundary(days, expected):
    day = NOW.date()
    film = CinemaDigestFilm(
        absent_since_day=day - timedelta(days=days),
        absence_checked_through_day=day - timedelta(days=1),
    )
    assert digest.returned(film, day) is expected
    film.absence_checked_through_day = day - timedelta(days=2)
    assert digest.returned(film, day) is False


def test_missing_failed_and_positive_days_reset_observed_absence():
    day = NOW.date()
    film = CinemaDigestFilm(
        absent_since_day=day - timedelta(days=12),
        absence_checked_through_day=day - timedelta(days=1),
    )
    digest.absence(film, day, observed_all=False, present=False)
    assert film.absent_since_day is None
    digest.absence(film, day, observed_all=True, present=False)
    assert film.absent_since_day == day
    digest.absence(film, day + timedelta(days=2), observed_all=True, present=False)
    assert film.absent_since_day == day + timedelta(days=2)
    digest.absence(film, day + timedelta(days=3), observed_all=True, present=True)
    assert film.absent_since_day is None


async def test_preferences_additive_and_movie_night_untouched(client):
    before = (await client.get("/api/v1/notifications/preferences")).json()
    assert before["cinemasEnabled"] is True and before["cinemasOlderOnly"] is False
    response = await client.put(
        "/api/v1/notifications/preferences",
        json={"cinemasOlderOnly": True, "cinemasEnabled": False},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["cinemasOlderOnly"] is True and result["cinemasEnabled"] is False
    assert result["movieNightEnabled"] == before["movieNightEnabled"]


@pytest.mark.parametrize("failed_day,expected", [(None, 2), (15, 1)])
async def test_real_thirty_day_return_and_failure_interruption(api_session, failed_day, expected):
    db = api_session
    run = await finished(db)
    await showing(db, VENUES[0])
    await digest.evaluate(db, run, now=NOW)
    for offset in range(1, 31):
        now = NOW + timedelta(days=offset)
        run = await finished(db, now, failed=(VENUES[1].slug,) if offset == failed_day else ())
        await digest.evaluate(db, run, now=now)
    now = NOW + timedelta(days=31)
    run = await finished(db, now)
    await showing(db, VENUES[2], now=now)
    await digest.evaluate(db, run, now=now)
    rows = list(
        (
            await db.scalars(
                select(CinemaDigestAppearance).order_by(CinemaDigestAppearance.recognised_utc)
            )
        ).all()
    )
    assert len(rows) == expected
    assert rows[0].is_return is False
    if expected == 2:
        assert rows[1].is_return is True and rows[1].episode_number == 2


async def test_new_unmatched_listing_notifies_once_when_matched_and_preserves_first_listing(
    api_session,
):
    db = api_session
    run = await finished(db)
    film, row = await showing(db, VENUES[0], status="unverified")
    assert (await digest.evaluate(db, run, now=NOW))["appearanceIds"] == []
    later = NOW + timedelta(days=1)
    film.identity_status = "verified"
    row.local_date, row.last_seen_utc, row.starts_utc = (
        later.date(),
        later,
        later + timedelta(hours=12),
    )
    run = await finished(db, later)
    result = await digest.evaluate(db, run, now=later)
    assert len(result["appearanceIds"]) == 1
    appearance = await db.scalar(select(CinemaDigestAppearance))
    assert appearance.first_listing_utc == NOW and appearance.recognised_utc == later


@pytest.mark.parametrize("confirmation", ["cancelled", "withdrawn", "unconfirmed"])
async def test_non_confirmed_showing_never_adds_an_appearance(api_session, confirmation):
    run = await finished(api_session)
    await showing(api_session, VENUES[0], confirmation=confirmation)
    assert (await digest.evaluate(api_session, run, now=NOW))["appearanceIds"] == []


@pytest.mark.parametrize(
    "instant,day",
    [(datetime(2026, 3, 29, 23, 30), "2026-03-30"), (datetime(2026, 10, 25, 23, 30), "2026-10-25")],
)
def test_daily_boundary_uses_london_not_machine_timezone(instant, day):
    assert digest.london_day(instant).isoformat() == day


async def test_switch_off_then_on_cancels_pending_without_backfill(api_session, client, admin):
    db = api_session
    run = await finished(db)
    await showing(db, VENUES[0])
    await digest.evaluate(db, run, now=NOW)
    assert (
        await client.put("/api/v1/notifications/preferences", json={"cinemasEnabled": False})
    ).status_code == 200
    assert (
        await client.put("/api/v1/notifications/preferences", json={"cinemasEnabled": True})
    ).status_code == 200
    row = await db.scalar(
        select(Notification).where(
            Notification.user_id == admin.id, Notification.category == "cinemas"
        )
    )
    assert row.status == "suppressed" and row.suppressed_reason == "category_disabled"


async def test_narrow_then_broaden_does_not_restore_excluded_pending_titles(
    api_session, client, admin
):
    db = api_session
    run = await finished(db)
    await showing(db, VENUES[0])
    await showing(db, VENUES[1], identity=950007, category="newRelease")
    await digest.evaluate(db, run, now=NOW)
    assert (
        await client.put("/api/v1/notifications/preferences", json={"cinemasOlderOnly": True})
    ).status_code == 200
    assert (
        await client.put("/api/v1/notifications/preferences", json={"cinemasOlderOnly": False})
    ).status_code == 200
    row = await db.scalar(
        select(Notification).where(
            Notification.user_id == admin.id, Notification.category == "cinemas"
        )
    )
    assert row.title == "1 older film newly listed at your cinemas"
    assert "950007" not in row.body
    day = await db.scalar(select(CinemaDigestDay))
    entry = day.report["recipients"][str(admin.id)]
    assert len(entry["appearanceIds"]) == 1 and len(entry["originalAppearanceIds"]) == 2


async def test_all_failed_venues_do_not_freeze_out_a_later_scheduled_recovery(api_session):
    db = api_session
    run = await finished(db, failed=tuple(venue.slug for venue in VENUES))
    assert (await digest.evaluate(db, run, now=NOW))["status"] == "no_successful_venues"
    later = NOW + timedelta(hours=1)
    run = await finished(db, later)
    await showing(db, VENUES[0], now=later)
    result = await digest.evaluate(db, run, now=later)
    assert result["status"] == "evaluated" and len(result["appearanceIds"]) == 1
