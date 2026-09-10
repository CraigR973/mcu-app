"""Wire models for movie night — Batch 35, §8.3 and §8.4."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime


class SessionCreateRequest(BaseModel):
    """§8.3's "session creation with filters", in Batch 12's smart-collection shape."""

    filters: dict[str, Any] = Field(default_factory=dict)


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
    createdAt: UtcDatetime
    endedAt: UtcDatetime | None = None


class MovieNightSessionListResponse(BaseModel):
    items: list[MovieNightSessionResponse]
    total: int = Field(ge=0)


class CandidateResponse(BaseModel):
    """A film still to swipe on."""

    movieId: uuid.UUID
    title: str
    year: int | None = None
    posterPath: str | None = None
    overview: str | None = None


class CandidateListResponse(BaseModel):
    items: list[CandidateResponse]
    total: int = Field(ge=0)


class VoteRequest(BaseModel):
    movieId: uuid.UUID
    liked: bool


class MatchResponse(BaseModel):
    movieId: uuid.UUID
    title: str
    posterPath: str | None = None


class VoteResponse(BaseModel):
    """The result of one swipe.

    `match` is non-null only on the swipe that *completes* one, so the browser can show it
    immediately without waiting for the event stream to come back round.
    """

    recorded: bool
    match: MatchResponse | None = None
