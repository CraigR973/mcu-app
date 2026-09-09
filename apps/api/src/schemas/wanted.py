"""Wire models for the wanted list and retailers — Batch 18, §3.5, §3.16, §5.1, §5.2."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.wire import UtcDatetime


def _validate_max_price(value: str | None) -> str | None:
    """A price threshold, as a decimal string.

    A plain function reused by both request models rather than a validator borrowed from
    one class into the other. The borrowing form needs a ``type: ignore[attr-defined]``,
    and `STATUS.md` gotcha 21 is the standing record of what an ignore costs here: mypy is
    unpinned, so CI's version and this machine's disagree about whether it is *used*, and
    ``warn_unused_ignores`` turns that disagreement into a red gate. It did, once, in this
    same session.
    """
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("maxPrice must be a decimal number") from exc
    # `Decimal("NaN")` **parses**, and then every comparison against it raises
    # `InvalidOperation` — so the guard below would have been the thing that 500'd, not the
    # parse. Found by this batch's security review. `"Infinity"` is finite-checked by the
    # same call.
    if not parsed.is_finite():
        raise ValueError("maxPrice must be a real number")
    if parsed <= 0:
        raise ValueError("maxPrice must be greater than zero")
    if parsed >= Decimal("1000000"):
        raise ValueError("maxPrice is implausibly large")
    return value


FormatCode = Literal["4k_uhd", "blu_ray", "dvd", "download"]
ScraperType = Literal["built_in", "generic_css", "custom"]
ScrapeFrequency = Literal["daily", "weekly", "manual"]


class WantedCreateRequest(BaseModel):
    """Add a film to the wanted list — §5.1.

    Either a ``movieId`` for something already catalogued, or a ``tmdbId`` for something
    that is not. The second is what makes §11.2's "bulk add missing to wanted list" and
    §7.2's recommendation cards work at all: **the whole point of wanting a film is that
    you do not own it**, so requiring it to exist in `movies` first would exclude every
    realistic case.
    """

    model_config = ConfigDict(extra="forbid")

    movieId: uuid.UUID | None = None
    tmdbId: Annotated[int | None, Field(gt=0)] = None
    preferredFormat: FormatCode | None = None
    #: A string on the wire, like `purchasePrice`. Money must not round-trip through a
    #: float — this value is the threshold Batch 20's alerts compare against, and a float
    #: compares wrongly at exactly the boundary someone cared about.
    maxPrice: Annotated[str | None, Field(max_length=12)] = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GBP"
    notes: str | None = None

    @field_validator("maxPrice")
    @classmethod
    def _check_price(cls, value: str | None) -> str | None:
        return _validate_max_price(value)


class WantedUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferredFormat: FormatCode | None = None
    maxPrice: Annotated[str | None, Field(max_length=12)] = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GBP"
    isActive: bool = True
    notes: str | None = None

    @field_validator("maxPrice")
    @classmethod
    def _check_price(cls, value: str | None) -> str | None:
        return _validate_max_price(value)


class WantedItemResponse(BaseModel):
    id: uuid.UUID
    movieId: uuid.UUID
    movieTitle: str
    year: int | None
    posterPath: str | None
    preferredFormat: str | None
    maxPrice: str | None
    currency: str
    isActive: bool
    notes: str | None
    #: True when a live disc of this film is already on the shelf. Wanting something you
    #: own is not an error — an upgrade from DVD to 4K is exactly that — so it is
    #: surfaced rather than refused.
    ownedAlready: bool
    addedAt: UtcDatetime


class WantedListResponse(BaseModel):
    items: list[WantedItemResponse]
    total: int
    activeCount: int


class RetailerFieldsMixin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=100)]
    #: Validated for scheme here as well as by a CHECK. This URL is fetched by a
    #: background job, so a `file:` or `gopher:` value would be a request the server makes
    #: on someone else's behalf.
    baseUrl: Annotated[str, Field(min_length=1, max_length=2000)]
    dealsUrl: Annotated[str | None, Field(max_length=2000)] = None
    searchUrlTemplate: Annotated[str | None, Field(max_length=2000)] = None
    scraperType: ScraperType = "generic_css"
    scraperConfig: dict[str, Any] = {}
    scrapeFrequency: ScrapeFrequency = "weekly"
    enabled: bool = True
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GBP"
    region: Annotated[str, Field(pattern=r"^[A-Z]{2}$")] = "GB"
    notes: str | None = None

    @field_validator("baseUrl", "dealsUrl", "searchUrlTemplate")
    @classmethod
    def _http_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if not candidate.lower().startswith(("http://", "https://")):
            raise ValueError("URLs must start with http:// or https://")
        return candidate


class RetailerCreateRequest(RetailerFieldsMixin):
    pass


class RetailerUpdateRequest(RetailerFieldsMixin):
    pass


class RetailerResponse(BaseModel):
    id: uuid.UUID
    name: str
    baseUrl: str
    dealsUrl: str | None
    searchUrlTemplate: str | None
    scraperType: ScraperType
    scraperConfig: dict[str, Any]
    scrapeFrequency: ScrapeFrequency
    enabled: bool
    currency: str
    region: str
    notes: str | None
    lastScrapedAt: UtcDatetime | None
    lastScrapeStatus: str | None
    lastScrapeError: str | None
    consecutiveFailures: int
    #: False until Batch 19 gives this retailer selectors. Surfaced so the settings page
    #: can say "not configured" instead of implying a scraper exists for it.
    isConfigured: bool
    addedAt: UtcDatetime


class RetailerListResponse(BaseModel):
    items: list[RetailerResponse]
    total: int
    enabledCount: int
    #: How many have selectors. Zero on day one, and saying so is the honest version of
    #: §5.2's "seeded default retailers".
    configuredCount: int


class RetailerSeedResponse(BaseModel):
    created: int
    existing: int
    names: list[str]


# ---------------------------------------------------------------------------
# Scraping (Batch 19) — §5.3, §5.4
# ---------------------------------------------------------------------------


class ScraperTestRequest(BaseModel):
    """§5.4's "test scraper" — run selectors against a page and show what they matched.

    **This makes the server fetch a URL a person typed**, which is why `services/scraping/
    fetcher.py` resolves the host and refuses anything not publicly routable. Admin-only,
    but the realistic risk is a paste or a typo reaching the container's own loopback
    interface, not malice.
    """

    model_config = ConfigDict(extra="forbid")

    url: Annotated[str, Field(min_length=1, max_length=2000)]
    scraperConfig: dict[str, Any]
    #: Optional: when given, the shape check can also say whether the page is about the
    #: right film, which is the failure that otherwise looks completely normal.
    expectedTitle: Annotated[str | None, Field(max_length=500)] = None
    expectedCurrency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GBP"

    @field_validator("url")
    @classmethod
    def _http_only_url(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate.lower().startswith(("http://", "https://")):
            raise ValueError("URLs must start with http:// or https://")
        return candidate


class ScraperTestResponse(BaseModel):
    """What the selectors matched, and whether it looks like a price.

    ``ok`` is **not** "the request succeeded" — it is "this looks like a real price for
    this film". A page that fetched perfectly and yielded a plausible-looking wrong number
    reports ``ok: false`` with the reason, which is the entire point of §5.4 existing
    before a retailer is enabled.
    """

    fetched: bool
    finalUrl: str | None
    title: str | None
    rawPriceText: str | None
    price: str | None
    currency: str | None
    listingUrl: str | None
    ok: bool
    reasons: list[str]
    error: str | None


class ScrapeOutcomeResponse(BaseModel):
    retailer: str
    wantedTitle: str
    ok: bool
    price: str | None
    #: The currency `price` was read in. Never converted, so a report showing the number
    #: must show this beside it rather than assuming pounds.
    currency: str | None
    url: str | None
    reasons: list[str]
    error: str | None


class ScrapeRunResponse(BaseModel):
    outcomes: list[ScrapeOutcomeResponse]
    succeeded: int
    failed: int
    written: int
    #: Retailers switched off by this run, after three consecutive failures.
    disabled: list[str]
    dryRun: bool


class BuiltInScraperResponse(BaseModel):
    name: str
    searchUrlTemplate: str
    scraperConfig: dict[str, Any]
    #: True only after a permitted live check. Until then a selector is a guess, and the
    #: honest state of a guess is "unverified".
    verified: bool
    note: str | None


class BuiltInScraperListResponse(BaseModel):
    items: list[BuiltInScraperResponse]
    unverified: list[str]
