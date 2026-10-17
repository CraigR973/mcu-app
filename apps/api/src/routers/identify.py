"""The Identify films page — Batch T9.

**Every route is admin-only but three.** Identification rewrites the film identities that
discs, watches and movie nights hang off, and merges two films into one, so it is Craig's.
Since Batch Y4 (#276) Mark settles a doubt from the film page: keeping it, moving one copy,
and the TMDB search that move uses take any signed-in person, and the audit row names who.
The queue, the doubts list, the recent list and its undo stay Craig's.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, cast

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query, status

from src.auth import AdminUser, CurrentUser
from src.models.admin_action import AdminAction
from src.models.identify import IdentifyRun
from src.routers.movies import Database, TmdbClient
from src.schemas.identify import (
    DoubtSource,
    FilmInCollectionResponse,
    IdentifyCandidateResponse,
    IdentifyDecisionResponse,
    IdentifyDiscResponse,
    IdentifyDoubtResponse,
    IdentifyDoubtsResponse,
    IdentifyOverviewResponse,
    IdentifyPickRequest,
    IdentifyQueueItemResponse,
    IdentifyQueueResponse,
    IdentifyRunResponse,
    IdentifySearchResponse,
    IdentifySetAsideRequest,
    MoveCopyRequest,
    MoveCopyResponse,
    RecentIdentificationResponse,
    RecentIdentificationsResponse,
)
from src.services.identification import IdentifyError, MergeNeeded, undo_identification
from src.services.identify.doubts import (
    KEEP_KIND,
    DoubtError,
    correct,
    keep,
    open_doubts,
    undo_keep,
)
from src.services.identify.matcher import find_series
from src.services.identify.move_copy import MOVE_KIND, MoveError, move_copy, undo_move
from src.services.identify.queue import (
    FilmInCollection,
    QueueError,
    in_collection,
    mark,
    overview,
    pick,
    put_back,
    queue,
    recent,
    search_again,
    skip,
)
from src.tmdb.client import TMDBRefused
from src.tmdb.models import Movie as TmdbMovie
from src.tmdb.models import TvShow

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["identify"])

_RUN_STATUSES: dict[str, Any] = {
    "running": "running",
    "finished": "finished",
    "stopped": "stopped",
    "abandoned": "abandoned",
}


def _run(run: IdentifyRun) -> IdentifyRunResponse:
    return IdentifyRunResponse(
        id=run.id,
        status=_RUN_STATUSES[run.status],
        startedAt=run.started_utc,
        finishedAt=run.finished_utc,
        films=run.films,
        identified=run.identified,
        queued=run.queued,
        setAside=run.set_aside,
        unchanged=run.unchanged,
        failed=run.failed,
        searches=run.searches,
        lastError=run.last_error,
    )


def _in_collection(film: FilmInCollection | None) -> FilmInCollectionResponse | None:
    if film is None:
        return None
    return FilmInCollectionResponse(
        movieId=film.movie_id,
        title=film.title,
        year=film.year,
        discs=film.discs,
        watches=film.watches,
    )


def _candidates(
    raw: list[dict[str, Any]], held: dict[int, FilmInCollection]
) -> list[IdentifyCandidateResponse]:
    found: list[IdentifyCandidateResponse] = []
    for candidate in raw:
        tmdb_id = int(candidate["tmdb_id"])
        found.append(
            IdentifyCandidateResponse(
                tmdbId=tmdb_id,
                title=str(candidate.get("title") or ""),
                year=candidate.get("year"),
                posterPath=candidate.get("poster_path"),
                overview=str(candidate.get("overview") or ""),
                votes=int(candidate.get("votes") or 0),
                notes=[str(note) for note in candidate.get("notes") or []],
                inCollection=_in_collection(held.get(tmdb_id)),
            )
        )
    return found


def _refuse(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/identify/overview", response_model=IdentifyOverviewResponse)
async def read_overview(_user: AdminUser, db: Database) -> IdentifyOverviewResponse:
    """How many unmatched films wait for Craig, and what became of the rest."""
    counts = await overview(db)
    return IdentifyOverviewResponse(
        unidentified=counts.unidentified,
        waiting=counts.waiting,
        setAsideTv=counts.set_aside_tv,
        setAsideNotFilm=counts.set_aside_not_film,
        skipped=counts.skipped,
        identified=counts.identified,
        inDoubt=counts.in_doubt,
        run=_run(counts.latest_run) if counts.latest_run else None,
    )


@router.get("/identify/queue", response_model=IdentifyQueueResponse)
async def read_queue(
    _user: AdminUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> IdentifyQueueResponse:
    """Films waiting for Craig, with the films offered and why each waits."""
    entries, total = await queue(db, limit=limit)
    tmdb_ids = [int(c["tmdb_id"]) for entry in entries for c in entry.candidates]
    held = await in_collection(db, tmdb_ids)
    return IdentifyQueueResponse(
        items=[
            IdentifyQueueItemResponse(
                movieId=entry.movie.id,
                title=entry.movie.title,
                discs=[IdentifyDiscResponse(label=disc.label()) for disc in entry.discs],
                watches=entry.watches,
                note=entry.lookup.note if entry.lookup else None,
                proposedTmdbId=entry.lookup.proposed_tmdb_id if entry.lookup else None,
                candidates=_candidates(entry.candidates, held),
            )
            for entry in entries
        ],
        total=total,
    )


@router.get("/identify/films/{movie_id}/search", response_model=IdentifySearchResponse)
async def search_film(
    movie_id: uuid.UUID,
    _user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
    query: Annotated[str, Query(min_length=1, max_length=300)],
) -> IdentifySearchResponse:
    """TMDB's films for a corrected title. Nothing is saved until Craig picks one. Either
    person since Batch Y4: "Move only this copy" searches with it, and it writes nothing.
    Since Batch Y5 it answers TMDB's series apart, which a copy can move to."""
    del movie_id
    try:
        found = await search_again(tmdb, query.strip())
    except (httpx.HTTPError, TMDBRefused) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="TMDB search is unavailable"
        ) from exc
    held = await in_collection(db, [int(c["tmdb_id"]) for c in found])
    return IdentifySearchResponse(
        query=query.strip(),
        candidates=_candidates(found, held),
        seriesCandidates=await _series_candidates(db, tmdb, query.strip()),
    )


