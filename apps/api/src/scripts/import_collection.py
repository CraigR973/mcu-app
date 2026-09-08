"""Bulk import: spreadsheet → movies + movie_credits + collection_items.

Roadmap phase 1.7, re-landed in Batch 4 against the §3.4 schema.

Pipeline: parse xlsx → match via TMDB → enrich → insert.

Usage (from the repo root):

    set -a; source apps/api/.env.local; set +a
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.import_collection \\
        --xlsx "Film Catalogue - 4k Blu Ray DVD v1.0.xlsx" \\
        [--dry-run] \\
        [--review-out import_review.csv]

Two behaviours are worth knowing before running it.

**Every owned item is catalogued, matched or not.** A row TMDB cannot identify — or
identifies ambiguously — still gets a ``movies`` row (title only, ``tmdb_id`` NULL) and
its ``collection_items`` row, location included. The April importer inserted nothing at
all for those rows, so a disc genuinely on the shelf was absent from the catalogue with
only a CSV to say so. The review file is a queue of rows needing identification, not a
list of rows that were dropped.

**A confident match is not enriched if it is ambiguous.** The matcher reports
``ambiguous`` when the leading candidate is tied with films that are not plausibly the
same film — "Frankenstein" ties at 1.000 across 1910, 1931 and 2025 — in which case its
position came from TMDB popularity rather than from anything in the spreadsheet row.
Those go to review with their alternatives listed (`DECISIONS.md` #31).

**Re-running is safe.** Movies deduplicate on ``tmdb_id`` (or on title for unmatched
rows) and items on ``import_source_row`` — the spreadsheet line the item came from — so a
second run inserts nothing. Keying on the line rather than on the item's contents means
two rows the owner wrote down separately stay two items even when TMDB collapses them
onto one film (`DECISIONS.md` #32).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from src.config import psycopg2_dsn, settings
from src.matching import LOW_CONFIDENCE, MatchingEngine, MatchResult
from src.spreadsheet import ImportCandidate, parse_xlsx
from src.tmdb import TMDBClient
from src.tmdb.models import Movie

#: §3.4's condition vocabulary has no "unknown". Everything in the spreadsheet is a disc
#: in ordinary use, so "good" is the honest default; Batch 7's edit UI lets it be
#: corrected per item.
DEFAULT_CONDITION = "good"

#: TMDB crew jobs → §3.3's role vocabulary. Anything not listed is not stored: the
#: catalogue is searched by the people who define a film, not by its whole crew list.
CREW_ROLE_BY_JOB: dict[str, str] = {
    "Director": "director",
    "Writer": "writer",
    "Screenplay": "writer",
    "Story": "writer",
    "Producer": "producer",
    "Original Music Composer": "composer",
    "Music": "composer",
}

#: How many cast members are stored per film, and how many of those are denormalised
#: onto ``movies.top_cast_summary`` for the grid.
MAX_CAST_STORED = 50
TOP_CAST_SUMMARY_SIZE = 5

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
    # Every candidate the matcher could not rank below the leader on merit. Present so an
    # `ambiguous_match` row can actually be settled from this file — without the
    # alternatives listed, "ambiguous" is a complaint rather than a question.
    "alternatives",
]


@dataclass
class ImportRow:
    candidate: ImportCandidate
    match: MatchResult | None = None
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
    ambiguous: int = 0
    no_match: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def parse_year(raw: str | None) -> int | None:
    """Extract the release year from a TMDB ``YYYY-MM-DD`` string."""
    if not raw:
        return None
    try:
        return int(raw.split("-", 1)[0])
    except (ValueError, IndexError):
        return None


def pick_trailer_key(movie: Movie) -> str | None:
    """Return the YouTube key of the film's trailer, preferring the official one."""
    if movie.videos is None:
        return None
    youtube = [v for v in movie.videos.results if v.site == "YouTube" and v.type == "Trailer"]
    if not youtube:
        return None
    for video in youtube:
        if video.official:
            return video.key
    return youtube[0].key


