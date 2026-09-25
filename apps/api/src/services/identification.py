"""Applying a TMDB identification to a film row — extracted in Batch S8, audited in T9.

This was `routers/movies.py::_apply_identification`, reachable only through
`POST /movies/{id}/identify`. S8 needs exactly the same operation from a script: its
import matches **396 distinct films** that the April import never identified, and filling
in `tmdb_id`, year, poster, runtime and cast is half of what makes that import worth
running (`DECISIONS.md` #160).

**The only behavioural change is who commits.** The router committed inside; a batch
import must commit once per batch of rows, not once per film, so the caller owns the
transaction. The router now commits immediately after calling, which leaves its behaviour
identical.

**Batch T9 adds three things, because it rewrites 357 films' identities at once:**

- **A merge moves everything that points at the film**, not only its discs and watches.
  Wanted rows and movie-night suggestions are ``RESTRICT``, so a merge of a film anyone had
  suggested failed outright; votes are ``CASCADE``, so they vanished; calendar entries,
  barcode lookups and deals are ``SET NULL``, so they came loose. Fourteen of the unmatched
  films had movie-night suggestions on 25 Sep. A row the target already has a copy of (the
  same person's vote on the same film in the same night) is dropped, and recorded.
- **:func:`identify_film` audits every identification** with the title it replaced and
  enough of the row's old state to undo it, and keeps that title as an alias, so the
  collection refresh still finds the film by the spreadsheet's spelling (#198).
- **:func:`undo_identification` reverses one**, merges included.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.barcode import BarcodeLookup
from src.models.collection_item import CollectionItem
from src.models.deal import Deal
from src.models.identify import IdentifyLookup, MovieTitleAlias
from src.models.movie import Movie, MovieCredit
from src.models.movie_night import MovieNightSuggestion, MovieNightVote
from src.models.release_calendar import ReleaseCalendarEntry
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.services.audit import record_action
from src.services.movie_metadata import credit_rows, movie_metadata_values

MOVIES_TABLE = "movies"

#: The columns a snapshot keeps, so an undo can put a row back as it was. Everything an
#: identification writes, plus what a merge would otherwise lose with the row.
SNAPSHOT_FIELDS = (
    "tmdb_id",
    "imdb_id",
    "title",
    "original_title",
    "year",
    "runtime_minutes",
    "overview",
    "tagline",
    "poster_path",
    "backdrop_path",
    "tmdb_rating",
    "tmdb_vote_count",
    "genres",
    "genre_ids",
    "top_cast_summary",
    "trailer_key",
    "letterboxd_slug",
    "media_type",
    "is_tv",
    "last_tmdb_sync_utc",
)
_DECIMAL_FIELDS = {"tmdb_rating"}
_DATETIME_FIELDS = {"last_tmdb_sync_utc"}


class IdentifyError(ValueError):
    """The identification cannot be made, or undone, as asked."""


class MergeNeeded(IdentifyError):
    """The collection already has this film. Merging needs someone to say so."""

    def __init__(self, existing: Movie) -> None:
        super().__init__(
            f"The collection already has this film as '{existing.title}'. Choosing it merges "
            "the two."
        )
        self.existing = existing


# ---------------------------------------------------------------------------
# Snapshots, for undo
# ---------------------------------------------------------------------------


def _jsonable(name: str, value: Any) -> Any:
    if value is None:
        return None
    if name in _DECIMAL_FIELDS or isinstance(value, Decimal):
        return str(value)
    if name in _DATETIME_FIELDS or isinstance(value, datetime):
        return value.isoformat()
    return value


def _from_json(name: str, value: Any) -> Any:
    if value is None:
        return None
    if name in _DECIMAL_FIELDS:
        return Decimal(str(value))
    if name in _DATETIME_FIELDS:
        return datetime.fromisoformat(str(value))
    return value


def snapshot(movie: Movie) -> dict[str, Any]:
    """The row's identity and metadata, in a form the audit log can hold."""
    return {name: _jsonable(name, getattr(movie, name)) for name in SNAPSHOT_FIELDS}


def _restore(movie: Movie, values: dict[str, Any]) -> None:
    for name in SNAPSHOT_FIELDS:
        if name in values:
            setattr(movie, name, _from_json(name, values[name]))