#: Series offered beside the films, as Correct match offers them.
SERIES_OFFERED = 5


async def _series_candidates(
    db: Database, tmdb: TmdbClient, query: str
) -> list[IdentifyCandidateResponse]:
    """TMDB's series for the words — Batch Y5. A failure leaves the films to answer alone."""
    try:
        _, ranked = await find_series(tmdb, query, limit=SERIES_OFFERED)
    except (httpx.HTTPError, TMDBRefused):
        logger.warning("tmdb_series_search_unavailable", query=query)
        return []
    held = await in_collection(db, [show.id for show, _ in ranked], series=True)
    return [
        IdentifyCandidateResponse(
            tmdbId=show.id,
            title=show.name,
            year=show.year,
            posterPath=show.poster_path,
            overview=(show.overview or "")[:600],
            votes=show.vote_count,
            notes=[],
            inCollection=_in_collection(held.get(show.id)),
            mediaType="tv",
        )
        for show, _ in ranked
    ]


@router.post("/identify/films/{movie_id}/identify", response_model=IdentifyDecisionResponse)
async def identify(
    movie_id: uuid.UUID,
    payload: IdentifyPickRequest,
    user: AdminUser,
    db: Database,
    tmdb: TmdbClient,
) -> IdentifyDecisionResponse:
    """Craig's choice. A choice that merges into a film the collection has needs ``merge``."""
    try:
        identified = await pick(
            db,
            movie_id,
            payload.tmdbId,
            tmdb,
            by=user.id,
            merge=payload.merge,
            searched=payload.searched,
        )
    except MergeNeeded as exc:
        await db.rollback()
        raise _refuse(exc) from exc
    except (LookupError, QueueError, IdentifyError) as exc:
        await db.rollback()
        raise _refuse(exc) from exc
    except httpx.HTTPError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="TMDB could not be reached"
        ) from exc
    return IdentifyDecisionResponse(
        movieId=identified.film.id,
        outcome="merged" if identified.merged else "identified",
        title=identified.film.title,
    )


