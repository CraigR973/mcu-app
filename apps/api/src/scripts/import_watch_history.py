"""Record every dated diary entry not yet recorded — Batch X5 (#269), on S8's import.

Two steps, as T9's identification has (``services/letterboxd/backfill.py``):

    DATABASE_URL=... TMDB_READ_TOKEN=... PYTHONPATH=apps/api \\
      apps/api/.venv/bin/python3.12 -m src.scripts.import_watch_history plan \\
        --csv .letterboxd-export/craig-diary.csv --user Craig \\
        --out .letterboxd-export/craig-backfill.json \\
        --doubtful .letterboxd-export/craig-doubtful.csv

    DATABASE_URL=... TMDB_READ_TOKEN=... PYTHONPATH=apps/api \\
      apps/api/.venv/bin/python3.12 -m src.scripts.import_watch_history apply \\
        --plan .letterboxd-export/craig-backfill.json

``plan`` writes nothing to the database: it can run on the read-only role. It decides each
unrecorded entry (an owned film, a film already listed, a film to add, or doubtful), saves
that as JSON, writes the doubtful ones to a CSV for Craig, and prints the counts. ``apply``
writes the plan's watches and adds its films, exactly, after checking each is still
unrecorded. **``apply`` is a live data change: it runs at Craig's word, with the counts
``plan`` printed** (`docs/agent-commands/group-start.md`).

**Re-running is safe.** Every watch carries its ``letterboxd_viewing_id``; an entry already
recorded is skipped by both steps, so a second ``apply`` of the same plan writes nothing.

**Do not use `set -a; source apps/api/.env.local`.** `DATABASE_URL` is unquoted in that
file and contains an `&`, so sourcing splits the line and the value silently truncates
(`DECISIONS.md` #191). Export each value whole.

Since X5 this command no longer identifies owned films (``--identify`` is gone): its
``MatchingEngine`` step put three diary films on the wrong owned rows (CT46-01). That is
T9's job, ``src.scripts.identify_films``.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.models.profile import Profile
from src.services.identify.matcher import Identifier
from src.services.letterboxd import read_diary_csv
from src.services.letterboxd.backfill import (
    BackfillPlan,
    apply_backfill,
    plan_backfill,
    write_doubtful,
)
from src.tmdb import TMDBClient


async def _resolve_person(db: AsyncSession, display_name: str) -> tuple[uuid.UUID, str]:
    """The profile's id and name, and nothing else: the read-only role cannot read a PIN."""
    row = (
        await db.execute(
            select(Profile.id, Profile.display_name).where(Profile.display_name == display_name)
        )
    ).first()
    if row is None:
        known = list(await db.scalars(select(Profile.display_name)))
        raise SystemExit(f"No profile named {display_name!r}. Known profiles: {known}")
    return row[0], row[1]


def _progress(films: int) -> None:
    if films % 25 == 0:
        print(f"  … {films} films put to TMDB", flush=True)


async def run_plan(csv_path: Path, display_name: str, out: Path, doubtful: Path) -> int:
    entries = read_diary_csv(csv_path)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            person = await _resolve_person(db, display_name)
            async with TMDBClient() as tmdb:
                plan = await plan_backfill(db, person, entries, Identifier(tmdb), on_film=_progress)
            await db.rollback()
    finally:
        await engine.dispose()
    out.write_text(plan.to_json() + "\n", encoding="utf-8")
    asked = write_doubtful(plan, doubtful)
    print(plan.summary())
    print(f"  TMDB calls                {plan.tmdb_calls}")
    print(f"\nPlan saved to {out}; {asked} doubtful entries listed in {doubtful}.")
    print("Nothing was written. `apply --plan` writes it, at Craig's word.")
    return 0


async def run_apply(plan_path: Path) -> int:
    plan = BackfillPlan.from_json(plan_path.read_text(encoding="utf-8"))
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with (
            async_sessionmaker(engine, expire_on_commit=False)() as db,
            TMDBClient() as tmdb,
        ):
            result = await apply_backfill(db, plan, tmdb)
    finally:
        await engine.dispose()
    print(f"{plan.person}: wrote {result.written} watches; added {result.films_added} films")
    print(f"  filled in from TMDB       {result.films_filled}")
    print(f"  recorded since the plan   {result.already}")
    for line in result.skipped:
        print(f"  skipped: {line}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="decide every unrecorded entry; write nothing")
    plan.add_argument("--csv", required=True, type=Path, help="A Letterboxd diary CSV")
    plan.add_argument("--user", required=True, help="The profile display name")
    plan.add_argument("--out", required=True, type=Path, help="Where the plan is saved")
    plan.add_argument("--doubtful", required=True, type=Path, help="The CSV for Craig")
    apply = commands.add_parser("apply", help="write a saved plan, at Craig's word")
    apply.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        return asyncio.run(run_plan(args.csv, args.user, args.out, args.doubtful))
    return asyncio.run(run_apply(args.plan))


if __name__ == "__main__":
    raise SystemExit(main())
