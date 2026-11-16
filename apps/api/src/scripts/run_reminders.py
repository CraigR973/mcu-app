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

**Since AG1 (CR49-01) every step after the reminders' own work is guarded.** The watch-history
sync runs on a session of its own, and it, the cinema refresh, the cinema check and the cinema
digest each run inside :func:`_phase`: an exception in one is printed with its traceback and the
next step still runs. Wave 2's review proved that one person's failed sync used to stop the
other person's sync, delivery, the heartbeat, the cinema refresh and the digest. The reminders,
the daily check and the delivery stay unguarded: they are this job's own work, and their
failure is the job's failure.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from collections.abc import Awaitable, Callable
from datetime import date

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from src.clock import utc_today, utcnow
from src.config import settings
from src.services import heartbeat
from src.services.cinema_digest.delivery import deliver as deliver_cinema_digest
from src.services.cinemas.refresh import refresh_due
from src.services.health_checks import CheckSummary, run_cinema_check, run_daily_check
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
    print(f"  cinema trips:    {summary.cinema_trips}")
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


async def _phase[T](name: str, step: Callable[[], Awaitable[T]], fallback: T) -> T:
    """Run one guarded step of the morning: a failure is printed, and the job carries on.

    AG1 (CR49-01): one step's exception must never skip the steps after it. The step builds
    its own session, so nothing it leaves half-done reaches the next one.
    """
    try:
        return await step()
    except Exception as exc:  # noqa: BLE001 - a guarded phase never stops the morning
        print(f"{name}: failed, {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return fallback


async def _sync_watch_history(engine: AsyncEngine) -> list[SyncResult]:
    """The weekly Letterboxd sync on a session of its own (X5, guarded since AG1)."""
    async with AsyncSession(engine, expire_on_commit=False) as db:
        return await sync_due(db, now=utcnow())


async def _cinema_check(engine: AsyncEngine) -> CheckSummary:
    async with AsyncSession(engine, expire_on_commit=False) as db:
        cinema_check = await run_cinema_check(db)
        await db.commit()
    return cinema_check


async def _run(*, as_of: date | None, deliver: bool) -> int:
    engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            summary = await run_reminders(db, as_of=as_of)
            # Batch X2: the daily check, queued before delivery so its pushes go out now.
            check = await run_daily_check(db)
            await db.commit()
            # Batch X5: the weekly watch-history sync, each run recorded on its own row. AG1:
            # on a session of its own, and guarded, so a failure cannot skip what follows.
            synced = await _phase(
                "watch history", lambda: _sync_watch_history(engine), list[SyncResult]()
            )
            delivered = 0
            failed = 0
            if deliver:
                async with push_sender() as sender:
                    delivery = await deliver_pending(db, sender=sender)
                    delivered = delivery.sent
                    failed = delivery.failed
            await db.commit()
            await heartbeat.beat(db, heartbeat.REMINDERS, "ran")
        # AB6: independent sessions after delivery/commit. Disabled venue seeds cause
        # zero source requests. Cinema status is separate from the reminder exit code.
        cinema = await _phase("cinema programme", lambda: refresh_due(engine), {"status": "failed"})
        print(f"cinema programme:  {cinema['status']}")
        # The ODEON fast lane (#381): the cinema rows again, now that today's run is written, so a
        # cinema that failed this morning reaches Craig this morning, not tomorrow.
        cinema_check = await _phase("cinema check", lambda: _cinema_check(engine), CheckSummary())
        print(f"cinema check:      {cinema_check.problems} problems")
        for message in cinema_check.new or []:
            print(f"  new:             {message}")
        if deliver:
            async with push_sender() as sender:
                cinema_delivery = await _phase(
                    "cinema digest", lambda: deliver_cinema_digest(engine, sender), None
                )
                if cinema_delivery is not None:
                    delivered += cinema_delivery.sent
                    failed += cinema_delivery.failed
                if cinema_check.new:
                    async with AsyncSession(engine, expire_on_commit=False) as db:
                        attention = await deliver_pending(db, sender=sender)
                        await db.commit()
                    delivered += attention.sent
                    failed += attention.failed
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
