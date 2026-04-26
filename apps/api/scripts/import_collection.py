"""
Bulk import script for Phase 1.7.

Pipeline: parse xlsx → match via TMDB → enrich → insert movies + collection_items.

Usage (from repo root):

    set -a; source apps/api/.env.local; set +a
    apps/api/.venv/bin/python -m apps.api.scripts.import_collection \\
        --xlsx "Film Catalogue - 4k Blu Ray DVD v1.0.xlsx" \\
        [--dry-run] \\
        [--review-out import_review.csv]

Re-running is safe: movies and collection items already in the DB are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import settings  # noqa: E402
from src.matching import HIGH_CONFIDENCE, LOW_CONFIDENCE, MatchingEngine, MatchResult  # noqa: E402
from src.spreadsheet import ImportCandidate, parse_xlsx  # noqa: E402
from src.tmdb import TMDBClient  # noqa: E402
from src.tmdb.models import Movie  # noqa: E402

# Maps parser format codes → DB check-constraint values.
FORMAT_MAP: dict[str, str] = {
    "4k_uhd": "4k_bluray",
    "blu_ray": "bluray",
    "dvd": "dvd",
    "download": "digital",
}

DEFAULT_CONDITION = "good"

REVIEW_FIELDNAMES = [
    "row",
    "title",
    "query",
    "query_year",
    "top_tmdb_id",
    "top_title",
    "top_year",
    "confidence",
    "reason",
]


@dataclass
class ImportRow:
    candidate: ImportCandidate
    match: MatchResult
    movie: Movie | None = None


@dataclass
class ImportStats:
    total: int = 0
    matched: int = 0
    enriched: int = 0
    movies_inserted: int = 0
    items_inserted: int = 0
    items_skipped: int = 0
    review: int = 0
    no_match: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def map_format(parser_fmt: str) -> str | None:
    """Return the DB format code for a parser format code, or None if unknown."""
    return FORMAT_MAP.get(parser_fmt)


def parse_release_date(raw: str | None) -> date | None:
    """Parse an ISO date string; return None on failure."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Async: match + enrich
# ---------------------------------------------------------------------------


async def match_and_enrich(
    candidates: list[ImportCandidate],
    tmdb: TMDBClient,
    stats: ImportStats,
) -> tuple[list[ImportRow], list[dict[str, Any]]]:
    """Match all candidates, enrich high-confidence ones.

    Returns (matched_rows, review_rows) where review_rows is a list of dicts
    ready to write to the review CSV.
    """
    engine = MatchingEngine(tmdb)
    matched_rows: list[ImportRow] = []
    review_rows: list[dict[str, Any]] = []

    total = len(candidates)
    print(f"Matching {total} titles…")

    for i, cand in enumerate(candidates, 1):
        if i % 25 == 0 or i == total:
            print(f"  {i}/{total} matched", flush=True)

        try:
            result = await engine.match(cand.title)
        except Exception as exc:
            stats.errors.append(f"row {cand.row_number}: match error — {exc}")
            continue

        top = result.candidates[0] if result.candidates else None

        if result.matched:
            matched_rows.append(ImportRow(candidate=cand, match=result))
            stats.matched += 1
        elif top and top.confidence >= LOW_CONFIDENCE:
            review_rows.append({
                "row": cand.row_number,
                "title": cand.title,
                "query": result.query,
                "query_year": result.year or "",
                "top_tmdb_id": top.tmdb_id,
                "top_title": top.title,
                "top_year": top.year or "",
                "confidence": f"{top.confidence:.3f}",
                "reason": "low_confidence",
            })
            stats.review += 1
        else:
            review_rows.append({
                "row": cand.row_number,
                "title": cand.title,
                "query": result.query,
                "query_year": result.year or "",
                "top_tmdb_id": top.tmdb_id if top else "",
                "top_title": top.title if top else "",
                "top_year": top.year or "" if top else "",
                "confidence": f"{top.confidence:.3f}" if top else "",
                "reason": "no_results" if not top else "below_threshold",
            })
            stats.no_match += 1

    print(
        f"Matching done — {stats.matched} high-confidence, "
        f"{stats.review} for review, {stats.no_match} no-match"
    )

    # Enrich matched rows via get_movie_full (credits + genres + runtime etc.)
    print(f"Enriching {len(matched_rows)} matched titles…")
    for i, row in enumerate(matched_rows, 1):
        if i % 10 == 0 or i == len(matched_rows):
            print(f"  {i}/{len(matched_rows)} enriched", flush=True)
        top = row.match.candidates[0]
        try:
            row.movie = await tmdb.get_movie_full(top.tmdb_id)
            stats.enriched += 1
        except Exception as exc:
            stats.errors.append(
                f"row {row.candidate.row_number}: enrich error for tmdb_id={top.tmdb_id} — {exc}"
            )

    return matched_rows, review_rows


