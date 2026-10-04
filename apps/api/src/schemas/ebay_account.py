"""Wire models for "Connect eBay" and a person's eBay lists — Batch T8b, #245."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime


class EbayAccountResponse(BaseModel):
    """Whether connecting is set up, whether this person is connected, and as whom."""

    configured: bool
    #: The variables connecting needs and this deployment lacks, by name only.
    missing: list[str]
    connected: bool
    #: The eBay account's name, read live from eBay; never stored.
    accountName: str | None = None
    connectedAt: UtcDatetime | None = None
    #: Why a connection ended or cannot be read, for the person.
    note: str | None = None


class EbayConnectStartResponse(BaseModel):
    """Where to send the person to sign in to eBay and agree."""

    authorizeUrl: str


class EbayConnectFinishRequest(BaseModel):
    """What eBay put on the address it sent the person back to."""

    code: str = Field(min_length=1, max_length=4000)
    state: str = Field(min_length=16, max_length=200)


class EbayListingResponse(BaseModel):
    itemId: str
    title: str
    url: str
    price: str | None = None
    currency: str | None = None
    postage: str | None = None
    isAuction: bool
    bidCount: int | None = None
    endsAt: UtcDatetime | None = None


class EbaySavedSearchResponse(BaseModel):
    name: str
    keywords: str | None = None
    url: str | None = None


class EbaySoldResponse(BaseModel):
    itemId: str
    title: str
    url: str
    price: str | None = None
    currency: str | None = None
    soldAt: UtcDatetime | None = None


class EbayWatchingResponse(BaseModel):
    """The person's watch list and saved searches, as eBay holds them now."""

    items: list[EbayListingResponse]
    savedSearches: list[EbaySavedSearchResponse]
    totalItems: int = Field(ge=0)
    fetchedAt: UtcDatetime


class EbaySellingResponse(BaseModel):
    """The person's listings for sale and what sold in the last 60 days."""

    active: list[EbayListingResponse]
    sold: list[EbaySoldResponse]
    totalActive: int = Field(ge=0)
    totalSold: int = Field(ge=0)
    fetchedAt: UtcDatetime
