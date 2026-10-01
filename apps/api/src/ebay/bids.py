"""Auctions in a Browse payload — Batch V6, snag 2's first step.

The valuation's search names no buying option, and that returns Buy It Now listings: the
captured Blade Runner 2049 search (`tests/fixtures/ebay_browse_blade_runner_2049.json`)
holds one auction among 200 listings, and that one has a Buy It Now price too. Asking for
:data:`BUY_IT_NOW_AND_AUCTIONS` brings auctions into the same 200 results, at no extra call.

This module reads what an auction adds, in one place, as :mod:`~src.ebay.matching` reads the
rest of a listing:

- ``bidCount``: whether anyone has bid. With no bids, ``currentBidPrice`` is the seller's
  opening price, which says no more than an asking price does.
- ``currentBidPrice``: the highest bid so far. It is below the final price until the last
  minutes of an auction, which is why the trial counts how many end within a day.
- ``itemEndDate``: when the auction ends.

An auction's current bid becomes its :class:`~src.ebay.matching.Listing`'s ``price``, so the
same matcher judges it and the same median prices it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .matching import Listing, listing_from_summary

#: Browse's ``filter`` for Buy It Now and auctions in one search (snag 2's "with no extra
#: eBay calls"). The deal scan already sends a ``buyingOptions`` filter live (#218).
BUY_IT_NOW_AND_AUCTIONS = "buyingOptions:{FIXED_PRICE|AUCTION}"

BUY_IT_NOW = "FIXED_PRICE"
AUCTION = "AUCTION"


def buying_options(summary: dict[str, object]) -> frozenset[str]:
    """The listing's buying options, empty when the payload names none."""
    options = summary.get("buyingOptions")
    if not isinstance(options, list):
        return frozenset()
    return frozenset(option for option in options if isinstance(option, str))


def offers_buy_it_now(summary: dict[str, object]) -> bool:
    """A listing with a Buy It Now price: what the valuation's own search returns."""
    return BUY_IT_NOW in buying_options(summary)


@dataclass(frozen=True)
class Auction:
    """One auction, its current bid as the listing's price."""

    listing: Listing
    bid_count: int
    #: Naive UTC, as every timestamp here. ``None`` when the payload gives no end date.
    ends_utc: datetime | None


def _end_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment


def auction_from_summary(summary: dict[str, object]) -> Auction | None:
    """The auction in an ``itemSummaries`` entry, or ``None``.

    ``None`` when the listing is not an auction, or carries no usable current bid. An
    auction with no bids is still returned: whether it counts is the caller's rule, and
    the trial reports how many had none.
    """
    if AUCTION not in buying_options(summary):
        return None
    bid_count = summary.get("bidCount")
    if not isinstance(bid_count, int) or isinstance(bid_count, bool):
        bid_count = 0
    current_bid = summary.get("currentBidPrice")
    if not isinstance(current_bid, dict):
        return None
    # The current bid stands in for the price, so the listing is judged and priced on it.
    listing = listing_from_summary({**summary, "price": current_bid})
    if listing is None:
        return None
    return Auction(
        listing=listing, bid_count=bid_count, ends_utc=_end_date(summary.get("itemEndDate"))
    )
