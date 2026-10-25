"""Daily IMDb ratings for ids this private app already holds (AA5).

Contract: https://data.imdb.com/non-commercial-datasets/ . No website scraping.
Download to a bounded temporary spool, validate the complete gzip/TSV before any write,
then update only stored ids. A failed or truncated download cannot erase prior scores.
"""

from __future__ import annotations

import asyncio
import gzip
import io
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import IO

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.movie import Movie
from src.models.movie_night import MovieNightSuggestion

RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
DOWNLOAD_SECONDS = 180
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
MAX_TEXT_BYTES = 256 * 1024 * 1024
MAX_ROWS = 5_000_000
SCORE = re.compile(r"(?:[0-9](?:\.[0-9]{1,6})?|10(?:\.0{1,6})?)\Z")
IMDB_ID = re.compile(r"tt[0-9]{7,18}\Z")
HEADER = "tconst\taverageRating\tnumVotes"


@dataclass(frozen=True)
class Rating:
    score: Decimal
    votes: int | None


@dataclass(frozen=True)
class RatingsResult:
    rows: int
    matched: int
    updated: int


def read_ratings(source: IO[bytes], wanted: set[str]) -> tuple[dict[str, Rating | None], int]:
    """Only retain wanted rows; reject invalid/truncated files before touching the DB."""
    found: dict[str, Rating | None] = {}
    rows = 0
    size = 0
    with (
        gzip.GzipFile(fileobj=source, mode="rb") as zipped,
        io.TextIOWrapper(zipped, encoding="utf-8-sig", newline="") as text,
    ):
        if text.readline(513).rstrip("\r\n") != HEADER:
            raise ValueError("IMDb ratings header changed")
        while line := text.readline(513):
            size += len(line.encode("utf-8"))
            rows += 1
            if len(line) > 512 or size > MAX_TEXT_BYTES or rows > MAX_ROWS:
                raise ValueError("IMDb ratings file exceeds its bounds")
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) != 3 or IMDB_ID.fullmatch(fields[0]) is None:
                raise ValueError(f"Invalid IMDb ratings row {rows}")
            if fields[1] != "\\N" and SCORE.fullmatch(fields[1]) is None:
                raise ValueError(f"Invalid IMDb ratings row {rows}")
            try:
                score = None if fields[1] == "\\N" else Decimal(fields[1])
                votes = None if fields[2] == "\\N" else int(fields[2])
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(f"Invalid IMDb ratings row {rows}") from exc
            if (score is not None and (not score.is_finite() or not 0 <= score <= 10)) or (
                votes is not None and not 0 <= votes <= 2_147_483_647
            ):
                raise ValueError(f"Invalid IMDb ratings row {rows}")
            if fields[0] in wanted:
                if fields[0] in found:
                    raise ValueError("Duplicate stored IMDb id in ratings file")
                found[fields[0]] = Rating(score, votes) if score is not None else None
    if not rows:
        raise ValueError("IMDb ratings file has no ratings")
    return found, rows


async def refresh_ratings(
    db: AsyncSession, client: httpx.AsyncClient, *, now: datetime | None = None
) -> RatingsResult:
    wanted = {
        imdb_id
        for model in (Movie, MovieNightSuggestion)
        for imdb_id in await db.scalars(select(model.imdb_id).where(model.imdb_id.is_not(None)))
        if imdb_id is not None and IMDB_ID.fullmatch(imdb_id)
    }
    # Release the read transaction while waiting for the outside world.
    await db.commit()
    if not wanted:
        return RatingsResult(rows=0, matched=0, updated=0)
    with tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b") as spool:
        downloaded = 0
        async with asyncio.timeout(DOWNLOAD_SECONDS):
            async with client.stream(
                "GET",
                RATINGS_URL,
                headers={"Accept-Encoding": "identity"},
                timeout=httpx.Timeout(120, connect=15),
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(64 * 1024):
                    downloaded += len(chunk)
                    if downloaded > MAX_DOWNLOAD_BYTES:
                        raise ValueError("IMDb ratings download exceeds its bound")
                    spool.write(chunk)
        spool.seek(0)
        found, rows = read_ratings(spool, wanted)
    if not found:
        raise ValueError("IMDb ratings file matches no stored ids; previous scores kept")
    checked = now or utcnow()
    updated = await _apply_ratings(db, Movie, wanted, found, checked)
    updated += await _apply_ratings(db, MovieNightSuggestion, wanted, found, checked)
    await db.commit()
    return RatingsResult(rows=rows, matched=len(found), updated=updated)


async def _apply_ratings[RatedModel: (Movie, MovieNightSuggestion)](
    db: AsyncSession,
    model: type[RatedModel],
    wanted: set[str],
    found: dict[str, Rating | None],
    checked: datetime,
) -> int:
    query = select(model).where(model.imdb_id.in_(wanted))
    if model is Movie:
        query = query.where(Movie.deleted_at.is_(None))
    query = query.order_by(model.id).with_for_update().execution_options(populate_existing=True)
    updated = 0
    for item in await db.scalars(query):
        if (
            item.imdb_ratings_checked_utc is not None
            and item.imdb_ratings_checked_utc > checked
            and item.imdb_ratings_id == item.imdb_id
        ):
            continue
        rating = found.get(item.imdb_id or "")
        item.imdb_ratings_id = item.imdb_id
        item.imdb_rating = rating.score if rating else None
        item.imdb_vote_count = rating.votes if rating else None
        item.imdb_ratings_checked_utc = checked
        updated += 1
    return updated
