"""eBay price alerts — Batch T8a, `DECISIONS.md` #203 and #216.

**Both people set their own, and each sees only their own.** A target is a person's
standing request to be told about a price, and the push goes to them alone. Mark asked for
this (snag 8), and he is not an admin, so every route here is ``CurrentUser``.

Setting a target on a listing reads the listing from eBay once (one call of the day's
allowance, as the film page's "What is it worth?" is). A saved search costs nothing until
the next scheduled pass searches for it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.clock import utcnow
from src.ebay.client import EbayClient, EbayError, EbayNotConfigured
from src.models.ebay_watch import EbayTarget, EbayWatchRun
from src.models.movie import Movie
from src.routers.movies import Database
from src.schemas.ebay_watch import (
    EbayTargetResponse,
    EbayTargetsResponse,
    EbayWatchRunResponse,
    ListingTargetRequest,
    SearchTargetRequest,
    TargetPriceRequest,
)
from src.services.ebay_watch.runs import latest_run
from src.services.ebay_watch.targets import (
    PENNY,
    TargetError,
    create_listing_target,
    create_search_target,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ebay-watch"])


def get_ebay_client_factory() -> Callable[[], AbstractAsyncContextManager[Any]]:
    """How a request opens an eBay client. Tests replace it with a scripted eBay."""
    return EbayClient


EbayClientFactory = Annotated[
    Callable[[], AbstractAsyncContextManager[Any]], Depends(get_ebay_client_factory)
]


def _money(value: object) -> str | None:
    return None if value is None else str(value)


def _target(target: EbayTarget) -> EbayTargetResponse:
    return EbayTargetResponse(
        id=target.id,
        kind="search" if target.kind == "search" else "listing",
        status=target.status,
        title=target.title,
        movieId=target.movie_id,
        formatCode=target.format_code,
        targetPrice=str(target.target_price),
        currency=target.currency,
        url=target.url,
        imageUrl=target.image_url,
        isAuction=target.is_auction,
        currentPrice=_money(target.current_price),
        currentPostage=_money(target.current_postage),
        currentUrl=target.current_url,
        endsAt=target.ends_at_utc,
        lastCheckedAt=target.last_checked_utc,
        metAt=target.met_at_utc,
        lastError=target.last_error,
        createdAt=target.created_at_utc,
    )


def _run(run: EbayWatchRun, empty_in_a_row: int) -> EbayWatchRunResponse:
    return EbayWatchRunResponse(
        status=run.status,
        startedAt=run.started_utc,
        finishedAt=run.finished_utc,
        targetsChecked=run.targets_checked,
        dealsFound=run.deals_found,
        listingsSeen=run.listings_seen,
        emptyInARow=empty_in_a_row,
    )


#: How far back "in a row" counts: two days of two-hourly passes, plenty to say "many".
EMPTY_RUNS_LOOKED_AT = 48


async def _empty_in_a_row(db: AsyncSession) -> int:
    """Passes in a row, newest first, that read no new listing (Batch X2)."""
    seen = (
        await db.scalars(
            select(EbayWatchRun.listings_seen)
            .where(EbayWatchRun.status != "running")
            .order_by(EbayWatchRun.started_utc.desc())
            .limit(EMPTY_RUNS_LOOKED_AT)
        )
    ).all()
    count = 0
    for listings in seen:
        if listings:
            break
        count += 1
    return count


async def _own_target(db: AsyncSession, target_id: uuid.UUID, user_id: uuid.UUID) -> EbayTarget:
    target = await db.get(EbayTarget, target_id)
    if target is None or target.deleted_at is not None or target.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price alert not found")
    return target


def _refuse(exc: TargetError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/ebay/targets", response_model=EbayTargetsResponse)
async def list_targets(
    user: CurrentUser,
    db: Database,
    movie_id: Annotated[uuid.UUID | None, Query(alias="movieId")] = None,
) -> EbayTargetsResponse:
    """The signed-in person's price alerts, watching ones first, and the latest pass."""
    query = select(EbayTarget).where(
        EbayTarget.owner_id == user.id, EbayTarget.deleted_at.is_(None)
    )
    if movie_id is not None:
        query = query.where(EbayTarget.movie_id == movie_id)
    order = case({"watching": 0, "met": 1}, value=EbayTarget.status, else_=2)
    targets = (await db.scalars(query.order_by(order, EbayTarget.created_at_utc.desc()))).all()
    run = await latest_run(db)
    return EbayTargetsResponse(
        items=[_target(target) for target in targets],
        lastRun=_run(run, await _empty_in_a_row(db)) if run else None,
    )


@router.post(
    "/ebay/targets/listing",
    response_model=EbayTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_listing_target(
    payload: ListingTargetRequest,
    user: CurrentUser,
    db: Database,
    open_client: EbayClientFactory,
) -> EbayTargetResponse:
    """A price alert on one eBay listing, from its web address. One eBay call."""
    try:
        async with open_client() as client:
            target = await create_listing_target(
                db,
                client,
                owner_id=user.id,
                address=payload.address,
                target_price=payload.targetPrice,
                now=utcnow(),
            )
    except TargetError as exc:
        await db.rollback()
        raise _refuse(exc) from exc
    except EbayNotConfigured as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="eBay is not configured in this deployment.",
        ) from exc
    except EbayError as exc:
        await db.rollback()
        logger.warning("ebay_listing_target_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="eBay did not answer."
        ) from exc
    await db.commit()
    return _target(target)


@router.post(
    "/ebay/targets/search",
    response_model=EbayTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_search_target(
    payload: SearchTargetRequest, user: CurrentUser, db: Database
) -> EbayTargetResponse:
    """A price alert on any UK Buy It Now listing of a film on a format. No eBay call."""
    movie = await db.get(Movie, payload.movieId)
    if movie is None or movie.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Film not found")
    try:
        target = await create_search_target(
            db,
            owner_id=user.id,
            movie=movie,
            format_code=payload.formatCode,
            target_price=payload.targetPrice,
            now=utcnow(),
        )
    except TargetError as exc:
        await db.rollback()
        raise _refuse(exc) from exc
    await db.commit()
    return _target(target)


@router.patch("/ebay/targets/{target_id}", response_model=EbayTargetResponse)
async def change_target(
    target_id: uuid.UUID, payload: TargetPriceRequest, user: CurrentUser, db: Database
) -> EbayTargetResponse:
    """A new target price. A listing already met is watched again, and may alert again."""
    target = await _own_target(db, target_id, user.id)
    target.target_price = payload.targetPrice.quantize(PENNY)
    if target.status == "met":
        target.status = "watching"
        target.met_at_utc = None
    await db.commit()
    return _target(target)


@router.delete("/ebay/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_target(target_id: uuid.UUID, user: CurrentUser, db: Database) -> Response:
    target = await _own_target(db, target_id, user.id)
    target.deleted_at = utcnow()
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