def build_top_cast_summary(movie: Movie) -> list[dict[str, Any]] | None:
    """Top billed cast, denormalised onto the movie row for the collection grid.

    Keys are snake_case because this is a database column; Batch 5's response models
    are what turn the payload camelCase on the wire (`DECISIONS.md` #12).
    """
    if movie.credits is None or not movie.credits.cast:
        return None
    ordered = sorted(movie.credits.cast, key=lambda member: member.order)
    return [
        {
            "tmdb_person_id": member.id,
            "name": member.name,
            "character_name": member.character,
            "profile_path": member.profile_path,
        }
        for member in ordered[:TOP_CAST_SUMMARY_SIZE]
    ]


def credit_rows(movie_id: uuid.UUID, movie: Movie) -> list[tuple[Any, ...]]:
    """Flatten TMDB credits into ``movie_credits`` rows in §3.3's shape."""
    if movie.credits is None:
        return []

    rows: list[tuple[Any, ...]] = []
    ordered_cast = sorted(movie.credits.cast or [], key=lambda member: member.order)
    for member in ordered_cast[:MAX_CAST_STORED]:
        rows.append(
            (
                str(uuid.uuid4()),
                str(movie_id),
                member.name,
                member.id,
                "cast",
                member.character,
                member.order,
            )
        )

    for crew in movie.credits.crew or []:
        role = CREW_ROLE_BY_JOB.get(crew.job)
        if role is None:
            continue
        rows.append((str(uuid.uuid4()), str(movie_id), crew.name, crew.id, role, None, None))

    return rows


def review_row(candidate: ImportCandidate, result: MatchResult, reason: str) -> dict[str, Any]:
    top = result.candidates[0] if result.candidates else None
    return {
        "row": candidate.row_number,
        "title": candidate.title,
        "query": result.query,
        "query_year": result.year or "",
        "top_tmdb_id": top.tmdb_id if top else "",
        "top_title": top.title if top else "",
        "top_year": (top.year or "") if top else "",
        "confidence": f"{top.confidence:.3f}" if top else "",
        "reason": reason,
        "alternatives": " | ".join(
            f"{c.tmdb_id}:{c.title} ({c.year or '?'})" for c in result.candidates
        ),
    }


def write_review_file(review_rows: list[dict[str, Any]], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REVIEW_FIELDNAMES)
        writer.writeheader()
        writer.writerows(review_rows)


# ---------------------------------------------------------------------------
# Async: match + enrich
# ---------------------------------------------------------------------------


async def match_and_enrich(
    candidates: list[ImportCandidate],
    tmdb: TMDBClient,
    stats: ImportStats,
) -> tuple[list[ImportRow], list[dict[str, Any]]]:
    """Match every candidate and enrich the confident ones.

    Returns ``(rows, review_rows)``. **Every** candidate appears in ``rows``, including
    ones with no match — those carry ``movie=None`` and are imported title-only.
    """
    engine = MatchingEngine(tmdb)
    rows: list[ImportRow] = []
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
            # Still catalogued: a TMDB outage must not lose a disc off the shelf.
            rows.append(ImportRow(candidate=cand))
            continue

        top = result.candidates[0] if result.candidates else None

        if result.matched and not result.ambiguous:
            rows.append(ImportRow(candidate=cand, match=result))
            stats.matched += 1
            continue

        if result.ambiguous:
            # Confident but tied between films that are not plausibly the same one. The
            # disc is still catalogued with its location; only the identification waits
            # for a person. Guessing here writes a wrong poster, cast and search vector
            # that nothing downstream would flag as wrong (`DECISIONS.md` #31).
            review_rows.append(review_row(cand, result, "ambiguous_match"))
            stats.ambiguous += 1
            rows.append(ImportRow(candidate=cand))
            continue

        if top and top.confidence >= LOW_CONFIDENCE:
            review_rows.append(review_row(cand, result, "low_confidence"))
            stats.review += 1
        else:
            review_rows.append(
                review_row(cand, result, "no_results" if not top else "below_threshold")
            )
            stats.no_match += 1
        rows.append(ImportRow(candidate=cand))

    print(
        f"Matching done — {stats.matched} settled, {stats.ambiguous} ambiguous, "
        f"{stats.review} low-confidence, {stats.no_match} no-match"
    )

    to_enrich = [row for row in rows if row.match is not None]
    print(f"Enriching {len(to_enrich)} matched titles…")
    for i, row in enumerate(to_enrich, 1):
        if i % 10 == 0 or i == len(to_enrich):
            print(f"  {i}/{len(to_enrich)} enriched", flush=True)
        assert row.match is not None
        top_candidate = row.match.candidates[0]
        try:
            row.movie = await tmdb.get_movie_full(top_candidate.tmdb_id)
            stats.enriched += 1
        except Exception as exc:
            stats.errors.append(
                f"row {row.candidate.row_number}: "
                f"enrich error for tmdb_id={top_candidate.tmdb_id} — {exc}"
            )

    return rows, review_rows


