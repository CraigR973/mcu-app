"""Identify the TV series still to identify, where TMDB leaves no doubt — Batch Y3.

**First, a dry run, which writes nothing.** It reads the titles "Still to identify" (the list
Mark sees in the Archive), asks TMDB's series index for each, and saves the plan and a report:

    DATABASE_URL="$(grep '^DATABASE_URL=' apps/api/.env.local | cut -d= -f2-)" \\
    TMDB_READ_TOKEN="$(grep '^TMDB_READ_TOKEN=' apps/api/.env.local | cut -d= -f2-)" \\
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.identify_series \\
        --app-url https://mcu-app-fawn.vercel.app

It reads in a ``READ ONLY`` transaction that is over before TMDB is asked anything. The values
are exported explicitly because ``.env.local``'s connection string holds an unquoted ``&``.

**Then, after Craig has read ``series-plan.html``, the live run applies that exact plan:**

    … -m src.scripts.identify_series --apply series-plan.json

It identifies only the titles the report lists under "Will be identified", re-checking each
first; each is audited and undone from the Identify films page. It never merges. It exits
non-zero if any failed. The rule is ``services/identify/series_pass.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import text

from src.clock import utcnow
from src.config import settings
from src.database import AsyncSessionLocal
from src.services.identify.series_pass import (
    SeriesPlan,
    apply_one,
    dry_run,
    read_waiting,
    render_report,
)
from src.tmdb.client import TMDBClient

#: TMDB allows about 50 requests a second; the app's own client keeps to 3, T9's run to 8.
TMDB_RATE = 8.0


def _progress(index: int, total: int) -> None:
    if index % 10 == 0 or index == total:
        print(f"  {index} of {total} titles looked at", flush=True)


async def run_dry(plan_out: Path, report_out: Path, app_url: str) -> int:
    async with AsyncSessionLocal() as db:
        # Postgres refuses any write in this transaction, and it is over before TMDB is asked.
        await db.execute(text("SET TRANSACTION READ ONLY"))
        waiting = await read_waiting(db)
        await db.rollback()
    print(f"{len(waiting)} titles still to identify.", flush=True)
    async with TMDBClient(rate=TMDB_RATE) as tmdb:
        plan = await dry_run(waiting, tmdb, now=utcnow(), progress=_progress)
    plan.save(plan_out)
    report_out.write_text(render_report(plan, app_url=app_url), encoding="utf-8")
    print(
        f"Will identify {plan.count('identify')}, left for Mark {plan.count('ask')}, "
        f"TMDB failed on {len(plan.failed)}. Plan {plan_out}, report {report_out}."
    )
    return 1 if plan.failed else 0


async def run_apply(plan_path: Path) -> int:
    plan = SeriesPlan.load(plan_path)
    planned = [p for p in plan.proposals if p.outcome == "identify"]
    tally: Counter[str] = Counter()
    async with TMDBClient(rate=TMDB_RATE) as tmdb:
        for proposal in planned:
            async with AsyncSessionLocal() as db:
                outcome = await apply_one(db, tmdb, proposal)
            tally[outcome.result] += 1
            print(f"  {outcome.result:<10} {outcome.title}: {outcome.note}", flush=True)
    print(
        f"Identified {tally['identified']}, unchanged {tally['unchanged']}, "
        f"waiting for Mark {tally['waits']}, failed {tally['failed']}."
    )
    return 1 if tally["failed"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Identify the TV series still to identify.")
    parser.add_argument("--plan-out", type=Path, default=Path("series-plan.json"))
    parser.add_argument("--report-out", type=Path, default=Path("series-plan.html"))
    parser.add_argument("--app-url", default=settings.frontend_origin)
    parser.add_argument("--apply", type=Path, help="Apply this plan, after reading its report.")
    args = parser.parse_args(argv)
    if args.apply is not None:
        return asyncio.run(run_apply(args.apply))
    return asyncio.run(run_dry(args.plan_out, args.report_out, args.app_url))


if __name__ == "__main__":
    sys.exit(main())
