"""
Eval harness for Phase 1.6 — runs the matching engine on a sample of
spreadsheet titles and writes a CSV for human review.

Usage (from the repo root):

    apps/api/.venv/bin/python -m apps.api.scripts.eval_matching \\
        --xlsx "Film Catalogue - 4k^J Blu Ray ^0 DVD v 1.0 bit 02.02.26.xlsx" \\
        --sample 100 \\
        --out matching_eval.csv

The CSV has columns: row, raw_title, query, query_year, top_tmdb_id,
top_title, top_year, top_confidence, year_match, matched.

Acceptance: spot-check the CSV — ≥90% of confident rows should be the right
film and the unmatched rows should be ones a human would also struggle with.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import random
import sys
from pathlib import Path

# Make ``src`` importable when invoked as ``python scripts/eval_matching.py``
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.matching import MatchingEngine  # noqa: E402
from src.spreadsheet import parse_xlsx  # noqa: E402
from src.tmdb import TMDBClient  # noqa: E402


async def run(xlsx_path: Path, sample: int, out_path: Path, seed: int) -> None:
    candidates = parse_xlsx(xlsx_path)
    print(f"Parsed {len(candidates)} rows from {xlsx_path}")

    rng = random.Random(seed)
    if sample and sample < len(candidates):
        chosen = rng.sample(candidates, sample)
    else:
        chosen = list(candidates)

    fieldnames = [
        "row",
        "raw_title",
        "query",
        "query_year",
        "top_tmdb_id",
        "top_title",
        "top_year",
        "top_confidence",
        "year_match",
        "matched",
    ]

    matched_count = 0
    no_results_count = 0

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        async with TMDBClient() as tmdb:
            engine = MatchingEngine(tmdb)
            for i, cand in enumerate(chosen, start=1):
                result = await engine.match(cand.title)
                top = result.candidates[0] if result.candidates else None
                writer.writerow(
                    {
                        "row": cand.row_number,
                        "raw_title": cand.title,
                        "query": result.query,
                        "query_year": result.year or "",
                        "top_tmdb_id": top.tmdb_id if top else "",
                        "top_title": top.title if top else "",
                        "top_year": top.year if top and top.year else "",
                        "top_confidence": f"{top.confidence:.3f}" if top else "",
                        "year_match": top.year_match if top else "",
                        "matched": "yes" if result.matched else "no",
                    }
                )
                if result.matched:
                    matched_count += 1
                if not result.candidates:
                    no_results_count += 1
                if i % 10 == 0:
                    print(f"  {i}/{len(chosen)} processed", flush=True)

    print(
        f"Wrote {out_path} — {matched_count}/{len(chosen)} confident, "
        f"{no_results_count} with no TMDB hits"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", required=True, type=Path)
    parser.add_argument("--sample", type=int, default=100, help="0 = all rows")
    parser.add_argument("--out", type=Path, default=Path("matching_eval.csv"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    asyncio.run(run(args.xlsx, args.sample, args.out, args.seed))


if __name__ == "__main__":
    main()
