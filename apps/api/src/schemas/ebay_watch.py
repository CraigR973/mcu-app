"""Wire models for eBay price alerts — Batch T8a. Money travels as strings, as elsewhere."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime

FormatCode = Literal["4k_uhd", "blu_ray", "dvd"]
#: A target in pounds and pence, above nothing and below an absurd price.
Price = Annotated[
    Decimal, Field(gt=Decimal("0"), le=Decimal("99999.99"), max_digits=7, decimal_places=2)
]


class EbayTargetResponse(BaseModel):
    id: uuid.UUID
    kind: Literal["listing", "search"]
    status: Literal["watching", "met", "ended"]
    #: The listing's title, or the film's for a saved search.
    title: str
    movieId: uuid.UUID | None
    formatCode: FormatCode | None
    targetPrice: str
    currency: str
    #: The listing's page, for a listing target.
    url: str | None
    imageUrl: str | None
    #: An auction with no Buy It Now: the price is the current bid.
    isAuction: bool
    #: What the last check found: the listing's price or bid, or for a saved search the
    #: cheapest matching UK Buy It Now listing, with its page.
    currentPrice: str | None
    currentPostage: str | None
    currentUrl: str | None
    endsAt: UtcDatetime | None
    lastCheckedAt: UtcDatetime | None
    metAt: UtcDatetime | None
    lastError: str | None
    createdAt: UtcDatetime


class EbayWatchRunResponse(BaseModel):
    """The latest scheduled pass, so the page can say when targets were last checked."""

    status: Literal["running", "finished", "budget_spent", "stopped", "abandoned"]
    startedAt: UtcDatetime
    finishedAt: UtcDatetime | None
    targetsChecked: int = Field(ge=0)
    dealsFound: int = Field(ge=0)
    #: Batch X2 (UX48-02): the new listings this pass read, and how many passes in a row,
    #: this one included, read none. Price alerts said "Last check 19:20" through 45 blind
    #: passes; now it says "read 0 new listings, 33 checks in a row".
    listingsSeen: int = Field(default=0, ge=0)
    emptyInARow: int = Field(default=0, ge=0)


class EbayTargetsResponse(BaseModel):
    items: list[EbayTargetResponse]
    #: Null until the first scheduled pass: the schedule starts with Craig's config apply.
    lastRun: EbayWatchRunResponse | None


class ListingTargetRequest(BaseModel):
    #: The listing's web address, as copied.
    address: str = Field(min_length=1, max_length=2000)
    targetPrice: Price


class SearchTargetRequest(BaseModel):
    movieId: uuid.UUID
    formatCode: FormatCode
    targetPrice: Price


class TargetPriceRequest(BaseModel):
    targetPrice: Price
