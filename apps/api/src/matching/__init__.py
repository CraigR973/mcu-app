from .engine import (
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE,
    MatchingEngine,
    extract_year,
    normalise_query,
    rotate_trailing_article,
    score,
    strip_annotations,
    strip_edition_suffix,
    title_similarity,
)
from .models import MatchCandidate, MatchResult

__all__ = [
    "MatchingEngine",
    "MatchCandidate",
    "MatchResult",
    "extract_year",
    "normalise_query",
    "rotate_trailing_article",
    "strip_annotations",
    "strip_edition_suffix",
    "title_similarity",
    "score",
    "HIGH_CONFIDENCE",
    "LOW_CONFIDENCE",
]
