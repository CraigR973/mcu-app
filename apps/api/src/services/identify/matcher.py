"""Which TMDB film a spreadsheet title names — Batch T9.

**For each film, in this order, stopping as soon as the title is found:**

1. Search TMDB with each whole reading of the title (``titles.py``), with its year when it
   has one. A result counts when its title is ours, allowing for a typo.
2. If none is, search again more loosely: "Ep" spelt out and "&" as "and", without a leading
   article ("The Marathon Man" found nothing, "Marathon Man" the film), and by the first half
   of the title, which a typo later on cannot spoil ("Fantastic Beasts and…").
3. Read the alternative titles of the leading results. TMDB's search matches them: "Ice Age
   3" finds "Ice Age: Dawn of the Dinosaurs" by its US title, and "Marie Walewska" finds
   "Conquest" by its French one.
4. Ask TMDB's TV index, so "Dynasties" is set aside as a series rather than asked about.
5. **One** Brave web search for the film's TMDB page, for typos TMDB cannot see past
   ("Peepiing Tom"). Each page is fetched from TMDB's own API and counts only if TMDB's record
   matches the title. Brave bills every search, so it is the last resort.

**Then the rule from ``docs/phase-batches.md``:** a film is identified automatically only
when one TMDB film is a strong match and, whenever TMDB holds another film of the same
title, a year or a person agrees with it and not with the others. A match that would merge
into a film the collection already has waits for Craig, however strong.

**"The same title" means the same title**, typos allowed, and includes TMDB's obscure
namesakes: 15 films are called "Speed" and 50 "Emma", mostly shorts nobody has rated. They
count because the rule says they do, and because TMDB's ranking cannot be trusted to put the
real rivals first: its search for "Seven" does not show "Se7en" in twenty results. **It does
not include a title that is ours plus a subtitle.** "Death on the Nile: Making of Featurette"
is not a rival to "Death on the Nile" (1978), and counting it hid the year that decides it.

**What a match on one side of a colon is worth.** "Dr. Strangelove" is the start of TMDB's
title, and "Live Baby Live" the end of "INXS: Live Baby Live". The first is taken only with a
year or a person agreeing; the second never, because it is also how a documentary about a
film is named ("Unseen + Untold: National Lampoon's Animal House" was taken for the film by
an early version of this).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Protocol

import httpx

from src.services.identify.titles import (
    ParsedTitle,
    Reading,
    TitleMatch,
    compare,
    fold,
    leading_words,
    simplified,
    without_article,
)
from src.services.specs.search import SearchHit
from src.tmdb.models import Movie as TmdbMovie
from src.tmdb.models import (
    PersonMovieCredits,
    PersonSearchResults,
    SearchResult,
    SearchResults,
    TvSearchResults,
)

#: Result pages read for other films of the same title. TMDB lists them among everything
#: else that shares the words, so a short title needs several pages; five is 100 results.
MAX_PAGES = 5
#: Leading results whose alternative titles are read when none matches by its own title.
ALT_TITLE_LOOKS = 8
#: TMDB pages taken from one Brave search.
BRAVE_PAGES = 3
#: Namesakes whose credits are read to test a surname ("Hitchcock"). Past this a surname
#: cannot decide, because the rivals were not all checked.
MAX_RIVAL_CREDITS = 40
#: A year on the disc and TMDB's may differ by one: a festival or UK release date.
YEAR_TOLERANCE = 1
#: Cast members a name is looked for among. A bit part is no evidence.
TOP_BILLED = 15
#: Candidates offered to Craig.
OFFERED = 5
#: The fewest TMDB votes for a film to be "well known" when Craig's words ("Original",
#: "Remake") order what he is offered: the 1916 "Clash of the Titans" is not the original.
KNOWN_VOTES = 50

_TMDB_MOVIE_PAGE = re.compile(r"themoviedb\.org/(?:[a-z]{2}(?:-[A-Z]{2})?/)?movie/(\d+)")
_TMDB_TV_PAGE = re.compile(r"themoviedb\.org/(?:[a-z]{2}(?:-[A-Z]{2})?/)?tv/(\d+)")
#: Where a TMDB page's title stops naming the show: "Fingerbobs (TV Series 1972-1972) — The
#: Movie Database (TMDB)".
_PAGE_TITLE_TAIL = re.compile(r"\s+\((?:TV|\d{4})|\s+[\u2014|-]\s+|\s+\|\s+")

#: Where a name came from, in the words Craig reads.
TITLE_SOURCE = "named in the title"
GROUPING_SOURCE = "from the disc's grouping"
DASH_SOURCE = "after the dash in the title"

#: Crew jobs a name may match, best first. A caterer called Powell is not evidence.
_ROLE_ORDER = (
    "director",
    "screenplay",
    "writer",
    "novel",
    "story",
    "author",
    "characters",
    "producer",
    "original music composer",
    "cast",
)
_ROLE_WORDS = {
    "director": "directed it",
    "screenplay": "wrote it",
    "writer": "wrote it",
    "novel": "wrote the novel",
    "story": "wrote the story",
    "author": "wrote it",
    "characters": "created its characters",
    "producer": "produced it",
    "original music composer": "wrote its music",
    "cast": "is in its cast",
}


class Tmdb(Protocol):
    """What identification needs from TMDB. :class:`~src.tmdb.client.TMDBClient` is one."""

    async def search_movie(
        self, query: str, year: int | None = None, page: int = 1
    ) -> SearchResults: ...

    async def get_movie(
        self, movie_id: int, append_to_response: list[str] | None = None
    ) -> TmdbMovie: ...

    async def search_tv(self, query: str, page: int = 1) -> TvSearchResults: ...

    async def search_person(self, query: str, page: int = 1) -> PersonSearchResults: ...

    async def get_person_movie_credits(self, person_id: int) -> PersonMovieCredits: ...


class WebSearch(Protocol):
    """What identification needs from Brave. :class:`~src.services.specs.search.BraveSearch`
    is one; ``search_calls`` counts every billed request, retries included."""

    search_calls: int

    @property
    def configured(self) -> bool: ...

    async def search(
        self, query: str, *, count: int = ..., country: str = ...
    ) -> list[SearchHit]: ...


# ---------------------------------------------------------------------------
# Candidates and what is known about them
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Credit:
    name: str
    #: "cast", or the crew job in lower case: "director", "novel", "screenplay"…
    role: str
    order: int = 0

    @property
    def counts(self) -> bool:
        """A credit a name hint may match: a creative job, or near the top of the cast."""
        if self.role == "cast":
            return self.order < TOP_BILLED
        return self.role in _ROLE_WORDS


@dataclass
class Candidate:
    """One TMDB film that might be the one on the shelf."""

    tmdb_id: int
    title: str
    original_title: str
    year: int | None
    popularity: float = 0.0
    vote_count: int = 0
    poster_path: str | None = None
    overview: str = ""
    genre_ids: tuple[int, ...] = ()
    #: "search", "brave" (a web search for its TMDB page), "rivals" (the scan for other
    #: films of the same title) or "person" (found in a named person's films).
    origin: str = "search"
    #: None until fetched.
    alt_titles: tuple[str, ...] | None = None
    credits: tuple[Credit, ...] | None = None
    #: TMDB's rank in the search that found it, for ordering only.
    rank: int = 999

    @classmethod
    def from_search(cls, result: SearchResult, *, origin: str, rank: int) -> Candidate:
        return cls(
            tmdb_id=result.id,
            title=result.title,
            original_title=result.original_title,
            year=result.year,
            popularity=result.popularity,
            vote_count=result.vote_count,
            poster_path=result.poster_path,
            overview=result.overview,
            genre_ids=tuple(result.genre_ids),
            origin=origin,
            rank=rank,
        )

    @classmethod
    def from_movie(cls, movie: TmdbMovie, *, origin: str, rank: int) -> Candidate:
        candidate = cls(
            tmdb_id=movie.id,
            title=movie.title,
            original_title=movie.original_title,
            year=None,
            popularity=movie.popularity,
            vote_count=movie.vote_count,
            poster_path=movie.poster_path,
            overview=movie.overview,
            genre_ids=tuple(g.id for g in movie.genres),
            origin=origin,
            rank=rank,
        )
        candidate.absorb(movie)
        return candidate

    def absorb(self, movie: TmdbMovie) -> None:
        """Take the details a search result lacks: alternative titles and credits."""
        if movie.alternative_titles is not None:
            self.alt_titles = tuple(t.title for t in movie.alternative_titles.titles if t.title)
        if movie.credits is not None:
            people = [Credit(c.name, "cast", c.order) for c in movie.credits.cast]
            people += [Credit(c.name, c.job.lower()) for c in movie.credits.crew]
            self.credits = tuple(people)
        if self.year is None and movie.release_date:
            try:
                self.year = int(movie.release_date.split("-", 1)[0])
            except ValueError:
                self.year = None

    @property
    def titles(self) -> list[tuple[str, str]]:
        """Every title this film goes by, with where it came from."""
        found = [(self.title, "title")]
        if self.original_title and fold(self.original_title) != fold(self.title):
            found.append((self.original_title, "original title"))
        for alternate in self.alt_titles or ():
            found.append((alternate, "alternative title"))
        return found


@dataclass(frozen=True)
class Fit:
    """How well a candidate fits the title: the best reading it matched, and how."""

    tier: int
    match: TitleMatch
    reading: str
    matched_title: str
    matched_by: str

    @property
    def near_exact(self) -> bool:
        return self.match.near_exact

    @property
    def same_title(self) -> bool:
        return self.match.same_title


_NO_FIT = Fit(tier=9, match=TitleMatch("none", 0.0), reading="", matched_title="", matched_by="")
_HOW_RANK = {"exact": 5, "words": 4, "typo": 3, "subtitle": 2, "tail": 1, "none": 0}


def fit(candidate: Candidate, readings: Sequence[Reading]) -> Fit:
    """The best match between any reading of ours and any title of the candidate's.

    A lower tier beats a higher one, then an exact match beats a typo, then the closer ratio.
    An alternative title counts only as the same title: TMDB holds hundreds of them per film,
    in every language, and one side of a colon in one of those is no evidence ("A todo gas:
    7", Furious 7's Spanish title, is not "Seven").
    """
    best = _NO_FIT
    for reading in readings:
        for title, source in candidate.titles:
            match = compare(reading.text, title)
            if not match.near_exact or (source == "alternative title" and not match.same_title):
                continue
            here = Fit(reading.tier, match, reading.text, title, source)
            if best is _NO_FIT or (
                here.tier,
                -_HOW_RANK[here.match.how],
                -here.match.ratio,
            ) < (best.tier, -_HOW_RANK[best.match.how], -best.match.ratio):
                best = here
    return best


def year_agrees(candidate: Candidate, year: int | None) -> bool | None:
    """True or False against the title's year; None when either has none."""
    if year is None or candidate.year is None:
        return None
    return abs(candidate.year - year) <= YEAR_TOLERANCE


def _role_rank(role: str) -> int:
    return _ROLE_ORDER.index(role) if role in _ROLE_ORDER else len(_ROLE_ORDER)


def person_credited(name: str, credits: Sequence[Credit]) -> Credit | None:
    """The credit that confirms a name, if any, preferring the job that best explains it.

    A full name is matched against every credit, allowing for a typo ("Alec Guiness"). A
    surname alone ("Hitchcock", "Kubrick", "Powell") is matched against surnames, and only
    in the creative credits and the top of the cast, so a crew member who shares it is not
    evidence.
    """
    wanted = fold(name)
    tokens = wanted.split()
    if not tokens:
        return None
    found: list[Credit] = []
    for credit in credits:
        folded = fold(credit.name)
        if len(tokens) > 1:
            if folded == wanted or SequenceMatcher(None, folded, wanted).ratio() >= 0.88:
                found.append(credit)
        elif credit.counts and folded.split():
            surname = folded.split()[-1]
            if surname == tokens[0] or (
                len(tokens[0]) >= 6 and SequenceMatcher(None, surname, tokens[0]).ratio() >= 0.9
            ):
                found.append(credit)
    counted = [c for c in found if c.counts] or found
    return min(counted, key=lambda c: _role_rank(c.role)) if counted else None


def describe_credit(credit: Credit, source: str) -> str:
    phrase = _ROLE_WORDS.get(credit.role, f"is credited on it ({credit.role})")
    return f"{credit.name}, {source}, {phrase}"


# ---------------------------------------------------------------------------
# The outcome
# ---------------------------------------------------------------------------


@dataclass
class Proposal:
    """What the dry run proposes for one film, and why."""

    outcome: str  #: "identify", "ask" or "set_aside"
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    chosen: Candidate | None = None
    candidates: list[Candidate] = field(default_factory=list)
    set_aside_as: str | None = None  #: "tv" or "not_film"
    #: The collection's film this would merge into, as (movie id, title, year).
    merge_into: tuple[str, str, int | None] | None = None
    brave_query: str | None = None
    #: Evidence per offered candidate, by TMDB id, in the words Craig reads.
    notes: dict[int, list[str]] = field(default_factory=dict)


@dataclass
class Counters:
    tmdb_calls: int = 0
    brave_searches: int = 0


@dataclass(frozen=True)
class PersonFilm:
    title: str
    year: int | None
    role: str


Holder = Callable[[int], tuple[str, str, int | None] | None]


# ---------------------------------------------------------------------------
# The search
# ---------------------------------------------------------------------------


class Identifier:
    """Finds and judges TMDB candidates for one title at a time, caching across titles."""

    def __init__(
        self,
        tmdb: Tmdb,
        web: WebSearch | None = None,
        *,
        brave_budget: int = 0,
    ) -> None:
        self._tmdb = tmdb
        self._web = web
        self.brave_budget = brave_budget
        self.counters = Counters()
        self._searches: dict[tuple[str, int | None, int], SearchResults] = {}
        self._details: dict[int, TmdbMovie | None] = {}
        self._tv: dict[str, TvSearchResults] = {}
        self._people: dict[str, dict[int, PersonFilm] | None] = {}

    # -- TMDB, cached ------------------------------------------------------------

    async def _search(self, query: str, year: int | None = None, page: int = 1) -> SearchResults:
        key = (fold(query), year, page)
        if key not in self._searches:
            self.counters.tmdb_calls += 1
            self._searches[key] = await self._tmdb.search_movie(query, year=year, page=page)
        return self._searches[key]

    async def _details_for(self, tmdb_id: int) -> TmdbMovie | None:
        if tmdb_id not in self._details:
            self.counters.tmdb_calls += 1
            try:
                self._details[tmdb_id] = await self._tmdb.get_movie(
                    tmdb_id, append_to_response=["credits", "alternative_titles"]
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                self._details[tmdb_id] = None
        return self._details[tmdb_id]

    async def _fill(self, candidate: Candidate) -> None:
        if candidate.alt_titles is not None and candidate.credits is not None:
            return
        movie = await self._details_for(candidate.tmdb_id)
        if movie is not None:
            candidate.absorb(movie)
        candidate.alt_titles = candidate.alt_titles or ()
        candidate.credits = candidate.credits or ()

    async def _search_tv(self, query: str) -> TvSearchResults:
        key = fold(query)
        if key not in self._tv:
            self.counters.tmdb_calls += 1
            self._tv[key] = await self._tmdb.search_tv(query)
        return self._tv[key]

    async def _filmography(self, name: str) -> dict[int, PersonFilm] | None:
        """The films of the person a full name names, or None if TMDB has no such person.

        Used for names of two words or more. The person's own list covers every film of the
        title they made, however many namesakes the title has: "The Letter" has 64 on TMDB,
        and Bette Davis made one of them.
        """
        key = fold(name)
        if key in self._people:
            return self._people[key]
        self.counters.tmdb_calls += 1
        people = await self._tmdb.search_person(name)
        person = next(
            (
                p
                for p in people.results
                if fold(p.name) == key or SequenceMatcher(None, fold(p.name), key).ratio() >= 0.9
            ),
            None,
        )
        if person is None:
            self._people[key] = None
            return None
        self.counters.tmdb_calls += 1
        credits = await self._tmdb.get_person_movie_credits(person.id)
        films: dict[int, PersonFilm] = {}
        for crew in credits.crew:
            role = (crew.job or "").lower()
            if role not in _ROLE_WORDS:
                continue
            known = films.get(crew.id)
            if known is None or _role_rank(role) < _role_rank(known.role):
                films[crew.id] = PersonFilm(crew.title, _year_of(crew.release_date), role)
        for cast in credits.cast:
            if cast.id not in films and (cast.order is None or cast.order < TOP_BILLED):
                films[cast.id] = PersonFilm(cast.title, _year_of(cast.release_date), "cast")
        self._people[key] = films
        return films

    # -- gathering -----------------------------------------------------------------

    async def _gather(
        self,
        found: dict[int, Candidate],
        query: str,
        *,
        year: int | None,
        origin: str,
        pages: int = 1,
        seen: list[int] | None = None,
    ) -> bool:
        """Add a search's results to ``found``, and their ids to ``seen`` in TMDB's order.
        True when every page was read."""
        page = 1
        while True:
            results = await self._search(query, year, page)
            for rank, result in enumerate(results.results):
                if seen is not None and result.id not in seen:
                    seen.append(result.id)
                if result.id not in found:
                    found[result.id] = Candidate.from_search(
                        result, origin=origin, rank=(page - 1) * 20 + rank
                    )
            if page >= results.total_pages or page >= pages:
                return page >= results.total_pages
            page += 1

    async def _scan_namesakes(
        self, found: dict[int, Candidate], title: str, year: int | None, seen: list[int]
    ) -> bool:
        """Every TMDB film of this title we can see, and whether we saw them all.

        Without a year, up to :data:`MAX_PAGES` pages of results. With one, the searches for
        that year and the years either side are complete on their own, because a namesake
        from another year cannot share it. ``seen`` collects what the searches returned.
        """
        complete = await self._gather(
            found, title, year=None, origin="rivals", pages=MAX_PAGES, seen=seen
        )
        if year is not None and not complete:
            for near in (year - 1, year, year + 1):
                await self._gather(
                    found, title, year=near, origin="rivals", pages=MAX_PAGES, seen=seen
                )
            return True
        return complete

    async def _brave(self, parsed: ParsedTitle) -> tuple[str | None, list[int], bool]:
        """One web search for the film's TMDB page: (query, movie ids, whether a TV page led)."""
        if self._web is None or not self._web.configured:
            return None, [], False
        if self.counters.brave_searches >= self.brave_budget:
            return None, [], False
        query = f"site:themoviedb.org {parsed.main}"
        if parsed.year is not None:
            query += f" {parsed.year}"
        before = self._web.search_calls
        try:
            hits = await self._web.search(query, count=10, country="GB")
        finally:
            self.counters.brave_searches += self._web.search_calls - before
        ids: list[int] = []
        tv_first = False
        for index, hit in enumerate(hits):
            movie = _TMDB_MOVIE_PAGE.search(hit.url)
            if movie is not None:
                tmdb_id = int(movie.group(1))
                if tmdb_id not in ids:
                    ids.append(tmdb_id)
            elif index == 0 and _TMDB_TV_PAGE.search(hit.url):
                # Only a page for a show of this very title says TV. The first page Brave
                # gave for "Munch - Our Greatest Hits" was an unrelated series called "Munch".
                show = _PAGE_TITLE_TAIL.split(hit.title, maxsplit=1)[0].strip()
                tv_first = bool(show) and any(
                    compare(title, show).same_title for title in (parsed.main, parsed.tv_title)
                )
        return query, ids[:BRAVE_PAGES], tv_first

    @staticmethod
    def _fits(found: dict[int, Candidate], parsed: ParsedTitle) -> dict[int, Fit]:
        return {c.tmdb_id: fit(c, parsed.readings) for c in found.values()}

    # -- the whole thing -----------------------------------------------------------

    async def identify(self, parsed: ParsedTitle, *, held: Holder | None = None) -> Proposal:
        """Propose what to do with one film. Reads TMDB and Brave; writes nothing."""
        if parsed.not_film:
            return Proposal("set_aside", reason=parsed.not_film, set_aside_as="not_film")
        if parsed.tv:
            return Proposal("set_aside", reason=f"A TV series: {parsed.tv}.", set_aside_as="tv")

        found: dict[int, Candidate] = {}
        whole = [r for r in parsed.readings if r.tier == 1]
        for reading in whole:
            if parsed.year is not None:
                await self._gather(found, reading.text, year=parsed.year, origin="search")
            await self._gather(found, reading.text, year=None, origin="search")
        fits = self._fits(found, parsed)

        def strong() -> bool:
            return any(f.tier == 1 and f.same_title for f in fits.values())

        def near() -> bool:
            return any(f.tier == 1 and f.near_exact for f in fits.values())

        if not strong():
            # Step 2: looser searches, then the title's other parts.
            queries: list[str] = []
            for reading in whole:
                for query in (
                    simplified(reading.text),
                    without_article(reading.text),
                    without_article(simplified(reading.text)),
                    leading_words(reading.text),
                ):
                    if query and query not in queries and query != reading.text:
                        queries.append(query)
            for query in queries:
                await self._gather(found, query, year=None, origin="search")
            for reading in parsed.readings:
                if reading.tier > 1:
                    await self._gather(found, reading.text, year=parsed.year, origin="search")
            fits = self._fits(found, parsed)

        if not strong():
            # Step 3: why did the leading results come back? Often an alternative title.
            leading = sorted(
                found.values(),
                key=lambda c: (not fits[c.tmdb_id].near_exact, c.rank, -c.vote_count),
            )
            for candidate in leading[:ALT_TITLE_LOOKS]:
                await self._fill(candidate)
            fits = self._fits(found, parsed)

        proposal = Proposal("ask")
        if not strong():
            # Step 4: is it a TV series? Only part of a title, or nothing, matched as a film.
            show = await self._tv_show(parsed)
            if show is not None:
                return Proposal(
                    "set_aside",
                    reason=f"TMDB lists '{show[0]}' as a TV series"
                    + (f" ({show[1]})" if show[1] else "")
                    + ", and has no film of exactly that name.",
                    set_aside_as="tv",
                )
        if not near():
            # Step 5: one web search for its TMDB page.
            query, ids, tv_first = await self._brave(parsed)
            proposal.brave_query = query
            for tmdb_id in ids:
                if tmdb_id in found:
                    await self._fill(found[tmdb_id])
                    found[tmdb_id].origin = "brave"
                    continue
                movie = await self._details_for(tmdb_id)
                if movie is not None:
                    found[tmdb_id] = Candidate.from_movie(movie, origin="brave", rank=500)
            fits = self._fits(found, parsed)
            if tv_first and not near():
                return Proposal(
                    "set_aside",
                    reason="The web search's first TMDB page for it is a TV series, and "
                    "TMDB has no film of that name.",
                    set_aside_as="tv",
                    brave_query=query,
                )

        return await self._decide(parsed, found, fits, proposal, held=held)

    async def _tv_show(
        self, parsed: ParsedTitle, *, whole_title_only: bool = False
    ) -> tuple[str, int | None, int] | None:
        """A show in TMDB's TV index with this title: (name, first year, votes).

        The title without its TV words ("Game of Thrones" for "... Season 1") is tried too,
        except once a film has matched: then only the whole title counts, or "Open Season
        2" would meet a series called "Open".
        """
        titles = [parsed.main] if whole_title_only else [parsed.tv_title or parsed.main]
        if parsed.main not in titles:
            titles.append(parsed.main)
        for title in titles:
            results = await self._search_tv(title)
            for show in results.results[:10]:
                for name in (show.name, show.original_name):
                    if name and compare(title, name).same_title:
                        return show.name, show.year, show.vote_count
        return None

    async def _people_evidence(
        self,
        parsed: ParsedTitle,
        leader: Candidate,
        namesakes: list[Candidate],
        found: dict[int, Candidate],
        title: str,
    ) -> tuple[dict[int, list[tuple[str, Credit]]], bool]:
        """Which contenders each name confirms, and whether every namesake was checked.

        A full name is checked against the person's own films, which covers every namesake.
        A surname is checked against each contender's credits, which covers them only while
        there are no more than :data:`MAX_RIVAL_CREDITS`.
        """
        hints = [(name, TITLE_SOURCE) for name in parsed.people]
        hints += [(name, GROUPING_SOURCE) for name in parsed.grouping_people]
        hints += [(name, DASH_SOURCE) for name in parsed.weak_people]
        credited: dict[int, list[tuple[str, Credit]]] = {}
        if not hints:
            return credited, True
        contenders = [leader, *namesakes]
        surnames = [(name, source) for name, source in hints if len(fold(name).split()) == 1]
        for name, source in hints:
            if (name, source) in surnames:
                continue
            films = await self._filmography(name)
            if films is None:
                surnames.append((name, source))
                continue
            # A film of this title the person made that the searches did not turn up.
            for tmdb_id, film in films.items():
                if tmdb_id in found or not compare(title, film.title).same_title:
                    continue
                movie = await self._details_for(tmdb_id)
                if movie is not None:
                    found[tmdb_id] = Candidate.from_movie(movie, origin="person", rank=600)
                    contenders.append(found[tmdb_id])
                    namesakes.append(found[tmdb_id])
            for candidate in contenders:
                made = films.get(candidate.tmdb_id)
                if made is not None:
                    credited.setdefault(candidate.tmdb_id, []).append(
                        (source, Credit(name, made.role))
                    )
        checked_all = True
        if surnames:
            checked_all = len(namesakes) <= MAX_RIVAL_CREDITS
            for candidate in contenders if checked_all else [leader]:
                await self._fill(candidate)
                for name, source in surnames:
                    credit = person_credited(name, candidate.credits or ())
                    if credit is not None:
                        credited.setdefault(candidate.tmdb_id, []).append((source, credit))
        return credited, checked_all

    async def _decide(
        self,
        parsed: ParsedTitle,
        found: dict[int, Candidate],
        fits: dict[int, Fit],
        proposal: Proposal,
        *,
        held: Holder | None,
    ) -> Proposal:
        near = [c for c in found.values() if fits[c.tmdb_id].near_exact]
        if not near:
            proposal.candidates = sorted(found.values(), key=lambda c: (c.rank, -c.vote_count))[
                :OFFERED
            ]
            proposal.reason = (
                "TMDB has no film of this name"
                + (" and the web search found none" if proposal.brave_query else "")
                + ". Search again with a corrected title, or set it aside."
            )
            if parsed.tv_hint:
                proposal.reason = (
                    f"It may be TV ({parsed.tv_hint}), but TMDB has no film or series of this "
                    "name. Search again, or set it aside."
                )
            return proposal

        best_tier = min(fits[c.tmdb_id].tier for c in near)
        first = self._rank(parsed, [c for c in near if fits[c.tmdb_id].tier == best_tier], fits)[0]
        title = fits[first.tmdb_id].matched_title
        # The title as TMDB writes it finds namesakes a typo'd reading cannot.
        scanned: list[int] = []
        complete = await self._scan_namesakes(found, title, parsed.year, scanned)
        fits = self._fits(found, parsed)

        def namesake(candidate: Candidate) -> bool:
            if candidate.tmdb_id == first.tmdb_id:
                return False
            f = fits[candidate.tmdb_id]
            if f.same_title and f.tier <= best_tier:
                return True
            return any(compare(title, other).same_title for other, _ in candidate.titles)

        # A film the search returned for this title without carrying it as its own may carry
        # it as an alternative title: TMDB lists The Devil and Daniel Webster (1941) as "All
        # That Money Can Buy", and an early version took a 2007 film of that working title.
        unexplained = [
            found[tmdb_id]
            for tmdb_id in scanned
            if tmdb_id != first.tmdb_id
            and found[tmdb_id].alt_titles is None
            and not namesake(found[tmdb_id])
        ]
        for candidate in unexplained[:ALT_TITLE_LOOKS]:
            await self._fill(candidate)
        fits = self._fits(found, parsed)
        namesakes = [c for c in found.values() if namesake(c)]
        credited, checked_all = await self._people_evidence(parsed, first, namesakes, found, title)
        fits = self._fits(found, parsed)
        ranked = self._rank(parsed, [first, *namesakes], fits, credited=credited)
        leader = ranked[0]
        rivals = ranked[1:]
        offered = ranked[:OFFERED]
        for extra in sorted(near, key=lambda c: -c.vote_count):
            if len(offered) >= OFFERED:
                break
            if extra not in offered:
                offered.append(extra)
        proposal.candidates = offered
        for candidate in offered:
            proposal.notes[candidate.tmdb_id] = self._notes(
                parsed, candidate, fits[candidate.tmdb_id], credited.get(candidate.tmdb_id, [])
            )

        lead_fit = fits[leader.tmdb_id]
        evidence: list[str] = [self._title_evidence(lead_fit, leader)]
        blockers: list[str] = []
        agrees = year_agrees(leader, parsed.year)
        people = credited.get(leader.tmdb_id, [])
        own_people = [credit for source, credit in people if source == TITLE_SOURCE]

        if lead_fit.tier != 1:
            blockers.append(
                f"Only part of the title ('{lead_fit.reading}') matches, so it could be "
                "another film."
            )
        if lead_fit.match.how == "tail":
            blockers.append(
                f"Only the end of TMDB's title ('{lead_fit.matched_title}') matches, which is "
                "also how a documentary about a film is named."
            )
        elif lead_fit.match.how == "subtitle" and not (agrees or people):
            blockers.append(
                f"Only part of TMDB's title ('{lead_fit.matched_title}') matches, and nothing "
                "else confirms it."
            )
        if parsed.year is not None:
            if agrees:
                evidence.append(f"The year agrees ({parsed.year}; TMDB has {leader.year}).")
            else:
                blockers.append(
                    f"The title says {parsed.year} and the closest film is from "
                    f"{leader.year or 'an unknown year'}."
                )
        if parsed.people and not own_people:
            blockers.append(
                f"The title names {' and '.join(parsed.people)}, and TMDB does not credit "
                + ("them" if len(parsed.people) > 1 else parsed.people[0])
                + " on this film."
            )
        described: set[str] = set()
        for source, credit in people:
            if credit.name not in described:
                evidence.append(describe_credit(credit, source) + ".")
                described.add(credit.name)

        if rivals:
            others = _others(rivals)
            year_singles = bool(agrees) and not any(year_agrees(r, parsed.year) for r in rivals)
            person_singles = (
                bool(people) and checked_all and not any(credited.get(r.tmdb_id) for r in rivals)
            )
            if year_singles:
                evidence.append(f"TMDB holds {others}; none is from {parsed.year}.")
            elif person_singles:
                named = " and ".join(sorted({credit.name for _, credit in people}))
                evidence.append(f"TMDB holds {others}; {named} made none of them.")
            else:
                blockers.append(
                    f"TMDB holds {others}, and nothing in the title or the grouping says which."
                )
        elif complete or agrees or people:
            evidence.append("TMDB holds no other film of this title.")
        else:
            blockers.append(
                "TMDB lists too many films with these words to be sure there is no other film "
                "of this title."
            )

        if not blockers and not agrees and not people:
            show = await self._tv_show(parsed, whole_title_only=True)
            if show is not None and (
                leader.vote_count < KNOWN_VOTES or show[2] >= leader.vote_count
            ):
                blockers.append(
                    f"TMDB also lists a TV series called '{show[0]}'"
                    + (f" ({show[1]})" if show[1] else "")
                    + ", which may be what this disc is."
                )

        merge = held(leader.tmdb_id) if held is not None else None
        if merge is not None:
            proposal.merge_into = merge
            blockers.append(
                f"The collection already has this film as '{merge[1]}'"
                + (f" ({merge[2]})" if merge[2] else "")
                + ". Choosing it merges the two."
            )

        proposal.chosen = leader
        proposal.evidence = evidence
        if blockers:
            proposal.outcome = "ask"
            proposal.reason = " ".join(blockers)
            hint_note = _hint_note(parsed)
            if hint_note:
                proposal.reason += f" {hint_note}"
            return proposal
        proposal.outcome = "identify"
        return proposal

    @staticmethod
    def _rank(
        parsed: ParsedTitle,
        candidates: Sequence[Candidate],
        fits: dict[int, Fit],
        *,
        credited: dict[int, list[tuple[str, Credit]]] | None = None,
    ) -> list[Candidate]:
        """Best first: the tier, then a year that agrees, then a name the title gives, then
        any other name, then how exact the title is, then Craig's words ("Original",
        "Remake"), then how well known."""
        credited = credited or {}
        order = _hint_order(parsed, candidates)

        def key(candidate: Candidate) -> tuple[int, int, int, int, int, int, float, int]:
            f = fits[candidate.tmdb_id]
            agrees = year_agrees(candidate, parsed.year)
            people = credited.get(candidate.tmdb_id, [])
            return (
                f.tier,
                0 if agrees else (1 if agrees is None else 2),
                0 if any(source == TITLE_SOURCE for source, _ in people) else 1,
                0 if people else 1,
                -_HOW_RANK[f.match.how],
                order.get(candidate.tmdb_id, 0),
                -f.match.ratio,
                -candidate.vote_count,
            )

        return sorted(candidates, key=key)

    @staticmethod
    def _title_evidence(f: Fit, candidate: Candidate) -> str:
        via = "" if f.matched_by == "title" else f" (its {f.matched_by} '{f.matched_title}')"
        source = (
            " A web search found its TMDB page, and TMDB confirmed it."
            if candidate.origin == "brave"
            else ""
        )
        if f.match.how == "typo":
            return f"The title matches{via}, allowing for a typo.{source}"
        if f.match.how in ("subtitle", "tail"):
            return f"The title matches part of TMDB's title{via}.{source}"
        return f"The title matches{via}.{source}"

    @staticmethod
    def _notes(
        parsed: ParsedTitle,
        candidate: Candidate,
        f: Fit,
        people: list[tuple[str, Credit]],
    ) -> list[str]:
        notes: list[str] = []
        if f.near_exact and f.matched_by != "title":
            notes.append(f"Also known as '{f.matched_title}'")
        agrees = year_agrees(candidate, parsed.year)
        if agrees:
            notes.append(f"The year agrees ({parsed.year})")
        elif agrees is False:
            notes.append(f"The title says {parsed.year}")
        for source, credit in people:
            notes.append(describe_credit(credit, source))
        if candidate.vote_count:
            notes.append(f"{candidate.vote_count:,} TMDB votes")
        return notes


def _year_of(release_date: str | None) -> int | None:
    if not release_date:
        return None
    try:
        return int(release_date.split("-", 1)[0])
    except ValueError:
        return None


def _others(rivals: Sequence[Candidate]) -> str:
    years = sorted({str(r.year) for r in rivals if r.year is not None})
    shown = ", ".join(years[:6]) + ("…" if len(years) > 6 else "")
    count = len(rivals)
    films = "another film" if count == 1 else f"{count} other films"
    return f"{films} of this title" + (f" ({shown})" if shown else "")


def _hint_order(parsed: ParsedTitle, candidates: Sequence[Candidate]) -> dict[int, int]:
    """Craig's words on the title, used only to order what he is offered, among films well
    enough known to be what he meant."""
    known = [c for c in candidates if c.year is not None and c.vote_count >= KNOWN_VOTES]
    if not known:
        return {}
    if "original" in parsed.hints:
        return {min(known, key=lambda c: c.year or 0).tmdb_id: -1}
    if "remake" in parsed.hints or "prequel" in parsed.hints or "live action" in parsed.hints:
        return {max(known, key=lambda c: c.year or 0).tmdb_id: -1}
    if "animation" in parsed.hints:
        return {c.tmdb_id: -1 for c in known if 16 in c.genre_ids}
    return {}


def _hint_note(parsed: ParsedTitle) -> str:
    words = {
        "original": "The title says 'Original', so the earliest is offered first.",
        "remake": "The title says 'Remake', so the latest is offered first.",
        "prequel": "The title says 'Prequel', so the latest is offered first.",
        "animation": "The title says 'Animation', so the animated one is offered first.",
        "live action": "The title says 'Live Action', so the latest is offered first.",
    }
    for hint in parsed.hints:
        if hint in words:
            return words[hint]
    return ""
