"""Check the eBay price targets and scan the newest listings for deals — Batch T8a.

The job ``cron-ebay`` runs this every two hours (`.railway/railway.ts`), and it can be run
by hand the same way:

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.ebay_watch

It needs ``DATABASE_URL``, ``EBAY_CLIENT_ID`` and ``EBAY_CLIENT_SECRET``, and the push keys
to send what it finds. It spends at most what is left of the day's share of eBay calls.

It **exits non-zero** when eBay is not configured or the pass stopped on eBay's errors, so
a job that quietly did nothing does not look like a quiet two hours.
"""

from __future__ import annotations

import asyncio
import sys

from src.database import AsyncSessionLocal
from src.ebay.client import EbayClient
from src.models.ebay_watch import EbayWatchRun
from src.services import heartbeat
from src.services.ebay_watch.runs import (
    StartOutcome,
    deliver_now,
    record_delivered,
    start_run,
    work_run,
)

_NOT_STARTED = {
    "running": "Another pass is running; nothing was done.",
    "budget_spent": "Today's share of eBay calls is spent; the next pass after midnight UTC "
    "carries on.",
}


def report(outcome: StartOutcome, run: EbayWatchRun | None) -> int:
    """Print what happened and return the exit code."""
    if run is None:
        print(_NOT_STARTED.get(outcome.reason, outcome.reason))
        return 0
    print(f"eBay watch pass {run.status}")
    print(f"  eBay calls:      {run.calls} of {run.budget}")
    print(f"  targets checked: {run.targets_checked}, met {run.target_alerts}")
    print(
        f"  new listings:    {run.listings_seen} in {run.pages} pages; "
        f"{run.candidates} wanted or upgrades"
    )
    print(f"  usual prices:    {run.refs_fetched} looked up")
    print(f"  deals:           {run.deals_found} found, {run.deals_pushed} pushed")
    if run.last_error:
        print(f"  last error:      {run.last_error}")
    return 1 if run.status == "stopped" else 0


async def main() -> int:
    async with EbayClient() as client:
        if not client.configured:
            print("EBAY_CLIENT_ID and EBAY_CLIENT_SECRET are not set; nothing was done.")
            return 1
        async with AsyncSessionLocal() as db:
            outcome = await start_run(db, trigger="job")
            if outcome.run is None:
                # Batch X2: a beat when no pass starts, so idle reads differently from stopped.
                await heartbeat.beat(db, heartbeat.EBAY, outcome.reason.replace("_", " "))
                return report(outcome, None)
            result = await work_run(db, client, outcome.run.id)
            await deliver_now(db, result.told)
            # Batch X3: "pushed" is what reached a phone, not what was queued.
            await record_delivered(db, result.run)
            await heartbeat.beat(
                db,
                heartbeat.EBAY,
                f"{result.run.status.replace('_', ' ')}, {result.run.listings_seen} listings read",
            )
    return report(outcome, result.run)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
