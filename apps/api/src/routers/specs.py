"""Disc specs from Blu-ray.com — §3.7.

**Every route is admin-only, and the fetching one makes live third-party requests.**
`DECISIONS.md` #110 is a risk acceptance the owner made, not a permission the site granted,
and `docs/agent-commands/group-start.md` puts live third-party runs in the owner's hands.
So this endpoint exists, is tested against fixture HTML, and is invoked by a person.
"""

from __future__ import annotations

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from src.auth import AdminUser
from src.clock import utcnow
from src.models.collection_item import CollectionItem
from src.routers.movies import Database
from src.schemas.specs import SpecsFetchRequest, SpecsRunResponse, SpecsStateResponse
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
    source URL and is left alone.
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
