"""Wire models for the Identify films page — Batch T9."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime


class IdentifyRunResponse(BaseModel):
    id: uuid.UUID
    status: Literal["running", "finished", "stopped", "abandoned"]
    startedAt: UtcDatetime
    finishedAt: UtcDatetime | None
    films: int
    identified: int
    queued: int
    setAside: int
    unchanged: int
    failed: int
    searches: int
    lastError: str | None


class IdentifyOverviewResponse(BaseModel):
    """How many unmatched films wait, and what became of the rest."""

    unidentified: int
    waiting: int
    setAsideTv: int
    setAsideNotFilm: int
    skipped: int
    identified: int
    run: IdentifyRunResponse | None


class FilmInCollectionResponse(BaseModel):
    """The film a choice would merge into, shown beside the one waiting."""

    movieId: uuid.UUID
    title: str
    year: int | None
    discs: int
    watches: int


class IdentifyCandidateResponse(BaseModel):
    tmdbId: int
    title: str
    year: int | None
    posterPath: str | None
    overview: str
    votes: int
    notes: list[str]
    #: Set when the collection already has this film: choosing it merges the two.
    inCollection: FilmInCollectionResponse | None


class IdentifyDiscResponse(BaseModel):
    label: str


class IdentifyQueueItemResponse(BaseModel):
    movieId: uuid.UUID
    title: str
    discs: list[IdentifyDiscResponse]
    watches: int
    note: str | None
    proposedTmdbId: int | None
    candidates: list[IdentifyCandidateResponse]


class IdentifyQueueResponse(BaseModel):
    items: list[IdentifyQueueItemResponse]
    total: int


class IdentifySearchResponse(BaseModel):
    query: str
    candidates: list[IdentifyCandidateResponse]


class IdentifyPickRequest(BaseModel):
    tmdbId: int = Field(gt=0)
    #: Craig has seen both films and means to merge them.
    merge: bool = False
    #: The film came from searching again rather than from the offered list.
    searched: bool = False


class IdentifySetAsideRequest(BaseModel):
    kind: Literal["tv", "not_film"]


class IdentifyDecisionResponse(BaseModel):
    movieId: uuid.UUID
    outcome: Literal["identified", "merged", "set_aside", "skipped", "waiting"]
    title: str


class RecentIdentificationResponse(BaseModel):
    actionId: uuid.UUID
    at: UtcDatetime
    by: str | None
    movieId: uuid.UUID
    replaced: str
    title: str
    year: int | None
    how: str
    merged: bool
    undone: bool


class RecentIdentificationsResponse(BaseModel):
    items: list[RecentIdentificationResponse]
