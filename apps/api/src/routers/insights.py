"""Completion insights — roadmap §11.2 and §6.5's ``/insights/completion``.

Reads are open to both people; the refresh is admin-only, because it spends a shared TMDB
budget and rewrites a table everyone reads.

**Owned-ness is computed at read time by intersecting the cached member ids with
``movies.tmdb_id``.** Nothing is stored about what is owned, so buying a film changes
every set it belongs to at once, with no job to run and nothing to invalidate — the same
reasoning that keeps smart collections unmaterialised.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Annotated, Any, cast

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AdminUser, CurrentUser
from src.models.collection_item import owned_film
from src.models.completion_exclusion import CompletionExclusion
from src.models.completion_set import CompletionSet, member_display
from src.models.movie import Movie
from src.models.wanted import WantedItem
from src.routers.movies import Database, TmdbClient
from src.schemas.collections import (
    CompletionExclusionRequest,
    CompletionFilmResponse,
    CompletionInsightsResponse,
    CompletionRefreshResponse,
    CompletionSetDetailResponse,
    CompletionSetResponse,
    SetType,
)
from src.services.audit import record_action
from src.services.completion import refresh_sets

router = APIRouter(prefix="/api/v1", tags=["insights"])

#: AE3: how many missing films Home's row names for each set; "+N more" opens the rest.
MISSING_NAMED = 3


async def _owned_by_tmdb_id(db: AsyncSession, tmdb_ids: set[int]) -> dict[int, uuid.UUID]:
    """Which of these TMDB ids this collection holds, and under which movie row.

    One query for every set on the page. Asking per set would be 25 queries for a page
    that has one question.
    """
    if not tmdb_ids:
        return {}
    rows = (
        await db.execute(
            select(Movie.tmdb_id, Movie.id).where(
                Movie.tmdb_id.in_(tmdb_ids), Movie.deleted_at.is_(None), owned_film()
            )
        )
    ).all()
    return {int(tmdb_id): movie_id for tmdb_id, movie_id in rows if tmdb_id is not None}


async def _wanted_tmdb_ids(db: AsyncSession, tmdb_ids: set[int]) -> set[int]:
    """The completion films already on the shared, active Wanted list."""
    if not tmdb_ids:
        return set()
    rows = await db.scalars(
        select(Movie.tmdb_id)
        .join(WantedItem, WantedItem.movie_id == Movie.id)
        .where(
            Movie.tmdb_id.in_(tmdb_ids),
            Movie.deleted_at.is_(None),
            WantedItem.deleted_at.is_(None),
            WantedItem.is_active.is_(True),
        )
    )
    return {int(tmdb_id) for tmdb_id in rows if tmdb_id is not None}


async def _excluded(db: AsyncSession, set_ids: set[uuid.UUID]) -> dict[uuid.UUID, set[int]]:
    """The members each set's people said do not count — AE3. One query for the page."""
    if not set_ids:
        return {}
    rows = (
        await db.execute(
            select(CompletionExclusion.set_id, CompletionExclusion.tmdb_id).where(
                CompletionExclusion.set_id.in_(set_ids)
            )
        )
    ).all()
    excluded: dict[uuid.UUID, set[int]] = defaultdict(set)
    for set_id, tmdb_id in rows:
        excluded[set_id].add(int(tmdb_id))
    return dict(excluded)


def _film(
    tmdb_id: int,
    display: dict[int, dict[str, Any]],
    owned: dict[int, uuid.UUID],
    wanted: set[int],
    excluded: set[int],
) -> CompletionFilmResponse:
    return CompletionFilmResponse(
        tmdbId=tmdb_id,
        # A member whose display row is missing still renders, with the id as its
        # name. Dropping it would silently shrink the denominator the counts above
        # are computed from, which is the one number this page must not get wrong.
        title=str(display.get(tmdb_id, {}).get("title") or f"TMDB {tmdb_id}"),
        year=display.get(tmdb_id, {}).get("year"),
        posterPath=display.get(tmdb_id, {}).get("posterPath"),
        owned=tmdb_id in owned,
        movieId=owned.get(tmdb_id),
        wanted=tmdb_id in wanted,
        # An owned film always counts, whatever was said about it while it was missing.
        counts=tmdb_id in owned or tmdb_id not in excluded,
    )