@router.post("/identify/films/{movie_id}/set-aside", response_model=IdentifyDecisionResponse)
async def set_film_aside(
    movie_id: uuid.UUID, payload: IdentifySetAsideRequest, user: AdminUser, db: Database
) -> IdentifyDecisionResponse:
    """A TV series, or not a film."""
    try:
        await mark(db, movie_id, payload.kind, by=user.id)
    except (LookupError, QueueError) as exc:
        raise _refuse(exc) from exc
    return IdentifyDecisionResponse(movieId=movie_id, outcome="set_aside", title="")


@router.post("/identify/films/{movie_id}/skip", response_model=IdentifyDecisionResponse)
async def skip_film(movie_id: uuid.UUID, user: AdminUser, db: Database) -> IdentifyDecisionResponse:
    """Leave the film as it is, out of the queue."""
    try:
        await skip(db, movie_id, by=user.id)
    except (LookupError, QueueError) as exc:
        raise _refuse(exc) from exc
    return IdentifyDecisionResponse(movieId=movie_id, outcome="skipped", title="")


@router.post("/identify/films/{movie_id}/put-back", response_model=IdentifyDecisionResponse)
async def put_film_back(
    movie_id: uuid.UUID, user: AdminUser, db: Database
) -> IdentifyDecisionResponse:
    """A set-aside or skipped film, back in the queue as a film."""
    try:
        await put_back(db, movie_id, by=user.id)
    except (LookupError, QueueError) as exc:
        raise _refuse(exc) from exc
    return IdentifyDecisionResponse(movieId=movie_id, outcome="waiting", title="")


@router.get("/identify/doubts", response_model=IdentifyDoubtsResponse)
async def read_doubts(
    _user: AdminUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> IdentifyDoubtsResponse:
    """Identified films that may be the wrong one, with the evidence — Batch X9."""
    entries, total = await open_doubts(db, limit=limit)
    tmdb_ids = [int(c["tmdb_id"]) for entry in entries for c in entry.doubt.candidates]
    held = await in_collection(db, tmdb_ids)
    return IdentifyDoubtsResponse(
        items=[
            IdentifyDoubtResponse(
                doubtId=entry.doubt.id,
                movieId=entry.movie.id,
                title=entry.movie.title,
                year=entry.movie.year,
                tmdbId=entry.movie.tmdb_id or 0,
                posterPath=entry.movie.poster_path,
                source=cast(DoubtSource, entry.doubt.source),
                note=entry.doubt.note,
                evidence=list(entry.doubt.evidence),
                discs=[IdentifyDiscResponse(label=label) for label in entry.discs],
                copies=entry.copies,
                watches=entry.watches,
                collectionItemId=entry.doubt.collection_item_id,
                candidates=_candidates(entry.doubt.candidates, held),
                proposedTmdbId=entry.doubt.proposed_tmdb_id,
                searchHint=entry.doubt.search_hint or entry.movie.title,
                raisedAt=entry.doubt.created_utc,
            )
            for entry in entries
        ],
        total=total,
    )


@router.post("/identify/doubts/{doubt_id}/keep", response_model=IdentifyDecisionResponse)
async def keep_film(
    doubt_id: uuid.UUID, user: CurrentUser, db: Database
) -> IdentifyDecisionResponse:
    """The film is right after all. Either person, from the film page, since Batch Y4."""
    try:
        doubt = await keep(db, doubt_id, by=user.id)
    except (LookupError, DoubtError) as exc:
        await db.rollback()
        raise _refuse(exc) from exc
    return IdentifyDecisionResponse(movieId=doubt.movie_id, outcome="kept", title="")


@router.post("/identify/doubts/{doubt_id}/identify", response_model=IdentifyDecisionResponse)
async def correct_film(
    doubt_id: uuid.UUID,
    payload: IdentifyPickRequest,
    user: AdminUser,
    db: Database,
    tmdb: TmdbClient,
) -> IdentifyDecisionResponse:
    """The film is another one. A choice that merges into a film the collection has needs
    ``merge``; undone from the recent list, which opens the doubt again."""
    try:
        identified = await correct(
            db,
            doubt_id,
            payload.tmdbId,
            tmdb,
            by=user.id,
            merge=payload.merge,
            searched=payload.searched,
        )
    except (LookupError, DoubtError, IdentifyError) as exc:
        await db.rollback()
        raise _refuse(exc) from exc
    except (httpx.HTTPError, TMDBRefused) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="TMDB could not be reached"
        ) from exc
    return IdentifyDecisionResponse(
        movieId=identified.film.id,
        outcome="merged" if identified.merged else "identified",
        title=identified.film.title,
    )


