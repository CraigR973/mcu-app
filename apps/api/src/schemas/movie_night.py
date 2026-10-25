"""Wire models for movie night — Batch 35, §8.3 and §8.4."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime, UtcDatetimeIn


class SessionCreateRequest(BaseModel):
    """§8.3's "session creation with filters", in Batch 12's smart-collection shape."""

    filters: dict[str, Any] = Field(default_factory=dict)
    plannedStart: UtcDatetimeIn | None = None


class PersonResponse(BaseModel):
    id: uuid.UUID
    displayName: str


class ParticipantResponse(PersonResponse):
    #: Batch T4 — whether tonight was sent to this person as a push, so the page can say
    #: "Sent to Mark" rather than offering to send it again.
    invited: bool = False


class SendRequest(BaseModel):
    """Batch T4, snag 11 — who to send tonight to.

    Omitted, it means everyone who is not in the night yet. In a two-person app that is
    "the other person", which is the one-tap case the snag asked for.
    """

    userIds: list[uuid.UUID] | None = None


class MatchResponse(BaseModel):
    #: Null when the match is a film nobody owns, which Batch S7 made possible.
    movieId: uuid.UUID | None = None
    title: str
    year: int | None = None
    posterPath: str | None = None


class MovieNightSessionResponse(BaseModel):
    """One sitting.

    `inviteToken` is returned **only to people already in the session**. It is the whole
    credential for joining — the same reasoning as Batch 27's gift slug — so an endpoint
    that leaked it would be an open door with extra steps.
    """

    id: uuid.UUID
    status: Literal["open", "ended"]
    filters: dict[str, Any]
    inviteToken: str
    invitePath: str
    participantCount: int = Field(ge=1)
    #: Batch T4. Who is in tonight, and who could still be sent it (empty once it ends).
    people: list[ParticipantResponse] = Field(default_factory=list)
    invitable: list[PersonResponse] = Field(default_factory=list)
    plannedStart: UtcDatetime | None = None
    createdAt: UtcDatetime
    endedAt: UtcDatetime | None = None
    #: Batch X12a: the film of the latest match, read back from the session, so a night opened
    #: from "It's a match" shows it. Null until two people like the same film.
    match: MatchResponse | None = None


class MovieNightSessionListResponse(BaseModel):
    items: list[MovieNightSessionResponse]
    total: int = Field(ge=0)


class WatchedByResponse(BaseModel):
    """One other participant who has seen this film, and when — Batch S7.

    `DECISIONS.md` #157's fourth point. **Everyone except the person asking**: "have I
    seen it" is on the film's own page; what a card needs to say is whether the people you
    are choosing with have.
    """

    personName: str
    watchedAt: str


class PersonFilmResponse(BaseModel):
    personId: uuid.UUID
    personName: str
    lastWatchedAt: date | None = None
    personalRating: float | None = Field(default=None, ge=0.5, le=5)


class CopyPlaceResponse(BaseModel):
    location: str | None = None
    section: str | None = None
    shelf: str | None = None


class CandidateResponse(BaseModel):
    """A film on tonight's list.

    **Batch S7 made this a suggestion rather than a deal from the deck.** `movieId` is null
    for a film outside the Archive — those can be suggested now, and carry their own title
    and poster because there is no `movies` row to read them from.
    """

    suggestionId: uuid.UUID
    movieId: uuid.UUID | None = None
    tmdbId: int | None = None
    title: str
    year: int | None = None
    posterPath: str | None = None
    overview: str | None = None
    runtimeMinutes: int | None = None
    genres: list[str] = Field(default_factory=list)
    #: Top billing, for the "what is this" question a card has to answer before a swipe.
    cast: list[str] = Field(default_factory=list)
    #: Who put it forward. Null for the films the session was seeded with — nobody
    #: suggested those.
    suggestedBy: str | None = None
    suggestedAt: UtcDatetime | None = None
    #: Where it can be streamed, for a film nobody owns. #157: `get_watch_providers`
    #: already exists, so the streaming half needed no new integration.
    streamingOn: list[str] = Field(default_factory=list)
    #: Which *other* participants have seen it, and when.
    watchedBy: list[WatchedByResponse] = Field(default_factory=list)
    #: This person's own swipe, if they have made one. The deck no longer hides what you
    #: have voted on, because a shortlist everyone is adding to is a list you re-read.
    myVote: bool | None = None
    people: list[PersonFilmResponse] = Field(default_factory=list)
    locations: list[CopyPlaceResponse] = Field(default_factory=list)
    imdbId: str | None = None
    imdbRating: float | None = Field(default=None, ge=0, le=10)
    imdbVotes: int | None = Field(default=None, ge=0)
    imdbCheckedAt: UtcDatetime | None = None
    streamingLink: str | None = None


class CandidateListResponse(BaseModel):
    items: list[CandidateResponse]
    total: int = Field(ge=0)


class SuggestionRequest(BaseModel):
    """Put a film forward. **Exactly one of `movieId` and `tmdbId`.**"""

    movieId: uuid.UUID | None = None
    tmdbId: int | None = None
    #: Required with `tmdbId`, ignored with `movieId` — a film in the collection reads its
    #: own metadata, and one outside it has none to read.
    title: str | None = Field(default=None, max_length=500)
    year: int | None = None
    posterPath: str | None = None
    overview: str | None = None


class VoteRequest(BaseModel):
    suggestionId: uuid.UUID
    liked: bool


class VoteResponse(BaseModel):
    """The result of one swipe.

    `match` is non-null only on the swipe that *completes* one, so the browser can show it
    immediately without waiting for the event stream to come back round.
    """

    recorded: bool
    match: MatchResponse | None = None
