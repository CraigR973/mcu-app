"""Disc specs from Blu-ray.com — §3.7.

**Every route is admin-only, and the fetching one makes live third-party requests.**
`DECISIONS.md` #110 is a risk acceptance the owner made, not a permission the site granted,
and `docs/agent-commands/group-start.md` puts live third-party runs in the owner's hands.
So this endpoint exists, is tested against fixture HTML, and is invoked by a person.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, select

from src.auth import AdminUser
from src.clock import utcnow
from src.config import settings
from src.models.collection_item import CollectionItem
from src.models.specs_backfill import SpecLookup, SpecRun
from src.routers.movies import Database
from src.schemas.specs import (
    SpecAcceptRequest,
    SpecBackfillResponse,
    SpecBackfillStartResponse,
    SpecCandidateResponse,
    SpecCoverageResponse,
    SpecDecisionResponse,
    SpecQueueItemResponse,
    SpecQueueResponse,
    SpecRunResponse,
    SpecsFetchRequest,
    SpecsRunResponse,
    SpecsStateResponse,
)
from src.services.specs.backfill import (
    FETCHES_PER_RUN,
    MONTHLY_SEARCH_CEILING,
    SEARCHES_PER_RUN,
    QueueError,
    accept_page,
    continue_run_in_background,
    coverage,
    latest_run,
    queue,
    searches_this_month,
    skip_disc,
    start_run,
)
from src.services.specs.editions import page_edition
from src.services.specs.runner import get_state, halt, run_specs_fetch

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["specs"])


async def _state_response(db: Database) -> SpecsStateResponse:
    state = await get_state(db)
    count = (
        await db.execute(
            select(func.count())
            .select_from(CollectionItem)
            .where(CollectionItem.specs_source_url.is_not(None))
        )
    ).scalar_one()
    return SpecsStateResponse(
        halted=state.halted,
        haltedReason=state.halted_reason,
        haltedAt=state.halted_at_utc,
        lastFetchAt=state.last_fetch_at_utc,
        fetchCount=state.fetch_count,
        discsWithSpecs=count,
    )


@router.get("/specs/state", response_model=SpecsStateResponse)
async def read_state(_user: AdminUser, db: Database) -> SpecsStateResponse:
    """Is the integration running, what has it fetched, and how much data is derived?"""
    return await _state_response(db)


@router.post("/specs/halt", response_model=SpecsStateResponse)
async def halt_integration(_user: AdminUser, db: Database) -> SpecsStateResponse:
    """Stop it, now.

    Here because #110 names *"an explicit objection"* as a halt condition alongside the HTTP
    ones, and an objection arrives in an email rather than a status code. One button.

    **There is deliberately no endpoint that un-halts.** #110: *"resuming after any of those
    requires a new owner decision."* A decision is a `DECISIONS.md` entry and a deliberate
    database change, not a button somebody can press twice by accident.
    """
    await halt(db, "Halted by hand from the app")
    await db.commit()
    return await _state_response(db)


@router.post("/specs/fetch", response_model=SpecsRunResponse)
async def fetch_specs(
    payload: SpecsFetchRequest, _user: AdminUser, db: Database
) -> SpecsRunResponse:
    """§3.7 — fetch specs for a list of discs. **Makes live requests to Blu-ray.com.**

    Each `sourceUrl` was already checked against #110's bounds by the request model, so a
    search URL or another host is a 422 before anything leaves the building. Requests are
    sequential and spaced; a `403` or `429` halts the whole integration and abandons the
    rest of the batch.
    """
    state = await get_state(db)
    if state.halted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The Blu-ray.com integration is halted: "
                f"{state.halted_reason}. Resuming needs an owner decision (DECISIONS.md #110)."
            ),
        )

    async with httpx.AsyncClient() as client:
        result = await run_specs_fetch(
            db,
            [(target.collectionItemId, target.sourceUrl) for target in payload.targets],
            client=client,
            refresh=payload.refresh,
        )
    await db.commit()

    logger.info(
        "specs_fetch_complete",
        fetched=len(result.fetched),
        updated=result.updated,
        halted=result.halted,
        at=utcnow().isoformat(),
    )
    return SpecsRunResponse(
        fetched=result.fetched,
        updated=result.updated,
        skipped=result.skipped,
        failed=result.failed,
        halted=result.halted,
        haltReason=result.halt_reason,
    )


@router.delete("/specs", response_model=SpecsStateResponse)
async def forget_all_specs(_user: AdminUser, db: Database) -> SpecsStateResponse:
    """Remove every field derived from Blu-ray.com.

    **This is the endpoint that makes #110's acceptance reversible.** The owner accepted the
    risk partly on the basis that *"deletion remains an explicit owner action"* and that
    every derived row records its source — this is the action, and `specs_source_url` is what
    makes it possible to find them.

    Only rows that actually came from there are touched: a spec typed in by hand has no
    source URL and is left alone. **An edition goes only when it is the one the page names**
    (Batch U2): one typed or corrected by hand stays.
    """
    rows = list(
        (
            await db.execute(
                select(CollectionItem).where(CollectionItem.specs_source_url.is_not(None))
            )
        )
        .scalars()
        .all()
    )
    for item in rows:
        if item.edition is not None:
            lookup = await db.scalar(
                select(SpecLookup).where(SpecLookup.collection_item_id == item.id)
            )
            if lookup is not None and item.edition == await page_edition(db, lookup):
                item.edition = None
                item.edition_source = None
        item.video_specs = None
        item.audio_specs = None
        item.special_features = None
        item.region_code = None
        item.release_label = None
        item.specs_source_url = None
        item.specs_fetched_at_utc = None
    await db.commit()
    logger.warning("specs_deleted", rows=len(rows))
    return await _state_response(db)


# ---------------------------------------------------------------------------
# The backfill (Batch T7, `DECISIONS.md` #202)
# ---------------------------------------------------------------------------

_RUN_STATUSES: dict[
    str, Literal["running", "finished", "budget_spent", "stopped", "halted", "abandoned"]
] = {
    "running": "running",
    "finished": "finished",
    "budget_spent": "budget_spent",
    "stopped": "stopped",
    "halted": "halted",
    "abandoned": "abandoned",
}
_LOOKUP_STATUSES: dict[str, Literal["needs_you", "no_match", "accepted", "done", "skipped"]] = {
    "needs_you": "needs_you",
    "no_match": "no_match",
    "accepted": "accepted",
    "done": "done",
    "skipped": "skipped",
}
_HOW: dict[str, Literal["auto", "confirmed", "pasted", "restored"]] = {
    "auto": "auto",
    "confirmed": "confirmed",
    "pasted": "pasted",
    "restored": "restored",
}


def _run_response(run: SpecRun) -> SpecRunResponse:
    return SpecRunResponse(
        id=run.id,
        trigger="admin" if run.trigger == "admin" else "job",
        status=_RUN_STATUSES[run.status],
        startedAt=run.started_utc,
        finishedAt=run.finished_utc,
        searchBudget=run.search_budget,
        searches=run.searches,
        searched=run.searched,
        accepted=run.accepted,
        queued=run.queued,
        noMatch=run.no_match,
        restored=run.restored,
        fetchBudget=run.fetch_budget,
        fetched=run.fetched,
        applied=run.applied,
        sentBack=run.sent_back,
        fetchFailed=run.fetch_failed,
        lastError=run.last_error,
    )


def _decision(lookup: SpecLookup) -> SpecDecisionResponse:
    return SpecDecisionResponse(
        lookupId=lookup.id,
        status=_LOOKUP_STATUSES[lookup.status],
        acceptedUrl=lookup.accepted_url,
        how=_HOW[lookup.how] if lookup.how else None,
    )


@router.get("/specs/backfill", response_model=SpecBackfillResponse)
async def read_backfill(_user: AdminUser, db: Database) -> SpecBackfillResponse:
    """How far the backfill has got across the ~1,250 Blu-ray and 4K discs, and its spend."""
    state = await get_state(db)
    counts = await coverage(db)
    run = await latest_run(db)
    return SpecBackfillResponse(
        searchConfigured=bool(settings.brave_search_api_key),
        halted=state.halted,
        haltedReason=state.halted_reason,
        coverage=SpecCoverageResponse(
            discs=counts.discs,
            withSpecs=counts.with_specs,
            accepted=counts.accepted,
            needsYou=counts.needs_you,
            noMatch=counts.no_match,
            skipped=counts.skipped,
            notSearched=counts.not_searched,
        ),
        run=_run_response(run) if run else None,
        searchesThisMonth=await searches_this_month(db, now=utcnow()),
        monthlyCeiling=MONTHLY_SEARCH_CEILING,
        searchesPerRun=SEARCHES_PER_RUN,
        fetchesPerRun=FETCHES_PER_RUN,
    )


@router.get("/specs/queue", response_model=SpecQueueResponse)
async def read_queue(
    _user: AdminUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SpecQueueResponse:
    """Discs waiting for Craig to pick a page, paste one, or skip."""
    entries, total = await queue(db, limit=limit)
    return SpecQueueResponse(
        items=[
            SpecQueueItemResponse(
                lookupId=entry.lookup.id,
                collectionItemId=entry.item.id,
                movieId=entry.movie.id,
                filmTitle=entry.movie.title,
                year=entry.movie.year,
                formatCode=entry.format_code,
                location=entry.item.location,
                status="no_match" if entry.lookup.status == "no_match" else "needs_you",
                note=entry.lookup.note,
                searchQuery=entry.lookup.search_query,
                candidates=[
                    SpecCandidateResponse(
                        url=candidate.url,
                        title=candidate.title,
                        country=candidate.country,
                        edition=candidate.edition,
                        matches=candidate.matches,
                        origin="restored" if candidate.origin == "restored" else "search",
                    )
                    for candidate in entry.candidates
                ],
            )
            for entry in entries
        ],
        total=total,
    )


@router.post("/specs/queue/{lookup_id}/accept", response_model=SpecDecisionResponse)
async def accept_queued_page(
    lookup_id: uuid.UUID, payload: SpecAcceptRequest, user: AdminUser, db: Database
) -> SpecDecisionResponse:
    """Craig's choice of page for one disc. Nothing is fetched now: the next batch does it."""
    try:
        lookup = await accept_page(db, lookup_id, payload.url, by=user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except QueueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _decision(lookup)


@router.post("/specs/queue/{lookup_id}/skip", response_model=SpecDecisionResponse)
async def skip_queued_disc(
    lookup_id: uuid.UUID, user: AdminUser, db: Database
) -> SpecDecisionResponse:
    """No specs for this disc."""
    try:
        lookup = await skip_disc(db, lookup_id, by=user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except QueueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _decision(lookup)


@router.post("/specs/backfill/run", response_model=SpecBackfillStartResponse)
async def run_backfill_now(
    user: AdminUser, db: Database, background_tasks: BackgroundTasks
) -> SpecBackfillStartResponse:
    """One batch now, rather than tonight: the same budgets, rules and halt as the job.

    Claimed before the response, so ``started`` means this batch exists. It then searches
    and fetches after the response, which can take a quarter of an hour.
    """
    outcome = await start_run(
        db,
        trigger="admin",
        search_configured=bool(settings.brave_search_api_key),
        started_by=user.id,
    )
    if outcome.run is not None:
        background_tasks.add_task(continue_run_in_background, outcome.run.id)
    return SpecBackfillStartResponse(
        outcome=outcome.reason,
        run=_run_response(outcome.run) if outcome.run else None,
    )
