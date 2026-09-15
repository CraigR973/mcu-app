"""The watch-history sync — Batch S5, snag 10a.

**Caller-scoped throughout, and not admin-gated.** Each person has their own diary, their
own username and their own watch rows; there is no version of this where one of them
administers the other's viewing history. Same reasoning as Batch 11's notification
endpoints.

**A manual sync, because the crons are crashing.** `DECISIONS.md` #156 requires the first
version to work from a button the way the scraper does — both Railway crons have been
failing on every scheduled fire since 2026-09-10 (`OWNER-ACTIONS.md` item 1), so a design
that assumed a schedule would ship inert. `letterboxd_syncs.trigger` already accepts
``cron`` so adding one later needs no migration.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from src.auth import CurrentUser
from src.models.letterboxd_sync import LetterboxdSync
from src.models.watch_log import WatchLog
from src.routers.movies import Database
from src.schemas.watch_history import (
    SyncResponse,
    SyncRunResponse,
    UsernameRequest,
    WatchHistoryStatusResponse,
)
from src.services.letterboxd.sync import SyncNotConfigured, last_sync, sync_watch_history

router = APIRouter(prefix="/api/v1", tags=["watch-history"])


def _run_response(run: LetterboxdSync) -> SyncRunResponse:
    return SyncRunResponse(
        id=str(run.id),
        startedAt=run.started_at_utc,
        finishedAt=run.finished_at_utc,
        trigger=run.trigger,
        entries=run.entries,
        written=run.written,
        alreadyImported=run.already_imported,
        ambiguous=run.ambiguous,
        notInCollection=run.not_in_collection,
        error=run.error,
    )


@router.get("/watch-history/status", response_model=WatchHistoryStatusResponse)
async def watch_history_status(user: CurrentUser, db: Database) -> WatchHistoryStatusResponse:
    """What the panel shows before anybody presses anything.

    **The last run is the point.** The feed carries 50 entries and no more, and Mark
    cycles his in about eight weeks, so a sync that silently stopped running would lose
    history without ever failing (`DECISIONS.md` #159).
    """
    run = await last_sync(db, user.id)
    watches = await db.scalar(
        select(func.count(WatchLog.id)).where(
            WatchLog.user_id == user.id, WatchLog.deleted_at.is_(None)
        )
    )
    return WatchHistoryStatusResponse(
        letterboxdUsername=user.letterboxd_username,
        lastSync=_run_response(run) if run is not None else None,
        watchCount=int(watches or 0),
    )


@router.put("/watch-history/username", response_model=WatchHistoryStatusResponse)
async def set_username(
    payload: UsernameRequest, user: CurrentUser, db: Database
) -> WatchHistoryStatusResponse:
    """Set or clear **your own** Letterboxd username.

    Caller-scoped with no admin override: there is no reason for one person to set the
    other's, and every reason not to have the endpoint that would allow it.
    """
    user.letterboxd_username = payload.letterboxdUsername
    await db.commit()
    await db.refresh(user)
    return await watch_history_status(user, db)


@router.post("/watch-history/sync", response_model=SyncResponse)
async def sync_now(user: CurrentUser, db: Database) -> SyncResponse:
    """Fetch this person's diary feed and write whatever is new.

    **Reuses S8's matcher and writer whole** — the feed reader's only job is to produce the
    same `DiaryEntry` the file import produces, so a viewing present in both sources
    becomes exactly one row (`DECISIONS.md` #176).

    **Does not identify films**, even though every feed entry carries a TMDB id. That
    rewrites `movies` rows, which is the operation S8 put in the owner's hands; doing it
    from a button on a schedule would make it happen quietly and repeatedly instead.
    """
    try:
        result = await sync_watch_history(db, user)
    except SyncNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Set your Letterboxd username before syncing.",
        ) from exc

    return SyncResponse(
        run=_run_response(result.run),
        ambiguities=result.ambiguities,
        feedWasFull=result.feed_was_full,
    )
