"""Film rows left with nothing on them — Batch X10 (CT46-04, `DECISIONS.md` #280).

The 18 Sep sheet refresh minted new rows for titles it could not tell apart (two *Dunkirk*s,
two *Titanic*s) and binned the discs on the old ones, leaving 9 rows that hold only a binned
copy; binning has left 3 more like them since. Such a row shows nowhere: not on the shelf, not
on "Still to identify", which asks for an owned copy. It is still a film to every query that
counts rows.

**A leftover** is a live film row with no TMDB id of either kind, at least one copy and every
copy binned, and no watch, want or movie-night suggestion. Anything a person did with the
film keeps it.

**Removing one puts it in the Trash**, as deleting a film does, audited as the person who
said so; restoring it from the Trash undoes it. Nothing is deleted outright. Its binned copies
stay in the Trash beside it: they are the refresh's discards, whose discs now sit on the new
rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.movie_night import MovieNightSuggestion
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.services.audit import record_action

MOVIES_TABLE = "movies"
NOTE = "A film row with nothing left on it: every copy binned, no watch or want (X10)."


@dataclass(frozen=True)
class Leftover:
    """One row as the dry run lists it."""

    movie_id: uuid.UUID
    title: str
    binned_copies: int
    last_binned_utc: datetime | None


def _is_leftover() -> list[ColumnElement[bool]]:
    """The rule, as SQL, so the listing and the removal ask the same question."""
    return [
        Movie.deleted_at.is_(None),
        Movie.tmdb_id.is_(None),
        Movie.tmdb_tv_id.is_(None),
        exists(select(CollectionItem.id).where(CollectionItem.movie_id == Movie.id)),
        ~exists(
            select(CollectionItem.id).where(
                CollectionItem.movie_id == Movie.id, CollectionItem.deleted_at.is_(None)
            )
        ),
        ~exists(select(WatchLog.id).where(WatchLog.movie_id == Movie.id)),
        ~exists(select(WantedItem.id).where(WantedItem.movie_id == Movie.id)),
        ~exists(select(MovieNightSuggestion.id).where(MovieNightSuggestion.movie_id == Movie.id)),
    ]


async def leftover_films(db: AsyncSession) -> list[Leftover]:
    """Every leftover row, by title."""
    binned = (
        select(
            CollectionItem.movie_id,
            func.count(CollectionItem.id).label("n"),
            func.max(CollectionItem.deleted_at).label("last"),
        )
        .group_by(CollectionItem.movie_id)
        .subquery()
    )
    rows = await db.execute(
        select(Movie.id, Movie.title, binned.c.n, binned.c.last)
        .join(binned, binned.c.movie_id == Movie.id)
        .where(*_is_leftover())
        .order_by(Movie.title, Movie.id)
    )
    return [Leftover(movie_id, title, int(n), last) for movie_id, title, n, last in rows.all()]


async def remove(db: AsyncSession, movie_id: uuid.UUID, *, by: uuid.UUID) -> bool:
    """Put one leftover in the Trash, audited. False, and nothing written, when it is no
    longer a leftover: a copy restored or a watch logged since the listing keeps it."""
    movie = await db.scalar(select(Movie).where(Movie.id == movie_id, *_is_leftover()))
    if movie is None:
        return False
    movie.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    record_action(
        db,
        user_id=by,
        action_type="delete",
        target_table=MOVIES_TABLE,
        target_id=movie.id,
        changes={"title": movie.title, "note": NOTE},
    )
    await db.flush()
    return True
