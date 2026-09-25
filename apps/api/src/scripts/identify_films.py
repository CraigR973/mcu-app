"""Identify the films TMDB never matched — Batch T9.

**First, a dry run, which writes nothing.** It reads the collection, asks TMDB and at most
``--brave-budget`` Brave searches, and saves the plan and a report for Craig:

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.identify_films \\
        --plan-out plan.json --report-out report.html

It reads the collection in a short read-only transaction, so Postgres itself refuses a
write, and closes it before asking TMDB anything, so no connection sits idle for Neon to drop.
It reads no table the batch's migration adds, so it can run before the merge that applies it.

**Then, after Craig has read the report and said go, the live run applies that plan:**

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.identify_films \\
        --apply plan.json

The live run records the Brave searches the dry run spent, and ``--earlier-searches`` adds
those of dry runs this month that were never applied. It **exits non-zero** if it stopped on
errors.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.database import AsyncSessionLocal
from src.models.specs_backfill import SpecRun
from src.services.identify.apply import RunInProgress, apply_plan, start_run
from src.services.identify.matcher import Identifier
from src.services.identify.plan import (
    Item,
    Plan,
    held_films,
    propose,
    table_exists,
    unidentified_films,
)
from src.services.identify.report import render_report
from src.services.specs.backfill import MONTHLY_SEARCH_CEILING, month_start
from src.services.specs.search import BraveSearch
from src.tmdb.client import TMDBClient

#: Brave searches one dry run may spend. 25 Sep's needed 24.
DEFAULT_BRAVE_BUDGET = 60
#: TMDB allows about 50 requests a second; the app's own client keeps to 3.
TMDB_RATE = 8.0


async def brave_spent_this_month(db: AsyncSession) -> int:
    """Brave searches billed this month by T7's batches and by identification runs.

    The same sum as T7's ``searches_this_month``, asking first whether the identification
    table exists, because the dry run runs before the migration that adds it.
    """
    start = month_start(utcnow())
    spent = int(
        await db.scalar(
            select(func.coalesce(func.sum(SpecRun.searches), 0)).where(SpecRun.started_utc >= start)
        )
        or 0
    )
    if await table_exists(db, "identify_runs"):
        spent += int(
            await db.scalar(
                text(
                    "SELECT coalesce(sum(searches), 0) FROM identify_runs "
                    "WHERE started_utc >= :start"
                ),
                {"start": start},
            )
            or 0
        )
    return spent


def _progress(index: int, total: int, item: Item) -> None:
    if index % 25 == 0 or index == total:
        print(f"  {index} of {total} films looked at", flush=True)


async def dry_run(plan_out: Path, report_out: Path, *, budget: int, only: set[str]) -> int:
    async with AsyncSessionLocal() as db:
        # Postgres refuses any write in this transaction: "writes nothing" is enforced, not
        # promised. It is over before TMDB is asked anything, so no connection is held
        # through the searches for Neon to close.
        await db.execute(text("SET TRANSACTION READ ONLY"))
        left = max(MONTHLY_SEARCH_CEILING - await brave_spent_this_month(db), 0)
        films = await unidentified_films(db)
        held = await held_films(db)
        await db.rollback()
    async with TMDBClient(rate=TMDB_RATE) as tmdb, BraveSearch() as brave:
        identifier = Identifier(tmdb, brave, brave_budget=min(budget, left))
        plan = await propose(
            films, held, identifier, now=utcnow(), only=only or None, progress=_progress
        )
    plan.save(plan_out)
    report_out.write_text(render_report(plan, ceiling_left=left), encoding="utf-8")
    print("dry run finished; nothing was written")
    print(f"  films:            {plan.films}")
    print(f"  identify:         {plan.count('identify')}")
    print(f"  ask Craig:        {plan.count('ask')}")
    print(f"  set aside:        {plan.count('set_aside')}")
    print(f"  TMDB calls:       {plan.tmdb_calls}")
    print(f"  Brave searches:   {plan.brave_searches} of {identifier.brave_budget}")
    print(f"  plan:   {plan_out}")
    print(f"  report: {report_out}")
    return 0


async def live_run(plan_path: Path, *, earlier_searches: int = 0) -> int:
    plan = Plan.load(plan_path)
    async with TMDBClient() as tmdb, AsyncSessionLocal() as db:
        try:
            run = await start_run(db, plan, earlier_searches=earlier_searches)
        except RunInProgress as exc:
            print(str(exc))
            return 1
        run = await apply_plan(db, plan, tmdb, run=run)
    print(f"identification run {run.status}")
    print(f"  films:        {run.films}")
    print(f"  identified:   {run.identified}")
    print(f"  for Craig:    {run.queued}")
    print(f"  set aside:    {run.set_aside}")
    print(f"  left alone:   {run.unchanged} (changed since the dry run, or already decided)")
    print(f"  failed:       {run.failed}")
    print(f"  Brave searches recorded: {run.searches}")
    if run.last_error:
        print(f"  last error: {run.last_error}")
    return 1 if run.status == "stopped" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else "")
    parser.add_argument("--plan-out", type=Path, help="Dry run: where to save the plan")
    parser.add_argument("--report-out", type=Path, help="Dry run: where to save the report")
    parser.add_argument("--brave-budget", type=int, default=DEFAULT_BRAVE_BUDGET)
    parser.add_argument("--only", action="append", default=[], help="A title or film id")
    parser.add_argument("--apply", type=Path, help="Live run: the plan Craig approved")
    parser.add_argument(
        "--earlier-searches",
        type=int,
        default=0,
        help="Live run: Brave searches spent by dry runs this month whose plans were not "
        "applied, so the monthly ceiling counts them too",
    )
    args = parser.parse_args(argv)
    if args.apply:
        return asyncio.run(live_run(args.apply, earlier_searches=args.earlier_searches))
    if not args.plan_out or not args.report_out:
        parser.error("a dry run needs --plan-out and --report-out")
    return asyncio.run(
        dry_run(args.plan_out, args.report_out, budget=args.brave_budget, only=set(args.only))
    )


if __name__ == "__main__":
    sys.exit(main())
