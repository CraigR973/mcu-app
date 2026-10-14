"""Move the 15 watches sitting on a namesake to the films they were of — Batch X5 (CT46-02).

    DATABASE_URL=... TMDB_READ_TOKEN=... PYTHONPATH=apps/api \\
      apps/api/.venv/bin/python3.12 -m src.scripts.repoint_watches plan \\
        --diaries .letterboxd-export --out .letterboxd-export/repoint.json

    DATABASE_URL=... TMDB_READ_TOKEN=... PYTHONPATH=apps/api \\
      apps/api/.venv/bin/python3.12 -m src.scripts.repoint_watches apply \\
        --plan .letterboxd-export/repoint.json

``plan`` writes nothing (the read-only role will do) and prints each move. ``apply`` is a
live data change, at Craig's word, from that list (``services/letterboxd/repoint.py``).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import settings
from src.services.identify.matcher import Identifier
from src.services.letterboxd import read_diary_csv
from src.services.letterboxd.repoint import RepointPlan, apply_repoint, plan_repoint
from src.tmdb import TMDBClient

DIARIES = ("craig-diary.csv", "mark-diary.csv")


async def run_plan(folder: Path, out: Path) -> int:
    diaries = {
        entry.viewing_id: entry for name in DIARIES for entry in read_diary_csv(folder / name)
    }
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with (
            async_sessionmaker(engine, expire_on_commit=False)() as db,
            TMDBClient() as tmdb,
        ):
            plan = await plan_repoint(db, diaries, Identifier(tmdb))
            await db.rollback()
    finally:
        await engine.dispose()
    out.write_text(plan.to_json() + "\n", encoding="utf-8")
    print(plan.summary())
    print(f"\nPlan saved to {out}. Nothing was written; `apply --plan` moves them.")
    return 0


async def run_apply(plan_path: Path) -> int:
    plan = RepointPlan.from_json(plan_path.read_text(encoding="utf-8"))
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with (
            async_sessionmaker(engine, expire_on_commit=False)() as db,
            TMDBClient() as tmdb,
        ):
            result = await apply_repoint(db, plan, tmdb)
    finally:
        await engine.dispose()
    print(f"Moved {result.moved} watches; added {result.films_added} films.")
    for line in result.skipped:
        print(f"  skipped: {line}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="list the moves; write nothing")
    plan.add_argument("--diaries", required=True, type=Path, help="The folder of diary CSVs")
    plan.add_argument("--out", required=True, type=Path)
    apply = commands.add_parser("apply", help="move the planned watches, at Craig's word")
    apply.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        return asyncio.run(run_plan(args.diaries, args.out))
    return asyncio.run(run_apply(args.plan))


if __name__ == "__main__":
    raise SystemExit(main())
