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

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import and_, distinct, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from src.clock import utcnow
from src.models.ai import AiUsageLogEntry
from src.models.collection_item import CollectionItem
from src.models.deal import Deal, live_deal
from src.models.ebay_watch import EbayWatchRun
from src.models.health import HealthCheck, JobHeartbeat
from src.models.identify import IdentifyLookup
from src.models.movie import Movie
from src.models.notification import (
    Notification,
    NotificationCategory,
    NotificationStatus,
    PushSubscription,
)
from src.models.price_history import ScrapeRun
from src.models.profile import Profile, UserRole
from src.models.reviews import FilmReview
from src.models.specs_backfill import SpecLookup, SpecRun
from src.models.specs_state import SINGLETON_ID, SpecsIntegrationState
from src.models.valuation import ValuationRun
from src.services import heartbeat
from src.services.notifications import queue_notification

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


@dataclass(frozen=True)
class Job:
    """A scheduled job, how long it may go quiet, and its own run table's start column."""

    name: str
    label: str
    cadence: timedelta
    #: Its run table's start time, which also counts: a run started from the app is a run.
    started: InstrumentedAttribute[datetime]


#: Each job's allowance is its schedule plus a margin: daily jobs 26 hours, the two-hourly
#: eBay scan 5 hours, the valuation (1st, 2nd, 15th, 16th) 17 days.
JOBS: tuple[Job, ...] = (
    Job(
        heartbeat.SCRAPE,
        "The nightly shop price check",
        timedelta(hours=26),
        ScrapeRun.started_at_utc,
    ),
    Job(
        heartbeat.SPECS,
        "The nightly disc spec and review job",
        timedelta(hours=26),
        SpecRun.started_utc,
    ),
    Job(heartbeat.EBAY, "The eBay scan", timedelta(hours=5), EbayWatchRun.started_utc),
    Job(heartbeat.VALUES, "The valuation job", timedelta(days=17), ValuationRun.started_utc),
)

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


async def check_jobs(db: AsyncSession, now: datetime) -> list[Result]:
    """Each job ran (or beat) within its cadence."""
    beats = {row.job: row for row in (await db.scalars(select(JobHeartbeat))).all()}
    results: list[Result] = []
    for job in JOBS:
        times = [beats[job.name].beat_utc] if job.name in beats else []
        started = await db.scalar(select(func.max(job.started)))
        if started is not None:
            times.append(started)
        last = max(times) if times else None
        if last is None:
            message: str | None = f"{job.label} has never run."
        elif last < now - job.cadence:
            message = f"{job.label} hasn't run since {day(last)}."
        else:
            message = None
        results.append((f"job:{job.name}", message))
    return results


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


async def check_people(db: AsyncSession, now: datetime) -> list[Result]:
    """Each person holds a live device, and their last three days are not all undelivered."""
    people = (
        await db.scalars(
            select(Profile).where(Profile.deleted_at.is_(None), Profile.is_active.is_(True))
        )
    ).all()
    results: list[Result] = []
    for person in people:
        devices = await db.scalar(
            select(func.count(PushSubscription.id)).where(
                PushSubscription.user_id == person.id, PushSubscription.revoked_at_utc.is_(None)
            )
        )
        key = f"person:{person.id}:notifications"
        if not devices:
            results.append((key, f"{person.display_name} has no phone getting notifications."))
            continue
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
            results.append(
                (
                    key,
                    f"None of {person.display_name}'s {len(statuses)} notifications since "
                    f"{day(now - NOTIFICATION_WINDOW)} reached a phone.",
                )
            )
        else:
            results.append((key, None))
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
    """Identify proposals older than a fortnight; identified films a page says are another year."""
    waiting = int(
        await db.scalar(
            select(func.count(IdentifyLookup.id)).where(
                IdentifyLookup.status == "needs_you",
                IdentifyLookup.created_utc < now - PROPOSAL_AGE,
            )
        )
        or 0
    )
    spec_doubt = (
        select(CollectionItem.movie_id)
        .join(SpecLookup, SpecLookup.collection_item_id == CollectionItem.id)
        .where(SpecLookup.note.like("The page is for a % film and this one is from %"))
    )
    review_doubt = select(FilmReview.movie_id).where(FilmReview.status == "mismatch")
    doubted = int(
        await db.scalar(
            select(func.count(distinct(Movie.id))).where(
                Movie.deleted_at.is_(None),
                Movie.tmdb_id.is_not(None),
                or_(Movie.id.in_(spec_doubt), Movie.id.in_(review_doubt)),
            )
        )
        or 0
    )
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


async def record(db: AsyncSession, results: list[Result], now: datetime) -> list[HealthCheck]:
    """Store each result; return the checks whose problem appeared with this run."""
    stored = {row.check_key: row for row in (await db.scalars(select(HealthCheck))).all()}
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


async def current_problems(db: AsyncSession) -> list[HealthCheck]:
    """The checks failing as of the last run, oldest problem first, for the Home row."""
    return list(
        (
            await db.scalars(
                select(HealthCheck)
                .where(HealthCheck.ok.is_(False))
                .order_by(HealthCheck.failing_since_utc, HealthCheck.check_key)
            )
        ).all()
    )


async def last_checked(db: AsyncSession) -> datetime | None:
    return await db.scalar(select(func.max(HealthCheck.checked_utc)))
