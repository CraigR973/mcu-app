"""Cinema trips on the wire — AC5 (#345). Members only; the web parses each through zod.

Replies are camelCase on the wire (`notGoing`, `anotherTime`) and snake_case in the database.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.models.cinema_trip import FILM_KEY_PATTERN
from src.schemas.cinemas import ProgrammeShowing, ProgrammeVenue
from src.schemas.wire import UtcDatetime

TripReply = Literal["invited", "going", "notGoing", "anotherTime"]
TripStatus = Literal["upcoming", "cancelled", "past"]
#: What the live programme says about a trip's showing, when it is not simply listed (#345 §3).
#: ``withdrawn`` also covers a showing the programme no longer holds, or now lists at another
#: time: either way the cinema no longer lists the time the trip has.
ShowingFlag = Literal["unconfirmed", "withdrawn", "cancelled"]

#: The most people one request may name. A guard on the request's size, not a rule about trips.
MAX_NAMED = 50


class TripShowing(BaseModel):
    """The showing as the trip keeps it, and what the programme says about it now."""

    showingId: uuid.UUID | None
    venueId: uuid.UUID | None
    venueName: str
    venueTimezone: str
    startsAtUtc: UtcDatetime
    endsAtUtc: UtcDatetime | None
    screen: str | None
    formats: list[str]
    #: Null on a trip that is cancelled or past, and while the cinema lists it as kept.
    flag: ShowingFlag | None
    #: The live showing and its venue, so the web draws Check tickets by AB7's own rule
    #: (`showingBooking`); null once the programme no longer lists it as the trip has it.
    live: ProgrammeShowing | None = None
    venue: ProgrammeVenue | None = None


class TripSuggestion(BaseModel):
    showingId: uuid.UUID | None
    venueName: str
    startsAtUtc: UtcDatetime
    formats: list[str]
    #: Whether the programme still lists it as suggested; a flagged one cannot be accepted.
    flag: ShowingFlag | None


class TripPerson(BaseModel):
    profileId: uuid.UUID
    displayName: str
    isYou: bool


class TripInvitee(TripPerson):
    reply: TripReply
    #: Named back when accepting or keeping this person's suggestion, so a reply changed
    #: since the screen was drawn is refused rather than acted on.
    replyRevision: int = Field(ge=0)
    repliedAtUtc: UtcDatetime | None
    suggestion: TripSuggestion | None


class TripCounts(BaseModel):
    """The proposer counts as going."""

    going: int = Field(ge=1)
    notGoing: int = Field(ge=0)
    anotherTime: int = Field(ge=0)
    invited: int = Field(ge=0)


class CinemaTripResponse(BaseModel):
    id: uuid.UUID
    filmKey: str
    filmTitle: str
    posterPath: str | None
    proposer: TripPerson
    status: TripStatus
    #: Named back by every reply and move.
    revision: int = Field(ge=1)
    showing: TripShowing
    invitees: list[TripInvitee]
    counts: TripCounts
    #: The reader's own reply; null for the proposer.
    yourReply: TripReply | None
    createdAtUtc: UtcDatetime
    movedAtUtc: UtcDatetime | None
    cancelledAtUtc: UtcDatetime | None


class CinemaTripList(BaseModel):
    #: Soonest first.
    upcoming: list[CinemaTripResponse]
    #: Past and cancelled, most recent first.
    past: list[CinemaTripResponse]


class InvitablePeople(BaseModel):
    people: list[TripPerson]


class ProposeTrip(BaseModel):
    clientRequestId: uuid.UUID
    #: The film page's address the time was picked on.
    filmKey: str = Field(pattern=FILM_KEY_PATTERN)
    showingId: uuid.UUID
    #: Nobody named is refused in words ("Pick at least one person"), not by a bound.
    inviteeIds: list[uuid.UUID] = Field(max_length=MAX_NAMED)


class ReplyToTrip(BaseModel):
    revision: int = Field(ge=1)
    reply: Literal["going", "notGoing", "anotherTime"]
    #: Another time's showing; only with ``anotherTime``.
    showingId: uuid.UUID | None = None

    @model_validator(mode="after")
    def _showing_only_for_another_time(self) -> "ReplyToTrip":
        if (self.reply == "anotherTime") != (self.showingId is not None):
            raise ValueError("Another time needs a showing, and only Another time takes one")
        return self


class MoveTrip(BaseModel):
    revision: int = Field(ge=1)
    showingId: uuid.UUID
    #: Accepting a suggestion: whose, and the reply revision it was shown at. Neither for the
    #: proposer's own move.
    fromProfileId: uuid.UUID | None = None
    fromReplyRevision: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _both_or_neither(self) -> "MoveTrip":
        if (self.fromProfileId is None) != (self.fromReplyRevision is None):
            raise ValueError("Name the suggestion's person and its reply revision together")
        return self


class KeepTime(BaseModel):
    profileId: uuid.UUID
    replyRevision: int = Field(ge=0)


class InviteMore(BaseModel):
    #: Nobody named is refused in words, as when proposing.
    profileIds: list[uuid.UUID] = Field(max_length=MAX_NAMED)
