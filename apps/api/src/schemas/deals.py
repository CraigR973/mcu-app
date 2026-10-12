"""Wire models for the deals feed — Batch 22, phases 5.9 and 5.10.

camelCase written directly, no envelope — `DECISIONS.md` #6. Money is a string, as
everywhere else here: a price must not round-trip through a float.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.wire import UtcDatetime


class UsualSourceResponse(BaseModel):
    """One part of an eBay find's usual price (Batch V8): eBay's figure, or a shop's."""

    source: str
    price: str


class DealResponse(BaseModel):
    """One discounted disc.

    **`discountPercent` is arithmetic on the two prices, never a number read off the
    page.** The batch's risk note is that a layout change stores a plausible wrong
    discount; a figure derived from two prices that each passed a shape check cannot be a
    "save 70%" banner that happened to match a selector.
    """

    id: uuid.UUID
    retailer: str
    title: str
    url: str
    imageUrl: str | None = None
    formatCode: str | None = None
    price: str
    wasPrice: str | None = None
    currency: str
    discountPercent: int | None = None
    #: Null when the title matched no catalogued film. An unmatched deal is **kept** —
    #: it is the evidence the matcher needs work, and hiding it would make a broken
    #: matcher look like a quiet sale page.
    movieId: uuid.UUID | None = None
    tmdbId: int | None = None
    posterPath: str | None = None
    genres: list[str] = Field(default_factory=list)
    #: How long it has been on offer, and whether it was still there at the last run.
    firstSeenAt: UtcDatetime
    lastSeenAt: UtcDatetime
    #: Batch V8, eBay finds only. ``wasPrice`` is the find's usual price: eBay's figure
    #: (asking prices, before postage), lowered to the cheapest shop's recent price when a
    #: New listing's is less (Batch X1). These are the parts, eBay first. Null for a
    #: retailer's own deal.
    usualSources: list[UsualSourceResponse] | None = None
    #: eBay's own sold listings for the film and format, to open in the person's browser.
    soldListingsUrl: str | None = None
    #: Batch X1, eBay finds only: the listing's own condition ("Very good"), and how many
    #: asking prices stand behind ``wasPrice``. Null for a shop's deal, for an eBay find
    #: stored before X1, and (the condition) once a find has expired.
    condition: str | None = None
    usualListings: int | None = None


class DealListResponse(BaseModel):
    items: list[DealResponse]
    total: int = Field(ge=0)
    #: Every retailer and genre present in the *unfiltered* feed, so §5.10's filters can
    #: be populated without a second request and without offering a filter that matches
    #: nothing.
    retailers: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)


class RetailerDealsOutcomeResponse(BaseModel):
    retailer: str
    ok: bool
    found: int
    kept: int
    skippedOwned: int
    rejected: int
    matched: int
    #: Batch 22b. Cards on the sale page at a single price: listed, not discounted, and
    #: counted apart from `rejected`, which is a card that failed a check.
    notDiscounted: int = 0
    #: Why the page as a whole was refused. A page-level failure discards every card, so
    #: this is what separates "a quiet sale" from "the selectors have moved".
    pageReasons: list[str] = Field(default_factory=list)
    #: Why the first few rejected cards were rejected (Batch 22b).
    rejectedReasons: list[str] = Field(default_factory=list)
    error: str | None = None


class DealsRunResponse(BaseModel):
    """§5.9's acceptance, as numbers somebody can check against the criterion."""

    dryRun: bool
    #: "populates the `deals` table with ≥ 20 rows"
    written: int
    #: "from ≥ 3 retailers"
    retailersWithDeals: int
    #: "skip already-owned verified against the real `collection_items` table"
    skippedOwned: int
    outcomes: list[RetailerDealsOutcomeResponse]


class DealDismissRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: False puts a dismissed deal back, because a mis-tap should not be permanent.
    dismissed: bool = True
