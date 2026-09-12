"""The deals feed — Batch 22, phases 5.9 and 5.10.

**§5.9's acceptance is a live third-party run, and therefore the owner's.**
`docs/agent-commands/group-start.md` puts scraper runs against real retailers in their
hands, exactly as Batch 19's checkpoint and Batch 23's §3.7 were. `POST /deals/scrape`
exists, is tested against fixtures, and is invoked by a person.

The response to that run is shaped to be **checked against the criterion rather than
believed**: it reports rows written, retailers that produced any, and how many were
skipped as already owned — which are the criterion's own three numbers.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from src.auth import AdminUser, CurrentUser
from src.clock import utcnow
from src.models.deal import Deal
from src.models.movie import Movie
from src.routers.movies import Database
from src.schemas.deals import (
    DealDismissRequest,
    DealListResponse,
    DealResponse,
    DealsRunResponse,
    RetailerDealsOutcomeResponse,
)
from src.services.audit import record_action
from src.services.scraping.deals_runner import run_deals_scrape

router = APIRouter(prefix="/api/v1", tags=["deals"])

logger = structlog.get_logger()

#: One page of the feed. Generous because a sale is a browsing surface rather than a
#: search result, and the whole point is to scroll it.
DEFAULT_LIMIT = 60
MAX_LIMIT = 200


def _genres(movie: Movie | None) -> list[str]:
    if movie is None or not movie.genres:
        return []
    return [str(entry.get("name")) for entry in movie.genres if entry.get("name")]


def _to_response(deal: Deal, movie: Movie | None) -> DealResponse:
    return DealResponse(
        id=deal.id,
        retailer=deal.retailer_name_snapshot,
        title=deal.title_snapshot,
        url=deal.url,
        imageUrl=deal.image_url,
        formatCode=deal.format_code,
        price=str(deal.price),
        wasPrice=str(deal.was_price) if deal.was_price is not None else None,
        currency=deal.currency,
        discountPercent=deal.discount_percent,
        movieId=deal.movie_id,
        tmdbId=deal.tmdb_id,
        posterPath=movie.poster_path if movie else None,
        genres=_genres(movie),
        firstSeenAt=deal.first_seen_at_utc,
        lastSeenAt=deal.last_seen_at_utc,
    )


@router.get("/deals", response_model=DealListResponse)
async def list_deals(
    _user: CurrentUser,
    db: Database,
    retailer: Annotated[str | None, Query()] = None,
    genre: Annotated[str | None, Query()] = None,
    format_code: Annotated[str | None, Query(alias="formatCode")] = None,
    min_discount: Annotated[int | None, Query(alias="minDiscount", ge=0, le=99)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> DealListResponse:
    """§5.10's filters: genre, discount %, retailer, format.

    **Dismissed deals are excluded and there is no way to ask for them.** §5.10's
    acceptance is *"dismissed items don't reappear"*, and an `includeDismissed` flag
    would be a way for them to. Putting one back is
    `POST /deals/{id}/dismiss {"dismissed": false}` — an act, not a view.

    Genre is filtered in Python rather than in SQL. `movies.genres` is a JSONB array of
    objects, and the containment query that would do this in Postgres needs a GIN index
    this table has no other use for — against a feed capped at 200 rows, the join is
    already the expensive part.
    """
    rows = (
        await db.execute(
            select(Deal, Movie)
            .outerjoin(Movie, Movie.id == Deal.movie_id)
            .where(Deal.dismissed_at_utc.is_(None))
            .order_by(Deal.discount_percent.desc().nullslast(), Deal.last_seen_at_utc.desc())
            .limit(MAX_LIMIT)
        )
    ).all()

    # The unfiltered vocabulary, so the filter controls can offer only what is there.
    all_retailers = sorted({deal.retailer_name_snapshot for deal, _ in rows})
    all_genres = sorted({name for _, movie in rows for name in _genres(movie)})

    items: list[DealResponse] = []
    for deal, movie in rows:
        if retailer and deal.retailer_name_snapshot != retailer:
            continue
        if format_code and deal.format_code != format_code:
            continue
        if min_discount is not None and (deal.discount_percent or 0) < min_discount:
            continue
        if genre and genre not in _genres(movie):
            continue
        items.append(_to_response(deal, movie))

    return DealListResponse(
        items=items[:limit],
        total=len(items),
        retailers=all_retailers,
        genres=all_genres,
    )


@router.post("/deals/{deal_id}/dismiss", response_model=DealResponse)
async def dismiss_deal(
    deal_id: uuid.UUID,
    payload: DealDismissRequest,
    user: AdminUser,
    db: Database,
) -> DealResponse:
    """§5.10's one-tap dismiss — and its undo.

    **A soft state, not a delete.** Tonight's scrape will re-find the same deal on the
    same URL, so "doesn't reappear" has to be something the row remembers; a deleted row
    would simply be re-created. `deals_runner._upsert` preserves this column for exactly
    that reason.
    """
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    deal.dismissed_at_utc = utcnow() if payload.dismissed else None
    deal.dismissed_by = user.id if payload.dismissed else None
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table="deals",
        target_id=deal.id,
        changes={"dismissed": payload.dismissed, "title": deal.title_snapshot},
    )
    await db.commit()
    await db.refresh(deal)

    movie = await db.get(Movie, deal.movie_id) if deal.movie_id else None
    return _to_response(deal, movie)


@router.post("/deals/scrape", response_model=DealsRunResponse)
async def scrape_deals(
    _user: AdminUser,
    db: Database,
    dry_run: Annotated[bool, Query(alias="dryRun")] = True,
) -> DealsRunResponse:
    """§5.9's run. **Dry by default, because this hits real shops.**

    The same default `POST /scrapers/run` carries, for the same reason: a live run against
    somebody else's website is something a person should have to ask for twice.

    The response carries the criterion's own three numbers — rows written, retailers that
    produced any, and how many were skipped as already owned — so the acceptance can be
    read off it rather than inferred.
    """
    summary = await run_deals_scrape(db, dry_run=dry_run)
    logger.info(
        "deals_run_complete",
        dry_run=dry_run,
        written=summary.written,
        retailers=summary.retailers_with_deals,
        skipped_owned=summary.skipped_owned,
    )
    return DealsRunResponse(
        dryRun=dry_run,
        written=summary.written,
        retailersWithDeals=summary.retailers_with_deals,
        skippedOwned=summary.skipped_owned,
        outcomes=[
            RetailerDealsOutcomeResponse(
                retailer=outcome.retailer,
                ok=outcome.ok,
                found=outcome.found,
                kept=outcome.kept,
                skippedOwned=outcome.skipped_owned,
                rejected=outcome.rejected,
                matched=outcome.matched,
                pageReasons=outcome.page_reasons,
                error=outcome.error,
            )
            for outcome in summary.outcomes
        ],
    )


@router.get("/deals/count", response_model=dict[str, int])
async def deals_count(_user: CurrentUser, db: Database) -> dict[str, int]:
    """How many live deals there are, for the nav badge."""
    total = await db.scalar(select(func.count(Deal.id)).where(Deal.dismissed_at_utc.is_(None)))
    return {"count": int(total or 0)}
