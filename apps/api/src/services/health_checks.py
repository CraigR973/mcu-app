"""The daily check: what has stopped, said in words, to Craig — Batch X2 (DS44-01, UX48-02).

**None of the seven failures between 9 Sep and 11 Oct reached anyone.** The crons crashed for
two weeks, the TMDB token was missing, Brave refused, the eBay scan went blind, both phones
stopped getting notifications; each was found days later by someone looking. This runs inside
the 08:00 reminders job (no new Railway service), reads only tables the app already writes,
records every result in ``health_checks``, and tells Craig two ways: a "Needs attention" row at
the top of Home (`routers/attention.py`), which works when push is what broke, and one push
when a problem first appears, not every morning it persists.

Each check answers ``(key, message)``: ``message`` is ``None`` when all is well, otherwise the
problem as the Home row says it. Keys are stable, so a problem that persists keeps its
``failing_since_utc`` and is pushed once.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.ai import AiUsageLogEntry
from src.models.cinema import CinemaRefreshRun, CinemaVenue
from src.models.deal import Deal, live_deal
from src.models.ebay_watch import EbayWatchRun
from src.models.health import HealthCheck, JobHeartbeat
from src.models.movie import Movie
from src.models.notification import (
    Notification,
    NotificationCategory,
    NotificationStatus,
    PushSubscription,
)
from src.models.price_history import ScrapeRun
from src.models.profile import Profile, UserRole
from src.models.specs_backfill import SpecRun
from src.models.specs_state import SINGLETON_ID, SpecsIntegrationState
from src.models.valuation import ValuationRun
from src.models.wanted import Retailer
from src.services import heartbeat
from src.services.identify.doubts import count_old as count_old_doubts
from src.services.identify.doubts import count_page_disagreements
from src.services.identify.queue import count_old_waiting
from src.services.notifications import queue_notification
from src.services.scraping.runner import WEEKLY_AFTER_NIGHTS

logger = structlog.get_logger(__name__)

Result = tuple[str, str | None]

#: The scan must have read listings in at least one of this many of its latest runs.
EBAY_RUNS_LOOKED_AT = 6
#: A person's notifications looked at: those of the last three days.
NOTIFICATION_WINDOW = timedelta(days=3)
#: Neon's free plan holds 1 GB; the check speaks up at half.
DATABASE_CAP_BYTES = 1024**3
#: How long an Identify proposal may wait before the check names it (CT46-03).
PROPOSAL_AGE = timedelta(days=14)
#: How old a deal on the page may be, by source: eBay's lifetime, and a shop's freshness.
EBAY_DEAL_FRESHNESS = timedelta(days=3)
SHOP_DEAL_FRESHNESS = timedelta(days=2)
#: The check itself is late when its last result is older than this (read by the Home row).
CHECK_STALE_AFTER = timedelta(hours=26)
#: The cinema programme runs inside the 08:00 reminders job: a day plus a margin, as the others.
CINEMA_CADENCE = heartbeat.BY_JOB[heartbeat.CINEMAS].cadence
#: Its heartbeat's name, the one `services/cinemas/refresh.py` writes.
CINEMA_HEARTBEAT = heartbeat.CINEMAS
#: How many of the programme's latest runs are read for a cinema's last good one: two months.
CINEMA_RUNS_LOOKED_AT = 60
#: Every cinema check's key starts with this, so the after-refresh pass records only its own.
CINEMA_SCOPE = "cinema:"


#: A job's run table's start time also counts as its having run: a run started from the app is
#: a run. The scheduled things themselves, and their cadences, are `heartbeat.SCHEDULED` (AG2).
RUN_STARTS: dict[str, InstrumentedAttribute[datetime]] = {
    heartbeat.SCRAPE: ScrapeRun.started_at_utc,
    heartbeat.SPECS: SpecRun.started_utc,
    heartbeat.EBAY: EbayWatchRun.started_utc,
    heartbeat.VALUES: ValuationRun.started_utc,
}
#: The TMDB refresh names a film once its TMDB details are this old: TMDB's terms allow six
#: months, the refresh takes films at 150 days (DS50-05).
TMDB_AGE_LIMIT = timedelta(days=165)

#: The API's readiness fields, as the row names each.
READINESS_LABELS = {
    "push": "Notifications",
    "ai": "The assistant",
    "ebay": "eBay",
    "tmdb": "TMDB",
    "brave": "Brave search",
}


def day(when: datetime) -> str:
    """ "9 Oct", as the app writes a recent date."""
    return f"{when.day} {when:%b}"


def moment(when: datetime) -> str:
    """ "9 Oct, 14:02" (UTC), for something within the last day or two."""
    return f"{day(when)}, {when:%H:%M}"


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def _failures(row: JobHeartbeat) -> int:
    value = (row.detail or {}).get("failures")
    if isinstance(value, bool):
        return int(value)
    return value if isinstance(value, int) else 0


def judge_beat(
    label: str, cadence: timedelta, last: datetime | None, row: JobHeartbeat | None, now: datetime
) -> str | None:
    """The one rule (AG2): quiet past its cadence, or its last run counted a failure."""
    if last is None:
        return f"{label} has never run."
    if last < now - cadence:
        return f"{label} hasn't run since {day(last)}."
    if row is not None and row.beat_utc == last and (failed := _failures(row)):
        what = "a failure" if failed == 1 else f"{failed} failures"
        return f"{label}'s last run, {moment(row.beat_utc)} UTC, had {what} ({row.outcome})."
    return None


async def check_jobs(db: AsyncSession, now: datetime) -> list[Result]:
    """Every heartbeat, by one rule: each scheduled thing ran within its cadence, and its last
    run counted no failure (AG2, DS50-01). At wave 2's review this read four of eight.

    A thing listed in `heartbeat.SCHEDULED` that has never beaten is named once its
    ``watched_from`` has passed; a beat not listed there is still judged, by the cadence it
    wrote, so nothing that beats goes unread. The cinema programme is judged by
    :func:`check_cinemas`, beside each cinema's own row.
    """
    beats = {row.job: row for row in (await db.scalars(select(JobHeartbeat))).all()}
    results: list[Result] = []
    for thing in heartbeat.SCHEDULED:
        if thing.row is not None:
            continue
        row = beats.get(thing.job)
        times = [row.beat_utc] if row is not None else []
        if thing.job in RUN_STARTS:
            started = await db.scalar(select(func.max(RUN_STARTS[thing.job])))
            if started is not None:
                times.append(started)
        last = max(times) if times else None
        if last is None and thing.watched_from is not None and now < thing.watched_from:
            message: str | None = None
        elif (
            thing.job == heartbeat.SPECS
            and row is not None
            and last is not None
            and last >= now - thing.cadence
            and (row.detail or {}).get("imdbError")
        ):
            message = (
                "IMDb scores could not be refreshed in the nightly job. "
                "Stored scores have been kept."
            )
        else:
            message = judge_beat(thing.label, thing.cadence, last, row, now)
        results.append((thing.key, message))
    for job, row in sorted(beats.items()):
        if job in heartbeat.BY_JOB or job == heartbeat.API:
            continue
        hours = (row.detail or {}).get("cadenceHours")
        cadence = timedelta(hours=float(hours)) if isinstance(hours, int | float) else None
        if cadence is None:
            continue
        results.append(
            (f"job:{job}", judge_beat(f"The {job} job", cadence, row.beat_utc, row, now))
        )
    return results


async def check_tmdb_age(db: AsyncSession, now: datetime) -> list[Result]:
    """No identified film's TMDB details older than 165 days (DS50-05; TMDB allows six months).

    The 08:00 job refreshes 100 a day from 150 days, so a row here means it has fallen behind
    or stopped. A film never synced is counted from the day it was added.
    """
    age = func.coalesce(Movie.last_tmdb_sync_utc, Movie.created_at)
    row = (
        await db.execute(
            select(func.count(Movie.id), func.min(age)).where(
                Movie.deleted_at.is_(None),
                or_(Movie.tmdb_id.is_not(None), Movie.tmdb_tv_id.is_not(None)),
                age < now - TMDB_AGE_LIMIT,
            )
        )
    ).one()
    count, oldest = int(row[0] or 0), row[1]
    if not count:
        return [("tmdb:age", None)]
    films = "film's" if count == 1 else "films'"
    return [
        (
            "tmdb:age",
            f"{count} {films} TMDB details are over {TMDB_AGE_LIMIT.days} days old"
            + (f", the oldest from {day(oldest)}." if oldest else "."),
        )
    ]


async def check_ebay_listings(db: AsyncSession, now: datetime) -> list[Result]:
    """The eBay scan read listings in at least one of its latest six runs (CR43-01's guard)."""
    runs = (
        await db.execute(
            select(EbayWatchRun.started_utc, EbayWatchRun.listings_seen)
            .where(EbayWatchRun.status.in_(("finished", "budget_spent", "stopped")))
            .order_by(EbayWatchRun.started_utc.desc())
            .limit(EBAY_RUNS_LOOKED_AT)
        )
    ).all()
    blind = len(runs) == EBAY_RUNS_LOOKED_AT and all(seen == 0 for _, seen in runs)
    if not blind:
        return [("ebay:listings", None)]
    since = runs[-1][0]
    return [
        (
            "ebay:listings",
            f"No eBay listings read in the last {EBAY_RUNS_LOOKED_AT} scans (since {day(since)}).",
        )
    ]


async def notification_trouble(
    db: AsyncSession, person: Profile, now: datetime
) -> tuple[str, int] | None:
    """Why this person's phone is not getting notifications, or None when it is.

    ``("noDevice", 0)``: no live device. ``("undelivered", n)``: n notifications in the last
    three days, none delivered. The daily check words it for the admin; since AG3 (UX54-02) the
    person's own Home says it too, from this one rule."""
    devices = await db.scalar(
        select(func.count(PushSubscription.id)).where(
            PushSubscription.user_id == person.id, PushSubscription.revoked_at_utc.is_(None)
        )
    )
    if not devices:
        return ("noDevice", 0)
    statuses = (
        await db.scalars(
            select(Notification.status).where(
                Notification.user_id == person.id,
                Notification.created_at_utc >= now - NOTIFICATION_WINDOW,
                Notification.status != NotificationStatus.queued.value,
            )
        )
    ).all()
    undelivered = {NotificationStatus.suppressed.value, NotificationStatus.failed.value}
    if statuses and all(status in undelivered for status in statuses):
        return ("undelivered", len(statuses))
    return None


async def check_people(db: AsyncSession, now: datetime) -> list[Result]:
    """Each person holds a live device, and their last three days are not all undelivered."""
    people = (
        await db.scalars(
            select(Profile).where(Profile.deleted_at.is_(None), Profile.is_active.is_(True))
        )
    ).all()
    results: list[Result] = []
    for person in people:
        key = f"person:{person.id}:notifications"
        trouble = await notification_trouble(db, person, now)
        if trouble is None:
            results.append((key, None))
        elif trouble[0] == "noDevice":
            results.append((key, f"{person.display_name} has no phone getting notifications."))
        else:
            results.append(
                (
                    key,
                    f"None of {person.display_name}'s {trouble[1]} notifications since "
                    f"{day(now - NOTIFICATION_WINDOW)} reached a phone.",
                )
            )
    return results


async def check_specs(db: AsyncSession, now: datetime) -> list[Result]:
    """The disc spec integration is not halted (#110)."""
    state = await db.get(SpecsIntegrationState, SINGLETON_ID)
    if state is None or not state.halted:
        return [("specs:halted", None)]
    reason = f": {state.halted_reason}" if state.halted_reason else ""
    return [("specs:halted", f"Disc spec lookups are halted{reason}.")]


async def check_readiness(db: AsyncSession, now: datetime) -> list[Result]:
    """Every readiness field configured, as the API reported it at its last boot."""
    row = await db.get(JobHeartbeat, heartbeat.API)
    detail = (row.detail or {}) if row is not None else {}
    missing = [
        label
        for field, label in READINESS_LABELS.items()
        if detail.get(field, "configured") != "configured"
    ]
    if not missing:
        return [("api:readiness", None)]
    return [("api:readiness", f"{', '.join(missing)} isn't set up on the server.")]


async def check_database_size(db: AsyncSession, now: datetime) -> list[Result]:
    """The database is under half Neon's free 1 GB."""
    size = int(await db.scalar(text("SELECT pg_database_size(current_database())")) or 0)
    if size < DATABASE_CAP_BYTES // 2:
        return [("database:size", None)]
    return [("database:size", f"The database is {size // 1024**2} MB, over half its 1 GB.")]


async def check_lockouts(db: AsyncSession, now: datetime) -> list[Result]:
    """Any profile whose PIN locked in the last day (DS44-05)."""
    people = (await db.scalars(select(Profile).where(Profile.deleted_at.is_(None)))).all()
    results: list[Result] = []
    for person in people:
        key = f"person:{person.id}:lockout"
        last = person.last_lockout_utc
        if last is None or last < now - timedelta(days=1):
            results.append((key, None))
            continue
        times = "once" if person.lockout_count <= 1 else f"{person.lockout_count} times"
        results.append(
            (key, f"{person.display_name}'s PIN locked {times}, last at {moment(last)} UTC.")
        )
    return results


async def check_identification(db: AsyncSession, now: datetime) -> list[Result]:
    """Identify proposals older than a fortnight; identified films a page says are another year.

    Batch X9: a doubt about an identified film is a proposal too, and counts once it is a
    fortnight old."""
    waiting = await count_old_waiting(db, before=now - PROPOSAL_AGE)
    waiting += await count_old_doubts(db, now)
    doubted = await count_page_disagreements(db)
    return [
        (
            "identify:waiting",
            f"{waiting} Identify {'proposal has' if waiting == 1 else 'proposals have'} waited "
            "more than a fortnight."
            if waiting
            else None,
        ),
        (
            "identify:year-doubt",
            f"{doubted} identified {'film has' if doubted == 1 else 'films have'} a disc page "
            "or review for another year."
            if doubted
            else None,
        ),
    ]


async def check_deal_freshness(db: AsyncSession, now: datetime) -> list[Result]:
    """No deal on the page older than its source's freshness: eBay 3 days, shops 2."""
    is_ebay = and_(Deal.retailer_id.is_(None), Deal.retailer_name_snapshot == "eBay")
    stale = int(
        await db.scalar(
            select(func.count(Deal.id)).where(
                live_deal(now),
                or_(
                    and_(is_ebay, Deal.last_seen_at_utc < now - EBAY_DEAL_FRESHNESS),
                    and_(~is_ebay, Deal.last_seen_at_utc < now - SHOP_DEAL_FRESHNESS),
                ),
            )
        )
        or 0
    )
    if not stale:
        return [("deals:freshness", None)]
    return [
        (
            "deals:freshness",
            f"{stale} {'deal' if stale == 1 else 'deals'} on the page "
            f"{'is' if stale == 1 else 'are'} older than its source's freshness.",
        )
    ]


async def check_assistant(db: AsyncSession, now: datetime) -> list[Result]:
    """Assistant calls that failed in the last day (Batch X7, AI45-04).

    Each failed call leaves a usage row with its error since X7; before it, a failure left
    one log line Railway did not keep, and the person was told to rephrase. This is what
    makes "Craig has been told" true.
    """
    since = now - timedelta(days=1)
    failed = (
        await db.execute(
            select(func.count(AiUsageLogEntry.id), func.max(AiUsageLogEntry.created_at_utc)).where(
                AiUsageLogEntry.error.is_not(None), AiUsageLogEntry.created_at_utc >= since
            )
        )
    ).one()
    count, latest = int(failed[0] or 0), failed[1]
    if not count:
        return [("assistant:failures", None)]
    last_error = await db.scalar(
        select(AiUsageLogEntry.error)
        .where(AiUsageLogEntry.error.is_not(None), AiUsageLogEntry.created_at_utc == latest)
        .limit(1)
    )
    what = (last_error or "").split(":", 1)[0].strip()
    return [
        (
            "assistant:failures",
            f"The assistant failed {'once' if count == 1 else f'{count} times'} in the last day, "
            f"last at {moment(latest)} UTC" + (f" ({what})." if what else "."),
        )
    ]


async def check_shops(db: AsyncSession, now: datetime) -> list[Result]:
    """Each switched-on shop the nightly check now asks only weekly, by name (AG2, MK53-02).

    A shop goes weekly after :data:`WEEKLY_AFTER_NIGHTS` scheduled nights in a row in which it
    refused, answered off its search page, or answered nothing for every want. Before AG2 only
    a 429 counted, so a shop whose search had moved read as "no results" for five weeks.
    """
    shops = (
        await db.execute(
            select(Retailer.id, Retailer.name, Retailer.refused_nights, Retailer.last_scrape_error)
            .where(Retailer.deleted_at.is_(None), Retailer.enabled.is_(True))
            .order_by(Retailer.name)
        )
    ).all()
    results: list[Result] = []
    for shop_id, name, nights, error in shops:
        key = f"shop:{shop_id}"
        if nights < WEEKLY_AFTER_NIGHTS:
            results.append((key, None))
            continue
        why = (error or "").split(". ", 1)[0].strip()[:160]
        results.append(
            (
                key,
                f"{name} has given no prices for {nights} nights in a row, so it is now asked "
                "weekly" + (f": {why}." if why else "."),
            )
        )
    return results


async def _switched_off_by_refusal(db: AsyncSession) -> dict[str, datetime]:
    """Each switched-off cinema whose latest change was the refresh switching it off, refused."""
    rows = (
        await db.execute(
            select(CinemaVenue.id, CinemaVenue.slug).where(
                CinemaVenue.collection_enabled.is_(False), CinemaVenue.deleted_at.is_(None)
            )
        )
    ).all()
    off: dict[uuid.UUID, str] = {venue_id: slug for venue_id, slug in rows}
    if not off:
        return {}
    changes = (
        await db.execute(
            select(
                AdminAction.target_id,
                AdminAction.user_id,
                AdminAction.changes,
                AdminAction.created_at,
            )
            .where(
                AdminAction.target_table == "cinema_venues",
                AdminAction.target_id.in_([str(venue_id) for venue_id in off]),
            )
            .order_by(AdminAction.created_at.desc())
        )
    ).all()
    latest: dict[str, tuple[Any, Any, datetime]] = {}
    for target, user, change, when in changes:
        latest.setdefault(target, (user, change, when))
    found: dict[str, datetime] = {}
    for venue_id, slug in off.items():
        last = latest.get(str(venue_id))
        if last is None:
            continue
        user, change, when = last
        reason = str((change or {}).get("reason") or "")
        if user is None and reason.startswith("Source host refusal"):
            found[slug] = when
    return found


async def check_cinemas(db: AsyncSession, now: datetime) -> list[Result]:
    """The ODEON fast lane (#381): the cinema programme ran, and every cinema switched on was read.

    From 12 Nov the four ODEONs came back with nothing every morning and nothing said so: each
    run ended ``partial``, as every run has since the first (no source proves a whole fortnight),
    so the status carries no signal. This reads each cinema's own result in the programme's
    latest run instead: one row per switched-on cinema whose read failed or found no showings,
    by name, with when it last found some. And one row when the job itself has gone quiet, or
    its whole run failed. Nothing is said while no cinema is switched on: the job then reads
    nothing, by design.

    It runs in the morning's check, and again straight after that morning's refresh
    (``run_cinema_check``), so a cinema that fails today is named today.
    """
    venues = (
        await db.execute(
            select(CinemaVenue.slug, CinemaVenue.name)
            .where(CinemaVenue.collection_enabled.is_(True), CinemaVenue.deleted_at.is_(None))
            .order_by(CinemaVenue.name)
        )
    ).all()
    job_key = CINEMA_SCOPE + "job"
    # AG2 (DS50-01): a cinema the refresh switched off after its source refused is named until
    # the owner switches it back on; before, only switched-on cinemas were read.
    refused = await _switched_off_by_refusal(db)
    names: dict[str, str] = {
        slug: name
        for slug, name in (await db.execute(select(CinemaVenue.slug, CinemaVenue.name))).all()
    }
    off_rows: list[Result] = [
        (
            CINEMA_SCOPE + slug,
            f"{names.get(slug, slug)} was switched off on {day(when)} after its listings site "
            "refused the app; it stays off until it is switched back on.",
        )
        for slug, when in sorted(refused.items())
    ]
    if not venues:
        return [(job_key, None), *off_rows]
    runs = (
        await db.execute(
            select(CinemaRefreshRun.started_utc, CinemaRefreshRun.status, CinemaRefreshRun.report)
            .where(CinemaRefreshRun.status.in_(("healthy", "partial", "failed")))
            .order_by(CinemaRefreshRun.started_utc.desc())
            .limit(CINEMA_RUNS_LOOKED_AT)
        )
    ).all()
    beat = await db.get(JobHeartbeat, CINEMA_HEARTBEAT)
    times = [t for t in (beat.beat_utc if beat else None, runs[0][0] if runs else None) if t]
    last = max(times) if times else None
    label = "The cinema programme"
    if last is None:
        job: str | None = f"{label} has never run."
    elif last < now - CINEMA_CADENCE:
        job = f"{label} hasn't run since {day(last)}."
    elif runs and runs[0][1] == "failed" and not (runs[0][2] or {}).get("venues"):
        job = f"{label}'s run on {day(runs[0][0])} failed before it read any cinema."
    else:
        job = None
    results: list[Result] = [(job_key, job)]

    def read(report: dict[str, Any] | None, slug: str) -> dict[str, Any] | None:
        value = ((report or {}).get("venues") or {}).get(slug)
        return value if isinstance(value, dict) else None

    for slug, name in venues:
        key = CINEMA_SCOPE + slug
        mine = [(started, found) for started, _, report in runs if (found := read(report, slug))]
        if not mine:
            results.append((key, None))
            continue
        started, latest = mine[0]
        failed = bool(latest.get("failed"))
        if not failed and int(latest.get("rows") or 0) > 0:
            results.append((key, None))
            continue
        good = next(
            (when for when, found in mine if not found.get("failed") and found.get("rows")), None
        )
        since = f"it last had showings on {day(good)}" if good else "it has had none in two months"
        if failed:
            errors = latest.get("errors") or []
            why = str(errors[0]).split(":", 1)[-1].strip()[:120] if errors else ""
            what = f"failed on {day(started)}" + (f" ({why})" if why else "")
        else:
            what = f"found no showings on {day(started)}"
        results.append((key, f"{name}'s listings {what}; {since}."))
    return results + off_rows


Check = Callable[[AsyncSession, datetime], Awaitable[list[Result]]]

#: Every check, in the order the Home row lists their problems.
CHECKS: Sequence[Check] = (
    check_jobs,
    check_ebay_listings,
    check_people,
    check_readiness,
    check_specs,
    check_database_size,
    check_lockouts,
    check_identification,
    check_deal_freshness,
    check_assistant,
    check_cinemas,
    check_shops,
    check_tmdb_age,
)


# ---------------------------------------------------------------------------
# Recording, and telling Craig
# ---------------------------------------------------------------------------


@dataclass
class CheckSummary:
    checked: int = 0
    problems: int = 0
    #: Problems that appeared today, each pushed once.
    new: list[str] | None = None


async def evaluate(db: AsyncSession, now: datetime) -> list[Result]:
    results: list[Result] = []
    for check in CHECKS:
        results.extend(await check(db, now))
    return results


async def record(
    db: AsyncSession, results: list[Result], now: datetime, *, scope: str = ""
) -> list[HealthCheck]:
    """Store each result; return the checks whose problem appeared with this run.

    ``scope`` limits the run to the keys that start with it: a pass of some checks only (the
    cinemas, after their refresh) leaves every other check's row as the morning left it.
    """
    stored = {
        row.check_key: row
        for row in (await db.scalars(select(HealthCheck))).all()
        if row.check_key.startswith(scope)
    }
    appeared: list[HealthCheck] = []
    seen: set[str] = set()
    for key, message in results:
        seen.add(key)
        row = stored.get(key)
        if row is None:
            row = HealthCheck(check_key=key, ok=True, checked_utc=now)
            db.add(row)
        was_ok = row.ok or row.failing_since_utc is None
        row.checked_utc = now
        row.message = message
        if message is None:
            row.ok, row.failing_since_utc, row.pushed_utc = True, None, None
            continue
        row.ok = False
        if was_ok:
            row.failing_since_utc = now
            row.pushed_utc = None
            appeared.append(row)
    # A check that no longer applies (a person removed) is no longer a problem.
    for key, row in stored.items():
        if key not in seen and not row.ok:
            row.ok, row.message, row.failing_since_utc, row.pushed_utc = True, None, None, None
            row.checked_utc = now
    await db.flush()
    return appeared


async def tell_craig(db: AsyncSession, appeared: list[HealthCheck], now: datetime) -> int:
    """One push to each admin for each problem that appeared; returns how many were queued."""
    if not appeared:
        return 0
    admins = (
        await db.scalars(
            select(Profile.id).where(
                Profile.role == UserRole.admin,
                Profile.deleted_at.is_(None),
                Profile.is_active.is_(True),
            )
        )
    ).all()
    queued = 0
    for row in appeared:
        if row.failing_since_utc is None or row.message is None:  # pragma: no cover
            continue
        for admin in admins:
            written = await queue_notification(
                db,
                user_id=admin,
                category=NotificationCategory.attention,
                title="Needs attention",
                body=row.message,
                url="/",
                dedupe_key=f"attention:{row.check_key}:{row.failing_since_utc:%Y%m%dT%H%M}:{admin}",
                now=now,
            )
            queued += written is not None
        row.pushed_utc = now
    return queued


async def run_daily_check(db: AsyncSession, *, now: datetime | None = None) -> CheckSummary:
    """Run every check, record every result, and queue one push per new problem.

    The caller commits and delivers: the reminders job does both, so the push goes out with
    the morning's reminders.
    """
    now = now or utcnow()
    results = await evaluate(db, now)
    appeared = await record(db, results, now)
    await tell_craig(db, appeared, now)
    problems = [message for _, message in results if message is not None]
    logger.info("daily_check", checked=len(results), problems=len(problems), new=len(appeared))
    return CheckSummary(
        checked=len(results),
        problems=len(problems),
        new=[row.message or "" for row in appeared],
    )


async def run_cinema_check(db: AsyncSession, *, now: datetime | None = None) -> CheckSummary:
    """The cinema checks again, after the morning's refresh has written today's run (#381).

    The daily check runs before the refresh, inside the same job, so on its own it would name
    a cinema that failed today only tomorrow. This records the cinema rows alone, and pushes
    each new one once, as the daily check does. The caller commits and delivers.
    """
    now = now or utcnow()
    results = await check_cinemas(db, now)
    appeared = await record(db, results, now, scope=CINEMA_SCOPE)
    await tell_craig(db, appeared, now)
    problems = [message for _, message in results if message is not None]
    logger.info("cinema_check", checked=len(results), problems=len(problems), new=len(appeared))
    return CheckSummary(
        checked=len(results),
        problems=len(problems),
        new=[row.message or "" for row in appeared],
    )


@dataclass(frozen=True)
class CurrentProblem:
    check_key: str
    message: str
    failing_since_utc: datetime | None


async def current_problems(
    db: AsyncSession, *, now: datetime | None = None
) -> list[CurrentProblem]:
    """Operational snapshots plus identification's current actionable state.

    Reconcile historical saved identification warnings at read time without writing a GET,
    refreshing the daily heartbeat or pushing. Only the real daily run records/notifies.
    """
    now = now or utcnow()
    saved = list((await db.scalars(select(HealthCheck).where(HealthCheck.ok.is_(False)))).all())
    identification = dict(await check_identification(db, now))
    by_key = {row.check_key: row for row in saved}
    problems = [
        CurrentProblem(row.check_key, row.message or "", row.failing_since_utc)
        for row in saved
        if row.check_key not in identification
    ]
    for key, message in identification.items():
        if message is not None:
            previous = by_key.get(key)
            problems.append(
                CurrentProblem(key, message, previous.failing_since_utc if previous else None)
            )
    return sorted(
        problems,
        key=lambda row: (
            row.failing_since_utc is None,
            row.failing_since_utc or now,
            row.check_key,
        ),
    )


async def last_checked(db: AsyncSession) -> datetime | None:
    return await db.scalar(select(func.max(HealthCheck.checked_utc)))
