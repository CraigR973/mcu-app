"""The Identify films page — Batch T9.

**Where Craig settles the films identification would not.** Every live film TMDB has not
matched that has a disc on the shelf waits here unless it has been set aside or skipped,
whether or not a run has looked at it yet. The dry run's candidates and reason come with
the films it looked at; any film can be searched again.

**Each choice is one tap:** this film, a film found by searching again, a TV series, not a
film, or skip. A choice that would merge into a film the collection already has is shown
with both films and needs saying so. Every identification can be undone from the recent
list, merges included.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem, owned_copy
from src.models.identify import IdentifyLookup, IdentifyRun
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.watch_log import WatchLog
from src.services.identification import (
    MOVIES_TABLE,
    Identified,
    IdentifyError,
    identify_film,
    is_undone,
    set_aside,
)
from src.services.identify.matcher import Identifier, offer_notes
from src.services.identify.plan import FORMAT_NAMES
from src.services.identify.titles import parse_title
from src.tmdb.client import TMDBClient


class QueueError(ValueError):
    """The film cannot take that decision."""


@dataclass(frozen=True)
class FilmInCollection:
    """A film the collection already holds under a TMDB id, as a merge would show it."""

    movie_id: uuid.UUID
    title: str
    year: int | None
    discs: int
    watches: int


@dataclass(frozen=True)
class DiscLine:
    format_code: str | None
    grouping: str | None
    location: str | None

    def label(self) -> str:
        parts = [FORMAT_NAMES.get(self.format_code or "", self.format_code or "No format")]
        parts += [part for part in (self.grouping, self.location) if part]
        return " · ".join(parts)


@dataclass
class QueueEntry:
    movie: Movie
    lookup: IdentifyLookup | None
    discs: list[DiscLine]
    watches: int
    candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Overview:
    unidentified: int
    waiting: int
    set_aside_tv: int
    set_aside_not_film: int
    skipped: int
    identified: int
    latest_run: IdentifyRun | None


def _unidentified_on_shelf() -> Any:
    on_shelf = select(CollectionItem.id).where(CollectionItem.movie_id == Movie.id, owned_copy())
    # Batch Y3: a series identified (from its page) has left the queue, as a film has.
    return (
        Movie.tmdb_id.is_(None),
        Movie.tmdb_tv_id.is_(None),
        Movie.deleted_at.is_(None),
        on_shelf.exists(),
    )


async def overview(db: AsyncSession) -> Overview:
    """How many films wait, and what has become of the rest."""
    conditions = _unidentified_on_shelf()
    row = (
        await db.execute(
            select(
                func.count(Movie.id),
                func.count(Movie.id).filter(
                    or_(IdentifyLookup.id.is_(None), IdentifyLookup.status == "needs_you")
                ),
                func.count(Movie.id).filter(IdentifyLookup.set_aside_as == "tv"),
                func.count(Movie.id).filter(IdentifyLookup.set_aside_as == "not_film"),
                func.count(Movie.id).filter(IdentifyLookup.status == "skipped"),
            )
            .select_from(Movie)
            .outerjoin(IdentifyLookup, IdentifyLookup.movie_id == Movie.id)
            .where(*conditions)
        )
    ).one()
    identified = await db.scalar(
        select(func.count())
        .select_from(IdentifyLookup)
        .where(IdentifyLookup.status == "identified")
    )
    latest = await db.scalar(select(IdentifyRun).order_by(IdentifyRun.started_utc.desc()).limit(1))
    unidentified, waiting, tv, not_film, skipped = (int(v) for v in row)
    return Overview(unidentified, waiting, tv, not_film, skipped, int(identified or 0), latest)


async def in_collection(db: AsyncSession, tmdb_ids: list[int]) -> dict[int, FilmInCollection]:
    """The collection's live films holding these TMDB ids, with their discs and watches."""
    if not tmdb_ids:
        return {}
    discs = (
        select(func.count(CollectionItem.id))
        .where(CollectionItem.movie_id == Movie.id, owned_copy())
        .scalar_subquery()
    )
    watches = select(func.count(WatchLog.id)).where(WatchLog.movie_id == Movie.id).scalar_subquery()
    rows = await db.execute(
        select(Movie.tmdb_id, Movie.id, Movie.title, Movie.year, discs, watches).where(
            Movie.tmdb_id.in_(tmdb_ids), Movie.deleted_at.is_(None)
        )
    )
    return {
        int(tmdb_id): FilmInCollection(movie_id, title, year, int(d or 0), int(w or 0))
        for tmdb_id, movie_id, title, year, d, w in rows
    }


