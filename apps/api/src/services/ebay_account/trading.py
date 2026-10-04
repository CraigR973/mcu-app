"""Reading a person's watch list and selling list from eBay — Batch T8b, #216, #245.

eBay's Trading API, from its reference (version 1477, read 4 Oct 2026): ``POST
https://api.ebay.com/ws/api.dll`` with the person's OAuth token in ``X-EBAY-API-IAF-TOKEN``
and three more headers naming the call, the site (3, the UK) and the compatibility level.
It answers in XML, read with ``defusedxml`` (`DECISIONS.md` #245).

- ``GetMyeBayBuying``: the ``WatchList`` and the ``FavoriteSearches`` (saved searches).
- ``GetMyeBaySelling``: the ``ActiveList`` and the ``SoldList``.
- ``GetUser``: the account's name, read for display and never stored.

**Only what the lists show is read.** A sold item's buyer (name, email, postcode) is in the
same document and is never touched: nothing here looks under ``Buyer``. Nor are listing
photos: the web app's content security policy allows images from TMDB alone, so a
thumbnail from eBay's image host would never load (T8a's pages show none either).

**Built from eBay's documented shapes, not a capture.** eBay prints sample responses on each
call's page, and the fixtures are those, made well-formed; no real response could be read
before a person had connected. The first live connection is where these parsers meet a real
answer (`STATUS.md`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlsplit
from xml.etree.ElementTree import Element

import httpx
import structlog
from defusedxml import ElementTree as SafeXml
from defusedxml.common import DefusedXmlException

logger = structlog.get_logger(__name__)

TRADING_URL = "https://api.ebay.com/ws/api.dll"
COMPATIBILITY_LEVEL = "1477"
#: eBay's numeric code for its UK site.
SITE_ID_UK = "3"
NS = "urn:ebay:apis:eBLBaseComponents"
TIMEOUT = 25.0
#: One page of each list: plenty for two people's eBay, and one request per list.
ENTRIES_PER_PAGE = 100
#: How far back the sold list goes.
SOLD_DAYS = 60

#: eBay's error codes for a user token it will not accept (the "Errors by Number" index).
TOKEN_ERROR_CODES = frozenset({"931", "932", "21916984", "21917053"})


class TradingError(RuntimeError):
    """eBay answered a list request with a failure, or could not be reached."""

    def __init__(self, message: str, *, token_rejected: bool = False) -> None:
        super().__init__(message)
        self.token_rejected = token_rejected


@dataclass(frozen=True)
class Listing:
    """One listing as a list shows it."""

    item_id: str
    title: str
    url: str
    price: Decimal | None
    currency: str | None
    postage: Decimal | None = None
    is_auction: bool = False
    bid_count: int | None = None
    ends_at: datetime | None = None


@dataclass(frozen=True)
class SavedSearch:
    name: str
    keywords: str | None
    url: str | None


@dataclass(frozen=True)
class Sold:
    item_id: str
    title: str
    url: str
    price: Decimal | None
    currency: str | None
    sold_at: datetime | None


@dataclass
class Watching:
    items: list[Listing] = field(default_factory=list)
    saved_searches: list[SavedSearch] = field(default_factory=list)
    total_items: int = 0


@dataclass
class Selling:
    active: list[Listing] = field(default_factory=list)
    sold: list[Sold] = field(default_factory=list)
    total_active: int = 0
    total_sold: int = 0


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


def _pagination() -> str:
    return (
        f"<Pagination><EntriesPerPage>{ENTRIES_PER_PAGE}</EntriesPerPage>"
        "<PageNumber>1</PageNumber></Pagination>"
    )


def buying_request() -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<GetMyeBayBuyingRequest xmlns="{NS}">'
        f"<WatchList><Include>true</Include>{_pagination()}</WatchList>"
        "<FavoriteSearches><Include>true</Include></FavoriteSearches>"
        "</GetMyeBayBuyingRequest>"
    )


def selling_request() -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<GetMyeBaySellingRequest xmlns="{NS}">'
        f"<ActiveList><Include>true</Include>{_pagination()}</ActiveList>"
        f"<SoldList><Include>true</Include><DurationInDays>{SOLD_DAYS}</DurationInDays>"
        f"{_pagination()}</SoldList>"
        "</GetMyeBaySellingRequest>"
    )


def user_request() -> str:
    return f'<?xml version="1.0" encoding="utf-8"?><GetUserRequest xmlns="{NS}"/>'


async def call(client: httpx.AsyncClient, token: str, name: str, body: str) -> Element:
    """One Trading API call. Returns the parsed response, or raises :class:`TradingError`."""
    try:
        response = await client.post(
            TRADING_URL,
            content=body.encode("utf-8"),
            headers={
                "X-EBAY-API-IAF-TOKEN": token,
                "X-EBAY-API-CALL-NAME": name,
                "X-EBAY-API-SITEID": SITE_ID_UK,
                "X-EBAY-API-COMPATIBILITY-LEVEL": COMPATIBILITY_LEVEL,
                "Content-Type": "text/xml",
            },
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise TradingError(f"eBay could not be reached ({type(exc).__name__})") from exc
    if response.status_code == 401:
        raise TradingError("eBay did not accept the sign-in (HTTP 401)", token_rejected=True)
    if response.status_code != 200:
        raise TradingError(f"eBay answered {name} with HTTP {response.status_code}")
    root = parse(response.content)
    ack = _text(root, "Ack")
    if ack not in ("Success", "Warning"):
        codes = [_text(error, "ErrorCode") or "" for error in _all(root, "Errors")]
        message = next(
            (
                _text(error, "LongMessage") or _text(error, "ShortMessage")
                for error in _all(root, "Errors")
                if _text(error, "LongMessage") or _text(error, "ShortMessage")
            ),
            None,
        )
        logger.warning("ebay_trading_failed", call=name, ack=ack, codes=codes)
        raise TradingError(
            f"eBay refused {name}: {message or 'no reason given'}"
            + (f" (error {', '.join(code for code in codes if code)})" if any(codes) else ""),
            token_rejected=any(code in TOKEN_ERROR_CODES for code in codes),
        )
    return root


def parse(content: bytes) -> Element:
    """eBay's XML, with entity expansion and external entities refused."""
    try:
        return SafeXml.fromstring(content)
    except (DefusedXmlException, SafeXml.ParseError) as exc:
        raise TradingError(f"eBay's answer could not be read ({type(exc).__name__})") from exc


