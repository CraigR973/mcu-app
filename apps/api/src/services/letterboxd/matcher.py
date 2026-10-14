"""Which film in *this* collection a diary entry refers to — Batch S8.

**Not the same job as `src/matching/engine.py`**, which scores a title against TMDB
*search results* to identify a disc. This matches against the 1,854 rows already in
`movies`, most of which the April import never identified. The normalisation primitives
are shared; the decision is not.

**The rules, and what each is for** (`DECISIONS.md` #158, #160, amended by #269):

1. **Exact on `tmdb_id` when the entry has one, and nothing else.** A CSV never has one;
   every RSS entry does (100 of 100 measured). Since Batch X5 an entry whose film is not in
   the catalogue is "not in the collection" and the sync gives it a film of its own: it no
   longer falls through to the title, which put a *Psycho* (1998) watch on the owned 1960
   film and *The Heat* (2013) on *Heat* (CT46-02).
2. **Otherwise normalised title, where a known year more than one apart excludes a
   candidate** (#158 amended, X5). Where either year is unknown the year never excludes,
   which is what #158 protected: an earlier pass required ``abs(year - filmYear) <= 1``
   everywhere and found **zero** owned-but-unidentified matches, because every
   unidentified row has ``year IS NULL``. Among what remains, an exact year breaks a tie.
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

        **The importer no longer reads this.** Since Batch 40 it re-checks ``tmdb_id`` on
        the row it is about to write against, because a merge earlier in the same run can
        replace that row and this outcome was decided before it (`DECISIONS.md` #197).
        Kept because it states the rule this module is judged by, and is tested directly.
        """
        return self.movie is not None and self.movie.tmdb_id is None


#: A known year this far from the entry's rules a candidate out: a UK release date or a
#: festival premiere can put a film's year one either side of Letterboxd's.
YEAR_TOLERANCE = 1


def year_excludes(entry_year: int | None, film_year: int | None) -> bool:
    """Both years known and more than :data:`YEAR_TOLERANCE` apart (#158 amended, X5)."""
    return (
        entry_year is not None
        and film_year is not None
        and abs(entry_year - film_year) > YEAR_TOLERANCE
    )


def match_entry(entry: DiaryEntry, index: CollectionIndex) -> MatchOutcome:
    """Decide which film this viewing was of, or refuse to."""
    if entry.tmdb_id is not None:
        # The feed names its film. Not in the catalogue is an answer, not a cue to guess by
        # title (X5): the caller gives the film a row of its own.
        movie = index.by_tmdb_id.get(entry.tmdb_id)
        if movie is not None:
            return MatchOutcome(entry=entry, movie=movie, via="tmdb_id")
        return MatchOutcome(entry=entry)

    candidates = [
        movie
        for movie in index.by_title.get(normalise_title(entry.title), [])
        if not year_excludes(entry.year, movie.year)
    ]
    if not candidates:
        return MatchOutcome(entry=entry)
    if len(candidates) == 1:
        return MatchOutcome(entry=entry, movie=candidates[0], via="title")

    # **Among what is left, an exact year breaks a tie.** A known year more than one apart
    # was excluded above; a NULL one (an unidentified row) never is, which is the artifact
    # #158 records.
    if entry.year is not None:
        exact = [m for m in candidates if m.year == entry.year]
        if len(exact) == 1:
            return MatchOutcome(entry=entry, movie=exact[0], via="title")

    return MatchOutcome(entry=entry, ambiguity=Ambiguity(entry=entry, candidates=candidates))
