"""Cinema source dry-run, reviewed artifact import and exact-count owner controls.

Importing this module does nothing. Each write needs an existing admin actor and the
exact reviewed count; imports additionally need the hash of a saved dry-run artifact.
No source is contacted while importing/enabling/disabling. The live dry-run itself is
an owner checkpoint under group-start; never run it as part of tests or deployment.
"""

import argparse
import asyncio
import json
import uuid
from datetime import UTC, date, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.clock import utcnow
from src.config import settings
from src.services.cinemas.domain import LONDON, SourceError, days_between
from src.services.cinemas.refresh import (
    apply_prepared,
    exclusive,
    load_artifact,
    prepare,
    preview,
    save_artifact,
    set_enabled,
)
from src.services.cinemas.venues import VENUES


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Owner-controlled cinema source review/import")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--write", action="store_true")
    action.add_argument("--enable", action="store_true")
    action.add_argument("--disable", action="store_true")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--confirm-digest")
    parser.add_argument("--confirm-count", type=int)
    parser.add_argument("--actor-profile-id", type=uuid.UUID)
    parser.add_argument("--date-from", type=date.fromisoformat)
    parser.add_argument("--date-to", type=date.fromisoformat)
    args = parser.parse_args(argv)
    if (args.dry_run or args.write) and args.snapshot is None:
        parser.error("--snapshot is required for a reviewable dry-run/import")
    if not args.dry_run and (args.actor_profile_id is None or args.confirm_count is None):
        parser.error("Every write/control needs --actor-profile-id and --confirm-count")
    if args.write and not args.confirm_digest:
        parser.error("--write requires the reviewed --confirm-digest")
    if not args.dry_run and (args.date_from or args.date_to):
        parser.error("Imported dates come from the reviewed artifact")
    if args.confirm_count is not None and args.confirm_count < 0:
        parser.error("--confirm-count cannot be negative")
    return args


async def run(args: argparse.Namespace) -> dict[str, Any]:
    engine = create_async_engine(settings.database_url)
    try:
        if args.dry_run:
            start = args.date_from or utcnow().replace(tzinfo=UTC).astimezone(LONDON).date()
            end = args.date_to or start + timedelta(days=13)
            days_between(start, end)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with asyncio.timeout(295), exclusive(engine, None, {}):
                async with httpx.AsyncClient(
                    timeout=15, headers={"User-Agent": "MCU-private-cinema-programme/1.0"}
                ) as client:
                    prepared = await prepare(list(VENUES), start, end, client)
                async with factory() as db:
                    report = await preview(db, prepared)
                digest = save_artifact(prepared, args.snapshot)
            try:
                prepared.require_all_nine()
                accepted_sources = True
            except SourceError:
                accepted_sources = False
            return {
                "mode": "dryRun",
                "sourcesObserved": accepted_sources,
                "snapshotSha256": digest,
                "snapshot": str(args.snapshot),
                **report,
            }
        if args.write:
            prepared = load_artifact(args.snapshot, args.confirm_digest, args.confirm_count)
            return await apply_prepared(engine, prepared, args.actor_profile_id)
        changed = await set_enabled(engine, args.actor_profile_id, args.enable, args.confirm_count)
        return {"mode": "enable" if args.enable else "disable", "changed": changed}
    finally:
        await engine.dispose()


def main() -> int:
    args = arguments()
    try:
        report = asyncio.run(run(args))
    except (SourceError, ValueError, FileExistsError, TimeoutError) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 2 if report.get("sourcesObserved") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
