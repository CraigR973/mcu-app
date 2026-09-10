"""Wire models for disc specs — Batch 23, §3.7."""

from __future__ import annotations

import uuid

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
