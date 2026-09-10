"""The nightly job — §5.5, and the thing a Railway cron calls.

**There is no scheduler in this process, deliberately.** §5.5 says "APScheduler job running
daily" and `DECISIONS.md` #60 rules that out: an in-process timer fires once per container,
so scaling to two instances silently doubles every scrape against every retailer. The
schedule is a Railway cron hitting one endpoint, which makes it a hosting change and
therefore an owner action — and leaves *"first overnight run completes"* as something an
agent cannot claim.

**One pass does four things in order**, and the order matters: scrape, alert on anything
that has just fallen below its threshold, deliver what is queued, then roll up whatever is
now older than 90 days. Aggregating first would be harmless; alerting after delivering
would hold every drop for a day.

**The run writes itself down before it starts and again when it ends.** A run that dies
halfway then reads as a run that died halfway, rather than as no run at all — which is the
only difference between "the cron is broken" and "the cron never fired", and they have
different fixes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.price_history import RETENTION_DAYS, ScrapeRun
from src.services.notifications import PushSender, deliver_pending
from src.services.scraping.aggregate import AggregationResult, aggregate_old_checks
from src.services.scraping.alerts import queue_price_drop_alerts
from src.services.scraping.runner import ScrapeRunResult, run_scrape

logger = structlog.get_logger(__name__)

#: How many failures are written down per run. A shop that fails on every one of a hundred
#: wants should not put a hundred near-identical strings in one JSONB column.
MAX_RECORDED_FAILURES = 50


@dataclass
class DailyRunSummary:
    """Everything one nightly pass did, for the endpoint and for the tests."""

    run_id: str
    scrape: ScrapeRunResult
    alerts_queued: int = 0
    pushes_sent: int = 0
    aggregation: AggregationResult | None = None


def failure_records(result: ScrapeRunResult) -> list[dict[str, str]]:
    """§5.5's "failures logged with retailer + reason", as rows rather than log lines."""
    records: list[dict[str, str]] = []
    for outcome in result.outcomes:
        if outcome.ok or outcome.skipped or outcome.not_stocked:
            continue
        reason = outcome.error or "; ".join(outcome.reasons) or "no usable result"
        records.append(
            {
                "retailer": outcome.retailer,
                "wanted": outcome.wanted_title,
                "reason": reason[:500],
            }
        )
        if len(records) >= MAX_RECORDED_FAILURES:
            break
    return records


async def run_daily_scrape(
    db: AsyncSession,
    *,
    sender: PushSender,
    client: httpx.AsyncClient | None = None,
    trigger: str = "cron",
    dry_run: bool = False,
    polite_pause: float | None = None,
    retention_days: int = RETENTION_DAYS,
    now: datetime | None = None,
    aggregate: bool = True,
) -> DailyRunSummary:
    """Scrape, alert, deliver and roll up. **Makes live requests unless ``dry_run``.**"""
    now = now or utcnow()
    run = ScrapeRun(started_at_utc=now, trigger=trigger, dry_run=dry_run)
    db.add(run)
    await db.flush()

    kwargs = {} if polite_pause is None else {"polite_pause": polite_pause}
    try:
        result = await run_scrape(db, client=client, dry_run=dry_run, **kwargs)
    except Exception as exc:
        # The run row survives to say what happened; re-raising without it would leave
        # "the cron fired and nothing exists" indistinguishable from "the cron never fired".
        run.finished_at_utc = utcnow()
        run.error = str(exc)[:2000]
        await db.flush()
        logger.exception("daily_scrape_failed")
        raise

    summary = DailyRunSummary(run_id=str(run.id), scrape=result)

    if not dry_run:
        summary.alerts_queued = await queue_price_drop_alerts(db, result.written_checks, now=now)
        delivery = await deliver_pending(db, sender=sender, now=now)
        summary.pushes_sent = delivery.sent
        if aggregate:
            summary.aggregation = await aggregate_old_checks(
                db, older_than_days=retention_days, now=now
            )

    run.finished_at_utc = utcnow()
    run.attempted = sum(1 for o in result.outcomes if not o.skipped and not o.not_stocked)
    run.not_stocked = result.not_stocked
    run.skipped = result.skipped
    run.succeeded = result.succeeded
    run.failed = result.failed
    run.written = result.written
    run.alerts_queued = summary.alerts_queued
    run.failures = failure_records(result)
    run.disabled_retailers = list(result.disabled)
    await db.flush()

    logger.info(
        "daily_scrape_complete",
        run_id=summary.run_id,
        attempted=run.attempted,
        not_stocked=run.not_stocked,
        written=run.written,
        failed=run.failed,
        alerts=summary.alerts_queued,
    )
    return summary