# ---------------------------------------------------------------------------
# DB writes (psycopg2 / sync)
# ---------------------------------------------------------------------------


def upsert_movie(conn: Any, movie: Movie) -> tuple[uuid.UUID, bool]:
    """Insert an enriched movie, or return the id of the existing row.

    Returns ``(movie_id, inserted)``. Deduplication is on ``tmdb_id``, which is the
    unique key §3.2 gives the table — not on the primary key, which is ours.
    """
    genres = [{"id": g.id, "name": g.name} for g in movie.genres] if movie.genres else None
    payload = {
        "id": str(uuid.uuid4()),
        "tmdb_id": movie.id,
        "imdb_id": movie.imdb_id,
        "title": movie.title,
        "original_title": movie.original_title,
        "year": parse_year(movie.release_date),
        "runtime_minutes": movie.runtime,
        "overview": movie.overview or None,
        "tagline": movie.tagline or None,
        "poster_path": movie.poster_path,
        "backdrop_path": movie.backdrop_path,
        "tmdb_rating": movie.vote_average,
        "tmdb_vote_count": movie.vote_count,
        "genres": psycopg2.extras.Json(genres) if genres else None,
        "genre_ids": [g.id for g in movie.genres] if movie.genres else None,
        "top_cast_summary": (
            psycopg2.extras.Json(summary)
            if (summary := build_top_cast_summary(movie)) is not None
            else None
        ),
        "trailer_key": pick_trailer_key(movie),
        # Everything the matching engine finds comes from /search/movie, so it is a
        # film by construction. `is_tv` is set by hand for the box-set series rows.
        "media_type": "film",
        "last_tmdb_sync_utc": datetime.now(UTC).replace(tzinfo=None),
    }

    with conn.cursor() as cur:
        columns = ", ".join(payload)
        placeholders = ", ".join(f"%({key})s" for key in payload)
        cur.execute(
            f"INSERT INTO movies ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT (tmdb_id) DO NOTHING RETURNING id",
            payload,
        )
        row = cur.fetchone()
        if row is not None:
            return uuid.UUID(str(row[0])), True

        cur.execute("SELECT id FROM movies WHERE tmdb_id = %s", (movie.id,))
        existing = cur.fetchone()
        assert existing is not None, "ON CONFLICT fired but the conflicting row is gone"
        return uuid.UUID(str(existing[0])), False


