"""Refresh the release calendar now — Batch T5.

The calendar refreshes itself when it is read and more than a day old. This is the same
refresh, forced, for a first run, a check, or a scheduled job if one is ever wanted.

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.refresh_calendar

It needs ``DATABASE_URL`` and ``TMDB_READ_TOKEN``. It **exits non-zero** when TMDB could
not be asked at all, or when every lookup failed — a run that wrote nothing because the
token was missing must not look like a quiet day. (That is what happened to the collection
importer's identification run on 2026-09-17.)
"""

from __future__ import annotations

import asyncio
import sys

from src.database import AsyncSessionLocal
from src.services.calendar import IngestResult, refresh_calendar
from src.tmdb import TMDBClient


def report(result: IngestResult | None) -> int:
    """Print what the run did and return the exit code."""
    if result is None:
        print("A refresh is already running; nothing was done.")
        return 0
    print("release calendar refreshed")
    print(f"  created:          {result.created}")
    print(f"  updated:          {result.updated}")
    print(f"  unchanged:        {result.unchanged}")
    print(f"  skipped:          {result.skipped}")
    print(f"  disc films found: {result.physical_found} of {result.physical_checked} checked")
    for error in result.errors:
        print(f"  error: {error}")
    asked_nothing = result.total == 0 and result.physical_checked == 0 and bool(result.errors)
    return 1 if asked_nothing else 0


async def main() -> int:
    async with AsyncSessionLocal() as db, TMDBClient() as tmdb:
        return report(await refresh_calendar(db, tmdb, force=True))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
