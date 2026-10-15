"""Find the TV series matched to a film of the same name — Batch Y3. **Writes nothing.**

Reads every identified film on the shelf, asks TMDB's series index for each title, and writes a
report of the ones that look like a series (the rule is ``services/identify/series_check.py``),
each linked to its page, where "Correct match" offers the series. About 1,450 searches, some
three minutes at eight a second.

On the Mac, against the live database in ``apps/api/.env.local``, in a ``READ ONLY``
transaction that ends before TMDB is asked anything. The values are exported explicitly,
because the connection string holds an unquoted ``&`` (``OWNER-ACTIONS.md`` item 31):

    DATABASE_URL="$(grep '^DATABASE_URL=' apps/api/.env.local | cut -d= -f2-)" \\
    TMDB_READ_TOKEN="$(grep '^TMDB_READ_TOKEN=' apps/api/.env.local | cut -d= -f2-)" \\
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.find_series_as_films \\
        --app-url https://mcu-app-fawn.vercel.app

In a cloud session, where no Postgres connection leaves the container, ``--over-https`` reads
through the read-only role in ``NEON_READONLY_URL``, as ``live_sql`` does (#236). Either way it
needs ``TMDB_READ_TOKEN``. It runs only once migration 056 is live: it reads ``tmdb_tv_id``.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.sql import Select

from src.config import settings
from src.database import AsyncSessionLocal, engine
from src.scripts import live_sql
from src.services.identify.series_check import (
    IdentifiedFilm,
    assemble,
    check,
    films_query,
    groupings_query,
    render_csv,
    render_html,
    replaced_titles_query,
)
from src.tmdb.client import TMDBClient

#: TMDB allows about 50 requests a second; the app's own client keeps to 3, T9's dry run to 8.
TMDB_RATE = 8.0


async def read_in_session() -> list[IdentifiedFilm]:
    async with AsyncSessionLocal() as db:
        # Postgres refuses any write in this transaction: "writes nothing" is enforced. It is
        # over before TMDB is asked anything, so no connection idles for Neon to close.
        await db.execute(text("SET TRANSACTION READ ONLY"))
        films = (await db.execute(films_query())).all()
        replaced = (await db.execute(replaced_titles_query())).all()
        groupings = (await db.execute(groupings_query())).all()
        await db.rollback()
    return assemble(films, replaced, groupings)


def as_sql(statement: Select[Any]) -> str:
    """The query as one statement Neon's HTTPS endpoint takes, its values written in."""
    # The app's own Postgres dialect; making the engine connects to nothing.
    compiled = statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
    return str(compiled)


def _rows(answer: dict[str, Any]) -> list[Sequence[Any]]:
    names = [field["name"] for field in answer.get("fields", [])]
    return [[row.get(name) for name in names] for row in answer.get("rows", [])]


def read_over_https() -> list[IdentifiedFilm]:
    url = os.environ.get(live_sql.ENV_VAR)
    if not url:
        raise SystemExit(f"{live_sql.ENV_VAR} is not set; see docs/mac-cloud-setup.md.")
    with httpx.Client(timeout=live_sql.TIMEOUT) as client:
        answers = [
            live_sql.run_query(as_sql(query), url=url, client=client)
            for query in (films_query(), replaced_titles_query(), groupings_query())
        ]
    return assemble(*(_rows(answer) for answer in answers))


def _progress(index: int, total: int) -> None:
    if index % 100 == 0 or index == total:
        print(f"  {index} of {total} films looked at", flush=True)


async def run(args: argparse.Namespace) -> int:
    films = read_over_https() if args.over_https else await read_in_session()
    print(f"{len(films)} identified films on the shelf.", flush=True)
    async with TMDBClient(rate=TMDB_RATE) as tmdb:
        result = await check(films, tmdb, progress=_progress)
    Path(args.report_out).write_text(render_html(result, app_url=args.app_url), encoding="utf-8")
    Path(args.csv_out).write_text(render_csv(result, app_url=args.app_url), encoding="utf-8")
    print(
        f"{len(result.suspects)} look like a series; report in {args.report_out}, "
        f"{args.csv_out}. TMDB failed on {len(result.failed)}."
    )
    return 1 if result.failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--report-out", default="series-as-films.html")
    parser.add_argument("--csv-out", default="series-as-films.csv")
    parser.add_argument(
        "--app-url",
        default=settings.frontend_origin,
        help="The web app the report links into (default: FRONTEND_ORIGIN).",
    )
    parser.add_argument(
        "--over-https",
        action="store_true",
        help=f"Read through {live_sql.ENV_VAR}, from a cloud session.",
    )
    return asyncio.run(run(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
