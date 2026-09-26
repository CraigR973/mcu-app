"""Fill each copy's edition from its Blu-ray.com page, once — Batch U2, `DECISIONS.md` #220.

For the discs whose specs were settled before editions existed; every spec batch since fills
the discs it settles. **First a dry run, which writes nothing:**

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.fill_editions

It reads in a read-only transaction, so Postgres itself refuses a write, and prints every
edition it would write and the kind of page each comes from. **Then, to write them:**

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.fill_editions --apply

Only blanks are written, and only where the settled page is certainly the copy: Craig chose
or pasted it, or it was the one UK edition the search found. It makes no request to anyone.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter

from sqlalchemy import text

from src.database import AsyncSessionLocal
from src.services.specs.backfill import EditionFound, editions_to_fill, fill_editions
from src.services.specs.editions import EditionKind

_KINDS: dict[EditionKind, str] = {
    "only_uk_edition": "the one UK edition the search found",
    "chosen": "chosen by Craig from the list",
    "pasted": "pasted by Craig",
}


def report(found: list[EditionFound], written: int | None) -> None:
    """What was found, by kind of page, and every edition written or to be written."""
    certain = Counter(entry.kind for entry in found)
    named = [entry for entry in found if entry.edition is not None]
    by_kind = Counter(entry.kind for entry in named)
    print(f"settled discs whose page is certainly the copy: {len(found)}")
    for kind, label in _KINDS.items():
        print(f"  {label}: {certain[kind]}, of which {by_kind[kind]} name an edition")
    verb = "would write" if written is None else "wrote"
    print(f"editions {verb}: {len(named) if written is None else written}")
    for entry in named:
        print(f"  {entry.title} ({entry.format_code}): {entry.edition} [{_KINDS[entry.kind]}]")


async def run(*, apply: bool) -> int:
    async with AsyncSessionLocal() as db:
        if not apply:
            await db.execute(text("SET TRANSACTION READ ONLY"))
        found = await editions_to_fill(db)
        written = await fill_editions(db, found) if apply else None
        if not apply:
            await db.rollback()
    report(found, written)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else "")
    parser.add_argument(
        "--apply", action="store_true", help="Write the editions; without it, a dry run"
    )
    args = parser.parse_args(argv)
    return asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    sys.exit(main())
