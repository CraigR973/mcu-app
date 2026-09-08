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
    #: The result's *displayed* title canonically equals the query. Used only to
    #: break a confidence tie — see :func:`~src.matching.engine.title_is_exact`.
    title_exact: bool = False
    popularity: float = 0.0
    poster_path: str | None = None
    overview: str = ""


class MatchResult(BaseModel):
    """The matcher's verdict for one input title."""

    raw_query: str
    query: str
    year: int | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list)
    matched: bool = False

    #: The leader is confident but tied with candidates that are not plausibly the
    #: same film, so its position was decided by TMDB popularity rather than by
    #: anything in the source row. Callers must not treat such a match as settled:
    #: the importer catalogues the item and sends the identification to review
    #: instead of enriching it. See :func:`~src.matching.engine.is_ambiguous`.
    ambiguous: bool = False
