"""Re-check the films the old paths identified — Batch X9 (CT46-01).

**First, a dry run, which writes nothing.** It reads every owned copy whose film the 8 Sep
import or the diary import identified (and neither T9 nor a person has since), asks T9's
identifier again about the copy's own spreadsheet row, with free TMDB calls and no Brave, and
saves a plan and a report:

    DATABASE_URL="$(grep '^DATABASE_URL=' apps/api/.env.local | cut -d= -f2-)" \\
    TMDB_READ_TOKEN="$(grep '^TMDB_READ_TOKEN=' apps/api/.env.local | cut -d= -f2-)" \\
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.recheck_identifications \\
        --xlsx "<the collection spreadsheet>" --app-url https://mcu-app-fawn.vercel.app

It reads in a ``READ ONLY`` transaction that is over before TMDB is asked anything. The values
are exported explicitly because ``.env.local``'s connection string holds an unquoted ``&``.
About 1,500 copies take one evening at TMDB's pace; nothing is written, so it can be run again.

**Then, after Craig has read ``recheck-report.md``, at his word:**

    … -m src.scripts.recheck_identifications --apply recheck-plan.json

raises a doubt for every copy T9 disagrees about (``--verdicts`` narrows it to some of
``different``, ``series``, ``not_offered``, ``unsure`` and ``not_film``), strongest first,
re-checking each copy
is still as the dry run saw it. Each waits on Identify films with its evidence; nothing is
re-identified. The rule is ``services/identify/recheck.py``.
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
from src.services.identify.matcher import Identifier
from src.services.identify.recheck import (
    DOUBT_CLASSES,
    RecheckPlan,
    SheetRow,
    known_copies,
    old_path_copies,
    raise_one,
    recheck,
    render_report,
    to_raise,
)
from src.spreadsheet import parse_xlsx
from src.tmdb.client import TMDBClient

#: As the series pass and T9's run keep to: well inside TMDB's 50 a second.
TMDB_RATE = 8.0


def _progress(index: int, total: int) -> None:
    if index % 50 == 0 or index == total:
        print(f"  {index} of {total} copies re-checked", flush=True)


def read_sheet(path: Path) -> dict[int, SheetRow]:
    return {row.row_number: SheetRow(row.title, row.sub_category) for row in parse_xlsx(path)}


async def run_dry(xlsx: Path, plan_out: Path, report_out: Path, app_url: str) -> int:
    sheet = read_sheet(xlsx)
    async with AsyncSessionLocal() as db:
        # Postgres refuses any write in this transaction, and it is over before TMDB is asked.
        await db.execute(text("SET TRANSACTION READ ONLY"))
        copies = await old_path_copies(db)
        known = await known_copies(db)
        await db.rollback()
    print(f"{len(copies)} copies the old paths identified; {len(sheet)} sheet rows.", flush=True)
    async with TMDBClient(rate=TMDB_RATE) as tmdb:
        plan = await recheck(
            copies, sheet, Identifier(tmdb), now=utcnow(), known=known, progress=_progress
        )
    plan.save(plan_out)
    report_out.write_text(render_report(plan, app_url=app_url), encoding="utf-8")
    counts = ", ".join(f"{verdict} {plan.count(verdict)}" for verdict in DOUBT_CLASSES)
    missed = [known for known in plan.known if known.status.startswith("MISSED")]
    print(
        f"Agrees {plan.count('agrees')}, {counts}, nothing {plan.count('nothing')}. "
        f"Not re-checked: {plan.without_row} without a sheet row, {len(plan.mismatched)} whose "
        f"row has another grouping. Known wrong copies missed: {len(missed)}. "
        f"Plan {plan_out}, report {report_out}."
    )
    return 0


async def run_apply(plan_path: Path, verdicts: list[str]) -> int:
    unknown = [verdict for verdict in verdicts if verdict not in DOUBT_CLASSES]
    if unknown:
        print(f"Not a verdict that raises a doubt: {', '.join(unknown)}.", file=sys.stderr)
        return 2
    plan = RecheckPlan.load(plan_path)
    tally: Counter[str] = Counter()
    for item in to_raise(plan, verdicts):
        async with AsyncSessionLocal() as db:
            result = await raise_one(db, item)
        tally[result] += 1
        print(
            f"  {result:<11} {item.film_title} (row {item.sheet_row}): {item.verdict}", flush=True
        )
    print(
        f"Doubts raised {tally['raised']}, kept by Craig before {tally['kept_before']}, "
        f"changed since the dry run {tally['changed']}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-check the old paths' identifications.")
    parser.add_argument("--xlsx", type=Path, help="The collection spreadsheet, for the dry run.")
    parser.add_argument("--plan-out", type=Path, default=Path("recheck-plan.json"))
    parser.add_argument("--report-out", type=Path, default=Path("recheck-report.md"))
    parser.add_argument("--app-url", default=settings.frontend_origin)
    parser.add_argument("--apply", type=Path, help="Raise doubts from this plan, at Craig's word.")
    parser.add_argument(
        "--verdicts",
        default=",".join(DOUBT_CLASSES),
        help="Comma-separated verdicts to raise doubts for (default: every disagreement).",
    )
    args = parser.parse_args(argv)
    if args.apply is not None:
        return asyncio.run(run_apply(args.apply, [v for v in args.verdicts.split(",") if v]))
    if args.xlsx is None:
        parser.error("--xlsx is needed for the dry run")
    return asyncio.run(run_dry(args.xlsx, args.plan_out, args.report_out, args.app_url))


if __name__ == "__main__":
    sys.exit(main())