def _missing_counted(
    row: CompletionSet, owned_ids: set[int], excluded: set[int], display: dict[int, dict[str, Any]]
) -> list[int]:
    """The set's missing films that count, oldest first, as the set's own page lists them."""
    missing = [
        tmdb_id
        for tmdb_id in row.member_tmdb_ids or []
        if tmdb_id not in owned_ids and tmdb_id not in excluded
    ]
    return sorted(
        missing,
        key=lambda tmdb_id: (
            display.get(tmdb_id, {}).get("year") or 0,
            str(display.get(tmdb_id, {}).get("title") or ""),
        ),
    )


def _summary(
    row: CompletionSet,
    owned_ids: set[int],
    excluded: set[int] | None = None,
    missing_films: list[CompletionFilmResponse] | None = None,
) -> CompletionSetResponse:
    """The set's counts, leaving out the missing films that do not count (AE3).

    A set whose only missing films do not count is complete, so Home's row moves on.
    """
    excluded = excluded or set()
    members = row.member_tmdb_ids or []
    counted = [tmdb_id for tmdb_id in members if tmdb_id in owned_ids or tmdb_id not in excluded]
    total = len(counted)
    owned = sum(1 for tmdb_id in counted if tmdb_id in owned_ids)
    return CompletionSetResponse(
        id=row.id,
        setType=cast(SetType, row.set_type),
        setKey=row.set_key,
        setName=row.set_name,
        ownedCount=owned,
        totalCount=total,
        missingCount=total - owned,
        # Integer percent, floored, computed here so the progress bar's width and the
        # "12 of 54" beside it can never tell different stories.
        percentComplete=round(owned * 100 / total) if total else 0,
        lastRefreshed=row.last_refreshed,
        personProfilePath=(
            row.set_metadata.get("personProfilePath")
            if isinstance(row.set_metadata.get("personProfilePath"), str)
            else None
        ),
        excludedCount=len(members) - total,
        missingFilms=missing_films or [],
    )


@router.get("/insights/completion", response_model=CompletionInsightsResponse)
async def completion_insights(
    _user: CurrentUser,
    db: Database,
    set_type: Annotated[str | None, Query(alias="setType")] = None,
) -> CompletionInsightsResponse:
    """Every set with its owned/missing counts — §11.2's acceptance criterion.

    Ordered by how close each set is to complete, so the page opens on the ones worth
    finishing rather than on an alphabet.
    """
    predicates = []
    if set_type is not None:
        predicates.append(CompletionSet.set_type == set_type)
    rows = (await db.execute(select(CompletionSet).where(*predicates))).scalars().all()

    all_ids: set[int] = set()
    for row in rows:
        all_ids.update(row.member_tmdb_ids or [])
    owned_rows = await _owned_by_tmdb_id(db, all_ids)
    owned = set(owned_rows)
    excluded = await _excluded(db, {row.id for row in rows})

    # AE3: the first few missing films of each set, named on Home with a Want button.
    displays = {row.id: member_display(row.set_metadata or {}) for row in rows}
    named = {
        row.id: _missing_counted(row, owned, excluded.get(row.id, set()), displays[row.id])[
            :MISSING_NAMED
        ]
        for row in rows
    }
    wanted = await _wanted_tmdb_ids(db, {tmdb_id for ids in named.values() for tmdb_id in ids})

    items = [
        _summary(
            row,
            owned,
            excluded.get(row.id, set()),
            [
                _film(tmdb_id, displays[row.id], owned_rows, wanted, set())
                for tmdb_id in named[row.id]
            ],
        )
        for row in rows
    ]
    items.sort(key=lambda item: (-item.percentComplete, -item.ownedCount, item.setName))

    refreshed = [row.last_refreshed for row in rows if row.last_refreshed is not None]
    return CompletionInsightsResponse(
        items=items,
        total=len(items),
        oldestRefresh=min(refreshed) if refreshed else None,
    )


@router.get("/insights/completion/{set_id}", response_model=CompletionSetDetailResponse)
async def completion_set_detail(
    set_id: uuid.UUID, _user: CurrentUser, db: Database
) -> CompletionSetDetailResponse:
    """One set's films, owned first — §11.2's "missing films list with posters"."""
    return await _detail(db, await _set_or_404(db, set_id))