async def _credits_of(db: AsyncSession, movie_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = await db.scalars(select(MovieCredit).where(MovieCredit.movie_id == movie_id))
    return [
        {
            "person_name": c.person_name,
            "tmdb_person_id": c.tmdb_person_id,
            "role": c.role,
            "character_name": c.character_name,
            "display_order": c.display_order,
        }
        for c in rows
    ]


# ---------------------------------------------------------------------------
# Merging: everything that points at a film moves with it
# ---------------------------------------------------------------------------


@dataclass
class Merge:
    """What a merge moved from the merged-away row, and what it dropped as a duplicate."""

    source_id: uuid.UUID
    source: dict[str, Any]
    moved: dict[str, list[str]] = field(default_factory=dict)
    dropped: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "sourceId": str(self.source_id),
            "source": self.source,
            "moved": self.moved,
            "dropped": self.dropped,
        }


def _ids(rows: Any) -> list[str]:
    return [str(row) for row in rows]


async def move_references(db: AsyncSession, source_id: uuid.UUID, target_id: uuid.UUID) -> Merge:
    """Point everything at ``target_id`` that pointed at ``source_id``. Does not commit.

    Rows move in place, so their ids survive and an undo can move exactly them back.
    """
    source = await db.get(Movie, source_id)
    merge = Merge(source_id=source_id, source=snapshot(source) if source else {})

    async def move(model: Any, *where: Any) -> list[str]:
        result = await db.execute(
            update(model)
            .where(model.movie_id == source_id, *where)
            .values(movie_id=target_id)
            .returning(model.id)
        )
        return _ids(result.scalars())

    merge.moved["collection_items"] = await move(CollectionItem)
    merge.moved["watch_log"] = await move(WatchLog)

    # Wanted: one live row per film. If both have one, the merged-away row's is binned.
    target_wants = await db.scalar(
        select(WantedItem.id).where(
            WantedItem.movie_id == target_id, WantedItem.deleted_at.is_(None)
        )
    )
    if target_wants is not None:
        binned = await db.execute(
            update(WantedItem)
            .where(WantedItem.movie_id == source_id, WantedItem.deleted_at.is_(None))
            .values(deleted_at=utcnow())
            .returning(WantedItem.id)
        )
        merge.dropped["wanted_list"] = [{"id": wanted_id} for wanted_id in _ids(binned.scalars())]
    merge.moved["wanted_list"] = await move(WantedItem)

    # Votes: one per person per film per night. The target's own vote stands.
    theirs = aliased(MovieNightVote)
    duplicate = exists().where(
        theirs.session_id == MovieNightVote.session_id,
        theirs.user_id == MovieNightVote.user_id,
        theirs.movie_id == target_id,
    )
    dupes = list(
        (
            await db.scalars(
                select(MovieNightVote).where(MovieNightVote.movie_id == source_id, duplicate)
            )
        ).all()
    )
    merge.dropped["movie_night_votes"] = [
        {
            "id": str(v.id),
            "session_id": str(v.session_id),
            "user_id": str(v.user_id),
            "suggestion_id": str(v.suggestion_id) if v.suggestion_id else None,
            "liked": v.liked,
        }
        for v in dupes
    ]
    if dupes:
        await db.execute(delete(MovieNightVote).where(MovieNightVote.id.in_([v.id for v in dupes])))
    merge.moved["movie_night_votes"] = await move(MovieNightVote)

    # Suggestions: one per film per night. If the target was suggested in the same night,
    # the merged-away suggestion's votes join it and the suggestion itself goes.
    suggestions = list(
        (
            await db.scalars(
                select(MovieNightSuggestion).where(MovieNightSuggestion.movie_id == source_id)
            )
        ).all()
    )
    repointed: list[str] = []
    dropped_suggestions: list[dict[str, Any]] = []
    for suggestion in suggestions:
        twin = await db.scalar(
            select(MovieNightSuggestion.id).where(
                MovieNightSuggestion.session_id == suggestion.session_id,
                MovieNightSuggestion.movie_id == target_id,
            )
        )
        if twin is None:
            continue
        result = await db.execute(
            update(MovieNightVote)
            .where(MovieNightVote.suggestion_id == suggestion.id)
            .values(suggestion_id=twin)
            .returning(MovieNightVote.id)
        )
        repointed += _ids(result.scalars())
        dropped_suggestions.append(
            {
                "id": str(suggestion.id),
                "session_id": str(suggestion.session_id),
                "title": suggestion.title,
                "into": str(twin),
            }
        )
        await db.execute(
            delete(MovieNightSuggestion).where(MovieNightSuggestion.id == suggestion.id)
        )
    merge.dropped["movie_night_suggestions"] = dropped_suggestions
    merge.moved["votes_repointed"] = repointed
    merge.moved["movie_night_suggestions"] = await move(MovieNightSuggestion)

    merge.moved["release_calendar"] = await move(ReleaseCalendarEntry)
    merge.moved["barcode_lookups"] = await move(BarcodeLookup)
    merge.moved["deals"] = await move(Deal)

    # Old titles go with the film, bar any the target already answers to.
    target_aliases = select(MovieTitleAlias.title).where(MovieTitleAlias.movie_id == target_id)
    await db.execute(
        delete(MovieTitleAlias).where(
            MovieTitleAlias.movie_id == source_id, MovieTitleAlias.title.in_(target_aliases)
        )
    )
    merge.moved["movie_title_aliases"] = await move(MovieTitleAlias)
    return merge


