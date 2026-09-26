"""One Blu-ray.com backfill batch — Batch T7, `DECISIONS.md` #202 within #110.

The nightly job, and how a first batch is run by hand:

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.spec_backfill

It needs ``DATABASE_URL``, and ``BRAVE_SEARCH_API_KEY`` to search. Without the key it still
fetches pages Craig has chosen. It searches up to 150 discs, then fetches up to 150 accepted
pages five seconds apart, and **stops everything on a 403 or 429 from Blu-ray.com**, which
only an owner decision undoes.

It **exits non-zero** when a batch stopped on errors or the integration is halted, so a job
that quietly did nothing does not look like a quiet night.
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from src.database import AsyncSessionLocal
from src.models.specs_backfill import SpecRun
from src.services.specs.backfill import Coverage, StartOutcome, coverage, start_run, work_run
from src.services.specs.search import BraveSearch

_NOT_STARTED = {
    "running": "Another batch is running; nothing was done.",
    "halted": "The Blu-ray.com integration is halted (DECISIONS.md #110); nothing was done.",
    "nothing_due": "Nothing to search for or fetch; nothing was done.",
}


def report(outcome: StartOutcome, run: SpecRun | None, counts: Coverage) -> int:
    """Print what happened and where the backfill stands; return the exit code."""
    if run is None:
        print(_NOT_STARTED.get(outcome.reason, outcome.reason))
    else:
        print(f"spec batch {run.status}")
        print(f"  Brave searches: {run.searches} of {run.search_budget}")
        print(f"  discs searched: {run.searched}")
        print(
            f"    again:        {run.searched_again}, film identified since; "
            f"{run.settled_again} of them accepted"
        )
        print(f"    accepted:     {run.accepted}")
        print(f"    for Craig:    {run.queued}")
        print(f"    nothing:      {run.no_match}")
        print(f"    restored:     {run.restored} (10 Sep specs, UK page confirmed)")
        print(f"  pages fetched:  {run.fetched} of {run.fetch_budget}")
        print(f"    specs saved:  {run.applied}")
        print(f"    sent back:    {run.sent_back}")
        print(f"    failed:       {run.fetch_failed}")
        if run.last_error:
            print(f"  note: {run.last_error}")
    print(
        f"coverage: {counts.with_specs} of {counts.discs} Blu-ray and 4K discs have specs; "
        f"{counts.accepted} waiting to be fetched, {counts.needs_you + counts.no_match} for "
        f"Craig, {counts.skipped} skipped, {counts.not_searched} not searched yet"
    )
    failed = outcome.reason == "halted" or (run is not None and run.status in ("stopped", "halted"))
    return 1 if failed else 0


async def main() -> int:
    async with BraveSearch() as brave, httpx.AsyncClient() as client, AsyncSessionLocal() as db:
        outcome = await start_run(db, trigger="job", search_configured=brave.configured)
        run = (
            await work_run(db, outcome.run.id, searcher=brave, client=client)
            if outcome.run
            else None
        )
        counts = await coverage(db)
    return report(outcome, run, counts)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