# ---------------------------------------------------------------------------
# Reading the answers
# ---------------------------------------------------------------------------


def _q(path: str) -> str:
    return "/".join(f"{{{NS}}}{part}" for part in path.split("/"))


def _one(element: Element | None, path: str) -> Element | None:
    return None if element is None else element.find(_q(path))


def _all(element: Element | None, path: str) -> list[Element]:
    return [] if element is None else element.findall(_q(path))


def _text(element: Element | None, path: str) -> str | None:
    found = _one(element, path)
    text = found.text.strip() if found is not None and found.text else ""
    return text or None


def _money(element: Element | None, path: str) -> tuple[Decimal | None, str | None]:
    found = _one(element, path)
    if found is None or not found.text:
        return None, None
    try:
        amount = Decimal(found.text.strip())
    except InvalidOperation:
        return None, None
    return amount, found.get("currencyID")


def _int(element: Element | None, path: str) -> int | None:
    text = _text(element, path)
    try:
        return int(text) if text is not None else None
    except ValueError:
        return None


def _when(element: Element | None, path: str) -> datetime | None:
    """eBay's ISO time, as the app's naive UTC."""
    text = _text(element, path)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def item_url(item_id: str) -> str:
    """eBay UK's own page for a listing: what the app links to, whatever eBay's answer says."""
    return f"https://www.ebay.co.uk/itm/{item_id}"


