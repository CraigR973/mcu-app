"""Wire models for the collection's value — Batch T6, snag 7.

camelCase written directly and money as strings, as everywhere else (`DECISIONS.md` #6).
Every total and price carries ``basis``: they are current eBay **asking** prices, and no
surface may present them as what the discs would sell for.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime

RunStatus = Literal["running", "finished", "budget_spent", "stopped", "abandoned"]


class ValuationRunResponse(BaseModel):
    id: uuid.UUID
    trigger: Literal["job", "admin"]
    status: RunStatus
    startedAt: UtcDatetime
    finishedAt: UtcDatetime | None
    #: eBay calls the run was allowed, and made.
    budget: int = Field(ge=0)
    calls: int = Field(ge=0)
    priced: int = Field(ge=0)
    notPriced: int = Field(ge=0)
    failed: int = Field(ge=0)
    #: Films still due a price when it ended. Null while it runs.
    remaining: int | None = Field(ge=0)
    lastError: str | None


class CollectionValueResponse(BaseModel):
    """What the owned discs add up to as used copies, at current eBay asking prices."""

    #: Null until at least one disc is priced.
    total: str | None
    currency: str
    basis: str
    #: "as used copies" (Batch X6, #256): what each disc is valued as.
    valuedAs: str
    #: Owned physical discs, and how they split. ``uncheckedDiscs`` have no price yet, or
    #: only one from before X6, which a run values again first.
    discs: int = Field(ge=0)
    pricedDiscs: int = Field(ge=0)
    notPricedDiscs: int = Field(ge=0)
    uncheckedDiscs: int = Field(ge=0)
    #: The oldest and newest price behind the total.
    checkedFrom: UtcDatetime | None
    checkedTo: UtcDatetime | None
    #: Films and formats due a price now, and the eBay calls left in today's share.
    due: int = Field(ge=0)
    budgetLeft: int = Field(ge=0)
    dailyShare: int = Field(gt=0)
    #: Fewer matching listings than this and a disc is not priced.
    minSample: int = Field(gt=0)
    #: The latest run, finished or not.
    run: ValuationRunResponse | None


class ValuationStartResponse(BaseModel):
    """What pressing "Update values" did. Only ``started`` spends anything."""

    outcome: Literal["started", "running", "budget_spent", "nothing_due"]
    run: ValuationRunResponse | None
    due: int = Field(ge=0)
    budgetLeft: int = Field(ge=0)


class CopyValuationResponse(BaseModel):
    """A disc's stored value as a used copy: its film on the format it is valued as."""

    formatCode: str
    status: Literal["priced", "not_priced"]
    #: Null when not priced, which is an answer: too few listings to say.
    price: str | None
    currency: str
    #: Listings behind the value; for one not priced, the larger of its two groups.
    sampleSize: int = Field(ge=0)
    conditionLabel: str | None
    checkedAt: UtcDatetime
    basis: str
    minSample: int = Field(gt=0)
    #: Batch X6. ``used``: the median of ``sampleSize`` used listings. ``new_scaled``: New's
    #: median of ``sampleSize`` listings times ``factor``. Null when not priced.
    valueBasis: Literal["used", "new_scaled"] | None
    factor: str | None
    #: The range of the listings the value rests on, before any factor.
    low: str | None
    high: str | None
    #: Both groups' sizes, so "not priced" can say what eBay had.
    usedCount: int = Field(ge=0)
    newCount: int = Field(ge=0)
    valuedAs: str
    #: Batch V8. eBay's own sold listings for the same search, opened in the person's
    #: browser: what discs went for, beside the asking prices the value is built from.
    soldListingsUrl: str