async def queue(db: AsyncSession, *, limit: int) -> tuple[list[QueueEntry], int]:
    """Films waiting for Craig: those a run looked at first, then the rest, by title."""
    conditions = _unidentified_on_shelf()
    waiting = or_(IdentifyLookup.id.is_(None), IdentifyLookup.status == "needs_you")
    base = (
        select(Movie, IdentifyLookup)
        .outerjoin(IdentifyLookup, IdentifyLookup.movie_id == Movie.id)
        .where(*conditions, waiting)
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(IdentifyLookup.id.is_(None), Movie.title, Movie.id).limit(limit)
        )
    ).all()
    ids = [movie.id for movie, _ in rows]
    discs: dict[uuid.UUID, list[DiscLine]] = {movie_id: [] for movie_id in ids}
    watches: dict[uuid.UUID, int] = {}
    if ids:
        items = await db.execute(
            select(
                CollectionItem.movie_id,
                CollectionItem.formats,
                CollectionItem.sub_category,
                CollectionItem.location,
            )
            .where(CollectionItem.movie_id.in_(ids), owned_copy())
            .order_by(CollectionItem.movie_id, CollectionItem.id)
        )
        for movie_id, formats, grouping, location in items:
            best = next((code for code in FORMAT_NAMES if code in (formats or [])), None)
            discs[movie_id].append(DiscLine(best, grouping, location))
        counted = await db.execute(
            select(WatchLog.movie_id, func.count())
            .where(WatchLog.movie_id.in_(ids))
            .group_by(WatchLog.movie_id)
        )
        watches = {movie_id: int(count) for movie_id, count in counted}
    entries = [
        QueueEntry(
            movie=movie,
            lookup=lookup,
            discs=discs.get(movie.id, []),
            watches=watches.get(movie.id, 0),
            candidates=list(lookup.candidates) if lookup is not None else [],
        )
        for movie, lookup in rows
    ]
    return entries, int(total or 0)


async def _waiting_film(db: AsyncSession, movie_id: uuid.UUID) -> Movie:
    movie = await db.get(Movie, movie_id)
    if movie is None or movie.deleted_at is not None:
        raise LookupError("No such film.")
    if movie.tmdb_id is not None:
        raise QueueError("This film has already been identified.")
    if movie.tmdb_tv_id is not None:
        raise QueueError("This has already been identified as a TV series.")
    return movie


#: Films the Identify films page offers for a typed title.
SEARCH_OFFERS = 8


async def search_again(tmdb: TMDBClient, query: str) -> list[dict[str, Any]]:
    """TMDB's films for a corrected title, in the shape the page offers them.

    X9 (CT46-01): ranked by T9's rule, with each film's votes and the notes the dry run gives
    (the year, another title it matched by), where ``MatchingEngine`` ranked them with no
    votes and no notes.
    """
    parsed = parse_title(query)
    ranked = await Identifier(tmdb).candidates_for(parsed)
    return [
        {
            "tmdb_id": c.tmdb_id,
            "title": c.title,
            "year": c.year,
            "poster_path": c.poster_path,
            "overview": c.overview[:600],
            "votes": c.vote_count,
            "origin": "search",
            "notes": offer_notes(parsed, c, f),
        }
        for c, f in ranked[:SEARCH_OFFERS]
    ]


