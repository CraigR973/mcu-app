"""Which of the collection's films a new eBay listing is — Batch T8a's deal scan.

The film page's estimator asks "is this listing that film?" of 200 listings it searched for
by name. The deal scan asks the reverse of listings nobody searched for: "is this listing
any film we care about?", for about a hundred new ones an hour. The films are few: those on
the Wanted list, and those owned on a format a Blu-ray or 4K would improve on.

**The film's title must open the listing's title**, after at most a few words sellers put
first ("NEW", "4K UHD", "Blu-ray"). The estimator's matcher accepts the title anywhere,
which is right for a search that named the film and wrong here: "Up" is a word in
thousands of listings. The matcher then still has its say, rejecting sequels, subtitles,
bundles, accessories and other formats as it does on the film page.

**A year straight after the title must be the film's** (Batch X1): "Halloween (2018)" is
not the 1978 film, though every word of the 1978 film's title opens it. Eight of the 25 wrong
products the scan found between 26 Sep and 9 Oct were another film of the same name.

**Two films named alike make no match.** If a listing opens with a title two catalogue films
share, it is skipped rather than filed under either.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ebay.matching import Listing, match, tokens
from src.models.collection_item import FORMAT_RANK, CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.wanted import WantedItem

#: The formats a deal can be for. A DVD is never an upgrade worth a push.
SCAN_FORMATS = ("4k_uhd", "blu_ray")

#: Words a seller puts before the title: condition, format, and the studio or label
#: ("Marvel Studios Guardians of the Galaxy Vol. 2", "Lionsgate The Expendables 3", both
#: seen on 26 Sep). Only these may precede it.
LEADING_NOISE = frozenset(
    {
        "new",
        "sealed",
        "brand",
        "rare",
        "mint",
        "4k",
        "uhd",
        "ultra",
        "hd",
        "blu",
        "ray",
        "bluray",
        "steelbook",
        "limited",
        "edition",
        "uk",
        "marvel",
        "studios",
        "disney",
        "pixar",
        "dc",
        "lionsgate",
        "paramount",
        "pictures",
        "universal",
        "warner",
        "bros",
        "sony",
        "arrow",
        "video",
        "criterion",
        "eureka",
    }
)
#: How far into the listing's title the film's may start.
MAX_LEADING_WORDS = 4

_ARTICLES = ("the ", "a ", "an ")


@dataclass(frozen=True)
class CatalogueFilm:
    """A film the scan looks for, and why."""

    movie_id: uuid.UUID
    tmdb_id: int | None
    title: str
    #: TMDB's release year, for the matcher's year rule; ``None`` refuses no year.
    year: int | None
    #: On the Wanted list and still looked for.
    wanted: bool
    #: The Wanted list's format, when one was asked for.
    preferred_format: str | None
    #: The best format owned, as an index into ``FORMAT_RANK``; ``None`` when nothing is
    #: owned. Owned with no readable format is ``len(FORMAT_RANK)``, which nothing improves.
    best_owned: int | None

    @property
    def owned(self) -> bool:
        return self.best_owned is not None

    def wants(self, format_code: str) -> bool:
        return self.wanted and self.preferred_format in (None, format_code)

    def upgraded_by(self, format_code: str) -> bool:
        """A listing on this format is better than anything owned."""
        if self.best_owned is None or format_code not in FORMAT_RANK:
            return False
        return FORMAT_RANK.index(format_code) < self.best_owned


@dataclass
class Catalogue:
    """The films, indexed by the first word of each way their title is written."""

    films: list[CatalogueFilm] = field(default_factory=list)
    _by_first: dict[str, list[tuple[CatalogueFilm, list[str]]]] = field(default_factory=dict)

    def add(self, film: CatalogueFilm) -> None:
        self.films.append(film)
        for variant in title_variants(film.title):
            words = tokens(variant)
            if words:
                self._by_first.setdefault(words[0], []).append((film, words))

    def named_in(self, listing: Listing) -> tuple[CatalogueFilm, str] | None:
        """The one film this listing is, and its format; ``None`` if none or several."""
        words = tokens(listing.title)
        leading = words[: MAX_LEADING_WORDS + 1]
        found: dict[uuid.UUID, tuple[CatalogueFilm, int, str]] = {}
        for word in dict.fromkeys(leading):
            for film, title_words in self._by_first.get(word, []):
                start = _opening_run(words, title_words)
                if start is None:
                    continue
                verdict = match(
                    listing, film_title=" ".join(title_words), country="GB", film_year=film.year
                )
                if not verdict.ok or verdict.format_code not in SCAN_FORMATS:
                    continue
                best = found.get(film.movie_id)
                if best is None or len(title_words) > best[1]:
                    found[film.movie_id] = (film, len(title_words), verdict.format_code)
        if not found:
            return None
        longest = max(length for _, length, _ in found.values())
        winners = [(film, code) for film, length, code in found.values() if length == longest]
        if len(winners) != 1:
            return None
        return winners[0]


def title_variants(title: str) -> list[str]:
    """A title, and without its leading article: sellers often drop "The"."""
    variants = [title]
    lowered = title.lower()
    for article in _ARTICLES:
        if lowered.startswith(article) and len(title) > len(article):
            variants.append(title[len(article) :])
    return variants


def _opening_run(words: list[str], title_words: list[str]) -> int | None:
    """Where the title's words start in the listing, if only seller's words precede them."""
    for start in range(min(MAX_LEADING_WORDS, len(words) - len(title_words)) + 1):
        if words[start : start + len(title_words)] == title_words and all(
            word in LEADING_NOISE for word in words[:start]
        ):
            return start
    return None


async def load_catalogue(db: AsyncSession) -> Catalogue:
    """The identified live films on the Wanted list or on the shelf."""
    wanted_rows = await db.execute(
        select(WantedItem.movie_id, WantedItem.preferred_format).where(
            WantedItem.deleted_at.is_(None), WantedItem.is_active.is_(True)
        )
    )
    wanted: dict[uuid.UUID, str | None] = {}
    for movie_id, preferred in wanted_rows:
        code = preferred if preferred in SCAN_FORMATS else None
        wanted[movie_id] = code if movie_id not in wanted else None

    owned_rows = await db.execute(
        select(CollectionItem.movie_id, CollectionItem.formats).where(owned_copy())
    )
    best: dict[uuid.UUID, int] = {}
    for movie_id, formats in owned_rows:
        ranks = [FORMAT_RANK.index(code) for code in formats or [] if code in FORMAT_RANK]
        rank = min(ranks) if ranks else len(FORMAT_RANK)
        best[movie_id] = min(rank, best.get(movie_id, len(FORMAT_RANK)))

    ids = set(wanted) | set(best)
    catalogue = Catalogue()
    if not ids:
        return catalogue
    films = await db.execute(
        select(Movie.id, Movie.tmdb_id, Movie.title, Movie.year).where(
            Movie.id.in_(ids), Movie.deleted_at.is_(None), Movie.tmdb_id.is_not(None)
        )
    )
    for movie_id, tmdb_id, title, year in films:
        catalogue.add(
            CatalogueFilm(
                movie_id=movie_id,
                tmdb_id=tmdb_id,
                title=title,
                year=year,
                wanted=movie_id in wanted,
                preferred_format=wanted.get(movie_id),
                best_owned=best.get(movie_id),
            )
        )
    return catalogue
