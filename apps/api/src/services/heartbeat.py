"""Each job's heartbeat — Batch X2 (DS44-01).

Every scheduled job calls :func:`beat` each time it runs, whatever it did, and the API calls it
once at boot with its readiness. Before X2 the spec, valuation and eBay jobs wrote no row when
nothing was due or the day's budget was spent, so from the database an idle job and a stopped
one looked the same; the daily check (`services/health_checks.py`) reads these to tell them
apart.

A beat that cannot be written never fails the job: the job's own work and exit code are what
matter, and a database that refuses the beat has refused the work too.

**Since AG2 (DS50-01) one rule covers every scheduled thing, not a list in the check.** Each is
named once in :data:`SCHEDULED`, with how long it may go quiet and where its schedule lives; each
writes a beat with a **failure figure** (what the run itself counts as failing, the same thing
its exit code is about) and its cadence; and the daily check reads every beat. At wave 2's review
the check watched four of eight. A CI test (`tests/test_every_scheduled_thing_watched.py`) reads
the Railway services and the scheduled workflows and fails on one that is not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.health import JobHeartbeat

logger = structlog.get_logger(__name__)

#: The Railway services' own names, so a row reads as the console does.
SCRAPE = "cron-scrape"
SPECS = "cron-specs"
EBAY = "cron-ebay"
VALUES = "cron-values"
REMINDERS = "cron-reminders"
API = "api"
#: Inside the 08:00 job: the cinema programme (AB6) and, since AG2, the TMDB refresh (DS50-05).
CINEMAS = "cinema-programme"
TMDB = "tmdb-refresh"
#: The weekly copy of the database, a GitHub Actions workflow (X4), beating since AG2.
BACKUP = "backup"


@dataclass(frozen=True)
class Scheduled:
    """Something that runs on a schedule, and how long it may go quiet before it is named."""

    job: str
    #: How the daily check names it.
    label: str
    #: Its schedule plus a margin.
    cadence: timedelta
    #: Where its schedule lives: ``railway:<service>``, ``workflow:<file>``, or
    #: ``inside:<service>`` for a step of another job. The CI test reads these.
    schedule: str
    #: The daily-check row that judges it, when it is not ``job:<job>``.
    row: str | None = None
    #: Not called late before this (UTC): a thing that began beating with a batch is not
    #: "never run" the morning after it shipped.
    watched_from: datetime | None = None

    @property
    def key(self) -> str:
        return self.row or f"job:{self.job}"


#: Every scheduled thing (AG2). Daily jobs 26 hours, the two-hourly eBay scan 5, the valuation
#: (1st, 2nd, 15th, 16th) 17 days, the weekly backup 8.
SCHEDULED: tuple[Scheduled, ...] = (
    Scheduled(SCRAPE, "The nightly shop price check", timedelta(hours=26), "railway:cron-scrape"),
    Scheduled(
        SPECS, "The nightly disc spec and review job", timedelta(hours=26), "railway:cron-specs"
    ),
    Scheduled(EBAY, "The eBay scan", timedelta(hours=5), "railway:cron-ebay"),
    Scheduled(VALUES, "The valuation job", timedelta(days=17), "railway:cron-values"),
    Scheduled(
        REMINDERS,
        "The 08:00 job (reminders, watch history, the cinema digest)",
        timedelta(hours=26),
        "railway:cron-reminders",
    ),
    Scheduled(
        CINEMAS,
        "The cinema programme",
        timedelta(hours=26),
        "inside:cron-reminders",
        # `health_checks.check_cinemas` judges it, beside each cinema's own row (#381).
        row="cinema:job",
    ),
    Scheduled(
        TMDB,
        "The TMDB refresh",
        timedelta(hours=26),
        "inside:cron-reminders",
        watched_from=datetime(2026, 11, 18, 10, 0),
    ),
    Scheduled(
        BACKUP,
        "The weekly backup",
        timedelta(days=8),
        "workflow:backup.yml",
        watched_from=datetime(2026, 11, 25, 8, 0),
    ),
)

BY_JOB = {thing.job: thing for thing in SCHEDULED}


async def beat(
    db: AsyncSession,
    job: str,
    outcome: str,
    *,
    failures: int = 0,
    detail: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    """Record that ``job`` ran just now, what it did, and how much of it failed.

    ``failures`` is the run's own count of what failed: zero for a run that did its work,
    whatever it found. The scheduled thing's cadence goes in beside it, so the check can judge
    any beat it finds, listed or not.
    """
    full: dict[str, Any] = dict(detail or {})
    full["failures"] = failures
    if job in BY_JOB:
        full["cadenceHours"] = BY_JOB[job].cadence / timedelta(hours=1)
    values = {"beat_utc": now or utcnow(), "outcome": outcome[:200], "detail": full}
    try:
        await db.execute(
            insert(JobHeartbeat)
            .values(job=job, **values)
            .on_conflict_do_update(index_elements=[JobHeartbeat.job], set_=values)
        )
        await db.commit()
    except Exception:  # noqa: BLE001 - see the module docstring
        logger.warning("heartbeat_failed", job=job, exc_info=True)
        await db.rollback()