# ---------------------------------------------------------------------------
# Identifying
# ---------------------------------------------------------------------------


async def _apply(db: AsyncSession, source: Movie, tmdb_movie: object) -> tuple[Movie, Merge | None]:
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
    merge: Merge | None = None
    if existing is not None:
        # Watch history moves with the discs, and so does everything else that points at
        # the film. Without it the ``RESTRICT`` on ``watch_log.movie_id`` refuses the delete
        # below for any film someone had logged a watch against — which is precisely the
        # film they cared enough about to watch. **Batch S8 makes that the common case
        # rather than the rare one:** it writes ~1,530 watches and then identifies 396
        # films, so every one of those identifications now has history behind it.
        merge = await move_references(db, source.id, existing.id)

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
        await db.execute(delete(MovieCredit).where(MovieCredit.movie_id == source.id))
        await db.delete(source)

    await db.flush()
    return target, merge


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
    target, _merge = await _apply(db, source, tmdb_movie)
    return target


@dataclass
class Identified:
    film: Movie
    merged: bool
    audit: AdminAction


async def _lookup_snapshot(db: AsyncSession, movie_id: uuid.UUID) -> dict[str, Any] | None:
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == movie_id))
    if lookup is None:
        return None
    return {
        "status": lookup.status,
        "note": lookup.note,
        "candidates": lookup.candidates,
        "proposed_tmdb_id": lookup.proposed_tmdb_id,
    }


