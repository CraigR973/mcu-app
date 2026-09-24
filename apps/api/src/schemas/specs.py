"""Wire models for disc specs — Batch 23, §3.7."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.schemas.wire import UtcDatetime
from src.services.specs.bluray_com import is_release_url


class SpecsTargetRequest(BaseModel):
    """One disc and the release page it is described by."""

    collectionItemId: uuid.UUID
    sourceUrl: str = Field(min_length=1, max_length=500)

    @field_validator("sourceUrl")
    @classmethod
    def _within_bounds(cls, value: str) -> str:
        """`DECISIONS.md` #110's "exact release URLs only", enforced at the door.

        A 422 here rather than at fetch time means a mistyped or pasted-search URL is
        refused before anything leaves the building, which is the point.
        """
        if not is_release_url(value):
            raise ValueError(
                "sourceUrl must be an exact Blu-ray.com release URL "
                "(https://www.blu-ray.com/movies/<Title>/<id>/). The site's search routes "
                "are not permitted — see DECISIONS.md #110."
            )
        return value


class SpecsFetchRequest(BaseModel):
    """A batch of targets. **Makes live requests to Blu-ray.com.**"""

    targets: list[SpecsTargetRequest] = Field(min_length=1, max_length=25)
    #: Re-fetch a disc that already has specs. Off by default: #110 says successful results
    #: are cached indefinitely rather than refreshed automatically.
    refresh: bool = False


class SpecsRunResponse(BaseModel):
    """What a run did. **Every URL fetched is listed** — the ledger requires that."""

    fetched: list[str] = Field(default_factory=list)
    updated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: list[dict[str, str]] = Field(default_factory=list)
    halted: bool
    haltReason: str | None = None


class SpecsStateResponse(BaseModel):
    """Whether the integration is running, and what it has done.

    `halted` is the state #110 makes sticky: a `403`, a `429` or an objection stops
    everything, and only an owner decision starts it again.
    """

    halted: bool
    haltedReason: str | None = None
    haltedAt: UtcDatetime | None = None
    lastFetchAt: UtcDatetime | None = None
    fetchCount: int = Field(ge=0)
    #: How many discs currently hold data derived from that site — the number that would be
    #: removed if the owner decided to remove it.
    discsWithSpecs: int = Field(ge=0)


# ---------------------------------------------------------------------------
# The backfill (Batch T7, `DECISIONS.md` #202)
# ---------------------------------------------------------------------------


class SpecCoverageResponse(BaseModel):
    """Where the ~1,250 Blu-ray and 4K discs stand."""

    discs: int = Field(ge=0)
    withSpecs: int = Field(ge=0)
    #: Chosen, and waiting for the nightly fetch.
    accepted: int = Field(ge=0)
    #: Waiting for Craig: several editions, no year, or the page failed its year check.
    needsYou: int = Field(ge=0)
    #: Searched, and no release page came back.
    noMatch: int = Field(ge=0)
    skipped: int = Field(ge=0)
    notSearched: int = Field(ge=0)


class SpecRunResponse(BaseModel):
    id: uuid.UUID
    trigger: Literal["job", "admin"]
    status: Literal["running", "finished", "budget_spent", "stopped", "halted", "abandoned"]
    startedAt: UtcDatetime
    finishedAt: UtcDatetime | None = None
    searchBudget: int = Field(ge=0)
    #: Brave requests sent, retries included. Each is billed.
    searches: int = Field(ge=0)
    searched: int = Field(ge=0)
    accepted: int = Field(ge=0)
    queued: int = Field(ge=0)
    noMatch: int = Field(ge=0)
    restored: int = Field(ge=0)
    fetchBudget: int = Field(ge=0)
    fetched: int = Field(ge=0)
    applied: int = Field(ge=0)
    sentBack: int = Field(ge=0)
    fetchFailed: int = Field(ge=0)
    lastError: str | None = None


class SpecBackfillResponse(BaseModel):
    searchConfigured: bool
    halted: bool
    haltedReason: str | None = None
    coverage: SpecCoverageResponse
    run: SpecRunResponse | None = None
    searchesThisMonth: int = Field(ge=0)
    monthlyCeiling: int = Field(ge=0)
    searchesPerRun: int = Field(ge=0)
    fetchesPerRun: int = Field(ge=0)


class SpecCandidateResponse(BaseModel):
    url: str
    #: The page title the search engine gave, which is what Craig chooses between.
    title: str
    country: str | None = None
    edition: str | None = None
    #: Same film, same format, UK edition.
    matches: bool
    #: ``restored`` is the page the 10 Sep test used for this disc.
    origin: Literal["search", "restored"]


class SpecQueueItemResponse(BaseModel):
    lookupId: uuid.UUID
    collectionItemId: uuid.UUID
    movieId: uuid.UUID
    filmTitle: str
    year: int | None = None
    formatCode: str
    location: str | None = None
    status: Literal["needs_you", "no_match"]
    note: str | None = None
    searchQuery: str | None = None
    candidates: list[SpecCandidateResponse]


class SpecQueueResponse(BaseModel):
    items: list[SpecQueueItemResponse]
    total: int = Field(ge=0)


class SpecAcceptRequest(BaseModel):
    """One of the offered pages, or a Blu-ray.com release address Craig pasted."""

    url: str = Field(min_length=1, max_length=500)

    @field_validator("url")
    @classmethod
    def _within_bounds(cls, value: str) -> str:
        if not is_release_url(value.strip()):
            raise ValueError(
                "url must be an exact Blu-ray.com release page, such as "
                "https://www.blu-ray.com/movies/Heat-Blu-ray/12345/ (DECISIONS.md #110)."
            )
        return value.strip()


class SpecDecisionResponse(BaseModel):
    lookupId: uuid.UUID
    status: Literal["needs_you", "no_match", "accepted", "done", "skipped"]
    acceptedUrl: str | None = None
    how: Literal["auto", "confirmed", "pasted", "restored"] | None = None


class SpecBackfillStartResponse(BaseModel):
    """What pressing "Run a batch now" did. Only ``started`` searches or fetches anything."""

    outcome: Literal["started", "running", "halted", "nothing_due"]
    run: SpecRunResponse | None = None
