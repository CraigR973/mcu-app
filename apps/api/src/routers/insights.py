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
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AdminUser, CurrentUser
from src.models.collection_item import owned_film
from src.models.completion_set import CompletionSet, member_display
from src.models.movie import Movie
from src.routers.movies import Database, TmdbClient
from src.schemas.collections import (
    CompletionFilmResponse,
    CompletionInsightsResponse,
    CompletionRefreshResponse,
    CompletionSetDetailResponse,
    CompletionSetResponse,
    SetType,
)
from src.services.completion import refresh_sets

router = APIRouter(prefix="/api/v1", tags=["insights"])


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


def _summary(row: CompletionSet, owned_ids: set[int]) -> CompletionSetResponse:
    members = row.member_tmdb_ids or []
    total = len(members)
    owned = sum(1 for tmdb_id in members if tmdb_id in owned_ids)
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
    owned = set(await _owned_by_tmdb_id(db, all_ids))

    items = [_summary(row, owned) for row in rows]
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
    row = await db.get(CompletionSet, set_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")

    members = row.member_tmdb_ids or []
    owned = await _owned_by_tmdb_id(db, set(members))
    display = member_display(row.set_metadata or {})

    films = [
        CompletionFilmResponse(
            tmdbId=tmdb_id,
            # A member whose display row is missing still renders, with the id as its
            # name. Dropping it would silently shrink the denominator the counts above
            # are computed from, which is the one number this page must not get wrong.
            title=str(display.get(tmdb_id, {}).get("title") or f"TMDB {tmdb_id}"),
            year=display.get(tmdb_id, {}).get("year"),
            posterPath=display.get(tmdb_id, {}).get("posterPath"),
            owned=tmdb_id in owned,
            movieId=owned.get(tmdb_id),
        )
        for tmdb_id in members
    ]
    films.sort(key=lambda film: (not film.owned, film.year or 0, film.title))

    return CompletionSetDetailResponse(
        **_summary(row, set(owned)).model_dump(),
        films=films,
    )


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
