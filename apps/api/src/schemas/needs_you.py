"""Home's "Needs you" row — Batch AC1 (#335)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.schemas.assigned_reviews import AssignedReviewResponse
from src.schemas.cinema_trips import ShowingFlag
from src.schemas.wire import UtcDatetime

#: A count of whole days, never negative.
Days = Annotated[int, Field(ge=0)]


class NeedsYouOwner(BaseModel):
    """Whose item it is — AE8 (#355): the web says "You" on the reader's own, the other's name
    on theirs. A shelf job both keepers can do is each keeper's own."""

    profileId: uuid.UUID
    name: str


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
    #: AE8: whose item it is. The reader's own for a shelf job, chasing an overdue loan
    #: included; the other keeper's on a loan they borrowed or a request the reader made.
    owner: NeedsYouOwner | None = None


class NextScreening(BaseModel):
    """The reader's next planned movie night, for the top of Home (AC2)."""

    sessionId: uuid.UUID
    plannedStart: UtcDatetime
    #: Everyone else in it, by name, in the order they joined.
    withNames: list[str]
    #: The film two people both liked, once they have.
    matchTitle: str | None = None


class NeedsYouTripItem(BaseModel):
    """A cinema trip only the reader can act on (AC5, #345). The web words it."""

    #: ``tripInvite``: waiting for the reader's reply. ``tripSuggestion``: to the proposer, an
    #: invitee suggests another time. ``tripWithdrawn``: to the proposer, the cinema no longer
    #: lists the time as the trip has it.
    kind: Literal["tripInvite", "tripSuggestion", "tripWithdrawn"]
    tripId: uuid.UUID
    filmTitle: str
    posterPath: str | None
    venueName: str
    venueTimezone: str
    startsAtUtc: UtcDatetime
    proposerName: str
    #: Who suggests another time, on a ``tripSuggestion``.
    fromName: str | None = None
    #: Why, on a ``tripWithdrawn``: withdrawn (which includes gone, or moved to another time)
    #: or cancelled.
    flag: ShowingFlag | None = None
    #: AE8: whose item it is: the invitee's reply, or the proposer's to deal with. Another
    #: keeper's item shows only on a trip the reader is on, and only its owner can act on it.
    owner: NeedsYouOwner | None = None


class NextTrip(BaseModel):
    """The reader's next cinema trip they proposed or are going on (AC5, #345)."""

    tripId: uuid.UUID
    filmTitle: str
    venueName: str
    venueTimezone: str
    startsAtUtc: UtcDatetime
    #: Everyone else going, the proposer first.
    withNames: list[str]


class NeedsYouResponse(BaseModel):
    #: AE8 (#355): for the people who keep the shelves, every keeper's open reviews, the
    #: reader's own first; only the assignee can answer (``canAnswer``).
    reviews: list[AssignedReviewResponse] = Field(default_factory=list)
    #: The reader's own first, then most pressing first. Empty when there is nothing to do.
    items: list[NeedsYouLoanItem]
    #: AC2: the next screening the reader is in, planned and not ended; null when none. Home
    #: shows it beside "Needs you" from this one read, so it adds no request.
    nextScreening: NextScreening | None = None
    #: AC5: cinema trips the reader can act on, soonest showing first. A field of its own, not
    #: new kinds in ``items``, so a build installed before AC5 still reads this answer.
    trips: list[NeedsYouTripItem] = Field(default_factory=list)
    #: AC5: the reader's next trip, for Home's top slot when it is sooner than the screening.
    nextTrip: NextTrip | None = None
