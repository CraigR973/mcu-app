"""The collection's row for a TMDB film or series: found, or made from TMDB's record.

The add form and "Move only this copy" both put a disc on the film TMDB says it is, making the
row when the collection lacks it. Since Batch Y5 (#277) either may be a series, held in
``tmdb_tv_id`` as Y3 identifies one, so the finding and the making live here once rather than
in each, where a series made by one path could differ from a series made by the other.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.movie import Movie, MovieCredit
from src.services.movie_metadata import (
    credit_rows,
    movie_metadata_values,
    tv_credit_rows,
    tv_metadata_values,
)
from src.tmdb.models import Movie as TmdbMovie
from src.tmdb.models import TvShow

TmdbRecord = TmdbMovie | TvShow


async def held_row(
    db: AsyncSession, *, tmdb_id: int | None = None, tmdb_tv_id: int | None = None
) -> Movie | None:
    """The row holding this TMDB film or series, trashed or not: both ids are unique, so the
    caller decides what a trashed one means."""
    if (tmdb_id is None) == (tmdb_tv_id is None):
        raise ValueError("Name a film or a series")
    column = Movie.tmdb_id if tmdb_id is not None else Movie.tmdb_tv_id
    held: Movie | None = await db.scalar(select(Movie).where(column == (tmdb_id or tmdb_tv_id)))
    return held


async def held_row_for(db: AsyncSession, record: TmdbRecord) -> Movie | None:
    if isinstance(record, TvShow):
        return await held_row(db, tmdb_tv_id=record.id)
    return await held_row(db, tmdb_id=record.id)


async def make_row(db: AsyncSession, record: TmdbRecord) -> Movie:
    """A new row from TMDB's record, with its credits, as an identification writes them.
    Flushes; does not commit."""
    if isinstance(record, TvShow):
        movie = Movie(id=uuid.uuid4(), **tv_metadata_values(record))
    else:
        movie = Movie(id=uuid.uuid4(), **movie_metadata_values(record))
    db.add(movie)
    # The credits reference the row, and the search_vector trigger reads the title and
    # overview this flush writes.
    await db.flush()
    rows = (
        tv_credit_rows(movie.id, record)
        if isinstance(record, TvShow)
        else credit_rows(movie.id, record)
    )
    for row in rows:
        db.add(
            MovieCredit(
                id=uuid.UUID(row[0]),
                movie_id=movie.id,
                person_name=row[2],
                tmdb_person_id=row[3],
                role=row[4],
                character_name=row[5],
                display_order=row[6],
            )
        )
    await db.flush()
    return movie
