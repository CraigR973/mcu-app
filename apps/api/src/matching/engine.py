from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..tmdb.client import TMDBClient
from ..tmdb.models import SearchResult
from .models import MatchCandidate, MatchResult

# A title is considered a confident match at or above this threshold.
HIGH_CONFIDENCE = 0.85
# Below this threshold the candidate should be flagged for human review.
LOW_CONFIDENCE = 0.6

_YEAR_RE = re.compile(r"\s*\((\d{4})\)\s*$")
_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def extract_year(title: str) -> tuple[str, int | None]:
    """Strip a trailing ``(YYYY)`` from the title and return (clean_title, year)."""
    stripped = title.strip()
    m = _YEAR_RE.search(stripped)
    if not m:
        return stripped, None
    cleaned = _YEAR_RE.sub("", stripped).rstrip()
    return cleaned, int(m.group(1))


def _canonicalise(title: str) -> str:
    no_punct = _PUNCT_RE.sub(" ", title.lower())
    return _WHITESPACE_RE.sub(" ", no_punct).strip()


def title_similarity(a: str, b: str) -> float:
    """Return a similarity score in [0, 1] for two titles, ignoring case and punctuation."""
    return SequenceMatcher(None, _canonicalise(a), _canonicalise(b)).ratio()


def score(
    query: str,
    query_year: int | None,
    result: SearchResult,
) -> tuple[float, float, str]:
    """Return (confidence, title_similarity, year_match_label) for one search result."""
    sim = title_similarity(query, result.title)
    if result.original_title and result.original_title.lower() != result.title.lower():
        sim = max(sim, title_similarity(query, result.original_title))

    result_year = result.year
    if query_year is None or result_year is None:
        year_label = "unknown"
        year_bonus = 0.0
    elif query_year == result_year:
        year_label = "exact"
        year_bonus = 0.15
    elif abs(query_year - result_year) <= 1:
        year_label = "close"
        year_bonus = 0.05
    else:
        year_label = "mismatch"
        year_bonus = -0.3

    confidence = max(0.0, min(1.0, sim + year_bonus))
    return confidence, sim, year_label


class MatchingEngine:
    """Find the most likely TMDB movies for a parsed spreadsheet title."""

    def __init__(
        self,
        tmdb: TMDBClient,
        top_n: int = 5,
        high_confidence: float = HIGH_CONFIDENCE,
    ) -> None:
        self._tmdb = tmdb
        self._top_n = top_n
        self._threshold = high_confidence
        self._cache: dict[tuple[str, int | None], MatchResult] = {}

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    async def match(self, raw_title: str) -> MatchResult:
        clean_title, year = extract_year(raw_title)
        cache_key = (_canonicalise(clean_title), year)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        results = await self._tmdb.search_movie(clean_title, year=year)
        # If a year-filtered search returned nothing, retry without the filter —
        # spreadsheet years sometimes disagree with TMDB's primary release date.
        if not results.results and year is not None:
            results = await self._tmdb.search_movie(clean_title, year=None)

        scored: list[MatchCandidate] = []
        for r in results.results:
            conf, sim, year_label = score(clean_title, year, r)
            scored.append(
                MatchCandidate(
                    tmdb_id=r.id,
                    title=r.title,
                    year=r.year,
                    confidence=conf,
                    title_similarity=sim,
                    year_match=year_label,
                    popularity=r.popularity,
                    poster_path=r.poster_path,
                )
            )

        scored.sort(key=lambda c: (c.confidence, c.popularity), reverse=True)
        top = scored[: self._top_n]
        matched = bool(top) and top[0].confidence >= self._threshold

        result = MatchResult(
            raw_query=raw_title,
            query=clean_title,
            year=year,
            candidates=top,
            matched=matched,
        )
        self._cache[cache_key] = result
        return result
