"""§5.5's nightly pass, as a command — **what the Railway cron actually runs.**

`POST /api/v1/scrapers/daily` does the same work, but it is `AdminUser`-authed and an
access token lives 24 hours (`auth.py`), so a cron container has no way to call it: no
browser, no login, nothing to refresh. Batches 11 and 20 shipped the endpoint and left
this half unbuilt, which made "wire the cron" an owner action nobody could complete.
`DECISIONS.md` #119 is the record.

The pattern is `refresh_completion_sets.py`'s, and for #60's reason: scheduling should be
one console action rather than a piece of engineering. Both are true here — the container
already holds `DATABASE_URL` and the VAPID keys, so this needs no credential of its own
and adds no second authentication path to the API.

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 \\
        -m src.scripts.daily_scrape --dry-run
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 \\
        -m src.scripts.daily_scrape

**``--dry-run`` makes live requests and writes nothing.** That is the opposite of harmless
— it is a rehearsal against real shops — so it is opt-in here exactly as it is opt-out on
the endpoint. A scheduled job whose whole purpose is to write must not default to writing
nothing: a cron that quietly did nothing every night is indistinguishable from one that
works.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.config import settings
from src.models.price_history import RETENTION_DAYS
from src.services.push_transport import push_sender
from src.services.scraping.daily import DailyRunSummary, failure_records, run_daily_scrape


def report(summary: DailyRunSummary, *, dry_run: bool) -> int:
    """Print what the night did and return the exit code the cron will see.

    Separated from the run so the exit code can be tested without a database. It is the
    part worth testing: a cron that exits 0 after a failed night is the same silence as a
    cron that never fired.
    """
    result = summary.scrape
    attempted = sum(1 for o in result.outcomes if not o.skipped and not o.not_stocked)

    print(f"{'DRY RUN — ' if dry_run else ''}daily scrape complete")
    print(f"  run id:        {summary.run_id}")
    print(f"  attempted:     {attempted}")
    print(f"  written:       {result.written}")
    print(f"  not stocked:   {result.not_stocked}")
    # Batch 20b: refusals are among the failures below, but never count towards a shop
    # being switched off. The count says how many of them were the shop saying no.
    print(f"  refused:       {result.refused}")
    print(f"  skipped:       {result.skipped}")
    print(f"  alerts queued: {summary.alerts_queued}")
    print(f"  pushes sent:   {summary.pushes_sent}")
    if summary.aggregation is not None:
        rollup = summary.aggregation
        print(
            f"  rolled up:     {rollup.raw_rows_removed} checks into "
            f"{rollup.rows_written} daily rows across {rollup.days_aggregated} days"
        )

    # Counted explicitly and printed last, per gotcha 16: read the failure count rather
    # than trusting the success lines above it. A partial night is still a real night —
    # the run row is written either way — so this reports rather than raises.
    failures = failure_records(result)
    if failures:
        print(f"  failures:      {len(failures)}", file=sys.stderr)
        for record in failures:
            line = f"    - {record['retailer']}: {record['wanted']} — {record['reason']}"
            print(line, file=sys.stderr)
        return 1
    print("  failures:      0")
    return 0


async def _run(*, dry_run: bool, retention_days: int) -> int:
    engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            async with push_sender() as sender:
                summary = await run_daily_scrape(
                    db,
                    sender=sender,
                    trigger="cron",
                    dry_run=dry_run,
                    retention_days=retention_days,
                )
            await db.commit()
    finally:
        await engine.dispose()
    return report(summary, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the nightly scrape, alert and roll-up pass.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Make the live requests and report what would happen, without writing",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=RETENTION_DAYS,
        help=f"Roll checks older than this into price_history_daily (default: {RETENTION_DAYS})",
    )
    args = parser.parse_args()
    if args.retention_days < 1:
        parser.error("--retention-days must be at least 1")
    return asyncio.run(_run(dry_run=args.dry_run, retention_days=args.retention_days))


if __name__ == "__main__":
    raise SystemExit(main())
