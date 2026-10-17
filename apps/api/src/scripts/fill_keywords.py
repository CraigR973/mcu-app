"""Fill in the TMDB keywords of films identified before Batch Y5 — `DECISIONS.md` #277.

The Archive's Film Noir reads each film's TMDB keywords (keyword 9807). Every film identified
since Y5 has them; this fills the rest, one TMDB call a film at 8 a second (about four
minutes for 1,850). **First a dry run, which reads TMDB and writes nothing:**

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.fill_keywords

It prints how many films and series it would fill, how many TMDB no longer has, and every
film it found tagged film noir. ``--limit 50`` reads the first fifty only. **Then, at Craig's
word, to write them:**

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.fill_keywords --apply

Only rows whose keywords are null and which are still the film read are written, committed a
hundred at a time, so it can be stopped and run again.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy import text

from src.database import AsyncSessionLocal
from src.services.keyword_backfill import Outcome, Target, run, targets, write
from src.tmdb.client import TMDBClient

#: TMDB calls a second, as Craig set it (#277): the app's own searches keep room beside it.
RATE = 8.0


def _name(target: Target) -> str:
    kind = " (series)" if target.tmdb_tv_id is not None else ""
    year = f" ({target.year})" if target.year else ""
    return f"{target.title}{year}{kind}"


def report(found: Sequence[Target], outcome: Outcome, *, apply: bool) -> None:
    series = sum(1 for target in found if target.tmdb_tv_id is not None)
    print(f"films and series with no keywords yet: {len(found)} ({series} series)")
    print(f"read from TMDB: {len(outcome.fetched)}")
    empty = sum(1 for ids in outcome.fetched.values() if not ids)
    print(f"  of which TMDB has no keywords for: {empty}")
    print(f"  of which tagged film noir: {len(outcome.noir)}")
    print(f"not on TMDB any more (left empty): {len(outcome.missing)}")
    for target in outcome.missing:
        print(f"  {_name(target)}")
    print(f"TMDB did not answer (left for the next run): {len(outcome.failed)}")
    if apply:
        print(f"written: {outcome.written}")
        print(f"changed while the run read TMDB (not written): {outcome.changed}")
    else:
        print(f"would write: {len(outcome.fetched)} (a dry run: nothing was written)")
    print("tagged film noir:")
    for target in outcome.noir:
        print(f"  {_name(target)}")


async def main_async(*, apply: bool, limit: int | None) -> int:
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        found = await targets(db, limit=limit)
        await db.rollback()

    async def commit(batch: Sequence[Target], outcome: Outcome) -> None:
        async with AsyncSessionLocal() as db:
            await write(db, batch, outcome)
            await db.commit()

    def progress(done: int) -> None:
        if done % 100 == 0:
            print(f"… {done} of {len(found)} read", file=sys.stderr)

    async with TMDBClient(rate=RATE) as tmdb:
        outcome = await run(tmdb, found, apply=apply, commit=commit, progress=progress)
    report(found, outcome, apply=apply)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else "")
    parser.add_argument(
        "--apply", action="store_true", help="Write the keywords; without it, a dry run"
    )
    parser.add_argument("--limit", type=int, default=None, help="Read only the first N")
    args = parser.parse_args(argv)
    return asyncio.run(main_async(apply=args.apply, limit=args.limit))


if __name__ == "__main__":
    sys.exit(main())