async def pick(
    db: AsyncSession,
    movie_id: uuid.UUID,
    tmdb_id: int,
    tmdb: TMDBClient,
    *,
    by: uuid.UUID,
    merge: bool,
    searched: bool,
) -> Identified:
    """Craig's choice of film. A merge needs ``merge`` set: the page shows both films first."""
    movie = await _waiting_film(db, movie_id)
    record = await tmdb.get_movie_full(tmdb_id)
    identified = await identify_film(
        db,
        movie,
        record,
        by=by,
        how="searched" if searched else "picked",
        evidence=["Chosen by Craig."],
        allow_merge=merge,
    )
    await db.commit()
    return identified


async def mark(db: AsyncSession, movie_id: uuid.UUID, kind: str, *, by: uuid.UUID) -> None:
    """A TV series, or not a film: out of the queue, and kept as it is."""
    movie = await _waiting_film(db, movie_id)
    note = "A TV series, by Craig." if kind == "tv" else "Not a film, by Craig."
    try:
        await set_aside(db, movie, kind, by=by, note=note)
    except IdentifyError as exc:
        raise QueueError(str(exc)) from exc
    await db.commit()


async def skip(db: AsyncSession, movie_id: uuid.UUID, *, by: uuid.UUID) -> None:
    """Leave this film unidentified and out of the queue."""
    movie = await _waiting_film(db, movie_id)
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == movie.id))
    if lookup is None:
        lookup = IdentifyLookup(id=uuid.uuid4(), movie_id=movie.id, candidates=[])
        db.add(lookup)
    lookup.status = "skipped"
    lookup.set_aside_as = None
    lookup.note = "Skipped by Craig."
    lookup.decided_by = by
    lookup.decided_utc = utcnow()
    await db.commit()


async def put_back(db: AsyncSession, movie_id: uuid.UUID, *, by: uuid.UUID) -> None:
    """Return a set-aside or skipped film to the queue, as a film again."""
    movie = await _waiting_film(db, movie_id)
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == movie.id))
    if lookup is None or lookup.status not in ("set_aside", "skipped"):
        raise QueueError("This film is not set aside or skipped.")
    movie.is_tv = False
    movie.media_type = "film"
    lookup.status = "needs_you"
    lookup.set_aside_as = None
    lookup.note = "Put back by Craig."
    lookup.decided_by = by
    lookup.decided_utc = utcnow()
    await db.commit()


@dataclass(frozen=True)
class RecentIdentification:
    action_id: uuid.UUID
    when: datetime
    by: str | None
    movie_id: uuid.UUID
    replaced: str
    title: str
    year: int | None
    how: str
    merged: bool
    undone: bool


async def recent(db: AsyncSession, *, limit: int) -> list[RecentIdentification]:
    """The latest identifications, newest first, and whether each has been undone."""
    rows = await db.execute(
        select(AdminAction, Profile.display_name)
        .outerjoin(Profile, Profile.id == AdminAction.user_id)
        .where(
            AdminAction.target_table == MOVIES_TABLE,
            AdminAction.changes["kind"].astext == "identify",
        )
        .order_by(AdminAction.created_at.desc(), AdminAction.id)
        .limit(limit)
    )
    found: list[RecentIdentification] = []
    for action, name in rows:
        changes = action.changes or {}
        title = changes.get("title") or {}
        found.append(
            RecentIdentification(
                action_id=action.id,
                when=action.created_at,
                by=name,
                movie_id=uuid.UUID(action.target_id),
                replaced=str(title.get("from") or ""),
                title=str(title.get("to") or ""),
                year=changes.get("year"),
                how=str(changes.get("how") or ""),
                merged="merge" in changes,
                undone=await is_undone(db, action.id),
            )
        )
    return found
