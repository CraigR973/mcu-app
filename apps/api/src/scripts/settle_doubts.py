"""Settle open identification doubts from an agreed plan — `DECISIONS.md` #278.

**First a dry run, which writes nothing:** it checks every entry against the live doubts and
prints what it would do and what it would skip.

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.settle_doubts \\
        --plan settle-plan.json --as Craig

**Then, at Craig's word, the same with ``--apply``.** Each entry is its own transaction,
audited as the person named, and undone from Identify films → Recently identified (a binned
copy from the Trash). An entry whose doubt was settled since, or whose film changed, is
skipped rather than forced.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import func, select, text

from src.database import AsyncSessionLocal
from src.models.profile import Profile
from src.services.identify.settle import PlanEntry, check, run_entry
from src.tmdb.client import TMDBClient


def load(path: Path) -> list[PlanEntry]:
    return [PlanEntry.model_validate(raw) for raw in json.loads(path.read_text())]


async def main_async(plan: list[PlanEntry], *, person: str, apply: bool) -> int:
    async with AsyncSessionLocal() as db:
        by = await db.scalar(
            select(Profile.id).where(func.lower(Profile.display_name) == person.lower())
        )
    if by is None:
        print(f"No profile called {person}.", file=sys.stderr)
        return 2
    outcomes: Counter[str] = Counter()
    lines: list[str] = []
    if not apply:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            for entry in plan:
                checked = await check(db, entry)
                state = "skip" if checked.skip else f"would {entry.action}"
                outcomes[state] += 1
                if checked.skip or entry.action != "keep":
                    lines.append(f"{state}: {entry.title} — {checked.skip or entry.tmdbId}")
            await db.rollback()
    else:
        async with TMDBClient() as tmdb:
            for entry in plan:
                async with AsyncSessionLocal() as db:
                    state, why = await run_entry(db, entry, tmdb, by=by)
                outcomes[f"{state} {entry.action}" if state == "done" else state] += 1
                if state != "done" or entry.action != "keep":
                    lines.append(f"{state}: {entry.title} — {why}")
    for key, count in sorted(outcomes.items()):
        print(f"{key}: {count}")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else "")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--as", dest="person", required=True, help="Whose decision it is")
    parser.add_argument("--apply", action="store_true", help="Settle them; without it, a dry run")
    args = parser.parse_args(argv)
    return asyncio.run(main_async(load(args.plan), person=args.person, apply=args.apply))


if __name__ == "__main__":
    sys.exit(main())
