"""Bulk import: spreadsheet → movies + movie_credits + collection_items.

Roadmap phase 1.7, re-landed in Batch 4 against the §3.4 schema.

Pipeline: parse xlsx → match via TMDB → enrich → insert.

Usage (from the repo root):

    set -a; source apps/api/.env.local; set +a
    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.import_collection \\
        --xlsx "Film Catalogue - 4k Blu Ray DVD v1.0.xlsx" \\
        [--dry-run] \\
        [--replace-items [--accept-split]] \\
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

**Replacing items is atomic and guarded.** ``--replace-items`` soft-deletes every live
item and imports the sheet in one transaction. It refuses while an unidentified film has
watch history, because a tidied spreadsheet title could otherwise put the replacement disc
on a new movie row while leaving the watches behind. ``--accept-split`` names and accepts
that consequence for films which cannot be identified (`DECISIONS.md` #194).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from src.config import psycopg2_dsn, settings
from src.matching import LOW_CONFIDENCE, MatchingEngine, MatchResult
from src.services.movie_metadata import (
    credit_rows,
    movie_metadata_values,
)
from src.spreadsheet import ImportCandidate, parse_xlsx
from src.tmdb import TMDBClient
from src.tmdb.models import Movie

#: §3.4's condition vocabulary has no "unknown". Everything in the spreadsheet is a disc
#: in ordinary use, so "good" is the honest default; Batch 7's edit UI lets it be
#: corrected per item.
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
    items_to_replace: int = 0
    items_replaced: int = 0
    review: int = 0
    ambiguous: int = 0
    no_match: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReplacementPlan:
    """The live rows a replacement would affect, read before any write."""

    live_items: int
    unidentified_films_with_watches: int
    watch_rows_at_risk: int


class ReplacementBlocked(RuntimeError):
    """Raised before a replacement that could silently split discs from watches."""

    def __init__(self, plan: ReplacementPlan) -> None:
        self.plan = plan
        super().__init__(
            "Refusing --replace-items: "
            f"{plan.unidentified_films_with_watches} unidentified films hold "
            f"{plan.watch_rows_at_risk} live watch rows. Run the watch-history import "
            "with --identify first (OWNER-ACTIONS.md 1i step 2), or pass "
            "--accept-split to accept that those watches may remain on the old movie rows."
        )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


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
    payload = {"id": str(uuid.uuid4()), **movie_metadata_values(movie)}
    if payload["genres"] is not None:
        payload["genres"] = psycopg2.extras.Json(payload["genres"])
    if payload["top_cast_summary"] is not None:
        payload["top_cast_summary"] = psycopg2.extras.Json(payload["top_cast_summary"])

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
            "SELECT 1 FROM collection_items WHERE import_source_row = %s AND deleted_at IS NULL",
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


def replacement_plan(conn: Any) -> ReplacementPlan:
    """Count the replacement and its silent history-split risk without writing."""
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM collection_items WHERE deleted_at IS NULL")
        live_row = cur.fetchone()
        assert live_row is not None

        cur.execute(
            """
            SELECT count(DISTINCT m.id), count(w.id)
            FROM movies m
            JOIN watch_log w ON w.movie_id = m.id AND w.deleted_at IS NULL
            WHERE m.tmdb_id IS NULL
              AND m.deleted_at IS NULL
            """
        )
        risk_row = cur.fetchone()
        assert risk_row is not None

    return ReplacementPlan(
        live_items=int(live_row[0]),
        unidentified_films_with_watches=int(risk_row[0]),
        watch_rows_at_risk=int(risk_row[1]),
    )


def ensure_replacement_allowed(plan: ReplacementPlan, *, accept_split: bool) -> None:
    """Stop before the one ordering error that otherwise succeeds silently."""
    if plan.unidentified_films_with_watches and not accept_split:
        raise ReplacementBlocked(plan)


def soft_delete_live_items(conn: Any) -> int:
    """Move every live collection item to Trash and return the affected count."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE collection_items
            SET deleted_at = clock_timestamp() AT TIME ZONE 'utc'
            WHERE deleted_at IS NULL
            """
        )
        return int(cur.rowcount)


def lock_replacement_tables(conn: Any) -> None:
    """Freeze every table whose writes could invalidate the replacement preconditions.

    TMDB enrichment happens before the replacement transaction, so ordinary reads remain
    available throughout the slow part. The lock covers only the database write pass and
    prevents a watch, movie or item write from landing between the final guard and the
    soft-delete. ``SHARE ROW EXCLUSIVE`` still permits this transaction's own writes.
    """
    with conn.cursor() as cur:
        cur.execute("LOCK TABLE collection_items, movies, watch_log IN SHARE ROW EXCLUSIVE MODE")


def write_import_row(conn: Any, row: ImportRow, stats: ImportStats) -> None:
    """Write one prepared row into the caller's current transaction."""
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


