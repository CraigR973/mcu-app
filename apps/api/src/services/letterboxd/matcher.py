"""Which film in *this* collection a diary entry refers to — Batch S8.

**Not the same job as `src/matching/engine.py`**, which scores a title against TMDB
*search results* to identify a disc. This matches against the 1,854 rows already in
`movies`, most of which the April import never identified. The normalisation primitives
are shared; the decision is not.

**The rules, and what each is for** (`DECISIONS.md` #158, #160):

1. **Exact on `tmdb_id` when the entry has one.** A CSV never does; every RSS entry does
   (100 of 100 measured), so this is the path S5 takes and it is written here so S5 adds
   no second matcher.
2. **Otherwise normalised title, with the year as a tie-breaker and never as a filter.**
   The filter version is the mistake #158 records: an earlier pass required
   ``abs(year - filmYear) <= 1`` and reported **zero** owned-but-unidentified matches —
   an artifact, because every unidentified row has ``year IS NULL`` and was excluded by
   the test itself. Taken at face value it would have shipped with neither an
   identification step nor a confirmation step.
3. **Anything that is not a single unambiguous candidate is offered, never guessed.**
   Measured across 2,047 distinct films, exactly **6 entries** are ambiguous —
   `Death on the Nile` and `Murder on the Orient Express`, both with several adaptations.

Normalisation covers what the real rows actually contain: trailing articles
(`'Collector, The'`), bracketed years (`'Death on the Nile [1978]'`), `&` against `and`,
and case. Those are not hypothetical — they are rows in this database.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

from src.matching.engine import rotate_trailing_article, strip_annotations
from src.models.movie import Movie
from src.services.letterboxd.diary import DiaryEntry

_AMPERSAND_RE = re.compile(r"\s*&\s*")
_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")
_LEADING_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)


def normalise_title(raw: str) -> str:
    """Reduce a title to the form two spellings of the same film share.

    Order matters. Bracketed annotations go first so ``'Death on the Nile [1978]'`` loses
    its year before anything else looks at the string; the trailing article is rotated
    while the comma is still there to find it by; ``&`` becomes ``and`` *before* punctuation
    is stripped, or the two spellings diverge into ``fast furious`` and ``fast and furious``.

    The leading article goes last and unconditionally, which makes ``'The Collector'``,
    ``'Collector, The'`` and ``'Collector'`` one key. That is deliberately aggressive: the
    cost is a rare collision between two genuinely different films, and **a collision is
    offered for confirmation rather than guessed**, so the aggressive version loses nothing
    that the confirmation step does not already catch.
    """
    text = unicodedata.normalize("NFKD", raw)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = strip_annotations(text)
    text = rotate_trailing_article(text.strip())
    text = _AMPERSAND_RE.sub(" and ", text)
    text = _PUNCT_RE.sub(" ", text.lower())
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return _LEADING_ARTICLE_RE.sub("", text).strip()


@dataclass(frozen=True)
class Ambiguity:
    """More than one film in the collection answers to this title."""

    entry: DiaryEntry
    candidates: list[Movie]

    def describe(self) -> str:
        options = ", ".join(
            f"{movie.title} ({movie.year if movie.year is not None else 'year unknown'})"
            for movie in self.candidates
        )
        return f"{self.entry.title} ({self.entry.year or '?'}) → {options}"


@dataclass
class CollectionIndex:
    """The collection, keyed the two ways a diary entry can arrive."""

    by_tmdb_id: dict[int, Movie] = field(default_factory=dict)
    by_title: dict[str, list[Movie]] = field(default_factory=lambda: defaultdict(list))
    total: int = 0


def build_index(movies: list[Movie]) -> CollectionIndex:
    """Index the live collection once, rather than querying per diary row.

    2,322 entries against 1,854 films is 2,322 queries the naive way, every one of them a
    round trip to Neon. Both fit in memory several times over.
    """
    index = CollectionIndex()
    for movie in movies:
        if movie.deleted_at is not None:
            continue
        index.total += 1
        if movie.tmdb_id is not None:
            index.by_tmdb_id[movie.tmdb_id] = movie
        for spelling in {movie.title, movie.original_title or movie.title}:
            key = normalise_title(spelling)
            if key and movie not in index.by_title[key]:
                index.by_title[key].append(movie)
    return index


@dataclass(frozen=True)
class MatchOutcome:
    """What the matcher decided, and why.

    Four possibilities, and the third is the one that exists for a reason:

    - ``movie`` set — a single film, safe to write against.
    - ``movie`` set and ``identifies`` true — it matched a row the April import never
      identified, so this import can fill in what is missing.
    - ``ambiguity`` set — several candidates, **offered rather than guessed**.
    - neither — not in the collection. Roughly a third of entries, and not an error.
    """

    entry: DiaryEntry
    movie: Movie | None = None
    ambiguity: Ambiguity | None = None
    #: How the film was found, for the report: ``"tmdb_id"``, ``"title"`` or ``None``.
    via: str | None = None

    @property
    def identifies(self) -> bool:
        """Whether writing this watch also lets the import identify the film.

        **580 of 2,322 entries**, covering **396 distinct films** — over half the 754 rows
        the April import never resolved (#160). One import, three dead features fixed.
        """
        return self.movie is not None and self.movie.tmdb_id is None


def match_entry(entry: DiaryEntry, index: CollectionIndex) -> MatchOutcome:
    """Decide which film this viewing was of, or refuse to."""
    if entry.tmdb_id is not None:
        movie = index.by_tmdb_id.get(entry.tmdb_id)
        if movie is not None:
            return MatchOutcome(entry=entry, movie=movie, via="tmdb_id")
        # Deliberately falls through to the title path rather than returning "not owned".
        # An unidentified row *has* no `tmdb_id` to match on, and those are exactly the
        # rows worth finding.

    candidates = index.by_title.get(normalise_title(entry.title), [])
    if not candidates:
        return MatchOutcome(entry=entry)
    if len(candidates) == 1:
        return MatchOutcome(entry=entry, movie=candidates[0], via="title")

    # **The year breaks a tie; it never excludes a candidate.** Narrowing to an exact year
    # is only safe among candidates that already agree on the title, and only when the
    # entry and the row both know their year — an unidentified row's is NULL, which is the
    # artifact #158 records.
    if entry.year is not None:
        exact = [m for m in candidates if m.year == entry.year]
        if len(exact) == 1:
            return MatchOutcome(entry=entry, movie=exact[0], via="title")

    return MatchOutcome(entry=entry, ambiguity=Ambiguity(entry=entry, candidates=candidates))
