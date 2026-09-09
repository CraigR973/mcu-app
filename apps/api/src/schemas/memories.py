"""Wire models for Batch 37's private watch memories."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field


class OnThisDayMemoryResponse(BaseModel):
    """One of the caller's viewings on this calendar day in a prior year."""

    id: uuid.UUID
    movieId: uuid.UUID
    movieTitle: str
    posterPath: str | None = None
    watchedAt: date
    yearsAgo: int = Field(ge=1)
    personalRating: float | None = Field(default=None, ge=0.5, le=5.0)


class RewatchSuggestionResponse(BaseModel):
    """A personally highly rated film whose latest viewing is no longer recent."""

    movieId: uuid.UUID
    movieTitle: str
    posterPath: str | None = None
    lastWatchedAt: date
    personalRating: float = Field(ge=0.5, le=5.0)
