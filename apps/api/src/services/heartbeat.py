"""Each job's heartbeat — Batch X2 (DS44-01).

Every scheduled job calls :func:`beat` each time it runs, whatever it did, and the API calls it
once at boot with its readiness. Before X2 the spec, valuation and eBay jobs wrote no row when
nothing was due or the day's budget was spent, so from the database an idle job and a stopped
one looked the same; the daily check (`services/health_checks.py`) reads these to tell them
apart.

A beat that cannot be written never fails the job: the job's own work and exit code are what
matter, and a database that refuses the beat has refused the work too.
"""

from __future__ import annotations

from datetime import datetime
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


async def beat(
    db: AsyncSession,
    job: str,
    outcome: str,
    *,
    detail: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    """Record that ``job`` ran just now, and what it did."""
    values = {"beat_utc": now or utcnow(), "outcome": outcome[:200], "detail": detail}
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
