"""Fill in the TMDB keywords of the films identified before Batch Y5 (#277).

Every full TMDB fetch since Y5 stores a film's keywords (``movies.tmdb_keyword_ids``), which
the Archive's Film Noir reads. The films identified before it have none yet: null, "not
fetched". This reads them one ``/movie/{id}/keywords`` call a film (``/tv/{id}/keywords`` a
series), and writes each list only onto a row still null and still that film, so a run can be
stopped and run again, and never overwrites a film identified as another meanwhile.

Its writes are metadata, as an identification's are, so they are not audited row by row; the
run's counts are its record.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.movie import Movie
from src.services.movie_metadata import keyword_ids
from src.tmdb.client import TMDBRefused
from src.tmdb.models import MovieKeywords, TvKeywords

#: TMDB's keyword "film noir", which the Archive offers as "Film Noir".
FILM_NOIR_KEYWORD = 9807
#: Rows written between commits, so a stopped run keeps what it wrote.
CHUNK = 100


class KeywordSource(Protocol):
    async def get_movie_keywords(self, movie_id: int) -> MovieKeywords: ...

    async def get_tv_keywords(self, tv_id: int) -> TvKeywords: ...


@dataclass(frozen=True)
class Target:
    movie_id: uuid.UUID
    title: str
    year: int | None
    tmdb_id: int | None
    tmdb_tv_id: int | None


@dataclass
class Outcome:
    #: Each row's keyword ids, as fetched.
    fetched: dict[uuid.UUID, list[int]] = field(default_factory=dict)
    #: TMDB answered 404: it no longer has the film. Left null.
    missing: list[Target] = field(default_factory=list)
    #: TMDB did not answer. Left null, for the next run.
    failed: list[Target] = field(default_factory=list)
    written: int = 0
    #: Rows that changed while the run read TMDB (identified as another, or filled), so the
    #: list fetched was not written onto them.
    changed: int = 0
    noir: list[Target] = field(default_factory=list)


async def targets(db: AsyncSession, *, limit: int | None = None) -> list[Target]:
    """Live films and series identified from TMDB whose keywords were never fetched."""
    query = (
        select(Movie.id, Movie.title, Movie.year, Movie.tmdb_id, Movie.tmdb_tv_id)
        .where(
            Movie.deleted_at.is_(None),
            Movie.tmdb_keyword_ids.is_(None),
            (Movie.tmdb_id.is_not(None)) | (Movie.tmdb_tv_id.is_not(None)),
        )
        .order_by(Movie.title, Movie.id)
    )
    if limit is not None:
        query = query.limit(limit)
    return [Target(*row) for row in (await db.execute(query)).all()]


async def _keywords_of(tmdb: KeywordSource, target: Target) -> list[int]:
    if target.tmdb_id is not None:
        found = await tmdb.get_movie_keywords(target.tmdb_id)
        return keyword_ids(found.keywords) or []
    assert target.tmdb_tv_id is not None
    series = await tmdb.get_tv_keywords(target.tmdb_tv_id)
    return keyword_ids(series.results) or []


async def fetch(
    tmdb: KeywordSource,
    batch: Sequence[Target],
    outcome: Outcome,
    *,
    progress: Callable[[int], None] | None = None,
) -> None:
    """Read each target's keywords into ``outcome``. One call each; the client paces them."""
    for target in batch:
        try:
            ids = await _keywords_of(tmdb, target)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                outcome.missing.append(target)
            else:
                outcome.failed.append(target)
            continue
        except (httpx.HTTPError, TMDBRefused):
            outcome.failed.append(target)
            continue
        outcome.fetched[target.movie_id] = ids
        if FILM_NOIR_KEYWORD in ids:
            outcome.noir.append(target)
        if progress is not None:
            progress(len(outcome.fetched))


async def write(db: AsyncSession, batch: Sequence[Target], outcome: Outcome) -> None:
    """Write the fetched lists of ``batch`` onto rows still null and still that film. Does not
    commit."""
    for target in batch:
        ids = outcome.fetched.get(target.movie_id)
        if ids is None:
            continue
        result = await db.execute(
            update(Movie)
            .where(
                Movie.id == target.movie_id,
                Movie.tmdb_keyword_ids.is_(None),
                Movie.tmdb_id.is_not_distinct_from(target.tmdb_id),
                Movie.tmdb_tv_id.is_not_distinct_from(target.tmdb_tv_id),
            )
            .values(tmdb_keyword_ids=ids)
        )
        if getattr(result, "rowcount", 0) == 1:
            outcome.written += 1
        else:
            outcome.changed += 1


async def run(
    tmdb: KeywordSource,
    all_targets: Sequence[Target],
    *,
    apply: bool,
    commit: Callable[[Sequence[Target], Outcome], Awaitable[None]] | None = None,
    progress: Callable[[int], None] | None = None,
) -> Outcome:
    """Fetch every target's keywords, a chunk at a time, writing each chunk through ``commit``
    when ``apply`` is set. A dry run fetches the same and writes nothing."""
    outcome = Outcome()
    for start in range(0, len(all_targets), CHUNK):
        batch = all_targets[start : start + CHUNK]
        await fetch(tmdb, batch, outcome, progress=progress)
        if apply and commit is not None:
            await commit(batch, outcome)
    return outcome
