""" "Connect eBay" and a person's own eBay lists — Batch T8b, `DECISIONS.md` #216, #245.

**Every route is the signed-in person's own.** Each person connects their own eBay (#245),
so every route here is ``CurrentUser`` and reads or changes only that person's row: there
is no route that names another profile, and so none that could show one person's eBay to
the other.

The flow: Settings asks ``POST /ebay/account/connect`` for eBay's consent address and goes
there; eBay sends the person back to the web app's ``/settings/ebay/connected`` with a code
and the state, which that page hands to ``POST /ebay/account/complete`` with the person's
own session (#227). Nothing reaches the API from eBay directly.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.auth import CurrentUser
from src.clock import utcnow
from src.models.ebay_account import EbayAccount
from src.routers.movies import Database
from src.schemas.ebay_account import (
    EbayAccountResponse,
    EbayConnectFinishRequest,
    EbayConnectStartResponse,
    EbayListingResponse,
    EbaySavedSearchResponse,
    EbaySellingResponse,
    EbaySoldResponse,
    EbayWatchingResponse,
)
from src.services.ebay_account import accounts, oauth, trading
from src.services.ebay_account.crypto import TokenKeyInvalid, TokenKeyMissing

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ebay-account"])


def get_ebay_http() -> Callable[[], httpx.AsyncClient]:
    """A factory for the client that talks to eBay. Tests replace it with a mock transport."""
    return httpx.AsyncClient


EbayHttp = Annotated[Callable[[], httpx.AsyncClient], Depends(get_ebay_http)]


def _money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


def _listing(item: trading.Listing) -> EbayListingResponse:
    return EbayListingResponse(
        itemId=item.item_id,
        title=item.title,
        url=item.url,
        price=_money(item.price),
        currency=item.currency,
        postage=_money(item.postage),
        isAuction=item.is_auction,
        bidCount=item.bid_count,
        endsAt=item.ends_at,
    )


def _account(
    account: EbayAccount | None, *, name: str | None = None, note: str | None = None
) -> EbayAccountResponse:
    missing = oauth.missing_settings()
    return EbayAccountResponse(
        configured=not missing,
        missing=missing,
        connected=account is not None,
        accountName=name if account is not None else None,
        connectedAt=account.connected_utc if account is not None else None,
        note=note,
    )


def _refuse(exc: Exception) -> HTTPException:
    """Each failure as the person should read it. Never a token, never eBay's raw body."""
    if isinstance(exc, oauth.EbayConnectNotConfigured | TokenKeyMissing | TokenKeyInvalid):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, accounts.ConnectError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, accounts.NotConnected):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, oauth.EbayAuthError | trading.TradingError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    raise exc  # pragma: no cover - only the failures above are passed here


@router.get("/ebay/account", response_model=EbayAccountResponse)
async def get_account(user: CurrentUser, db: Database, http: EbayHttp) -> EbayAccountResponse:
    """This person's connection, with the account's name read live from eBay."""
    account = await accounts.get_account(db, user.id)
    if account is None:
        return _account(None)
    try:
        async with http() as client:
            name = await accounts.account_name(db, account, client, now=utcnow())
    except accounts.NotConnected as exc:
        return _account(None, note=str(exc))
    except (TokenKeyMissing, TokenKeyInvalid) as exc:
        return _account(account, note=str(exc))
    return _account(account, name=name)


@router.post("/ebay/account/connect", response_model=EbayConnectStartResponse)
async def start_connect(user: CurrentUser, db: Database) -> EbayConnectStartResponse:
    """Begin connecting: a one-time state, and eBay's consent address to go to."""
    try:
        url = await accounts.start(db, user.id, now=utcnow())
    except (oauth.EbayConnectNotConfigured, TokenKeyMissing, TokenKeyInvalid) as exc:
        raise _refuse(exc) from exc
    return EbayConnectStartResponse(authorizeUrl=url)


@router.post("/ebay/account/complete", response_model=EbayAccountResponse)
async def finish_connect(
    payload: EbayConnectFinishRequest, user: CurrentUser, db: Database, http: EbayHttp
) -> EbayAccountResponse:
    """Finish a sign-in this person started, with the code eBay sent them back with."""
    try:
        async with http() as client:
            account = await accounts.finish(
                db, user.id, code=payload.code, state=payload.state, client=client, now=utcnow()
            )
            name = await accounts.account_name(db, account, client, now=utcnow())
    except (
        oauth.EbayConnectNotConfigured,
        TokenKeyMissing,
        TokenKeyInvalid,
        accounts.ConnectError,
        accounts.NotConnected,
        oauth.EbayAuthError,
    ) as exc:
        raise _refuse(exc) from exc
    return _account(account, name=name)


@router.delete("/ebay/account", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(user: CurrentUser, db: Database) -> Response:
    """Delete this person's eBay tokens. Removing the app's access on eBay is theirs to do."""
    await accounts.disconnect(db, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ebay/account/watching", response_model=EbayWatchingResponse)
async def watching(user: CurrentUser, db: Database, http: EbayHttp) -> EbayWatchingResponse:
    """This person's watch list and saved searches, read from eBay now."""
    try:
        async with http() as client:
            result = await accounts.read(db, user.id, client, trading.watching, now=utcnow())
    except (
        accounts.NotConnected,
        oauth.EbayAuthError,
        trading.TradingError,
        TokenKeyMissing,
        TokenKeyInvalid,
    ) as exc:
        raise _refuse(exc) from exc
    return EbayWatchingResponse(
        items=[_listing(item) for item in result.items],
        savedSearches=[
            EbaySavedSearchResponse(name=search.name, keywords=search.keywords, url=search.url)
            for search in result.saved_searches
        ],
        totalItems=result.total_items,
        fetchedAt=utcnow(),
    )


@router.get("/ebay/account/selling", response_model=EbaySellingResponse)
async def selling(user: CurrentUser, db: Database, http: EbayHttp) -> EbaySellingResponse:
    """This person's listings for sale and their last 60 days of sales, read from eBay now."""
    try:
        async with http() as client:
            result = await accounts.read(db, user.id, client, trading.selling, now=utcnow())
    except (
        accounts.NotConnected,
        oauth.EbayAuthError,
        trading.TradingError,
        TokenKeyMissing,
        TokenKeyInvalid,
    ) as exc:
        raise _refuse(exc) from exc
    return EbaySellingResponse(
        active=[_listing(item) for item in result.active],
        sold=[
            EbaySoldResponse(
                itemId=sold.item_id,
                title=sold.title,
                url=sold.url,
                price=_money(sold.price),
                currency=sold.currency,
                soldAt=sold.sold_at,
            )
            for sold in result.sold
        ],
        totalActive=result.total_active,
        totalSold=result.total_sold,
        fetchedAt=utcnow(),
    )