async def _set_or_404(db: AsyncSession, set_id: uuid.UUID) -> CompletionSet:
    row = await db.get(CompletionSet, set_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")
    return row


async def _detail(db: AsyncSession, row: CompletionSet) -> CompletionSetDetailResponse:
    members = row.member_tmdb_ids or []
    owned = await _owned_by_tmdb_id(db, set(members))
    wanted = await _wanted_tmdb_ids(db, set(members))
    excluded = (await _excluded(db, {row.id})).get(row.id, set())
    display = member_display(row.set_metadata or {})

    films = [_film(tmdb_id, display, owned, wanted, excluded) for tmdb_id in members]
    # Owned first, then the missing films that count, then those that do not (AE3).
    films.sort(key=lambda film: (not film.owned, not film.counts, film.year or 0, film.title))
    named = [film for film in films if not film.owned and film.counts][:MISSING_NAMED]

    return CompletionSetDetailResponse(
        **_summary(row, set(owned), excluded, named).model_dump(),
        films=films,
    )


@router.post(
    "/insights/completion/{set_id}/exclusions",
    response_model=CompletionSetDetailResponse,
)
async def exclude_completion_film(
    set_id: uuid.UUID, payload: CompletionExclusionRequest, user: CurrentUser, db: Database
) -> CompletionSetDetailResponse:
    """Say a missing film does not count toward this set — AE3 (#355, point 3).

    Either person may, as both keep the shelves. Saying it twice is one row and one audit
    entry: the second, or a replay of the first, finds the row there and changes nothing.
    """
    row = await _set_or_404(db, set_id)
    if payload.tmdbId not in (row.member_tmdb_ids or []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="That film is not in this set."
        )
    if await _owned_by_tmdb_id(db, {payload.tmdbId}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A film on the shelf always counts."
        )
    added = await db.scalar(
        insert(CompletionExclusion)
        .values(id=uuid.uuid4(), set_id=row.id, tmdb_id=payload.tmdbId, excluded_by=user.id)
        .on_conflict_do_nothing(constraint="uq_completion_exclusion")
        .returning(CompletionExclusion.id)
    )
    if added is not None:
        # The house's audit verbs, the table and what was said (admin_actions' check, #008).
        record_action(
            db,
            user_id=user.id,
            action_type="create",
            target_table="completion_exclusions",
            target_id=added,
            changes=_said(row, payload.tmdbId, counts=False),
        )
    await db.commit()
    return await _detail(db, row)


@router.delete(
    "/insights/completion/{set_id}/exclusions/{tmdb_id}",
    response_model=CompletionSetDetailResponse,
)
async def count_completion_film_again(
    set_id: uuid.UUID, tmdb_id: int, user: CurrentUser, db: Database
) -> CompletionSetDetailResponse:
    """ "Count it again" — AE3. Undoing what is already undone changes nothing."""
    row = await _set_or_404(db, set_id)
    removed = await db.scalar(
        delete(CompletionExclusion)
        .where(CompletionExclusion.set_id == row.id, CompletionExclusion.tmdb_id == tmdb_id)
        .returning(CompletionExclusion.id)
    )
    if removed is not None:
        record_action(
            db,
            user_id=user.id,
            action_type="delete",
            target_table="completion_exclusions",
            target_id=removed,
            changes=_said(row, tmdb_id, counts=True),
        )
    await db.commit()
    return await _detail(db, row)


def _said(row: CompletionSet, tmdb_id: int, *, counts: bool) -> dict[str, Any]:
    """What an audit entry records: which set, which film, and whether it now counts."""
    title = member_display(row.set_metadata or {}).get(tmdb_id, {}).get("title")
    return {
        "setId": str(row.id),
        "setName": row.set_name,
        "tmdbId": tmdb_id,
        "title": str(title or tmdb_id),
        "counts": counts,
    }


@router.post(
    "/insights/completion/refresh",
    response_model=CompletionRefreshResponse,
)
async def refresh_completion_sets(
    user: AdminUser,
    db: Database,
    tmdb: TmdbClient,
    limit_per_type: Annotated[int, Query(alias="limitPerType", ge=1, le=100)] = 20,
    dry_run: Annotated[bool, Query(alias="dryRun")] = False,
) -> CompletionRefreshResponse:
    """Rebuild the sets from TMDB — §11.1's refresh, on demand.

    **"Weekly" is not implemented here and deliberately so.** Scheduling belongs to the
    platform, and adding a Railway cron is a hosting change this project keeps explicit.
    This endpoint and `src/scripts/refresh_completion_sets.py` are what a schedule would
    call; wiring the schedule is an owner action.
    """
    del user
    result = await refresh_sets(db, tmdb, limit_per_type=limit_per_type, dry_run=dry_run)
    return CompletionRefreshResponse(
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        skipped=result.skipped,
        total=result.total,
        errors=result.errors,
        dryRun=dry_run,
    )
