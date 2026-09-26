"""Reading eBay's listing payloads for price targets and the deal scan — Batch T8a.

Two shapes, both read in one place each, as ``matching.listing_from_summary`` reads the
search summaries the estimator judges:

- :func:`item_state` reads ``get_item_by_legacy_id``: one listing, with its Buy It Now
  price, its current bid if it is an auction, its postage and when it ends.
- :func:`scan_listing` reads one ``itemSummaries`` entry of the newest-first search: the
  estimator's :class:`~src.ebay.matching.Listing`, plus when it was listed, its postage and
  whether it can be bought outright.

**Postage is part of the price.** A £2 disc with £9 postage is not a bargain, so every
comparison here is on what the buyer pays. The usual asking price it is compared with is
the film page's median, which leaves postage out, so the comparison errs towards "not a
deal".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from src.ebay.matching import Listing, listing_from_summary
from src.services.ebay_watch.links import listing_url

#: eBay's word for a listing with nothing left to sell.
OUT_OF_STOCK = "OUT_OF_STOCK"


def _money(value: object) -> Decimal | None:
    if not isinstance(value, dict):
        return None
    amount = value.get("value")
    if not isinstance(amount, str):
        return None
    try:
        return Decimal(amount)
    except (InvalidOperation, ValueError):
        return None


def _currency(*values: object) -> str | None:
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("currency"), str):
            return str(value["currency"])
    return None


def parse_utc(value: object) -> datetime | None:
    """eBay's ``2026-10-03T09:06:39.000Z`` as the naive UTC the database keeps."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        return None


def postage(payload: dict[str, Any]) -> Decimal | None:
    """The first shipping option's cost, or ``None`` when eBay did not state one."""
    options = payload.get("shippingOptions")
    if not isinstance(options, list) or not options or not isinstance(options[0], dict):
        return None
    return _money(options[0].get("shippingCost"))


def _image(payload: dict[str, Any]) -> str | None:
    image = payload.get("image")
    url = image.get("imageUrl") if isinstance(image, dict) else None
    return url if isinstance(url, str) else None


@dataclass(frozen=True)
class ItemState:
    """One listing as it stands now."""

    legacy_id: str
    title: str
    url: str
    image_url: str | None
    currency: str
    #: The Buy It Now price, when the listing has one.
    buy_now: Decimal | None
    #: The current bid (the opening price before anyone bids), when it is an auction.
    current_bid: Decimal | None
    postage: Decimal | None
    ends_at: datetime | None
    #: False once eBay says nothing is left to sell.
    available: bool
    country: str | None

    @property
    def is_auction_only(self) -> bool:
        return self.buy_now is None and self.current_bid is not None

    def total(self, price: Decimal) -> Decimal:
        return price + (self.postage or Decimal("0"))


def item_state(payload: dict[str, Any]) -> ItemState | None:
    """Read ``get_item_by_legacy_id``'s answer, or ``None`` if it is not a usable listing."""
    legacy_id = payload.get("legacyItemId")
    title = payload.get("title")
    if not isinstance(legacy_id, str) or not isinstance(title, str):
        return None
    options = payload.get("buyingOptions")
    options = [str(option) for option in options] if isinstance(options, list) else []
    price = _money(payload.get("price"))
    bid = _money(payload.get("currentBidPrice"))
    buy_now = price if "FIXED_PRICE" in options else None
    current_bid = bid if bid is not None else (price if "AUCTION" in options else None)
    if "AUCTION" not in options:
        current_bid = None
    currency = _currency(payload.get("price"), payload.get("currentBidPrice"))
    if (buy_now is None and current_bid is None) or currency is None:
        return None
    availability = payload.get("estimatedAvailabilities")
    status = (
        availability[0].get("estimatedAvailabilityStatus")
        if isinstance(availability, list) and availability and isinstance(availability[0], dict)
        else None
    )
    location = payload.get("itemLocation")
    return ItemState(
        legacy_id=legacy_id,
        title=title,
        url=listing_url(legacy_id),
        image_url=_image(payload),
        currency=currency,
        buy_now=buy_now,
        current_bid=current_bid,
        postage=postage(payload),
        ends_at=parse_utc(payload.get("itemEndDate")),
        available=status != OUT_OF_STOCK,
        country=location.get("country") if isinstance(location, dict) else None,
    )


@dataclass(frozen=True)
class ScanListing:
    """One of the newest UK listings, as the deal scan needs it."""

    listing: Listing
    legacy_id: str
    listed_at: datetime | None
    postage: Decimal | None
    image_url: str | None
    #: It can be bought outright. The scan asks eBay for these only, but says so here too.
    buy_now: bool

    @property
    def url(self) -> str:
        return listing_url(self.legacy_id)

    @property
    def total(self) -> Decimal:
        return self.listing.price + (self.postage or Decimal("0"))


def scan_listing(summary: dict[str, Any]) -> ScanListing | None:
    """Read one newest-first search result, or ``None`` if it is not a usable listing."""
    listing = listing_from_summary(summary)
    legacy_id = summary.get("legacyItemId")
    if listing is None or not isinstance(legacy_id, str):
        return None
    options = summary.get("buyingOptions")
    return ScanListing(
        listing=listing,
        legacy_id=legacy_id,
        listed_at=parse_utc(summary.get("itemCreationDate")),
        postage=postage(summary),
        image_url=_image(summary),
        buy_now=isinstance(options, list) and "FIXED_PRICE" in options,
    )
