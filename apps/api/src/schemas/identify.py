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
    films: int = Field(ge=0)
    identified: int = Field(ge=0)
    queued: int = Field(ge=0)
    setAside: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    failed: int = Field(ge=0)
    searches: int = Field(ge=0)
    lastError: str | None


class IdentifyOverviewResponse(BaseModel):
    """How many unmatched films wait, and what became of the rest."""

    unidentified: int = Field(ge=0)
    waiting: int = Field(ge=0)
    setAsideTv: int = Field(ge=0)
    setAsideNotFilm: int = Field(ge=0)
    skipped: int = Field(ge=0)
    identified: int = Field(ge=0)
    #: Batch X9: identified films with an open doubt.
    inDoubt: int = Field(ge=0)
    run: IdentifyRunResponse | None


class FilmInCollectionResponse(BaseModel):
    """The film a choice would merge into, shown beside the one waiting."""

    movieId: uuid.UUID
    title: str
    year: int | None
    discs: int = Field(ge=0)
    watches: int = Field(ge=0)


class IdentifyCandidateResponse(BaseModel):
    tmdbId: int = Field(gt=0)
    title: str
    year: int | None
    posterPath: str | None
    overview: str
    votes: int = Field(ge=0)
    notes: list[str]
    #: Set when the collection already has this film: choosing it merges the two.
    inCollection: FilmInCollectionResponse | None
    #: Batch Y5: "tv" for an entry of ``seriesCandidates``, whose ``tmdbId`` is the series'.
    mediaType: Literal["film", "tv"] = "film"


class IdentifyDiscResponse(BaseModel):
    label: str


class IdentifyQueueItemResponse(BaseModel):
    movieId: uuid.UUID
    title: str
    discs: list[IdentifyDiscResponse]
    watches: int = Field(ge=0)
    note: str | None
    proposedTmdbId: int | None
    candidates: list[IdentifyCandidateResponse]


class IdentifyQueueResponse(BaseModel):
    items: list[IdentifyQueueItemResponse]
    total: int = Field(ge=0)


class IdentifySearchResponse(BaseModel):
    query: str
    #: Films only, as before Y5: the Identify page picks films from it.
    candidates: list[IdentifyCandidateResponse]
    #: Batch Y5 (#277): TMDB's series for the same words, for "Move only this copy".
    seriesCandidates: list[IdentifyCandidateResponse] = Field(default_factory=list)


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
    outcome: Literal["identified", "merged", "set_aside", "skipped", "waiting", "kept", "moved"]
    title: str


DoubtSource = Literal["recheck", "specs", "review"]


class IdentifyDoubtResponse(BaseModel):
    """An identified film that may be the wrong one — Batch X9 (CT46-01, CT46-03)."""

    doubtId: uuid.UUID
    movieId: uuid.UUID
    title: str
    year: int | None
    #: The film it is identified as now.
    tmdbId: int = Field(gt=0)
    posterPath: str | None
    source: DoubtSource
    note: str
    evidence: list[str]
    #: The copy the doubt names, or the film's copies when it names none.
    discs: list[IdentifyDiscResponse]
    copies: int = Field(ge=0)
    watches: int = Field(ge=0)
    collectionItemId: uuid.UUID | None
    candidates: list[IdentifyCandidateResponse]
    proposedTmdbId: int | None
    #: What to search TMDB for first.
    searchHint: str
    raisedAt: UtcDatetime


class IdentifyDoubtsResponse(BaseModel):
    items: list[IdentifyDoubtResponse]
    total: int = Field(ge=0)


class IdentificationDoubtResponse(BaseModel):
    """What the film page says while a doubt is open, and since Batch Y4 what either person
    needs to settle it there."""

    note: str
    source: DoubtSource
    raisedAt: UtcDatetime
    #: Batch Y4. Defaulted, so the shape still reads as X9 wrote it.
    doubtId: uuid.UUID | None = None
    #: The copy the doubt names, and how it reads ("Blu-ray · Front"), or none.
    collectionItemId: uuid.UUID | None = None
    copyLabel: str | None = None
    evidence: list[str] = Field(default_factory=list)
    #: The film T9 proposes, when it proposes one.
    proposedTmdbId: int | None = None
    proposedTitle: str | None = None
    proposedYear: int | None = None
    #: Batch Y5: the title the doubt was raised from (the sheet row's, for the re-check), which
    #: "Move only this copy" searches first: "Tinker Tailor Soldier Spy (TV)".
    searchHint: str | None = None


class MoveCopyRequest(BaseModel):
    """One copy is another film — Batch X9."""

    tmdbId: int = Field(gt=0)
    #: Batch Y5: "tv" when ``tmdbId`` is a TMDB series' id. An app cached before Y5 sends
    #: none, and meant a film.
    mediaType: Literal["film", "tv"] = "film"
    #: The doubt the move settles, when it came from one.
    doubtId: uuid.UUID | None = None


class MoveCopyResponse(BaseModel):
    """Where the copy went, and the audit row that undoes the move."""

    movieId: uuid.UUID
    title: str
    year: int | None
    #: The collection had no such film, so the move made one.
    created: bool
    actionId: uuid.UUID


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