@router.post("/identify/copies/{item_id}/move", response_model=MoveCopyResponse)
async def move_a_copy(
    item_id: uuid.UUID,
    payload: MoveCopyRequest,
    user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
) -> MoveCopyResponse:
    """This copy is another film: it moves on its own, to that film — Batch X9. Undone from
    the recent list. Either person since Batch Y4; to a series too since Batch Y5."""
    record: TmdbMovie | TvShow
    try:
        if payload.mediaType == "tv":
            record = await tmdb.get_tv_full(payload.tmdbId)
        else:
            record = await tmdb.get_movie_full(payload.tmdbId)
        moved = await move_copy(db, item_id, record, by=user.id, doubt_id=payload.doubtId)
        await db.commit()
    except (LookupError, MoveError) as exc:
        await db.rollback()
        raise _refuse(exc) from exc
    except (httpx.HTTPError, TMDBRefused) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="TMDB could not be reached"
        ) from exc
    return MoveCopyResponse(
        movieId=moved.film.id,
        title=moved.film.title,
        year=moved.film.year,
        created=moved.created,
        actionId=moved.audit.id,
    )


@router.get("/identify/recent", response_model=RecentIdentificationsResponse)
async def read_recent(
    _user: AdminUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> RecentIdentificationsResponse:
    """The latest identifications, each with an undo."""
    rows = await recent(db, limit=limit)
    return RecentIdentificationsResponse(
        items=[
            RecentIdentificationResponse(
                actionId=row.action_id,
                at=row.when,
                by=row.by,
                movieId=row.movie_id,
                replaced=row.replaced,
                title=row.title,
                year=row.year,
                how=row.how,
                merged=row.merged,
                undone=row.undone,
            )
            for row in rows
        ]
    )


@router.post("/identify/recent/{action_id}/undo", response_model=IdentifyDecisionResponse)
async def undo(action_id: uuid.UUID, user: AdminUser, db: Database) -> IdentifyDecisionResponse:
    """Put the film back as it was before that identification, merges included, a moved
    copy back on the film it came from (Batch X9), or a kept doubt open again (Batch Y4)."""
    action = await db.get(AdminAction, action_id)
    kind = (action.changes or {}).get("kind") if action is not None else None
    try:
        if kind == MOVE_KIND:
            restored = await undo_move(db, action_id, by=user.id)
        elif kind == KEEP_KIND:
            restored = await undo_keep(db, action_id, by=user.id)
        else:
            restored = await undo_identification(db, action_id, by=user.id)
    except (IdentifyError, MoveError, DoubtError) as exc:
        await db.rollback()
        raise _refuse(exc) from exc
    await db.commit()
    return IdentifyDecisionResponse(movieId=restored.id, outcome="waiting", title=restored.title)