# ---------------------------------------------------------------------------
# DB helpers (psycopg2 / sync)
# ---------------------------------------------------------------------------


def insert_movie(conn: Any, movie: Movie) -> bool:
    """INSERT movie; returns True if newly inserted, False if already existed."""
    with conn.cursor() as cur:
        release_date = parse_release_date(movie.release_date)
        genre_ids = [g.id for g in movie.genres] if movie.genres else []

        cur.execute(
            """
            INSERT INTO movies (
                id, title, original_title, overview, release_date, runtime,
                popularity, vote_average, vote_count,
                poster_path, backdrop_path, genre_ids,
                status, tagline, budget, revenue, imdb_id, homepage
            ) VALUES (
                %(id)s, %(title)s, %(original_title)s, %(overview)s,
                %(release_date)s, %(runtime)s,
                %(popularity)s, %(vote_average)s, %(vote_count)s,
                %(poster_path)s, %(backdrop_path)s, %(genre_ids)s,
                %(status)s, %(tagline)s, %(budget)s, %(revenue)s,
                %(imdb_id)s, %(homepage)s
            )
            ON CONFLICT (id) DO NOTHING
            """,
            {
                "id": movie.id,
                "title": movie.title,
                "original_title": movie.original_title,
                "overview": movie.overview,
                "release_date": release_date,
                "runtime": movie.runtime,
                "popularity": movie.popularity,
                "vote_average": movie.vote_average,
                "vote_count": movie.vote_count,
                "poster_path": movie.poster_path,
                "backdrop_path": movie.backdrop_path,
                "genre_ids": genre_ids,
                "status": movie.status,
                "tagline": movie.tagline,
                "budget": movie.budget,
                "revenue": movie.revenue,
                "imdb_id": movie.imdb_id,
                "homepage": movie.homepage,
            },
        )
        return cur.rowcount > 0


