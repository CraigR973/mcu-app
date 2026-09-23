"""Price the films that are due, within today's eBay share — Batch T6.

The same run as the Home button's, for a scheduled job or a first run by hand:

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.value_collection

It needs ``DATABASE_URL``, ``EBAY_CLIENT_ID`` and ``EBAY_CLIENT_SECRET``. Run nightly, it
spends nothing on nights when nothing is due, and a full valuation of 1,454 films and
formats completes over two nights, then refreshes every 30 days.

It **exits non-zero** when eBay is not configured, or when a run stopped without pricing a
single film, so a job that quietly did nothing does not look like a quiet night.
"""

from __future__ import annotations

import asyncio
import sys

from src.database import AsyncSessionLocal
from src.ebay.client import EbayClient
from src.models.valuation import ValuationRun
from src.services.valuation import StartOutcome, start_run, work_run

_NOT_STARTED = {
    "running": "Another valuation run is in progress; nothing was done.",
    "nothing_due": "Every film was priced in the last 30 days; nothing was done.",
    "budget_spent": "Today's eBay share is spent; the next run carries on.",
}


def report(outcome: StartOutcome, run: ValuationRun | None) -> int:
    """Print what happened and return the exit code."""
    if run is None:
        print(_NOT_STARTED.get(outcome.reason, outcome.reason))
        print(f"  films due: {outcome.due}, calls left today: {outcome.budget_left}")
        return 0
    print(f"valuation run {run.status}")
    print(f"  eBay calls:  {run.calls} of {run.budget}")
    print(f"  priced:      {run.priced}")
    print(f"  not priced:  {run.not_priced} (too few matching listings)")
    print(f"  failed:      {run.failed}")
    print(f"  still due:   {run.remaining}")
    if run.last_error:
        print(f"  last error:  {run.last_error}")
    stopped_empty = run.status == "stopped" and run.priced + run.not_priced == 0
    return 1 if stopped_empty else 0


async def main() -> int:
    async with EbayClient() as client:
        if not client.configured:
            print("EBAY_CLIENT_ID and EBAY_CLIENT_SECRET are not set; nothing was done.")
            return 1
        async with AsyncSessionLocal() as db:
            outcome = await start_run(db, trigger="job")
            run = await work_run(db, client, outcome.run.id) if outcome.run else None
    return report(outcome, run)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
