"""Settle many identification doubts from one agreed plan — `DECISIONS.md` #278.

On 17 Oct Mark asked for the open re-check doubts to be settled "to what you think they are",
and Craig agreed a plan with five answers and three exceptions of his own. Each entry goes
through the same service the app's buttons use, so each is audited as Craig, listed under
Recently identified and undone there:

- ``keep``: It's right (:func:`keep`).
- ``correct``: the film is another one, or a TMDB series (:func:`correct`, or
  :func:`identify_film` with the series' record, which settles every doubt on the film as
  Correct match does).
- ``move``: Move only this copy (:func:`move_copy`).
- ``bin``: the copy goes to the Trash, as Delete on a copy does; restored from the Trash.

An entry is skipped, never forced, when its doubt is no longer open, its film is no longer
the TMDB id the plan was made against, or the copy it names is gone: someone has decided it
since. A correction that would merge into a film the collection already has is refused, as
the app refuses it without a merge being asked for.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.admin_action import COLLECTION_ITEMS_TABLE
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.services.audit import item_snapshot, record_action
from src.services.identification import identify_film
from src.services.identify.doubts import correct, keep
from src.services.identify.move_copy import move_copy
from src.tmdb.client import TMDBClient
from src.tmdb.models import Movie as TmdbMovie
from src.tmdb.models import TvShow

#: What an audit row of a series correction says of where it came from.
PLAN_EVIDENCE = "Settled from the agreed plan of 17 Oct, at Craig's and Mark's word."


class PlanEntry(BaseModel):
    doubt: uuid.UUID
    #: The film's TMDB id when the plan was made. A film identified as another since is skipped.
    expect: int = Field(gt=0)
    action: Literal["keep", "correct", "move", "bin"]
    tmdbId: int | None = Field(default=None, gt=0)
    media: Literal["film", "tv"] = "film"
    #: For the report only.
    title: str = ""

    @model_validator(mode="after")
    def _target_when_needed(self) -> PlanEntry:
        if (self.action in ("correct", "move")) != (self.tmdbId is not None):
            raise ValueError("correct and move name a TMDB id; keep and bin do not")
        return self


@dataclass
class Checked:
    entry: PlanEntry
    #: Why it is skipped, or None when it can be applied.
    skip: str | None
    copy: CollectionItem | None = None


async def check(db: AsyncSession, entry: PlanEntry) -> Checked:
    """Whether the plan still holds for this doubt. Reads only."""
    doubt = await db.get(IdentifyDoubt, entry.doubt)
    if doubt is None:
        return Checked(entry, "no such doubt")
    if doubt.status != "open":
        return Checked(entry, f"already settled ({doubt.status})")
    movie = await db.get(Movie, doubt.movie_id)
    if movie is None or movie.deleted_at is not None:
        return Checked(entry, "its film is gone")
    if movie.tmdb_id != entry.expect:
        return Checked(entry, "its film was identified as another since the plan")
    copy: CollectionItem | None = None
    if entry.action in ("move", "bin"):
        if doubt.collection_item_id is None:
            return Checked(entry, "the doubt names no copy")
        copy = await db.get(CollectionItem, doubt.collection_item_id)
        if copy is None or copy.deleted_at is not None or copy.movie_id != movie.id:
            return Checked(entry, "the copy it names has moved or gone")
    return Checked(entry, None, copy)


async def apply(db: AsyncSession, checked: Checked, tmdb: TMDBClient, *, by: uuid.UUID) -> str:
    """Settle one doubt as planned. Does not commit. Returns what was done, in a few words."""
    entry = checked.entry
    if entry.action == "keep":
        await keep(db, entry.doubt, by=by)
        return "kept"
    if entry.action == "bin":
        assert checked.copy is not None
        checked.copy.deleted_at = utcnow()
        record_action(
            db,
            user_id=by,
            action_type="delete",
            target_table=COLLECTION_ITEMS_TABLE,
            target_id=checked.copy.id,
            changes=item_snapshot(checked.copy),
        )
        await db.flush()
        return "copy binned"
    assert entry.tmdbId is not None
    record: TmdbMovie | TvShow = (
        await tmdb.get_tv_full(entry.tmdbId)
        if entry.media == "tv"
        else await tmdb.get_movie_full(entry.tmdbId)
    )
    if entry.action == "move":
        assert checked.copy is not None
        moved = await move_copy(db, checked.copy.id, record, by=by, doubt_id=entry.doubt)
        return f"copy moved to {moved.film.title} ({moved.film.year})"
    if entry.media == "film":
        identified = await correct(
            db, entry.doubt, entry.tmdbId, tmdb, by=by, merge=False, searched=False
        )
    else:
        doubt = await db.get(IdentifyDoubt, entry.doubt)
        movie = await db.get(Movie, doubt.movie_id) if doubt is not None else None
        assert movie is not None
        identified = await identify_film(
            db, movie, record, by=by, how="picked", evidence=[PLAN_EVIDENCE], allow_merge=False
        )
    return f"corrected to {identified.film.title} ({identified.film.year})"


async def run_entry(
    db: AsyncSession, entry: PlanEntry, tmdb: TMDBClient, *, by: uuid.UUID
) -> tuple[str, str]:
    """Check and settle one entry in its own transaction: ("done"|"skipped"|"failed", why)."""
    checked = await check(db, entry)
    if checked.skip is not None:
        await db.rollback()
        return "skipped", checked.skip
    try:
        done = await apply(db, checked, tmdb, by=by)
        await db.commit()
    except Exception as exc:  # one refusal must not stop the other 377
        await db.rollback()
        return "failed", f"{type(exc).__name__}: {exc}"
    return "done", done
