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
    #: Which edition within that format — "Arte Originale Slipcover", "Steelbook". Free
    #: text: boutique edition names are invented per release (`DECISIONS.md` #104). It
    #: never narrows the search, only which listing on the page gets priced.
    preferredEdition: Annotated[str | None, Field(max_length=100)] = None
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
    #: Which edition within that format — "Arte Originale Slipcover", "Steelbook". Free
    #: text: boutique edition names are invented per release (`DECISIONS.md` #104). It
    #: never narrows the search, only which listing on the page gets priced.
    preferredEdition: Annotated[str | None, Field(max_length=100)] = None
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
    preferredEdition: str | None
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

    #: May be a **search template** rather than a finished URL — ``{query}`` and
    #: ``{format}`` are substituted server-side, by the same function a real run uses.
    #: The browser must not do this itself: when it replaced ``{query}`` alone it sent
    #: Zavvi the literal string ``{format}`` (`DECISIONS.md` #99).
    url: Annotated[str, Field(min_length=1, max_length=2000)]
    scraperConfig: dict[str, Any]
    #: Optional: when given, the shape check can also say whether the page is about the
    #: right film, which is the failure that otherwise looks completely normal. It also
    #: picks which product card on a search page is the one being priced.
    expectedTitle: Annotated[str | None, Field(max_length=500)] = None
    expectedCurrency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GBP"
    #: The wanted item's format, so the test prices the same edition a run would.
    preferredFormat: Annotated[str | None, Field(max_length=50)] = None
    #: The retailer's own host, so the test applies the same-site rule a run applies.
    #: Without it the tool was blind to a listing that had left the shop.
    expectedHost: Annotated[str | None, Field(max_length=253)] = None

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
    #: False only when the wanted **edition** was not on the shelf and a different one was
    #: priced; null when the want named no edition. Same reasoning as `substitutedFormat`.
    editionMatched: bool | None
    #: The format actually priced, set **only** when it is not the one wanted. A fallback
    #: is allowed but never silent: a `max_price` alert compares against whatever was
    #: priced, so a Blu-ray want answered with a 4K disc has to say so.
    substitutedFormat: str | None
    #: True when nothing was attempted, because these shops cannot serve the want at all —
    #: a digital copy. Neither a success nor a failure, and not counted towards a
    #: retailer's auto-disable.
    skipped: bool
    #: True when the shop was asked, answered with real listings, and has not got this
    #: film. Also neither a success nor a failure: a boutique label that does not carry a
    #: blockbuster has not broken, and must not be switched off for saying so.
    notStocked: bool
    url: str | None
    reasons: list[str]
    error: str | None


class ScrapeRunResponse(BaseModel):
    outcomes: list[ScrapeOutcomeResponse]
    succeeded: int
    failed: int
    #: Wants these shops cannot serve. Reported separately so they never read as failures.
    skipped: int
    #: Films a shop answered about and has not got. Reported separately for the same
    #: reason, and counted apart from `skipped` because the question was actually asked.
    notStocked: int
    #: Wants whose shop answered with an **empty results page**. Neither a failure nor a
    #: claim that the shop has not got it — nothing in an empty page tells "we do not
    #: carry that" apart from "the selector stopped matching" (`DECISIONS.md` #125).
    noResults: int = 0
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


# ---------------------------------------------------------------------------
# Batch 20 — the daily job, its record, and the roll-up (§5.5, §5.6, §5.8)
# ---------------------------------------------------------------------------


class ScrapeRunRecordResponse(BaseModel):
    """One recorded run — §5.5's acceptance in the numbers it is stated in.

    **`attempted` already excludes `notStocked`** — `DECISIONS.md` #107: a shop that
    answered honestly and has not got the film was not an attempt that failed. This
    docstring used to say the denominator was "attempted minus notStocked", and the page
    believed it, so a real run of 17 attempted against 23 not-stocked rendered as
    "Nothing to price" over six priced discs (#125).

    The denominator #112's corrected criterion compares `written` against is `attempted`
    minus **`noResults`** alone: everything else in `attempted` was a pair somebody could
    have priced. `failures` is the criterion's "logged with retailer + reason".
    """

    id: uuid.UUID
    startedAt: UtcDatetime
    finishedAt: UtcDatetime | None = None
    trigger: Literal["cron", "manual"]
    dryRun: bool
    attempted: int = Field(ge=0)
    notStocked: int = Field(ge=0)
    #: See `ScrapeRunResponse.noResults` — recorded so the numbers add up.
    noResults: int = Field(ge=0, default=0)
    skipped: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    written: int = Field(ge=0)
    alertsQueued: int = Field(ge=0)
    failures: list[dict[str, str]] = Field(default_factory=list)
    disabledRetailers: list[str] = Field(default_factory=list)
    error: str | None = None


class ScrapeRunListResponse(BaseModel):
    items: list[ScrapeRunRecordResponse]
    total: int = Field(ge=0)


class AggregationResponse(BaseModel):
    """What one §5.8 roll-up did."""

    daysAggregated: int = Field(ge=0)
    rowsWritten: int = Field(ge=0)
    rowsMerged: int = Field(ge=0)
    rawRowsRemoved: int = Field(ge=0)


class DailyRunResponse(BaseModel):
    """The nightly pass: what it scraped, what it alerted on, what it rolled up."""

    runId: uuid.UUID
    written: int = Field(ge=0)
    attempted: int = Field(ge=0)
    notStocked: int = Field(ge=0)
    #: See `ScrapeRunResponse.noResults` — recorded so the numbers add up.
    noResults: int = Field(ge=0, default=0)
    skipped: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    alertsQueued: int = Field(ge=0)
    pushesSent: int = Field(ge=0)
    disabledRetailers: list[str] = Field(default_factory=list)
    failures: list[dict[str, str]] = Field(default_factory=list)
    aggregation: AggregationResponse | None = None
    dryRun: bool
