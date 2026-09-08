"""Camel-case wire contracts for the collection read and identify surface."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


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