def upsert_unmatched_movie(conn: Any, title: str) -> tuple[uuid.UUID, bool]:
    """Insert a title-only movie row for a candidate TMDB could not identify.

    ``tmdb_id`` stays NULL, which is what marks the row as needing enrichment. There is
    no unique constraint to lean on here — NULLs do not conflict — so the lookup is an
    explicit select on the title.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM movies WHERE title = %s AND tmdb_id IS NULL AND deleted_at IS NULL",
            (title,),
        )
        existing = cur.fetchone()
        if existing is not None:
            return uuid.UUID(str(existing[0])), False

        movie_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO movies (id, title, media_type) VALUES (%s, %s, %s)",
            (str(movie_id), title, "film"),
        )
        return movie_id, True


def insert_credits(conn: Any, movie_id: uuid.UUID, movie: Movie) -> int:
    """Insert cast/crew for a movie. No-op when the film already has credits."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM movie_credits WHERE movie_id = %s LIMIT 1", (str(movie_id),))
        if cur.fetchone() is not None:
            return 0

        rows = credit_rows(movie_id, movie)
        if not rows:
            return 0

        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO movie_credits
                (id, movie_id, person_name, tmdb_person_id, role, character_name, display_order)
            VALUES %s
            """,
            rows,
        )
        return len(rows)


def insert_collection_item(conn: Any, movie_id: uuid.UUID, candidate: ImportCandidate) -> bool:
    """Insert one collection item; returns False when an identical one already exists.

    This is where Batch 4's fix lands: ``location``, ``section`` and ``shelf`` are
    written as their own columns. ``notes`` is left NULL — it means notes now, not a
    place to hide the location string the schema had nowhere else to put.
    """
    formats = psycopg2.extras.Json(candidate.formats)
    location = candidate.location_raw or None

    with conn.cursor() as cur:
        # Keyed on the spreadsheet line, not on the item's contents. Two source rows that
        # resolve to the same film, shelf and format are still two discs; keying on
        # contents collapsed "French Connection" and "French Connection 2" into one.
        cur.execute(
            "SELECT 1 FROM collection_items WHERE import_source_row = %s",
            (candidate.row_number,),
        )
        if cur.fetchone() is not None:
            return False

        cur.execute(
            """
            INSERT INTO collection_items
                (id, movie_id, formats, location, section, shelf, sub_category, condition,
                 import_source_row)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                str(movie_id),
                formats,
                location,
                candidate.section,
                candidate.shelf,
                candidate.sub_category,
                DEFAULT_CONDITION,
                candidate.row_number,
            ),
        )
        return True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run(xlsx_path: Path, dry_run: bool, review_out: Path) -> ImportStats:
    stats = ImportStats()

    print(f"Parsing {xlsx_path}…")
    candidates = parse_xlsx(xlsx_path)
    stats.total = len(candidates)
    print(f"Parsed {stats.total} rows")

    # Prove the database is reachable *before* the TMDB pass. Matching and enriching
    # 1,857 titles takes roughly three quarters of an hour at the client's rate limit,
    # and connecting only afterwards means a bad DSN costs all of it.
    if not dry_run:
        psycopg2.connect(psycopg2_dsn(settings.database_url)).close()
        print("Database reachable")

    async with TMDBClient() as tmdb:
        rows, review_rows = await match_and_enrich(candidates, tmdb, stats)

    write_review_file(review_rows, review_out)
    print(f"Review file written → {review_out} ({len(review_rows)} rows)")

    if dry_run:
        print(f"[dry-run] Skipping DB writes ({len(rows)} items ready to insert)")
        return stats

    print("Writing to database…")
    conn = psycopg2.connect(psycopg2_dsn(settings.database_url))
    try:
        for i, row in enumerate(rows, 1):
            if i % 50 == 0 or i == len(rows):
                print(f"  {i}/{len(rows)} written", flush=True)

            try:
                with conn:  # one transaction per item
                    if row.movie is not None:
                        movie_id, inserted = upsert_movie(conn, row.movie)
                        if inserted:
                            stats.movies_inserted += 1
                        insert_credits(conn, movie_id, row.movie)
                    else:
                        movie_id, inserted = upsert_unmatched_movie(conn, row.candidate.title)
                        if inserted:
                            stats.movies_inserted += 1

                    if insert_collection_item(conn, movie_id, row.candidate):
                        stats.items_inserted += 1
                    else:
                        stats.items_skipped += 1
            except psycopg2.Error as exc:
                stats.errors.append(f"row {row.candidate.row_number}: insert error — {exc}")
    finally:
        conn.close()

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk import spreadsheet → MCU database (roadmap phase 1.7)"
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
    print(f"  Ambiguous         : {stats.ambiguous}  (catalogued, identification deferred)")
    print(f"  Low confidence    : {stats.review}  → {args.review_out}")
    print(f"  No match          : {stats.no_match}")
    if stats.errors:
        print(f"  Errors            : {len(stats.errors)}")
        for err in stats.errors[:10]:
            print(f"    - {err}")
        if len(stats.errors) > 10:
            print(f"    … and {len(stats.errors) - 10} more")


if __name__ == "__main__":
    main()
