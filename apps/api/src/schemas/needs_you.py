"""Home's "Needs you" row — Batch AC1 (#335)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime

#: A count of whole days, never negative.
Days = Annotated[int, Field(ge=0)]


class NeedsYouLoanItem(BaseModel):
    """One disc the reader can act on. The web words it; the API decides who sees it."""

    #: ``putBack``: back but not shelved. ``handOver``: asked for and waiting. ``overdue``:
    #: past its due date, or out 14 days or more with none.
    kind: Literal["putBack", "handOver", "overdue"]
    loanId: uuid.UUID
    movieId: uuid.UUID
    movieTitle: str
    posterPath: str | None
    #: The copy's home position, where "Put back" will shelve it unless changed.
    locationLabel: str
    #: Who has it, or who asked for it.
    borrowerName: str
    #: The reader is the borrower: "Give it back" rather than "Ask them for it".
    borrowerIsYou: bool
    lentDate: date | None
    returnedDate: date | None
    neededBy: date | None
    dueDate: date | None
    #: Days past the due date, on an overdue item that has one; null otherwise.
    daysOverdue: Days | None
    #: Days since it went out, on an overdue item; null otherwise.
    daysOut: Days | None


class NextScreening(BaseModel):
    """The reader's next planned movie night, for the top of Home (AC2)."""

    sessionId: uuid.UUID
    plannedStart: UtcDatetime
    #: Everyone else in it, by name, in the order they joined.
    withNames: list[str]
    #: The film two people both liked, once they have.
    matchTitle: str | None = None


class NeedsYouResponse(BaseModel):
    #: Most pressing first. Empty when there is nothing to do.
    items: list[NeedsYouLoanItem]
    #: AC2: the next screening the reader is in, planned and not ended; null when none. Home
    #: shows it beside "Needs you" from this one read, so it adds no request.
    nextScreening: NextScreening | None = None
