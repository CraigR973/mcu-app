"""Rebuild the completion sets from TMDB — roadmap §11.1's refresh job.

This is what a weekly schedule calls. **The schedule itself is not created here**: a
Railway cron is a hosting change, and this project keeps those explicit
(`AGENTS.md`, close-out protocol). The job is written so that scheduling it is one
console action rather than a piece of engineering.

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 \\
        -m src.scripts.refresh_completion_sets --dry-run
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 \\
        -m src.scripts.refresh_completion_sets

``--dry-run`` reads TMDB and writes nothing. `STATUS.md` gotcha 16 is the record of what
Batch 4's first real write against real data cost when it had not been rehearsed; this
job's rehearsal is free because reading a filmography changes nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.config import settings
from src.services.completion import refresh_sets
from src.tmdb import TMDBClient


async def _run(limit_per_type: int, dry_run: bool) -> int:
    engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db, TMDBClient() as tmdb:
            result = await refresh_sets(db, tmdb, limit_per_type=limit_per_type, dry_run=dry_run)
    finally:
        await engine.dispose()

    print(f"{'DRY RUN — ' if dry_run else ''}completion sets refreshed")
    print(f"  created:   {result.created}")
    print(f"  updated:   {result.updated}")
    print(f"  unchanged: {result.unchanged}")
    print(f"  skipped:   {result.skipped}  (no releasable films on TMDB)")
    print(f"  total:     {result.total}")

    # Printed last and counted explicitly. Gotcha 16: read the error count rather than
    # trusting the success lines above it.
    if result.errors:
        print(f"  errors:    {len(result.errors)}", file=sys.stderr)
        for message in result.errors:
            print(f"    - {message}", file=sys.stderr)
        return 1
    print("  errors:    0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit-per-type",
        type=int,
        default=20,
        help="How many directors and how many actors to build sets for (default: 20 each)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Call TMDB and report what would change, without writing",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.limit_per_type, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
