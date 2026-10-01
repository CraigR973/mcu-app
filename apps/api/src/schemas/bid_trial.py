"""The bid trial's report and wire models — Batch V6, snag 2's first step.

:class:`BidTrialReport` is both what Home is shown and what is kept on the trial's run row
(``valuation_runs.report``), so a later session reads exactly what Craig read. camelCase
written directly and money as strings, as everywhere else (`DECISIONS.md` #6).

Every price here is from one eBay search: **asking** prices are what sellers ask for with
Buy It Now, **bids** are the highest bids so far on auctions, which run below the final
price until an auction's last minutes. Neither is a sold price (#16, #126).
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.valuation import RunStatus
from src.schemas.wire import UtcDatetime


class TrialStoredPrice(BaseModel):
    """The film's stored value, from the last valuation run: asking prices only."""

    price: str
    sampleSize: int = Field(ge=0)


class TrialResults(BaseModel):
    """What the search returned, before any judging."""

    #: eBay's own count of matching listings. More than ``returned`` means the 200 places
    #: were full, and every auction in them took a place a Buy It Now listing could have had.
    total: int | None
    returned: int = Field(ge=0)
    buyItNow: int = Field(ge=0)
    #: Auctions with no Buy It Now price: listings the valuation's own search never returns.
    auctionOnly: int = Field(ge=0)


class TrialAsking(BaseModel):
    """The asking price from the same search, by the valuation's own rule."""

    #: Null when fewer than three Buy It Now listings matched: the film is not priced.
    price: str | None
    sampleSize: int = Field(ge=0)


class TrialBids(BaseModel):
    """The auctions in the same search."""

    #: Auctions with at least one bid that passed the matcher: the right film and format, a
    #: UK seller, a standard edition.
    counted: int = Field(ge=0)
    #: Matching auctions nobody has bid on. Their price is the seller's opening one.
    withoutBids: int = Field(ge=0)
    #: Auctions the matcher turned away, or with no usable current bid.
    rejected: int = Field(ge=0)
    #: The median of the counted bids, when there are three or more.
    price: str | None
    #: Counted auctions ending within the window (24 hours).
    endingSoon: int = Field(ge=0)


class TrialFilm(BaseModel):
    """One film and format in the sample, and what its search found."""

    movieId: uuid.UUID
    title: str
    formatCode: str
    #: Owned discs of it: a total counts each.
    copies: int = Field(ge=1)
    stored: TrialStoredPrice
    #: Null when eBay did not answer for it; ``error`` says why.
    results: TrialResults | None
    asking: TrialAsking | None
    bids: TrialBids | None
    error: str | None = None


class TrialTotal(BaseModel):
    """What the films add up to on one basis, and how many discs stand behind it."""

    total: str
    discs: int = Field(ge=0)


class TrialBlendTotal(TrialTotal):
    """Bids where a film has a bid price, asking prices otherwise."""

    fromBids: int = Field(ge=0)
    fromAsking: int = Field(ge=0)


class TrialSummary(BaseModel):
    """The trial's answer for one format, or for all of them (``formatCode`` null)."""

    formatCode: str | None
    #: Films searched with eBay answering.
    films: int = Field(ge=0)
    #: Films with three or more auctions with bids: a bid price.
    withBids: int = Field(ge=0)
    #: Films that would still have one counting only auctions ending within the window.
    withBidsEndingSoon: int = Field(ge=0)
    #: Auctions behind those bid prices, and how many of them end within the window.
    auctionsCounted: int = Field(ge=0)
    endingSoon: int = Field(ge=0)
    #: Films with both a bid price and an asking price, and the median of bid ÷ asking
    #: across them, as a percentage. Null when no film has both.
    compared: int = Field(ge=0)
    bidToAskingPercent: int | None
    #: Films whose 200 places were full, and the places auctions with no Buy It Now took in
    #: them: the Buy It Now listings that sharing may have cost.
    cut: int = Field(ge=0)
    auctionOnlyPlaces: int = Field(ge=0)
    #: Buy It Now listings behind the asking prices in this search, and behind the stored
    #: prices; and films with a stored price that this search could not price.
    askingSample: int = Field(ge=0)
    storedSample: int = Field(ge=0)
    askingLost: int = Field(ge=0)
    stored: TrialTotal
    asking: TrialTotal
    bids: TrialTotal
    blend: TrialBlendTotal


class BidTrialReport(BaseModel):
    """The whole report, written after every film so a stopped trial keeps what it found."""

    #: Films and formats in the sample.
    sampled: int = Field(ge=0)
    films: list[TrialFilm]
    formats: list[TrialSummary]
    overall: TrialSummary


class BidTrialResponse(BaseModel):
    """The latest trial: its run, and its report so far."""

    id: uuid.UUID
    status: RunStatus
    startedAt: UtcDatetime
    finishedAt: UtcDatetime | None
    #: eBay calls it was allowed, and made: they come out of the day's valuation share.
    budget: int
    calls: int
    failed: int
    lastError: str | None
    #: The rules it ran under, so the page states them rather than repeating them.
    sampleSize: int
    minSample: int
    endingWindowHours: int
    dailyShare: int
    currency: str
    report: BidTrialReport | None


class BidTrialStartResponse(BaseModel):
    """What pressing "Try bid prices" did. Only ``started`` spends anything."""

    outcome: Literal["started", "running", "budget_spent", "nothing_to_sample"]
    trial: BidTrialResponse | None
    #: Films and formats it would sample, and the eBay calls left in today's share.
    sampled: int
    budgetLeft: int
