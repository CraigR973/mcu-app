"""The reminder pass, as a command — **the second thing the Railway cron runs.**

`POST /api/v1/notifications/run-reminders` is the same work behind `AdminUser`, and for
the reason in `daily_scrape.py` a cron cannot call it. Until this existed, *every* reminder
in the app — sale seasons, upcoming releases, overdue loans — waited for a person to press
a button. `DECISIONS.md` #119.

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 \\
        -m src.scripts.run_reminders --no-deliver
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 \\
        -m src.scripts.run_reminders

**Daily is the right schedule, and a double fire is harmless**: each sender checks its
`notified` flag before setting it, and `queue_notification` deduplicates on `dedupe_key`,
so running twice sends nothing twice.

``--as-of`` is what makes §5.11's acceptance testable — *"test date set 2 weeks before a
seeded event triggers a reminder"* — and it is also how a missed day is caught up. It
cannot be pushed past today: reminding somebody about a sale that has not been announced
is not a feature.

**Since Batch X2 it also runs the daily check** (`services/health_checks.py`): every job's
heartbeat, the eBay scan, each person's notifications, readiness, the database's size, PIN
locks and identification's doubts, each result recorded, and one push to Craig for each new
problem, delivered with the morning's reminders. Problems found do not fail the job; the job
fails only when it could not do its own work.

**Since Batch X5 it also keeps the watch history current**: each person with a Letterboxd
username is synced once a week (``letterboxd.sync_due``, ``trigger = cron``), so a 50-entry
feed never runs out between syncs. A failed sync is recorded on its run and never fails the
job. The job has no TMDB token, so a film it gives a row keeps the feed's title and year
until a Sync now in the app fills it in.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.clock import utc_today, utcnow
from src.config import settings
from src.services import heartbeat
from src.services.health_checks import CheckSummary, run_daily_check
from src.services.letterboxd.sync import SyncResult, sync_due
from src.services.notifications import deliver_pending
from src.services.push_transport import push_sender
from src.services.reminders import ReminderSummary, run_reminders


def report(
    summary: ReminderSummary,
    *,
    delivered: int,
    failed: int,
    deliver: bool,
    check: CheckSummary | None = None,
    synced: list[SyncResult] | None = None,
) -> int:
    """Print what the pass did and return the exit code the cron will see.

    Separated from the run for the same reason as `daily_scrape.report`: the exit code is
    the only thing a scheduler reads, so it is the thing worth a test.
    """
    print(f"reminder pass complete for {summary.as_of}")
    print(f"  sale events:     {summary.sale_events}")
    print(f"  releases:        {summary.releases}")
    print(f"  overdue loans:   {summary.overdue_loans}")
    print(f"  seasons seeded:  {summary.seasons_seeded}")
    print(f"  queued:          {summary.queued}")
    print(f"  delivered:       {delivered}" if deliver else "  delivered:       (skipped)")
    if check is not None:
        print(f"daily check:       {check.checked} checks, {check.problems} problems")
        for message in check.new or []:
            print(f"  new:             {message}")
    for result in synced or []:
        run = result.run
        outcome = run.error or f"{run.written} written of {run.entries}"
        print(f"watch history:     {outcome}")

    # Gotcha 16 again: a delivery failure must not hide behind the queued count above it.
    if failed:
        print(f"  failed:          {failed}", file=sys.stderr)
        return 1
    return 0


async def _run(*, as_of: date | None, deliver: bool) -> int:
    engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            summary = await run_reminders(db, as_of=as_of)
            # Batch X2: the daily check, queued before delivery so its pushes go out now.
            check = await run_daily_check(db)
            await db.commit()
            # Batch X5: the weekly watch-history sync, each run recorded on its own row.
            synced = await sync_due(db, now=utcnow())
            delivered = 0
            failed = 0
            if deliver:
                async with push_sender() as sender:
                    delivery = await deliver_pending(db, sender=sender)
                    delivered = delivery.sent
                    failed = delivery.failed
            await db.commit()
            await heartbeat.beat(db, heartbeat.REMINDERS, "ran")
    finally:
        await engine.dispose()
    return report(
        summary, delivered=delivered, failed=failed, deliver=deliver, check=check, synced=synced
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run every reminder sender, then deliver what is due."
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="The calendar day the reminders are about (YYYY-MM-DD, default: today UTC)",
    )
    parser.add_argument(
        "--no-deliver",
        action="store_true",
        help="Queue the reminders but send nothing — leaves the outbox for a later pass",
    )
    args = parser.parse_args()
    if args.as_of is not None and args.as_of > utc_today():
        parser.error("--as-of cannot be in the future")
    return asyncio.run(_run(as_of=args.as_of, deliver=not args.no_deliver))


if __name__ == "__main__":
    raise SystemExit(main())
