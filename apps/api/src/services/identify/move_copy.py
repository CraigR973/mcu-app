"""Moving one copy to another film — Batch X9 (CT46-01).

**One film row can hold a right copy and a wrong one.** 3 of the 30 wrong copies found on 12
Oct share their row with a copy that is the film: the *French Connection II* row holds both
discs of *The French Connection*, BBC's *Life* sits with the 2017 film, the 1979 *Tinker
Tailor* with the 2011 one. Identifying the row again would carry the right copy off with the
wrong one, so a copy can be moved on its own.

The copy goes to the collection's film of that TMDB id, or to a new film made from TMDB's
record when the collection has none. Since Batch Y5 (#277) it can go to a series the same way,
by its series id: BBC's *Life*, the 1979 *Tinker Tailor* and the 2019 *Name of the Rose* are
series discs on the same-named films. Watches stay where they are: they are of a film, not a
disc. A doubt about this copy is settled by the move. The move is audited on the copy and
undone from Identify films' recent list: the copy goes back, the doubt opens again, and a
film the move made is removed if nothing else has come to point at it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.admin_action import COLLECTION_ITEMS_TABLE, AdminAction
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie, MovieCredit
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.services.audit import record_action
from src.services.film_rows import held_row_for, make_row
from src.services.identify.doubts import reaccept_disagreeing_page
from src.tmdb.models import Movie as TmdbMovie
from src.tmdb.models import TvShow

MOVE_KIND = "move_copy"


class MoveError(ValueError):
    """The copy cannot be moved there, or the move cannot be undone."""


@dataclass
class Moved:
    film: Movie
    created: bool
    audit: AdminAction


def _film_json(film: Movie) -> dict[str, Any]:
    return {
        "movieId": str(film.id),
        "title": film.title,
        "year": film.year,
        "tmdbId": film.tmdb_id,
        "tmdbTvId": film.tmdb_tv_id,
    }


async def move_copy(
    db: AsyncSession,
    item_id: uuid.UUID,
    record: TmdbMovie | TvShow,
    *,
    by: uuid.UUID | None,
    doubt_id: uuid.UUID | None = None,
) -> Moved:
    """Move one copy to the film or, since Batch Y5, the series ``record`` is, making that
    row if need be. Does not commit."""
    item = await db.get(CollectionItem, item_id)
    if item is None or item.deleted_at is not None:
        raise LookupError("No such copy.")
    source = await db.get(Movie, item.movie_id)
    if source is None:
        raise LookupError("No such copy.")
    series = isinstance(record, TvShow)
    if (source.tmdb_tv_id if series else source.tmdb_id) == record.id:
        raise MoveError(f"This copy is already on that {'series' if series else 'film'}.")
    doubt: IdentifyDoubt | None = None
    if doubt_id is not None:
        doubt = await db.get(IdentifyDoubt, doubt_id)
        if doubt is None or doubt.movie_id != source.id:
            raise LookupError("No such doubt about this copy's film.")
        if doubt.status != "open":
            raise MoveError("This doubt has already been settled.")

    target = await held_row_for(db, record)
    if target is not None and target.deleted_at is not None:
        raise MoveError(f"'{target.title}' is in the Trash. Restore it before moving a copy to it.")
    created = target is None
    if target is None:
        target = await make_row(db, record)

    about = [IdentifyDoubt.collection_item_id == item.id]
    if doubt is not None:
        about.append(IdentifyDoubt.id == doubt.id)
    settles = list(
        (
            await db.scalars(
                select(IdentifyDoubt).where(IdentifyDoubt.status == "open", or_(*about))
            )
        ).all()
    )
    item.movie_id = target.id
    audit = record_action(
        db,
        user_id=by,
        action_type="update",
        target_table=COLLECTION_ITEMS_TABLE,
        target_id=item.id,
        changes={
            "kind": MOVE_KIND,
            "from": _film_json(source),
            "to": _film_json(target),
            "created": created,
            "doubts": [str(settled.id) for settled in settles],
        },
    )
    await db.flush()
    now = utcnow()
    for settled in settles:
        settled.status = "moved"
        settled.decided_by = by
        settled.decided_utc = now
        settled.decided_action_id = audit.id
        await reaccept_disagreeing_page(db, settled, by=by)
    await db.flush()
    return Moved(film=target, created=created, audit=audit)


async def is_move_undone(db: AsyncSession, action_id: uuid.UUID) -> bool:
    found = await db.scalar(
        select(AdminAction.id).where(
            AdminAction.target_table == COLLECTION_ITEMS_TABLE,
            AdminAction.changes["undoes"].astext == str(action_id),
        )
    )
    return found is not None


async def _only_the_move_points_at(db: AsyncSession, film_id: uuid.UUID) -> bool:
    """Nothing but the moved copy came to point at a film the move made."""
    for model in (CollectionItem, WatchLog, WantedItem):
        if await db.scalar(select(exists().where(model.movie_id == film_id))):
            return False
    return True


async def undo_move(db: AsyncSession, action_id: uuid.UUID, *, by: uuid.UUID | None) -> Movie:
    """Put the copy back on the film it was moved from. Does not commit."""
    action = await db.get(AdminAction, action_id)
    changes = action.changes if action is not None else None
    if action is None or not changes or changes.get("kind") != MOVE_KIND:
        raise MoveError("That is not a copy moved to another film.")
    if await is_move_undone(db, action_id):
        raise MoveError("That move has already been undone.")
    item = await db.get(CollectionItem, uuid.UUID(action.target_id))
    moved_to = uuid.UUID(changes["to"]["movieId"])
    if item is None or item.movie_id != moved_to:
        raise MoveError("The copy has moved since. Undo that first.")
    source = await db.get(Movie, uuid.UUID(changes["from"]["movieId"]))
    if source is None or source.deleted_at is not None:
        raise MoveError("The film the copy came from is gone. Restore it first.")

    item.movie_id = source.id
    await db.flush()
    removed = False
    if changes.get("created") and await _only_the_move_points_at(db, moved_to):
        await db.execute(delete(MovieCredit).where(MovieCredit.movie_id == moved_to))
        await db.execute(delete(Movie).where(Movie.id == moved_to))
        removed = True
    await db.execute(
        update(IdentifyDoubt)
        .where(IdentifyDoubt.decided_action_id == action_id)
        .values(status="open", decided_by=None, decided_utc=None, decided_action_id=None)
    )
    record_action(
        db,
        user_id=by,
        action_type="update",
        target_table=COLLECTION_ITEMS_TABLE,
        target_id=item.id,
        changes={
            "kind": "undo_move_copy",
            "undoes": str(action_id),
            "back": _film_json(source),
            "removed": changes["to"] if removed else None,
        },
    )
    await db.flush()
    return source
