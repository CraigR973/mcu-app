"""The collection's value at current eBay asking prices — Batch T6, snag 7.

Two routes. Reading the total is for both people and spends nothing. Starting a run is
admin-only, because it spends a share of the eBay allowance the film page's checks also
use; the share, the one-at-a-time claim and the monthly clock all live in
``services/valuation.py``, so the button cannot spend more than a scheduled run would.

Batch V6 adds the bid trial's two, both admin-only: starting one spends the same share, and
its report is Craig's to read before he picks a blend or bids only (#228).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AdminUser, CurrentUser
from src.clock import utcnow
from src.database import get_db
from src.ebay.client import EbayClient
from src.ebay.estimate import sold_listings_url
from src.ebay.pricing import AS_USED_COPIES, ASKING_PRICES, MIN_SAMPLE
from src.models.valuation import DiscValuation, ValuationRun
from src.schemas.bid_trial import BidTrialReport, BidTrialResponse, BidTrialStartResponse
from src.schemas.valuation import (
    CollectionValueResponse,
    CopyValuationResponse,
    RunStatus,
    UsedSalesRunResponse,
    UsedSalesStartResponse,
    ValuationRunResponse,
    ValuationStartResponse,
)
from src.services.bid_trial import (
    ENDING_SOON,
    SAMPLE_SIZE,
    continue_trial_in_background,
    latest_trial,
    start_trial,
)
from src.services.ebay_sold import budget_left as sales_budget_left
from src.services.ebay_sold import continue_admin_run
from src.services.ebay_sold import latest_run as latest_sales_run
from src.services.ebay_sold import start_run as start_sales_run
from src.services.valuation import (
    CURRENCY,
    DAILY_SHARE,
    abandon_stale_runs,
    collection_value,
    continue_run_in_background,
    start_run,
)

router = APIRouter(prefix="/api/v1", tags=["valuation"])

# Not imported from ``routers.movies``, which imports :func:`copy_valuation` from here.
Database = Annotated[AsyncSession, Depends(get_db)]

#: The column's values, typed. The table's CHECK constraint allows exactly these.
_RUN_STATUSES: dict[str, RunStatus] = {
    "running": "running",
    "finished": "finished",
    "budget_spent": "budget_spent",
    "stopped": "stopped",
    "abandoned": "abandoned",
}


def value_basis(
    stored: str | None,
) -> Literal["used", "used_quartile", "new_scaled", "sales"] | None:
    """The column's value, typed. The table's CHECK constraint allows exactly these."""
    if stored == "used":
        return "used"
    if stored == "used_quartile":
        return "used_quartile"
    if stored == "sales":
        return "sales"
    return "new_scaled" if stored == "new_scaled" else None


def run_response(run: ValuationRun) -> ValuationRunResponse:
    return ValuationRunResponse(
        id=run.id,
        trigger="admin" if run.trigger == "admin" else "job",
        status=_RUN_STATUSES[run.status],
        startedAt=run.started_utc,
        finishedAt=run.finished_utc,
        budget=run.budget,
        calls=run.calls,
        priced=run.priced,
        notPriced=run.not_priced,
        failed=run.failed,
        remaining=run.remaining,
        lastError=run.last_error,
    )


def sales_run_response(run: object) -> UsedSalesRunResponse:
    from src.models.ebay_sold import EbayUsedRun

    assert isinstance(run, EbayUsedRun)
    return UsedSalesRunResponse(
        status=_RUN_STATUSES[run.status],
        trigger="admin" if run.trigger == "admin" else "job",
        startedAt=run.started_utc,
        finishedAt=run.finished_utc,
        budget=run.budget,
        calls=run.calls,
        searched=run.searched,
        checked=run.checked,
        sold=run.sold,
        ended=run.ended,
        lastError=run.last_error,
    )


def trial_response(run: ValuationRun) -> BidTrialResponse:
    return BidTrialResponse(
        id=run.id,
        status=_RUN_STATUSES[run.status],
        startedAt=run.started_utc,
        finishedAt=run.finished_utc,
        budget=run.budget,
        calls=run.calls,
        failed=run.failed,
        lastError=run.last_error,
        sampleSize=SAMPLE_SIZE,
        minSample=MIN_SAMPLE,
        endingWindowHours=int(ENDING_SOON.total_seconds() // 3600),
        dailyShare=DAILY_SHARE,
        currency=CURRENCY,
        report=BidTrialReport.model_validate(run.report) if run.report is not None else None,
    )


def _money(amount: Decimal | None) -> str | None:
    return str(amount) if amount is not None else None


def copy_valuation(valuation: DiscValuation) -> CopyValuationResponse:
    sales = valuation.sales_backed
    return CopyValuationResponse(
        formatCode=valuation.format_code,
        status="priced" if valuation.status == "priced" or sales else "not_priced",
        price=_money(valuation.effective_price),
        currency=valuation.currency,
        sampleSize=valuation.sales_count if sales else valuation.sample_size,
        conditionLabel="Used" if sales else valuation.condition_label,
        checkedAt=valuation.sales_checked_utc if sales else valuation.checked_utc,
        basis="observed sold listings" if sales else valuation.basis,
        minSample=MIN_SAMPLE,
        valueBasis=value_basis("sales" if sales else valuation.value_basis),
        factor=None if sales else _money(valuation.factor),
        low=_money(valuation.sales_low if sales else valuation.low),
        high=_money(valuation.sales_high if sales else valuation.high),
        usedCount=valuation.used_count or 0,
        newCount=valuation.new_count or 0,
        valuedAs=AS_USED_COPIES,
        soldListingsUrl=sold_listings_url(valuation.search_query),
    )


@router.get("/collection/value", response_model=CollectionValueResponse)
async def get_collection_value(_user: CurrentUser, db: Database) -> CollectionValueResponse:
    """Every owned physical disc at its stored price, and how many have one."""
    value = await collection_value(db)
    sales_run = await latest_sales_run(db)
    return CollectionValueResponse(
        total=str(value.total) if value.total is not None else None,
        currency=CURRENCY,
        basis="observed sales where available; current asking prices otherwise"
        if value.sales_backed
        else ASKING_PRICES,
        valuedAs=AS_USED_COPIES,
        discs=value.discs,
        pricedDiscs=value.priced,
        salesBackedDiscs=value.sales_backed,
        notPricedDiscs=value.not_priced,
        uncheckedDiscs=value.unchecked,
        checkedFrom=value.checked_from,
        checkedTo=value.checked_to,
        due=value.due,
        budgetLeft=value.budget_left,
        dailyShare=DAILY_SHARE,
        minSample=MIN_SAMPLE,
        run=run_response(value.latest_run) if value.latest_run else None,
        salesRun=sales_run_response(sales_run) if sales_run else None,
        salesBudgetLeft=await sales_budget_left(db, now=utcnow()),
    )


@router.post("/collection/value/sales/refresh", response_model=UsedSalesStartResponse)
async def refresh_used_sales(
    _user: AdminUser, db: Database, background_tasks: BackgroundTasks
) -> UsedSalesStartResponse:
    """Craig starts the first live pass; subsequent passes run in the existing eBay job."""
    _require_ebay()
    reason, run = await start_sales_run(db, trigger="admin")
    if run is not None:
        background_tasks.add_task(continue_admin_run, run.id)
    return UsedSalesStartResponse(
        outcome=reason,
        run=sales_run_response(run) if run else None,
    )


def _require_ebay() -> None:
    if not EbayClient().configured:
        # Refused before a run row exists, rather than recorded as a run that stopped at
        # once: the missing keyset is the deployment's problem, not the run's.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="eBay is not configured in this deployment.",
        )


@router.post("/collection/value/refresh", response_model=ValuationStartResponse)
async def refresh_collection_value(
    user: AdminUser, db: Database, background_tasks: BackgroundTasks
) -> ValuationStartResponse:
    """Start pricing the films that are due, within today's share, after the response.

    The run is claimed before the response, so the answer is definite: ``started`` means a
    run exists and is this one. Anything else starts nothing and spends nothing.
    """
    _require_ebay()
    outcome = await start_run(db, trigger="admin", started_by=user.id)
    if outcome.run is not None:
        background_tasks.add_task(continue_run_in_background, outcome.run.id)
    return ValuationStartResponse(
        outcome=outcome.reason,
        run=run_response(outcome.run) if outcome.run else None,
        due=outcome.due,
        budgetLeft=outcome.budget_left,
    )


@router.get("/collection/value/bid-trial", response_model=BidTrialResponse | None)
async def get_bid_trial(_admin: AdminUser, db: Database) -> BidTrialResponse | None:
    """The latest bid trial and its report, finished or not; null before the first."""
    await abandon_stale_runs(db, now=utcnow())
    run = await latest_trial(db)
    return trial_response(run) if run is not None else None


@router.post("/collection/value/bid-trial", response_model=BidTrialStartResponse)
async def start_bid_trial(
    user: AdminUser, db: Database, background_tasks: BackgroundTasks
) -> BidTrialStartResponse:
    """Start a bid trial within today's share, after the response. It saves no prices."""
    _require_ebay()
    outcome = await start_trial(db, started_by=user.id)
    if outcome.run is not None:
        background_tasks.add_task(continue_trial_in_background, outcome.run.id)
    return BidTrialStartResponse(
        outcome=outcome.reason,
        trial=trial_response(outcome.run) if outcome.run is not None else None,
        sampled=outcome.sampled,
        budgetLeft=outcome.budget_left,
    )
