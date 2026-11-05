"""Authenticated programme wire contract; dates, certainty and coverage stay separate."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas.wire import UtcDatetime

ReleaseCategory = Literal["newRelease", "olderFilm", "unclassified"]
ReleaseFilter = Literal["all", "newRelease", "olderFilm", "unclassified"]
CoverageStatus = Literal[
    "notEnabled", "unavailable", "failed", "empty", "partial", "healthy", "stale"
]


class ProgrammeWindow(BaseModel):
    dateFrom: date
    dateTo: date


class ProgrammeDateCoverage(BaseModel):
    localDate: date
    status: CoverageStatus
    observed: bool
    complete: bool
    lastAttemptUtc: UtcDatetime | None
    lastSuccessUtc: UtcDatetime | None
    sourceUpdateLabel: str | None
    upstreamUtc: UtcDatetime | None
    upstreamAge: Literal["unknown", "current", "stale"]
    error: str | None


class ProgrammeVenue(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    source: str
    sourceUrl: str
    officialUrl: str
    collectionEnabled: bool
    coverage: list[ProgrammeDateCoverage]


class ProgrammeCategoryEvidence(BaseModel):
    sourceUrl: str | None
    description: str


class ProgrammeShowing(BaseModel):
    id: uuid.UUID
    venueId: uuid.UUID
    sourceTitle: str
    startsAtUtc: UtcDatetime
    endsAtUtc: UtcDatetime | None
    screen: str | None
    formats: list[str]
    releaseCategory: ReleaseCategory
    sourceReleaseDate: date | None
    reissue: bool | None
    categoryConfidence: Literal["verified", "unverified"]
    categoryEvidence: ProgrammeCategoryEvidence
    #: AC3 (#335): the run's reason in words, "UK release 1975 · rerun"; null when unlinked.
    categoryReason: str | None = None
    confirmation: Literal["confirmed", "unconfirmed"]
    lastSeenUtc: UtcDatetime
    observationStale: bool
    upstreamAge: Literal["unknown", "current", "stale"]
    bookingUrl: str | None


class ProgrammeFilm(BaseModel):
    id: str
    title: str
    movieId: uuid.UUID | None
    originalYear: int | None
    yearConfidence: Literal["verified", "unverified"]
    #: AC3 (#335): "review" waits for Craig's review list; "event" is never one film.
    identityStatus: Literal["verified", "unverified", "conflict", "review", "event"]
    owned: bool | None
    watched: bool | None
    showings: list[ProgrammeShowing]


class ProgrammeCategoryCounts(BaseModel):
    newRelease: int = Field(ge=0)
    olderFilm: int = Field(ge=0)
    unclassified: int = Field(ge=0)


class CinemaProgrammeResponse(BaseModel):
    generatedAtUtc: UtcDatetime
    window: ProgrammeWindow
    venues: list[ProgrammeVenue]
    films: list[ProgrammeFilm]
    categoryCounts: ProgrammeCategoryCounts
    matchedShowingCount: int = Field(ge=0)
    returnedShowingCount: int = Field(ge=0)
    truncated: bool
    selectionComplete: bool


class ReviewCandidate(BaseModel):
    """One film the lookup found with the programme's title, for Craig to choose."""

    tmdbId: int = Field(gt=0)
    title: str
    year: int | None
    posterPath: str | None
    voteCount: int = Field(ge=0)


class ReviewItem(BaseModel):
    """One programme film AC3 could not settle alone (#335): its rows across the listings that
    share a title and facts, so a film listed once per showing reads as one film."""

    key: str
    title: str
    sourceTitles: list[str]
    venues: list[str]
    futureShowings: int = Field(ge=0)
    reason: str
    candidates: list[ReviewCandidate]


class ReviewList(BaseModel):
    #: Most showings first; only films still showing.
    items: list[ReviewItem]


class ReviewDecision(BaseModel):
    """Exactly one: the TMDB film it is, from the item's own candidates, or not a film."""

    model_config = ConfigDict(extra="forbid")

    tmdbId: int | None = Field(default=None, gt=0)
    notAFilm: bool = False

    @model_validator(mode="after")
    def exactly_one(self) -> "ReviewDecision":
        if (self.tmdbId is None) == (not self.notAFilm):
            raise ValueError("Choose one of the films, or say it is not a film")
        return self
