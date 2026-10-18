"""Put the film rows with nothing left on them in the Trash — Batch X10, `DECISIONS.md` #280.

**First a dry run, which writes nothing:** it lists every leftover row (no TMDB id, every copy
binned, no watch, want or suggestion) with its count.

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.remove_leftover_films \\
        --as Craig

**Then, at Craig's word and with the count he saw, the same with ``--apply --expect N``.** It
refuses unless exactly N rows are leftovers when it runs, so nothing he did not see goes. Each
row goes in its own transaction, audited as the person named, and comes back from the Trash.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import func, select, text

from src.database import AsyncSessionLocal
from src.models.profile import Profile
from src.services.leftover_films import leftover_films, remove


async def main_async(*, person: str, apply: bool, expect: int | None) -> int:
    async with AsyncSessionLocal() as db:
        by = await db.scalar(
            select(Profile.id).where(func.lower(Profile.display_name) == person.lower())
        )
    if by is None:
        print(f"No profile called {person}.", file=sys.stderr)
        return 2
    async with AsyncSessionLocal() as db:
        # The first statement of its transaction, as Postgres requires.
        await db.execute(text("SET TRANSACTION READ ONLY"))
        found = await leftover_films(db)
        await db.rollback()

    print(f"{len(found)} leftover film rows")
    for row in found:
        when = row.last_binned_utc.date().isoformat() if row.last_binned_utc else "?"
        print(f"  {row.title} — {row.binned_copies} binned, last on {when} ({row.movie_id})")
    if not apply:
        return 0
    if expect != len(found):
        print(f"Refused: {len(found)} found, {expect} expected. Nothing removed.", file=sys.stderr)
        return 3

    removed = 0
    for row in found:
        async with AsyncSessionLocal() as db:
            if await remove(db, row.movie_id, by=by):
                await db.commit()
                removed += 1
            else:
                print(f"  skipped, no longer a leftover: {row.title}")
    print(f"{removed} put in the Trash")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else "")
    parser.add_argument("--as", dest="person", required=True, help="Whose decision it is")
    parser.add_argument("--apply", action="store_true", help="Trash them; without it, a dry run")
    parser.add_argument("--expect", type=int, help="With --apply: the count the dry run showed")
    args = parser.parse_args(argv)
    if args.apply and args.expect is None:
        parser.error("--apply needs --expect N, the count the dry run showed")
    return asyncio.run(main_async(person=args.person, apply=args.apply, expect=args.expect))


if __name__ == "__main__":
    sys.exit(main())
