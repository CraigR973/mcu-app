"""Camel-case wire contracts for the collection read, identify and watch surface."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from src.schemas.reviews import FilmReviewResponse
from src.schemas.valuation import CopyValuationResponse
from src.schemas.wire import UtcDatetime


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
    #: **`ge=0`, and it was `ge=1` until Batch 29.** The old bound encoded a true
    #: invariant — a film reached this response only by having a live disc — and §4.4
    #: broke it: sell your only copy and the film still has a `movies` row, a watch
    #: history and a detail page, with **zero** owned discs. The bound turned that into a
    #: 500 on the film's own page.
    #:
    #: Latent rather than new: a film whose every copy was soft-deleted would have done
    #: the same, and there are none of those today (checked against live Neon on
    #: 2026-09-12: zero). Same shape as `DECISIONS.md` #93 and #73 — a rule that is only
    #: wrong once something else starts using it.
    copyCount: int = Field(ge=0)
    #: Distinct places this film's live copies are kept — §6.2's "results display ...
    #: crucially the physical storage location". Usually one entry; a film owned on the
    #: shelf and in the digital library has two.
    locations: list[LocationResponse] = Field(default_factory=list)
    #: Whether the *requesting* user has a live watch-log row for this film. Per-user by
    #: design: in a two-person app "have I seen it" and "has he seen it" are different
    #: questions and averaging them would answer neither.
    watched: bool = False
    #: The requesting user's most recent watch, when there is one — Batch T2's "Seen
    #: 12 Mar 2025". Per user for the same reason as ``watched``.
    lastWatchedAt: date | None = None
    #: Batch U2 — the distinct editions of this film's owned copies, "SteelBook" or
    #: "Masters of Cinema"; empty when none records one. Read for a whole page of films in
    #: one grouped query, as ``locations`` is, never once per film.
    editions: list[str] = Field(default_factory=list)


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
    #: Batch V9: every review found for the film, Blu-ray.com's first.
    reviews: list[FilmReviewResponse] = []


class CollectionCopyResponse(BaseModel):
    id: uuid.UUID
    formats: list[str]
    location: str | None = None
    section: str | None = None
    shelf: str | None = None
    subCategory: str | None = None
    #: Batch U2.
    edition: str | None = None
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
    #: Batch 29 §4.2/§4.4 — null until the disc is listed for sale.
    ebayListingUrl: str | None = None
    listingPrice: str | None = None
    #: Carried so an edit started from this view — which is where every edit starts — can
    #: say which version it was based on when it is finally sent (Batch 8).
    updatedAt: UtcDatetime
    #: Batch T6 — the disc's stored eBay asking price, when a valuation run has reached
    #: its film and format. Null for a download, or before the first run.
    valuation: CopyValuationResponse | None = None


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
    #: Batch T7 — owned discs with Blu-ray.com specs. The Dolby Vision, Atmos and
    #: Region-free filters stay hidden while it is 0, because nothing could match them.
    discsWithSpecs: int = Field(default=0, ge=0)
    #: Batch V4 — every section in the vocabulary, in ``SECTIONS`` order, whether or not a
    #: disc is there yet. The copy form offers all of them, so a disc can be the first in a
    #: new place (Craig's house held none when it was added); ``sections`` above, which the
    #: Archive's filter reads, still lists only the places that hold a disc.
    allSections: list[str] = Field(default_factory=list)


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
