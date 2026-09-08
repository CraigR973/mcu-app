"""Camel-case wire contracts for the collection read, identify and watch surface."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class GenreResponse(BaseModel):
    id: int
    name: str


class CastResponse(BaseModel):
    personName: str
    tmdbPersonId: int | None = None
    characterName: str | None = None
    profilePath: str | None = None


class CreditResponse(BaseModel):
    personName: str
    tmdbPersonId: int | None = None
    role: Literal["director", "writer", "producer", "composer"]


class LocationResponse(BaseModel):
    """Where one of a film's live copies sits.

    ``label`` is composed server-side so every surface says "Front 2nd" the same way,
    rather than each of the three collection views inventing its own join of the two
    columns.
    """

    section: str | None = None
    shelf: str | None = None
    label: str


class MovieListItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    originalTitle: str | None = None
    year: int | None = None
    posterPath: str | None = None
    backdropPath: str | None = None
    tmdbRating: float | None = None
    runtimeMinutes: int | None = None
    bestFormatOwned: str | None = None
    bestHdrOwned: str | None = None
    bestAudioOwned: str | None = None
    identified: bool
    copyCount: int = Field(ge=1)
    #: Distinct places this film's live copies are kept — §6.2's "results display ...
    #: crucially the physical storage location". Usually one entry; a film owned on the
    #: shelf and in the digital library has two.
    locations: list[LocationResponse] = Field(default_factory=list)
    #: Whether the *requesting* user has a live watch-log row for this film. Per-user by
    #: design: in a two-person app "have I seen it" and "has he seen it" are different
    #: questions and averaging them would answer neither.
    watched: bool = False


class MoviePageResponse(BaseModel):
    items: list[MovieListItemResponse]
    totalMovies: int = Field(ge=0)
    totalItems: int = Field(ge=0)
    page: int = Field(ge=1)
    perPage: int = Field(ge=1)
    pages: int = Field(ge=0)


class MovieDetailResponse(MovieListItemResponse):
    imdbId: str | None = None
    overview: str | None = None
    tagline: str | None = None
    genres: list[GenreResponse]
    cast: list[CastResponse]
    crew: list[CreditResponse]
    trailerKey: str | None = None
    letterboxdSlug: str | None = None
    mediaType: str | None = None


class CollectionCopyResponse(BaseModel):
    id: uuid.UUID
    formats: list[str]
    location: str | None = None
    section: str | None = None
    shelf: str | None = None
    subCategory: str | None = None
    notes: str | None = None
    purchasePrice: str | None = None
    purchaseSource: str | None = None
    purchaseDate: date | None = None
    condition: str | None = None
    hasPlaybackIssues: bool
    playbackNotes: str | None = None
    videoSpecs: dict[str, Any] | None = None
    audioSpecs: list[dict[str, Any]] | None = None
    specialFeatures: list[str] | None = None
    regionCode: str | None = None
    releaseLabel: str | None = None
    listingStatus: str


class SearchResponse(BaseModel):
    items: list[MovieListItemResponse]
    query: str
    total: int = Field(ge=0)


class CandidateResponse(BaseModel):
    tmdbId: int
    title: str
    year: int | None = None
    overview: str
    posterPath: str | None = None
    confidence: float = Field(ge=0, le=1)
    titleSimilarity: float = Field(ge=0, le=1)


class CandidateListResponse(BaseModel):
    movieId: uuid.UUID
    title: str
    query: str
    candidates: list[CandidateResponse]


class IdentifyMovieRequest(BaseModel):
    tmdbId: int = Field(gt=0)


# ---------------------------------------------------------------------------
# Facets (Batch 6)
#
# Served from the data rather than hard-coded, so the section and shelf pickers can
# never offer a shelf that holds nothing or omit one that does. The web app's format
# and genre lists are static because they are closed vocabularies; where the discs
# actually are is not.
# ---------------------------------------------------------------------------


class ShelfFacetResponse(BaseModel):
    shelf: str
    movieCount: int = Field(ge=0)
    itemCount: int = Field(ge=0)


class SectionFacetResponse(BaseModel):
    section: str
    movieCount: int = Field(ge=0)
    itemCount: int = Field(ge=0)
    #: Empty for a section with no numbered shelves — Digital, Garage, the cabinets.
    shelves: list[ShelfFacetResponse] = Field(default_factory=list)


class DecadeFacetResponse(BaseModel):
    #: The decade's first year: 1940 means 1940–1949.
    decade: int
    movieCount: int = Field(ge=0)


class CollectionFacetsResponse(BaseModel):
    sections: list[SectionFacetResponse]
    #: Discs whose location text names somewhere the vocabulary does not cover. Shown
    #: so the count is never silently missing from the section totals.
    unsectionedItemCount: int = Field(ge=0)
    decades: list[DecadeFacetResponse]
    #: Films with no year at all — every one of them unidentified. A decade filter
    #: cannot include them, and saying so is better than letting the totals not add up.
    undatedMovieCount: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Watch log (Batch 6, roadmap §3.7)
# ---------------------------------------------------------------------------


class WatchLogCreateRequest(BaseModel):
    movieId: uuid.UUID
    #: Defaults to today at the router, where "today" can be evaluated once per request.
    watchedAt: date | None = None
    isRewatch: bool = False
    personalRating: float | None = Field(default=None, ge=0.5, le=5.0)
    review: str | None = Field(default=None, max_length=5000)

    @field_validator("personalRating")
    @classmethod
    def _half_stars_only(cls, value: float | None) -> float | None:
        """Mirror the database CHECK, so a bad rating is a 422 and not a 500."""
        if value is not None and round(value * 10) % 5 != 0:
            raise ValueError("personalRating must be a whole or half star")
        return value


class WatchLogResponse(BaseModel):
    id: uuid.UUID
    movieId: uuid.UUID
    movieTitle: str
    posterPath: str | None = None
    watchedAt: date
    isRewatch: bool
    personalRating: float | None = None
    review: str | None = None


class WatchLogPageResponse(BaseModel):
    items: list[WatchLogResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    perPage: int = Field(ge=1)
    pages: int = Field(ge=0)