async def identify_film(
    db: AsyncSession,
    source: Movie,
    tmdb_movie: object,
    *,
    by: uuid.UUID | None,
    how: str,
    evidence: list[str] | None = None,
    allow_merge: bool = False,
    run_id: uuid.UUID | None = None,
) -> Identified:
    """Identify one film, audited, keeping the title it replaced. Does not commit.

    ``how`` is ``auto`` (a live run of the dry run's plan), ``picked`` or ``searched`` (Craig,
    on the Identify films page) or ``film_page``. A merge happens only when ``allow_merge``
    says someone chose it: otherwise :class:`MergeNeeded` names the film it would merge into.
    A film in the Trash is never merged into.
    """
    from src.tmdb.models import Movie as TmdbMovie

    if not isinstance(tmdb_movie, TmdbMovie):
        raise TypeError("Expected a validated TMDB movie")
    existing = await db.scalar(
        select(Movie).where(Movie.tmdb_id == tmdb_movie.id, Movie.id != source.id)
    )
    if existing is not None and existing.deleted_at is not None:
        raise IdentifyError(
            f"'{existing.title}' is in the Trash. Restore it before identifying a film as it."
        )
    if existing is not None and not allow_merge:
        raise MergeNeeded(existing)

    source_id = source.id
    replaced = source.title
    before = snapshot(source)
    had_credits = await _credits_of(db, source_id)
    lookup_before = await _lookup_snapshot(db, source_id)

    target, merge = await _apply(db, source, tmdb_movie)

    alias_added = False
    if replaced and replaced.strip() and replaced != target.title:
        known = await db.scalar(
            select(MovieTitleAlias.id).where(
                MovieTitleAlias.movie_id == target.id, MovieTitleAlias.title == replaced
            )
        )
        if known is None:
            db.add(MovieTitleAlias(id=uuid.uuid4(), movie_id=target.id, title=replaced))
            alias_added = True

    now = utcnow()
    if merge is None:
        lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == target.id))
        lookup_how = how if how in ("auto", "picked", "searched") else "picked"
        if lookup is None and how != "film_page":
            lookup = IdentifyLookup(id=uuid.uuid4(), movie_id=target.id, candidates=[])
            db.add(lookup)
        if lookup is not None:
            lookup.status = "identified"
            lookup.set_aside_as = None
            lookup.how = lookup_how
            lookup.tmdb_id = tmdb_movie.id
            lookup.replaced_title = replaced
            lookup.evidence = list(evidence or [])
            lookup.decided_by = by
            lookup.decided_utc = now
            lookup.run_id = run_id or lookup.run_id
            lookup.note = "Identified automatically." if how == "auto" else "Identified by hand."

    changes: dict[str, Any] = {
        "kind": "identify",
        "how": how,
        "tmdbId": tmdb_movie.id,
        "title": {"from": replaced, "to": target.title},
        "year": target.year,
        "evidence": list(evidence or []),
        "aliasAdded": alias_added,
        "lookup": lookup_before,
    }
    if merge is not None:
        changes["merge"] = merge.as_json()
        changes["mergedInto"] = {"id": str(target.id), "title": target.title}
    else:
        changes["before"] = before
        changes["credits"] = had_credits
    audit = record_action(
        db,
        user_id=by,
        action_type="update",
        target_table=MOVIES_TABLE,
        target_id=target.id,
        changes=changes,
    )
    await db.flush()
    return Identified(film=target, merged=merge is not None, audit=audit)


async def set_aside(
    db: AsyncSession,
    movie: Movie,
    kind: str,
    *,
    by: uuid.UUID | None,
    note: str,
    run_id: uuid.UUID | None = None,
) -> IdentifyLookup:
    """Mark a film as a TV series or as not a film, so identification leaves it alone.

    The film keeps its title and discs; ``is_tv`` and ``media_type`` say what it is. Audited,
    and reversible from the Identify films page. Does not commit.
    """
    if kind not in ("tv", "not_film"):
        raise IdentifyError(f"Unknown kind: {kind}")
    before = {"is_tv": movie.is_tv, "media_type": movie.media_type}
    movie.is_tv = kind == "tv"
    movie.media_type = "tv" if kind == "tv" else "other"
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == movie.id))
    if lookup is None:
        lookup = IdentifyLookup(id=uuid.uuid4(), movie_id=movie.id, candidates=[])
        db.add(lookup)
    lookup.status = "set_aside"
    lookup.set_aside_as = kind
    lookup.how = None
    lookup.tmdb_id = None
    lookup.note = note
    lookup.decided_by = by
    lookup.decided_utc = utcnow()
    lookup.run_id = run_id or lookup.run_id
    record_action(
        db,
        user_id=by,
        action_type="update",
        target_table=MOVIES_TABLE,
        target_id=movie.id,
        changes={
            "kind": "set_aside",
            "as": kind,
            "note": note,
            "is_tv": {"from": before["is_tv"], "to": movie.is_tv},
            "media_type": {"from": before["media_type"], "to": movie.media_type},
        },
    )
    await db.flush()
    return lookup


# ---------------------------------------------------------------------------
# Undoing
# ---------------------------------------------------------------------------


async def is_undone(db: AsyncSession, action_id: uuid.UUID) -> bool:
    found = await db.scalar(
        select(AdminAction.id).where(
            AdminAction.target_table == MOVIES_TABLE,
            AdminAction.changes["undoes"].astext == str(action_id),
        )
    )
    return found is not None


