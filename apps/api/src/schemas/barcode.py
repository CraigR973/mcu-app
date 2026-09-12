"""Wire models for barcode scanning — Batch 24, Phase 3.4.

camelCase written directly, no envelope — `DECISIONS.md` #6.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Which leg of §3.4's chain produced a candidate. `cache` and `collection` are certain;
#: `ebay` is a search result a person still has to confirm.
CandidateSource = Literal["cache", "collection", "ebay", "tmdb", "manual"]


class BarcodeLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: As the scanner read it. Normalised server-side — scanners add spaces and hyphens,
    #: and the check digit is verified before anything is looked up.
    barcode: str = Field(min_length=1, max_length=64)


class BarcodeCandidateResponse(BaseModel):
    """One possible film for a scanned code.

    **A candidate is never an answer.** §3.4 requires a confirmation step, and the risk
    note for this batch is explicit that wrong-edition matches are expected — so
    `confidence` exists to order this list and for no other purpose.
    """

    title: str
    source: CandidateSource
    confidence: float = Field(ge=0, le=1)
    #: Set when the film is already in the catalogue, so the client can link to it rather
    #: than creating a second row for the same TMDB id.
    movieId: uuid.UUID | None = None
    tmdbId: int | None = Field(default=None, gt=0)
    year: int | None = None
    posterPath: str | None = None
    #: What the source actually said. Shown beside the candidate, because "six eBay
    #: listings for this barcode read as 'Blade Runner 2049'" is the thing that makes a
    #: confirmation an informed one rather than a tap.
    evidence: str | None = None


class BarcodeLookupResponse(BaseModel):
    barcode: str
    #: Which leg answered, or null when none did — §3.4's *"unknown UPCs prompt manual
    #: search"*. Null is a result, not an error, and the endpoint still returns 200.
    source: CandidateSource | None = None
    #: True when the barcode matches a disc already owned. The single most useful fact a
    #: scan can produce while standing in a shop.
    alreadyOwned: bool = False
    candidates: list[BarcodeCandidateResponse] = Field(default_factory=list)


class BarcodeConfirmRequest(BaseModel):
    """What the person decided this barcode is."""

    model_config = ConfigDict(extra="forbid")

    barcode: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    source: Literal["collection", "ebay", "tmdb", "manual"]
    movieId: uuid.UUID | None = None
    tmdbId: int | None = Field(default=None, gt=0)

    @field_validator("title")
    @classmethod
    def _title_is_not_whitespace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title cannot be blank")
        return stripped
