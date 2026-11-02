"""Authenticated programme wire contract; dates, certainty and coverage stay separate."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

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
    identityStatus: Literal["verified", "unverified", "conflict"]
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