def replace_collection_items(
    conn: Any,
    rows: list[ImportRow],
    stats: ImportStats,
    *,
    accept_split: bool,
) -> ReplacementPlan:
    """Replace all live items inside the transaction owned by the caller.

    The guard is repeated here, immediately before the update, rather than trusting the
    earlier preflight. That closes the race where a watch is added while TMDB enrichment
    is running. Any exception escapes to the connection context in :func:`run`, which
    rolls the deletion and every insert back together.
    """
    lock_replacement_tables(conn)
    plan = replacement_plan(conn)
    ensure_replacement_allowed(plan, accept_split=accept_split)
    stats.items_to_replace = plan.live_items
    stats.items_replaced = soft_delete_live_items(conn)

    for row in rows:
        write_import_row(conn, row, stats)

    return plan


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run(
    xlsx_path: Path,
    dry_run: bool,
    review_out: Path,
    *,
    replace_items: bool = False,
    accept_split: bool = False,
) -> ImportStats:
    stats = ImportStats()

    print(f"Parsing {xlsx_path}…")
    candidates = parse_xlsx(xlsx_path)
    stats.total = len(candidates)
    print(f"Parsed {stats.total} rows")

    # Prove the database is reachable *before* the TMDB pass. Matching and enriching
    # 1,857 titles takes roughly three quarters of an hour at the client's rate limit,
    # and connecting only afterwards means a bad DSN costs all of it. A replacement dry
    # run also needs the database so it can report the rows it would remove and run the
    # history-split guard.
    if not dry_run or replace_items:
        preflight_conn = psycopg2.connect(psycopg2_dsn(settings.database_url))
        try:
            if replace_items:
                plan = replacement_plan(preflight_conn)
                stats.items_to_replace = plan.live_items
                print(f"Replacement would soft-delete {plan.live_items} live items")
                ensure_replacement_allowed(plan, accept_split=accept_split)
            print("Database reachable")
        finally:
            preflight_conn.close()

    async with TMDBClient() as tmdb:
        rows, review_rows = await match_and_enrich(candidates, tmdb, stats)

    write_review_file(review_rows, review_out)
    print(f"Review file written → {review_out} ({len(review_rows)} rows)")

    if dry_run:
        if replace_items:
            print(
                f"[dry-run] Would soft-delete {stats.items_to_replace} live collection items; "
                "removed nothing"
            )
        print(f"[dry-run] Skipping DB writes ({len(rows)} items ready to insert)")
        return stats

    # A normal import can still catalogue a row title-only when TMDB fails — the existing
    # fail-safe behaviour. A replacement cannot: doing so after removing every item would
    # split otherwise identified films from their metadata and history. Refuse before the
    # destructive statement, leaving the whole collection untouched.
    if replace_items and stats.errors:
        stats.errors.insert(
            0,
            "replacement refused before database writes because matching or enrichment failed",
        )
        return stats

    print("Writing to database…")
    conn = psycopg2.connect(psycopg2_dsn(settings.database_url))
    try:
        if replace_items:
            before = (
                stats.movies_inserted,
                stats.items_inserted,
                stats.items_skipped,
                stats.items_replaced,
            )
            try:
                with conn:
                    replace_collection_items(
                        conn,
                        rows,
                        stats,
                        accept_split=accept_split,
                    )
                print(f"Soft-deleted {stats.items_replaced} live collection items")
            except psycopg2.Error as exc:
                (
                    stats.movies_inserted,
                    stats.items_inserted,
                    stats.items_skipped,
                    stats.items_replaced,
                ) = before
                stats.errors.append(f"replacement rolled back — {exc}")
            return stats

        for i, row in enumerate(rows, 1):
            if i % 50 == 0 or i == len(rows):
                print(f"  {i}/{len(rows)} written", flush=True)

            try:
                with conn:  # one transaction per item
                    write_import_row(conn, row, stats)
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
        "--replace-items",
        action="store_true",
        help="Atomically soft-delete every live collection item before importing",
    )
    parser.add_argument(
        "--accept-split",
        action="store_true",
        help=(
            "Allow --replace-items while unidentified films hold watch history; "
            "those watches may remain on old movie rows"
        ),
    )
    parser.add_argument(
        "--review-out",
        type=Path,
        default=Path("import_review.csv"),
        metavar="PATH",
        help="Output path for low-confidence review file (default: import_review.csv)",
    )
    args = parser.parse_args()

    if args.accept_split and not args.replace_items:
        parser.error("--accept-split requires --replace-items")

    try:
        stats = asyncio.run(
            run(
                args.xlsx,
                args.dry_run,
                args.review_out,
                replace_items=args.replace_items,
                accept_split=args.accept_split,
            )
        )
    except ReplacementBlocked as exc:
        parser.error(str(exc))

    print("\n=== Import Summary ===")
    print(f"  Total rows parsed : {stats.total}")
    print(f"  High-confidence   : {stats.matched}")
    print(f"  Enriched          : {stats.enriched}")
    print(f"  Movies inserted   : {stats.movies_inserted}")
    print(f"  Items inserted    : {stats.items_inserted}")
    print(f"  Items skipped     : {stats.items_skipped}  (already in DB)")
    if args.replace_items:
        print(f"  Items to replace  : {stats.items_to_replace}")
        print(f"  Items soft-deleted: {stats.items_replaced}")
    print(f"  Ambiguous         : {stats.ambiguous}  (catalogued, identification deferred)")
    print(f"  Low confidence    : {stats.review}  → {args.review_out}")
    print(f"  No match          : {stats.no_match}")
    if stats.errors:
        print(f"  Errors            : {len(stats.errors)}")
        for err in stats.errors[:10]:
            print(f"    - {err}")
        if len(stats.errors) > 10:
            print(f"    … and {len(stats.errors) - 10} more")

    if args.replace_items and stats.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
