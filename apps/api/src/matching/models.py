from __future__ import annotations

from pydantic import BaseModel, Field


class MatchCandidate(BaseModel):
    """A TMDB search result paired with the matcher's confidence assessment."""

    tmdb_id: int
    title: str
    year: int | None = None
    confidence: float
    title_similarity: float
    year_match: str  # "exact" | "close" | "mismatch" | "unknown"
    popularity: float = 0.0
    poster_path: str | None = None


class MatchResult(BaseModel):
    """The matcher's verdict for one input title."""

    raw_query: str
    query: str
    year: int | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list)
    matched: bool = False
