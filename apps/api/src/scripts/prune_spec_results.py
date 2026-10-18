"""Delete the search results kept for spec lookups that are already settled — Batch X12c.

Brave's API terms bar storing a database of search results beyond transient storage
(`DECISIONS.md` #284). New lookups prune themselves when they settle (`done` or `skipped`);
this clears what was stored before that, and nothing else. The accepted page of each lookup
stays, and so does every result of a lookup still waiting for a person (``needs_you``,
``no_match``, ``accepted``): Craig picks from those.

**First a dry run, which writes nothing:**

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.prune_spec_results

**Then, at Craig's word and with the count he saw, ``--apply --expect N``.** It refuses unless
exactly N results qualify when it runs. One statement, one transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import delete, func, select, text

from src.database import AsyncSessionLocal
from src.models.specs_backfill import SpecCandidate, SpecLookup
from src.services.specs.backfill import SETTLED, settled_candidates_condition


async def main_async(*, apply: bool, expect: int | None) -> int:
    async with AsyncSessionLocal() as db:
        # The first statement of its transaction, as Postgres requires.
        await db.execute(text("SET TRANSACTION READ ONLY"))
        total = int(await db.scalar(select(func.count(SpecCandidate.id))) or 0)
        goes = settled_candidates_condition()
        qualify = int(await db.scalar(select(func.count(SpecCandidate.id)).where(goes)) or 0)
        lookups = int(
            await db.scalar(select(func.count(func.distinct(SpecCandidate.lookup_id))).where(goes))
            or 0
        )
        kept_waiting = int(
            await db.scalar(
                select(func.count(SpecCandidate.id))
                .join(SpecLookup, SpecLookup.id == SpecCandidate.lookup_id)
                .where(SpecLookup.status.not_in(SETTLED))
            )
            or 0
        )
        await db.rollback()
    print(f"{total} search results stored")
    print(f"{qualify} to delete, from {lookups} settled lookups")
    print(
        f"{total - qualify} kept: {kept_waiting} of lookups still waiting, the rest accepted pages"
    )
    if not apply:
        return 0
    if expect != qualify:
        print(f"Refused: {qualify} qualify, {expect} expected. Nothing deleted.", file=sys.stderr)
        return 3
    async with AsyncSessionLocal() as db:
        result = await db.execute(delete(SpecCandidate).where(settled_candidates_condition()))
        deleted = int(result.rowcount or 0)  # type: ignore[attr-defined]
        if deleted != expect:
            await db.rollback()
            print(f"Refused: {deleted} deleted, {expect} expected. Rolled back.", file=sys.stderr)
            return 3
        await db.commit()
    print(f"{deleted} deleted")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else "")
    parser.add_argument("--apply", action="store_true", help="Delete them; without it, a dry run")
    parser.add_argument("--expect", type=int, help="With --apply: the count the dry run showed")
    args = parser.parse_args(argv)
    if args.apply and args.expect is None:
        parser.error("--apply needs --expect N, the count the dry run showed")
    return asyncio.run(main_async(apply=args.apply, expect=args.expect))


if __name__ == "__main__":
    sys.exit(main())