async def undo_identification(
    db: AsyncSession, action_id: uuid.UUID, *, by: uuid.UUID | None
) -> Movie:
    """Put a film back as it was before one identification. Does not commit.

    A plain identification gets its old title, year and the rest back, loses the credits TMDB
    gave it, and returns to the Identify films queue. A merge re-creates the merged-away row
    with its own id and moves back exactly the rows the merge moved. Rows the merge dropped
    as duplicates of the target's stay dropped: the target's copy stands for both.
    """
    action = await db.get(AdminAction, action_id)
    changes = action.changes if action is not None else None
    if action is None or not changes or changes.get("kind") != "identify":
        raise IdentifyError("That is not an identification.")
    if await is_undone(db, action_id):
        raise IdentifyError("That identification has already been undone.")
    target = await db.get(Movie, uuid.UUID(action.target_id))
    if target is None or target.tmdb_id != changes.get("tmdbId"):
        raise IdentifyError("The film has changed since. Undo the later change first.")
    later = await db.scalar(
        select(AdminAction.id).where(
            AdminAction.target_table == MOVIES_TABLE,
            AdminAction.target_id == action.target_id,
            AdminAction.changes["kind"].astext == "identify",
            AdminAction.created_at > action.created_at,
        )
    )
    if later is not None and not await is_undone(db, later):
        raise IdentifyError("The film was identified again since. Undo that first.")

    replaced = (changes.get("title") or {}).get("from")
    if changes.get("aliasAdded") and replaced:
        await db.execute(
            delete(MovieTitleAlias).where(
                MovieTitleAlias.movie_id == target.id, MovieTitleAlias.title == replaced
            )
        )

    merge = changes.get("merge")
    restored: Movie
    if merge:
        source_id = uuid.UUID(merge["sourceId"])
        if await db.get(Movie, source_id) is not None:
            raise IdentifyError("The merged film already exists again.")
        restored = Movie(id=source_id)
        _restore(restored, merge.get("source", {}))
        db.add(restored)
        await db.flush()
        await _move_back(db, merge.get("moved", {}), source_id=source_id, target_id=target.id)
        binned = [uuid.UUID(row["id"]) for row in merge.get("dropped", {}).get("wanted_list", [])]
        if binned:
            await db.execute(
                update(WantedItem)
                .where(WantedItem.id.in_(binned), WantedItem.movie_id == source_id)
                .values(deleted_at=None)
            )
    else:
        restored = target
        _restore(restored, changes.get("before", {}))
        await db.execute(delete(MovieCredit).where(MovieCredit.movie_id == restored.id))
        for credit in changes.get("credits") or []:
            db.add(MovieCredit(id=uuid.uuid4(), movie_id=restored.id, **credit))

    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == restored.id))
    previous = changes.get("lookup") or {}
    if lookup is None:
        lookup = IdentifyLookup(id=uuid.uuid4(), movie_id=restored.id)
        db.add(lookup)
    lookup.status = "needs_you"
    lookup.set_aside_as = None
    lookup.how = None
    lookup.tmdb_id = None
    lookup.candidates = list(previous.get("candidates") or [])
    lookup.proposed_tmdb_id = previous.get("proposed_tmdb_id")
    lookup.note = "Put back by an undo. Pick the right film, search again, or skip."
    lookup.decided_by = by
    lookup.decided_utc = utcnow()

    record_action(
        db,
        user_id=by,
        action_type="update",
        target_table=MOVIES_TABLE,
        target_id=restored.id,
        changes={
            "kind": "undo_identify",
            "undoes": str(action_id),
            "title": {"from": target.title, "to": restored.title},
        },
    )
    await db.flush()
    return restored


async def _move_back(
    db: AsyncSession,
    moved: dict[str, list[str]],
    *,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
) -> None:
    models: dict[str, Any] = {
        "collection_items": CollectionItem,
        "watch_log": WatchLog,
        "wanted_list": WantedItem,
        "movie_night_votes": MovieNightVote,
        "movie_night_suggestions": MovieNightSuggestion,
        "release_calendar": ReleaseCalendarEntry,
        "barcode_lookups": BarcodeLookup,
        "deals": Deal,
        "movie_title_aliases": MovieTitleAlias,
    }
    for table, model in models.items():
        ids = [uuid.UUID(value) for value in moved.get(table, [])]
        if ids:
            await db.execute(
                update(model)
                .where(and_(model.id.in_(ids), model.movie_id == target_id))
                .values(movie_id=source_id)
            )
