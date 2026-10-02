"""Wire models for the collection's value — Batch T6, snag 7.

camelCase written directly and money as strings, as everywhere else (`DECISIONS.md` #6).
Every total and price carries ``basis``: they are current eBay **asking** prices, and no
surface may present them as what the discs would sell for.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

from src.schemas.wire import UtcDatetime

RunStatus = Literal["running", "finished", "budget_spent", "stopped", "abandoned"]


class ValuationRunResponse(BaseModel):
    id: uuid.UUID
    trigger: Literal["job", "admin"]
    status: RunStatus
    startedAt: UtcDatetime
    finishedAt: UtcDatetime | None
    #: eBay calls the run was allowed, and made.
    budget: int
    calls: int
    priced: int
    notPriced: int
    failed: int
    #: Films still due a price when it ended. Null while it runs.
    remaining: int | None
    lastError: str | None


class CollectionValueResponse(BaseModel):
    """What the owned discs add up to at current eBay asking prices."""

    #: Null until at least one disc is priced.
    total: str | None
    currency: str
    basis: str
    #: Owned physical discs, and how they split. ``uncheckedDiscs`` have no price yet.
    discs: int
    pricedDiscs: int
    notPricedDiscs: int
    uncheckedDiscs: int
    #: The oldest and newest price behind the total.
    checkedFrom: UtcDatetime | None
    checkedTo: UtcDatetime | None
    #: Films and formats due a price now, and the eBay calls left in today's share.
    due: int
    budgetLeft: int
    dailyShare: int
    #: Fewer matching listings than this and a disc is not priced.
    minSample: int
    #: The latest run, finished or not.
    run: ValuationRunResponse | None


class ValuationStartResponse(BaseModel):
    """What pressing "Update values" did. Only ``started`` spends anything."""

    outcome: Literal["started", "running", "budget_spent", "nothing_due"]
    run: ValuationRunResponse | None
    due: int
    budgetLeft: int


class CopyValuationResponse(BaseModel):
    """A disc's stored price: its film on the format it is valued as."""

    formatCode: str
    status: Literal["priced", "not_priced"]
    #: Null when not priced, which is an answer: too few listings to say.
    price: str | None
    currency: str
    sampleSize: int
    conditionLabel: str | None
    checkedAt: UtcDatetime
    basis: str
    minSample: int
    #: Batch V8. eBay's own sold listings for the same search, opened in the person's
    #: browser: what discs went for, beside the asking prices the value is built from.
    soldListingsUrl: str
