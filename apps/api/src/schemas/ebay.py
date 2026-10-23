"""Wire models for the eBay integration — Batch 28, phases 4.1 and 4.3.

camelCase written directly, no envelope, no alias generator — `DECISIONS.md` #6.

**Every money field is a string**, matching the rest of this API: a price is money and
must not round-trip through a float. `DECISIONS.md` #6's zod-schema rule applies too, so
these ship with matching parsers in `packages/shared`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

FormatCode = Literal["4k_uhd", "blu_ray", "dvd", "download"]
Edition = Literal["standard", "collector"]


class PriceSegmentResponse(BaseModel):
    """One comparable group of current listings.

    **`sampleSize` is not optional and never will be.** A median over three listings and a
    median over sixty look identical on a card, and `DECISIONS.md` #129 is an account of a
    number that looked perfectly reasonable and was 149% high. The UI is required to show
    this beside the price.
    """

    formatCode: str
    edition: Edition
    #: eBay's numeric condition code — the only stable key. `condition` is a *localised
    #: display string*: #129 found 16 distinct values for about five real conditions, in
    #: three languages, in one result set. `"unknown"` is its own bucket, never a default.
    conditionId: str
    #: The English label for `conditionId`, resolved by us rather than taken from eBay.
    conditionLabel: str
    sampleSize: int = Field(ge=0)
    median: str
    low: str
    high: str
    currency: str


class UsedValueResponse(BaseModel):
    """What one disc on the shelf is worth as a used copy — Batch X6 (#256).

    ``basis`` says how: ``used``, the median of ``sampleSize`` used listings; ``new_scaled``,
    New's median of ``sampleSize`` listings times ``factor``, the used-to-New ratio measured
    for the format, because used listings were too few. ``low`` and ``high`` are the range of
    those listings before any factor.
    """

    price: str
    currency: str
    basis: Literal["used_quartile", "new_scaled"]
    sampleSize: int = Field(gt=0)
    low: str
    high: str
    #: Null unless ``basis`` is ``new_scaled``.
    factor: str | None
    #: "as used copies": the words every surface shows beside the value.
    valuedAs: str


class PriceEstimateResponse(BaseModel):
    """What a title is currently being *asked* for on eBay UK — Phase 4.1.

    Never what it sold for. Marketplace Insights is closed to new applicants and eBay put
    sold listings behind a login wall in late August 2026, so sold comps are unobtainable
    (`DECISIONS.md` #16, re-confirmed by #126). `basis` carries the exact words every
    surface must show.
    """

    filmTitle: str
    formatCode: str | None
    marketplaceId: str
    #: How many listings the search returned, before any of them were judged.
    considered: int = Field(ge=0)
    #: How many survived the match filter and are behind the segments below.
    matched: int = Field(ge=0)
    segments: list[PriceSegmentResponse]
    #: The single segment to show, when there is one: standard edition, requested format,
    #: largest sample. Null when nothing matched — which is an answer, not an error.
    headline: PriceSegmentResponse | None
    #: Why the rest were rejected, by reason and count. **Part of the answer, not
    #: diagnostics**: a search that matched 4 of 200 is either a rare disc or a broken
    #: filter, and this is what tells the two apart (`DECISIONS.md` #122).
    rejected: dict[str, Annotated[int, Field(ge=0)]]
    #: Entries that were not the shape the Browse API documents. Counted apart from
    #: rejections because a rise here means eBay changed its response.
    unusable: int = Field(ge=0)
    #: Always "current asking prices".
    basis: str
    #: Batch X6: the disc's value as a used copy, for the requested format (or the
    #: headline's). Null when too few used and too few New listings matched.
    usedValue: UsedValueResponse | None = None


class PriceEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The film's title, used both to build the search and to match what comes back. Not a
    #: free-text query: the match filter needs to know what it is looking for.
    filmTitle: str = Field(min_length=1, max_length=200)
    #: Narrow to one disc format. Null considers every format and returns a segment per
    #: format, which is what the "what is this worth?" surface wants on first open.
    formatCode: FormatCode | None = None
    #: Restrict to sellers in this country. `"GB"` by default because the criterion asks
    #: for a *UK* median and eBay GB converts an overseas price into GBP without saying
    #: what the import duty will be — 52 of 200 Blade Runner listings ship from abroad.
    #: Null considers every country.
    country: str | None = Field(default="GB", max_length=2)
    #: Batch X6: the title is a TV series, so "Complete Series" and "Season" listings are it
    #: rather than another product. The film's own ``mediaType`` is ``tv``.
    isSeries: bool = False


class ListingUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filmTitle: str = Field(min_length=1, max_length=200)
    year: int | None = Field(default=None, ge=1880, le=2200)
    formatCode: FormatCode | None = None
    condition: Literal["new", "like_new", "good", "acceptable", "damaged"] | None = None
    #: As on :class:`PriceEstimateRequest`.
    isSeries: bool = False


class ListingUrlResponse(BaseModel):
    """A link that opens eBay's "start your listing" form with the title filled in.

    **Nothing is created by asking for this.** Phase 4.3's Option A — a Sell API draft —
    does not exist as described, so the app never holds a selling credential and never
    creates a live listing; the admin opens this link signed in as themselves and
    publishes from eBay. `DECISIONS.md` #142.
    """

    url: str
    #: The title that was packed into the link, within eBay's 80-character limit.
    suggestedTitle: str
    #: What to ask, when a price estimate was available — the disc's value as a used copy
    #: (Batch X6), unshaded. Null when too few listings matched.
    suggestedPrice: str | None
