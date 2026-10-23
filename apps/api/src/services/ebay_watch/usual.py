"""Shop price alert comparisons and the earlier eBay-find yardstick.

AA10b's eBay deal scan uses the disc's used figure in :mod:`scan`, not ``UsualPrice``.
``shop_usual`` still gives a wanted shop listing a like-for-like New asking reference.
The old ``UsualPrice`` and condition yardstick remain available for that earlier rule and
its regression tests; a shop's price can only lower the reference.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ebay.matching import classify_edition
from src.ebay.pricing import NEW_CONDITION_ID
from src.models.price_check import PriceCheck
from src.models.wanted import WantedItem
from src.services.ebay_watch.refs import Yardstick, stored_ref, yardstick
from src.services.scraping.extract import primary_format

#: How old a shop's price may be: the nightly check's last week.
SHOP_WINDOW = timedelta(days=7)

#: What the Deals page calls eBay's part of the figure.
EBAY_SOURCE = "eBay"


@dataclass(frozen=True)
class ShopPrice:
    """One shop's latest price for the film on the format."""

    retailer: str
    price: Decimal


@dataclass(frozen=True)
class UsualPrice:
    """eBay's figure and the shops' prices behind a find's "usually"."""

    ebay: Yardstick
    shops: tuple[ShopPrice, ...] = ()

    @property
    def amount(self) -> Decimal:
        """eBay's figure, lowered to the cheapest shop's price when that is less."""
        lowest = min([self.ebay.median, *(shop.price for shop in self.shops)])
        return lowest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def sources(self) -> list[dict[str, str]]:
        """Where the figure comes from, eBay first, as the Deals page lists it."""
        return [
            {"source": EBAY_SOURCE, "price": str(self.ebay.median)},
            *({"source": shop.retailer, "price": str(shop.price)} for shop in self.shops),
        ]


async def shop_prices(
    db: AsyncSession, *, movie_id: uuid.UUID, format_code: str, now: datetime
) -> tuple[ShopPrice, ...]:
    """Each shop's latest like-for-like price for the film on the format, this past week."""
    rows = (
        await db.execute(
            select(
                PriceCheck.retailer_name_snapshot,
                PriceCheck.price,
                PriceCheck.title_snapshot,
                PriceCheck.url,
            )
            .join(WantedItem, WantedItem.id == PriceCheck.wanted_id)
            .where(
                WantedItem.movie_id == movie_id,
                PriceCheck.checked_at >= now - SHOP_WINDOW,
                PriceCheck.currency == "GBP",
            )
            .order_by(PriceCheck.checked_at.desc())
        )
    ).all()

    latest: dict[str, ShopPrice] = {}
    for retailer, price, title, url in rows:
        # Newest first, so the first that qualifies for a shop is its latest.
        if retailer in latest:
            continue
        if primary_format(title, url) != format_code:
            continue
        if classify_edition(title or "") != "standard":
            continue
        latest[retailer] = ShopPrice(retailer, price)
    return tuple(sorted(latest.values(), key=lambda shop: shop.retailer))


async def shop_usual(
    db: AsyncSession, *, movie_id: uuid.UUID, title: str | None, url: str | None, now: datetime
) -> Yardstick | None:
    """What a shop's listing of the film is judged against when its want has no price limit.

    Batch X11 (MK47-05). The usual for **the format the listing is** (read off its title and
    address, as the nightly check reads it), as a New copy's, since a shop sells new ones.
    A limited or other non-standard edition has no like-for-like usual, and a film with no
    stored fresh figure for that format has none either: nothing here asks eBay, so the shop
    check makes no new calls to it.
    """
    format_code = primary_format(title, url)
    if format_code is None or classify_edition(title or "") != "standard":
        return None
    ref = await stored_ref(db, movie_id=movie_id, format_code=format_code, now=now)
    if ref is None:
        return None
    return yardstick(ref, NEW_CONDITION_ID)
