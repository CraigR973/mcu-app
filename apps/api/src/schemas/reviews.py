"""Wire models for a film's reviews — Batch V9, `DECISIONS.md` #228, #241."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime


class ReviewScoreResponse(BaseModel):
    """One score under the site's own heading: "Movie", "Video 4K", "Overall"."""

    heading: str
    score: float = Field(gt=0, le=10)


class FilmReviewResponse(BaseModel):
    """A site's review of the film: a link, Brave's line, and Blu-ray.com's scores once read."""

    site: Literal["bluray_com", "avforums"]
    siteName: str
    url: str
    #: The disc format reviewed; ``None`` for a review of the film itself.
    formatCode: str | None = None
    #: Brave's title and one-line description of the page.
    title: str | None = None
    description: str | None = None
    #: Empty until read; AVForums' never are (#241).
    scores: list[ReviewScoreResponse]
    overall: float | None = None
    outOf: int | None = None
    scoresReadAt: UtcDatetime | None = None
    #: Why there are no scores, when there are none.
    note: str | None = None
