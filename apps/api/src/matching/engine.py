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
_APOS_RE = re.compile(r"[\u2019']")  # straight + curly apostrophe
_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")
_BRACKET_RE = re.compile(r"\s*[\[(][^\[\]()]*[\])]\s*")
_TRAILING_ARTICLE_RE = re.compile(r"^(.+?),?\s+(the|a|an)\s*$", re.IGNORECASE)

# Trailing edition / cut markers that are not part of the canonical TMDB title.
_EDITION_SUFFIXES = [
    r"director'?s cut",
    r"the final cut",
    r"final cut",
    r"extended edition",
    r"extended cut",
    r"extended",
    r"special edition",
    r"theatrical cut",
    r"unrated(?: edition| cut)?",
    r"uncut",
    r"remastered",
    r"anniversary edition",
]
_EDITION_RE = re.compile(
    r"(?:\s*[:\-\u2013]\s*|\s+)(?:" + "|".join(_EDITION_SUFFIXES) + r")\s*$",
    re.IGNORECASE,
)


def extract_year(title: str) -> tuple[str, int | None]:
    """Strip a trailing ``(YYYY)`` from the title and return (clean_title, year)."""
    stripped = title.strip()
    m = _YEAR_RE.search(stripped)
    if not m:
        return stripped, None
    cleaned = _YEAR_RE.sub("", stripped).rstrip()
    return cleaned, int(m.group(1))


def strip_annotations(title: str) -> str:
    """Remove ``[...]`` and ``(...)`` annotations such as edition or box-set tags."""
    cleaned = _BRACKET_RE.sub(" ", title)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def rotate_trailing_article(title: str) -> str:
    """Rewrite library-card titles like 'Eiger Sanction, The' as 'The Eiger Sanction'."""
    m = _TRAILING_ARTICLE_RE.match(title)
    if not m:
        return title
    body = m.group(1).rstrip(",").strip()
    article = m.group(2).capitalize()
    return f"{article} {body}"


def strip_edition_suffix(title: str) -> str:
    """Drop trailing edition / cut markers (e.g. 'The Final Cut', 'Director's Cut')."""
    return _EDITION_RE.sub("", title).strip()


def normalise_query(raw_title: str) -> tuple[str, int | None]:
    """Apply year extraction, annotation stripping, edition stripping, and article rotation."""
    cleaned, year = extract_year(raw_title)
    cleaned = strip_annotations(cleaned)
    cleaned = strip_edition_suffix(cleaned)
    cleaned = rotate_trailing_article(cleaned)
    return cleaned, year


def _canonicalise(title: str) -> str:
    # Drop apostrophes outright so "Lampoon's" canonicalises identically to "Lampoons".
    no_apos = _APOS_RE.sub("", title.lower())
    no_punct = _PUNCT_RE.sub(" ", no_apos)
    return _WHITESPACE_RE.sub(" ", no_punct).strip()


def title_similarity(a: str, b: str) -> float:
    """Return a similarity score in [0, 1] for two titles, ignoring case and punctuation.

    When one canonical title is a strict substring of the other (e.g. a query
    matches the trailing portion of a longer subtitle-style result), the score
    is floored at 0.9 — high enough to clear the matched-flag threshold but
    not so high as to claim an exact match.
    """
    canon_a = _canonicalise(a)
    canon_b = _canonicalise(b)
    ratio = SequenceMatcher(None, canon_a, canon_b).ratio()
    if canon_a and canon_b and (canon_a in canon_b or canon_b in canon_a):
        return max(ratio, 0.9)
    return ratio


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
        clean_title, year = normalise_query(raw_title)
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