def insert_credits(conn: Any, movie: Movie) -> None:
    """Insert cast/crew for a movie; skips entirely if credits already exist."""
    if not movie.credits:
        return

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM movie_credits WHERE movie_id = %s",
            (movie.id,),
        )
        row = cur.fetchone()
        if row and row[0] > 0:
            return

        rows: list[tuple[Any, ...]] = []

        for member in (movie.credits.cast or [])[:50]:
            rows.append((
                movie.id, member.id, member.name, "cast",
                member.character, None, None, member.order, member.profile_path,
            ))

        key_jobs = {"Director", "Producer", "Screenplay", "Writer", "Story"}
        for member in (movie.credits.crew or []):
            if member.job in key_jobs:
                rows.append((
                    movie.id, member.id, member.name, "crew",
                    None, member.department, member.job, None, member.profile_path,
                ))

        if rows:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO movie_credits
                    (movie_id, person_id, person_name, credit_type,
                     character, department, job, credit_order, profile_path)
                VALUES %s
                """,
                rows,
            )


def insert_collection_item(
    conn: Any,
    movie_id: int,
    candidate: ImportCandidate,
    db_format: str,
) -> bool:
    """Insert one collection item; returns True if inserted, False if duplicate."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM collection_items
            WHERE movie_id = %s AND format = %s AND deleted_at IS NULL
            """,
            (movie_id, db_format),
        )
        if cur.fetchone():
            return False

        notes: str | None = candidate.location_raw or None

        cur.execute(
            """
            INSERT INTO collection_items (movie_id, format, condition, notes)
            VALUES (%s, %s, %s, %s)
            """,
            (movie_id, db_format, DEFAULT_CONDITION, notes),
        )
        return True


# ---------------------------------------------------------------------------
# Review file
# ---------------------------------------------------------------------------


def write_review_file(review_rows: list[dict[str, Any]], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REVIEW_FIELDNAMES)
        writer.writeheader()
        writer.writerows(review_rows)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run(
    xlsx_path: Path,
    dry_run: bool,
    review_out: Path,
) -> ImportStats:
    stats = ImportStats()

    print(f"Parsing {xlsx_path}…")
    candidates = parse_xlsx(xlsx_path)
    stats.total = len(candidates)
    print(f"Parsed {stats.total} rows")

    async with TMDBClient() as tmdb:
        matched_rows, review_rows = await match_and_enrich(candidates, tmdb, stats)

    write_review_file(review_rows, review_out)
    print(f"Review file written → {review_out} ({len(review_rows)} rows)")

    if dry_run:
        print(f"[dry-run] Skipping DB writes ({stats.enriched} movies ready to insert)")
        return stats

    print("Writing to database…")
    conn = psycopg2.connect(settings.database_url)
    try:
        for i, row in enumerate(matched_rows, 1):
            if row.movie is None:
                continue

            if i % 50 == 0:
                print(f"  {i}/{len(matched_rows)} inserted", flush=True)

            with conn:  # one transaction per movie
                if insert_movie(conn, row.movie):
                    stats.movies_inserted += 1
                insert_credits(conn, row.movie)

                if not row.candidate.formats:
                    # No format data — still worth having the movie in the DB
                    stats.items_skipped += 1
                    continue

                for parser_fmt in row.candidate.formats:
                    db_fmt = map_format(parser_fmt)
                    if db_fmt is None:
                        stats.errors.append(
                            f"row {row.candidate.row_number}: unknown format '{parser_fmt}' — skipped"
                        )
                        continue
                    if insert_collection_item(conn, row.movie.id, row.candidate, db_fmt):
                        stats.items_inserted += 1
                    else:
                        stats.items_skipped += 1
    finally:
        conn.close()

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk import spreadsheet → MCU database (Phase 1.7)"
    )
    parser.add_argument("--xlsx", required=True, type=Path, help="Source .xlsx spreadsheet")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Match and enrich only — skip all DB writes",
    )
    parser.add_argument(
        "--review-out",
        type=Path,
        default=Path("import_review.csv"),
        metavar="PATH",
        help="Output path for low-confidence review file (default: import_review.csv)",
    )
    args = parser.parse_args()

    stats = asyncio.run(run(args.xlsx, args.dry_run, args.review_out))

    print("\n=== Import Summary ===")
    print(f"  Total rows parsed : {stats.total}")
    print(f"  High-confidence   : {stats.matched}")
    print(f"  Enriched          : {stats.enriched}")
    print(f"  Movies inserted   : {stats.movies_inserted}")
    print(f"  Items inserted    : {stats.items_inserted}")
    print(f"  Items skipped     : {stats.items_skipped}  (already in DB)")
    print(f"  For review        : {stats.review}  → {args.review_out}")
    print(f"  No match          : {stats.no_match}")
    if stats.errors:
        print(f"  Errors            : {len(stats.errors)}")
        for err in stats.errors[:10]:
            print(f"    - {err}")
        if len(stats.errors) > 10:
            print(f"    … and {len(stats.errors) - 10} more")


if __name__ == "__main__":
    main()
