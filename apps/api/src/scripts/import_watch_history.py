"""Import a Letterboxd diary into `watch_log` — Batch S8, snag 10b.

Usage (from the repo root):

    set -a; source apps/api/.env.local; set +a
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.import_watch_history \\
        --csv .letterboxd-export/craig-diary.csv \\
        --user "Craig" \\
        [--write] [--identify] [--ambiguous-out ambiguous.csv]

**It is a dry run unless you pass `--write`.** That is the wrong way round for
convenience and the right way round for this: a real run writes ~1,530 watch rows and,
with `--identify`, **overwrites 396 existing `movies` rows** with TMDB metadata
(`DECISIONS.md` #160). `docs/agent-commands/group-start.md` puts an operation of that size
in the owner's hands, so no agent runs it.

**Re-running is safe.** Every row carries its `letterboxd_viewing_id`, and a viewing
already present for that person is skipped — so a second run of the same file writes zero
rows, and S5's RSS sync cannot re-import a viewing this file already wrote (#159, #161).

**`--identify` is separate from `--write` on purpose.** Writing watches is additive and
reversible: the rows soft-delete, and nothing that existed before changes. Identification
is neither — it rewrites title, year, poster, runtime and cast on rows that are already
there, and merges two rows into one where the collection turns out to hold both. They are
different-sized decisions and deserve different flags.

**Ambiguities are printed, never guessed.** Six across 2,322 entries — `Death on the Nile`
and `Murder on the Orient Express` — and `--ambiguous-out` writes them to a CSV so they
can be settled by hand.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.matching import MatchingEngine
from src.models.profile import Profile
from src.services.letterboxd import ImportReport, read_diary_csv, run_import
from src.tmdb import TMDBClient


async def _resolve_profile(db: AsyncSession, display_name: str) -> Profile:
    profile = await db.scalar(select(Profile).where(Profile.display_name == display_name))
    if profile is None:
        known = list(await db.scalars(select(Profile.display_name)))
        raise SystemExit(f"No profile named {display_name!r}. Known profiles: {known}")
    return profile


def _write_ambiguous(report: ImportReport, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["line", "viewing_id", "diary_title", "diary_year", "candidates"])
        for item in report.ambiguous:
            writer.writerow(
                [
                    item.entry.line,
                    item.entry.viewing_id,
                    item.entry.title,
                    item.entry.year or "",
                    " | ".join(
                        f"{movie.title} ({movie.year if movie.year is not None else '?'})"
                        for movie in item.candidates
                    ),
                ]
            )


async def run(
    csv_path: Path,
    display_name: str,
    *,
    write: bool,
    identify: bool,
    ambiguous_out: Path | None,
) -> ImportReport:
    entries = read_diary_csv(csv_path)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            profile = await _resolve_profile(db, display_name)
            if identify and write:
                async with TMDBClient() as tmdb:
                    report = await run_import(
                        db, profile, entries, dry_run=not write, engine=MatchingEngine(tmdb)
                    )
            else:
                report = await run_import(db, profile, entries, dry_run=not write)
    finally:
        await engine.dispose()

    if ambiguous_out is not None and report.ambiguous:
        _write_ambiguous(report, ambiguous_out)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path, help="A Letterboxd diary CSV")
    parser.add_argument("--user", required=True, help="The profile display name to log against")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write. Without it this is a dry run and touches nothing.",
    )
    parser.add_argument(
        "--identify",
        action="store_true",
        help="Also fill in films the April import never identified. Overwrites movies rows.",
    )
    parser.add_argument("--ambiguous-out", type=Path, default=None)
    args = parser.parse_args()

    report = asyncio.run(
        run(
            args.csv,
            args.user,
            write=args.write,
            identify=args.identify,
            ambiguous_out=args.ambiguous_out,
        )
    )

    print("\n=== Letterboxd import ===")
    print(report.summary())
    if report.ambiguous:
        print(f"\n  {len(report.ambiguous)} ambiguous — offered, not guessed:")
        for item in report.ambiguous[:20]:
            print(f"    - {item.describe()}")
        if len(report.ambiguous) > 20:
            print(f"    … and {len(report.ambiguous) - 20} more")
        if args.ambiguous_out:
            print(f"  written to {args.ambiguous_out}")
    if report.identified:
        print(f"\n  {len(report.identified)} films identified:")
        for title, tmdb_id in report.identified[:20]:
            print(f"    - {title} (tmdb {tmdb_id})")
        if len(report.identified) > 20:
            print(f"    … and {len(report.identified) - 20} more")
    if report.identification_failures:
        print(f"\n  {len(report.identification_failures)} identifications failed:")
        for failure in report.identification_failures[:10]:
            print(f"    - {failure}")
    if report.dry_run:
        print(f"\n  A real run would write {report.would_write} watches. Pass --write.")


if __name__ == "__main__":
    main()
