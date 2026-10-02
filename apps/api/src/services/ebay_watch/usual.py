"""What "usually" means on an eBay find — Batch V8, snag 1.

Before V8 it was eBay's figure alone: the median asking price of matching UK Buy It Now
listings (:mod:`refs`). Craig's answer to snag 1 (`DECISIONS.md` #228) was to average it
with the shops' prices, and V7 being shelved (#237) leaves eBay's figure on asking prices.

**The shops' part is thin by design.** The nightly check asks every watched shop about the
Wanted list and nothing else, so a shop price exists only for a Wanted film. Asking the
shops about every eBay find would multiply requests to the three that answer ``429``
(Batch 20b). Most finds are upgrades on owned films, which no shop is asked about, and for
those "usually" stays eBay's figure.

**Like for like, as eBay's figure is.** A shop's price counts only when it is the same
format (read off the listing it priced, as the nightly check reads it) and a standard
edition (by the eBay matcher's own rule), from the last seven days, the latest per shop.
A £49.99 limited edition averaged into a standard disc's usual price would make an ordinary
listing look like a deal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ebay.matching import classify_edition
from src.models.price_check import PriceCheck
from src.models.wanted import WantedItem
from src.services.ebay_watch.refs import Yardstick
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
        """The average of eBay's figure and each shop's price: eBay's alone with none."""
        prices = [self.ebay.median, *(shop.price for shop in self.shops)]
        average = sum(prices, Decimal(0)) / len(prices)
        return average.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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
