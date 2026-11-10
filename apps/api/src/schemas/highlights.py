"""Wire models for Home's Highlights panel — Batch V5, `DECISIONS.md` #228."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.reviews import ReviewScoreResponse
from src.schemas.wire import UtcDatetime


class HighlightRatingResponse(BaseModel):
    """One person's rating of a film: their highest, as "Worth a rewatch" reads it."""

    personName: str
    rating: float = Field(ge=0.5, le=5.0)


class TopRatedFilmResponse(BaseModel):
    movieId: uuid.UUID
    title: str
    year: int | None = None
    posterPath: str | None = None
    #: Whose rating it is. Usually one person, since only Craig rates (#159).
    ratings: list[HighlightRatingResponse]


class TopRatedRowResponse(BaseModel):
    """Films on the shelf rated 4½ or 5 stars, and whose ratings those are."""

    items: list[TopRatedFilmResponse]
    #: Who has rated any film, and who has rated none. Craig rates on Letterboxd and Mark
    #: does not (#159), so the row says whose ratings these are rather than implying both.
    ratedBy: list[str]
    notRatedBy: list[str]


class PersonViewingsResponse(BaseModel):
    personName: str
    viewings: int = Field(ge=1)
    #: AE9 (#355): whose page the name opens. Additive.
    personId: uuid.UUID | None = None


class RewatchedFilmResponse(BaseModel):
    """A film watched twice or more, counted across both diaries."""

    movieId: uuid.UUID
    title: str
    year: int | None = None
    posterPath: str | None = None
    viewings: int = Field(ge=2)
    byPerson: list[PersonViewingsResponse]


class ValuableDiscResponse(BaseModel):
    """An owned film and format at its stored value, with what the value rests on."""

    movieId: uuid.UUID
    title: str
    year: int | None = None
    posterPath: str | None = None
    formatCode: str
    price: str
    currency: str
    #: "current asking prices" today; the value's own basis, not a label chosen here.
    basis: str
    sampleSize: int = Field(ge=0)
    #: Batch X6: how the value was reached (``used`` or ``new_scaled``), the factor for the
    #: second, and the range of the listings behind it, for "7 used listings, £4–£9".
    valueBasis: Literal["used", "used_quartile", "new_scaled", "sales"]
    factor: str | None
    low: str
    high: str
    #: "as used copies".
    valuedAs: str
    checkedAt: UtcDatetime
    #: Owned discs of this film on this format. Two copies are two discs at one price.
    copies: int = Field(ge=1)


class BestReviewedFilmResponse(BaseModel):
    """An owned film by its Blu-ray.com review's Overall score, on a format on the shelf (V9)."""

    movieId: uuid.UUID
    title: str
    year: int | None = None
    posterPath: str | None = None
    overall: float = Field(gt=0, le=10)
    outOf: int = Field(gt=0)
    #: The format the review is of: one this film is owned on.
    formatCode: str | None = None
    #: The part of this disc review which scored best: picture, sound or extras.
    strength: str
    #: Kept with the card's link so the review page can show the site headings and scores.
    scores: list[ReviewScoreResponse] = Field(default_factory=list)


class RecentlyAddedFilmResponse(BaseModel):
    """A film by its newest owned copy added in the app — AE2 (#355, points 2 and 15)."""

    movieId: uuid.UUID
    title: str
    year: int | None = None
    posterPath: str | None = None
    #: Who added the copy. ``None`` when that profile has gone (``added_by`` is SET NULL).
    addedBy: str | None = None
    addedAt: UtcDatetime
    #: The copy's own formats, as it is on the shelf: two for a combo pack.
    formats: list[str]


class HighlightsResponse(BaseModel):
    """Everything the panel shows, in one request. An empty row is left for the page to hide."""

    topRated: TopRatedRowResponse
    mostRewatched: list[RewatchedFilmResponse]
    mostValuable: list[ValuableDiscResponse]
    #: Batch V9. Empty until Blu-ray.com's reviews are read.
    bestReviewed: list[BestReviewedFilmResponse] = []
    #: AE2. Empty when no copy was ever added in the app: the spreadsheet's rows carry no date.
    recentlyAdded: list[RecentlyAddedFilmResponse] = []