def _listing(item: Element) -> Listing | None:
    item_id = _text(item, "ItemID")
    title = _text(item, "Title")
    if not item_id or not title:
        return None
    price, currency = _money(item, "SellingStatus/CurrentPrice")
    if price is None:
        price, currency = _money(item, "BuyItNowPrice")
    postage, _ = _money(item, "ShippingDetails/ShippingServiceOptions/ShippingServiceCost")
    return Listing(
        item_id=item_id,
        title=title,
        url=item_url(item_id),
        price=price,
        currency=currency,
        postage=postage,
        is_auction=_text(item, "ListingType") in ("Chinese", "Auction"),
        bid_count=_int(item, "SellingStatus/BidCount"),
        ends_at=_when(item, "ListingDetails/EndTime"),
    )


def _listings(items: Iterable[Element]) -> list[Listing]:
    return [listing for listing in (_listing(item) for item in items) if listing is not None]


def _keywords(search: Element) -> str | None:
    """A saved search's words: eBay's own field, or the ``_nkw`` of its search address."""
    keywords = _text(search, "QueryKeywords")
    if keywords:
        return keywords
    query = _text(search, "SearchQuery")
    if query and query.startswith("http"):
        words = parse_qs(urlsplit(query).query).get("_nkw")
        if words:
            return words[0].strip() or None
    return None


def _saved_search(search: Element) -> SavedSearch:
    keywords = _keywords(search)
    query = _text(search, "SearchQuery")
    return SavedSearch(
        name=_text(search, "SearchName") or keywords or "Saved search",
        keywords=keywords,
        url=query if query and query.startswith("https://") else None,
    )


def read_watching(root: Element) -> Watching:
    watch = _one(root, "WatchList")
    searches = [_saved_search(search) for search in _all(root, "FavoriteSearches/FavoriteSearch")]
    items = _listings(_all(watch, "ItemArray/Item"))
    return Watching(
        items=items,
        saved_searches=searches,
        total_items=_int(watch, "PaginationResult/TotalNumberOfEntries") or len(items),
    )


def _sold(transaction: Element) -> Sold | None:
    item = _one(transaction, "Item")
    item_id = _text(item, "ItemID")
    title = _text(item, "Title")
    if item is None or not item_id or not title:
        return None
    price, currency = _money(transaction, "TransactionPrice")
    if price is None:
        price, currency = _money(item, "SellingStatus/CurrentPrice")
    return Sold(
        item_id=item_id,
        title=title,
        url=item_url(item_id),
        price=price,
        currency=currency,
        sold_at=_when(transaction, "CreatedDate") or _when(transaction, "PaidTime"),
    )


def read_selling(root: Element) -> Selling:
    active = _one(root, "ActiveList")
    sold_list = _one(root, "SoldList")
    transactions = _all(sold_list, "OrderTransactionArray/OrderTransaction/Transaction") + _all(
        sold_list, "OrderTransactionArray/OrderTransaction/Order/TransactionArray/Transaction"
    )
    active_items = _listings(_all(active, "ItemArray/Item"))
    sold = [entry for entry in (_sold(transaction) for transaction in transactions) if entry]
    return Selling(
        active=active_items,
        sold=sold,
        total_active=_int(active, "PaginationResult/TotalNumberOfEntries") or len(active_items),
        total_sold=_int(sold_list, "PaginationResult/TotalNumberOfEntries") or len(sold),
    )


def read_user_id(root: Element) -> str | None:
    return _text(root, "User/UserID")


async def watching(client: httpx.AsyncClient, token: str) -> Watching:
    return read_watching(await call(client, token, "GetMyeBayBuying", buying_request()))


async def selling(client: httpx.AsyncClient, token: str) -> Selling:
    return read_selling(await call(client, token, "GetMyeBaySelling", selling_request()))


async def user_id(client: httpx.AsyncClient, token: str) -> str | None:
    return read_user_id(await call(client, token, "GetUser", user_request()))
