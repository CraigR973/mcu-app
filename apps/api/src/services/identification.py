"""Applying a TMDB identification to a film row — extracted in Batch S8.

This was `routers/movies.py::_apply_identification`, reachable only through
`POST /movies/{id}/identify`. S8 needs exactly the same operation from a script: its
import matches **396 distinct films** that the April import never identified, and filling
in `tmdb_id`, year, poster, runtime and cast is half of what makes that import worth
running (`DECISIONS.md` #160).

**The only behavioural change is who commits.** The router committed inside; a batch
import must commit once per batch of rows, not once per film, so the caller owns the
transaction. The router now commits immediately after calling, which leaves its behaviour
identical.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_item import CollectionItem
from src.models.movie import Movie, MovieCredit
from src.models.watch_log import WatchLog
from src.services.movie_metadata import credit_rows, movie_metadata_values


async def apply_identification(
    db: AsyncSession,
    source: Movie,
    tmdb_movie: object,
) -> Movie:
    """Write TMDB's metadata onto ``source``, merging into an existing row if one exists.

    Returns the row that now holds the film — which is **not always ``source``**. If the
    collection already has a row for this TMDB id, the two are merged into it and
    ``source`` is deleted, because ``movies.tmdb_id`` is unique and two rows would split
    one film's discs and watches between them.

    Does not commit.
    """
    from src.tmdb.models import Movie as TmdbMovie

    if not isinstance(tmdb_movie, TmdbMovie):  # defensive boundary for dependency overrides
        raise TypeError("Expected a validated TMDB movie")

    existing = await db.scalar(
        select(Movie).where(
            Movie.tmdb_id == tmdb_movie.id,
            Movie.id != source.id,
        )
    )
    target = existing or source
    values = movie_metadata_values(tmdb_movie)
    for name, value in values.items():
        setattr(target, name, value)

    await db.execute(delete(MovieCredit).where(MovieCredit.movie_id == target.id))
    for row in credit_rows(target.id, tmdb_movie):
        db.add(
            MovieCredit(
                id=uuid.UUID(row[0]),
                movie_id=target.id,
                person_name=row[2],
                tmdb_person_id=row[3],
                role=row[4],
                character_name=row[5],
                display_order=row[6],
            )
        )

    if existing is not None:
        await db.execute(
            update(CollectionItem)
            .where(CollectionItem.movie_id == source.id)
            .values(movie_id=target.id)
        )
        # Watch history moves with the discs. Without this the ``RESTRICT`` on
        # ``watch_log.movie_id`` refuses the delete below and identification fails for
        # any film someone had already logged a watch against — which is precisely the
        # film they cared enough about to watch. **Batch S8 makes that the common case
        # rather than the rare one:** it writes ~1,530 watches and then identifies 396
        # films, so every one of those identifications now has history behind it.
        await db.execute(
            update(WatchLog).where(WatchLog.movie_id == source.id).values(movie_id=target.id)
        )
        await db.execute(delete(MovieCredit).where(MovieCredit.movie_id == source.id))
        await db.delete(source)

    await db.flush()
    return target
