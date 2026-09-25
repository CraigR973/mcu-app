"""Deciding which TMDB film a title names — Batch T9. A scripted TMDB and Brave; no database.

**What this proves:** the rule in ``docs/phase-batches.md`` — identify only when one TMDB
film is a strong match and a year or a person agrees whenever TMDB holds another film of the
same title; never merge on its own — and the mistakes the 25 Sep calibration runs made,
each now held: Furious 7 taken for "Seven" by its Spanish title, a documentary taken for
"Animal House", a making-of featurette hiding the year that decides "Death on the Nile", a
franchise after a dash read as a person, and a surname unable to decide past a handful of
namesakes. One Brave search at most per title, counted, and none past the budget.

**What it does not:** real TMDB or Brave responses. The 25 Sep dry run against production is
the check of those, and its report is what Craig approves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import pytest

from src.services.identify.matcher import Credit, Holder, Identifier, Proposal, person_credited
from src.services.identify.titles import fold, parse_title
from src.services.specs.search import SearchHit
from src.tmdb.models import (
    AlternativeTitle,
    AlternativeTitles,
    CastMember,
    Credits,
    CrewMember,
    PersonMovieCredit,
    PersonMovieCredits,
    PersonSearchResult,
    PersonSearchResults,
    SearchResult,
    SearchResults,
    TvSearchResult,
    TvSearchResults,
)
from src.tmdb.models import Movie as TmdbMovie

pytestmark = pytest.mark.asyncio


@dataclass
class Film:
    id: int
    title: str
    year: int | None
    votes: int = 10
    alt: tuple[str, ...] = ()
    cast: tuple[str, ...] = ()
    directors: tuple[str, ...] = ()
    original: str | None = None


@dataclass
class Show:
    id: int
    name: str
    year: int
    votes: int = 100


@dataclass
class FakeTmdb:
    """TMDB's search as it behaves: every word of the query in a title or an alternative
    title, 20 results a page, the best known first."""

    films: list[Film]
    shows: list[Show] = field(default_factory=list)
    calls: int = 0

    def _matches(self, film: Film, query: str) -> bool:
        words = fold(query).split()
        names = [film.title, film.original or film.title, *film.alt]
        return any(all(word in fold(name).split() for word in words) for name in names)

    async def search_movie(
        self, query: str, year: int | None = None, page: int = 1
    ) -> SearchResults:
        self.calls += 1
        found = [
            f
            for f in sorted(self.films, key=lambda f: -f.votes)
            if self._matches(f, query) and (year is None or f.year == year)
        ]
        chunk = found[(page - 1) * 20 : page * 20]
        return SearchResults(
            page=page,
            total_pages=max(1, (len(found) + 19) // 20),
            total_results=len(found),
            results=[
                SearchResult(
                    id=f.id,
                    title=f.title,
                    original_title=f.original or f.title,
                    release_date=f"{f.year}-01-01" if f.year else None,
                    vote_count=f.votes,
                )
                for f in chunk
            ],
        )

    async def get_movie(
        self, movie_id: int, append_to_response: list[str] | None = None
    ) -> TmdbMovie:
        self.calls += 1
        film = next((f for f in self.films if f.id == movie_id), None)
        if film is None:
            request = httpx.Request("GET", f"https://api.themoviedb.org/3/movie/{movie_id}")
            raise httpx.HTTPStatusError(
                "not found", request=request, response=httpx.Response(404, request=request)
            )
        return _movie(film)

    async def search_tv(self, query: str, page: int = 1) -> TvSearchResults:
        self.calls += 1
        found = [s for s in self.shows if fold(query) == fold(s.name)]
        return TvSearchResults(
            results=[
                TvSearchResult(
                    id=s.id, name=s.name, first_air_date=f"{s.year}-01-01", vote_count=s.votes
                )
                for s in found
            ]
        )

    async def search_person(self, query: str, page: int = 1) -> PersonSearchResults:
        self.calls += 1
        names = {name for f in self.films for name in (*f.cast, *f.directors)}
        return PersonSearchResults(
            results=[
                PersonSearchResult(id=abs(hash(name)) % 10_000_000, name=name)
                for name in sorted(names)
                if fold(name) == fold(query)
            ]
        )

    async def get_person_movie_credits(self, person_id: int) -> PersonMovieCredits:
        self.calls += 1
        name = next(
            n
            for f in self.films
            for n in (*f.cast, *f.directors)
            if abs(hash(n)) % 10_000_000 == person_id
        )
        return PersonMovieCredits(
            id=person_id,
            cast=[
                PersonMovieCredit(id=f.id, title=f.title, release_date=f"{f.year}-01-01", order=0)
                for f in self.films
                if name in f.cast
            ],
            crew=[
                PersonMovieCredit(
                    id=f.id, title=f.title, release_date=f"{f.year}-01-01", job="Director"
                )
                for f in self.films
                if name in f.directors
            ],
        )


def _movie(film: Film) -> TmdbMovie:
    return TmdbMovie(
        id=film.id,
        title=film.title,
        original_title=film.original or film.title,
        overview="",
        release_date=f"{film.year}-01-01" if film.year else None,
        vote_count=film.votes,
        alternative_titles=AlternativeTitles(
            titles=[AlternativeTitle(title=t, iso_3166_1="GB") for t in film.alt]
        ),
        credits=Credits(
            cast=[
                CastMember(id=i, name=n, character="", order=i, credit_id=f"c{i}")
                for i, n in enumerate(film.cast)
            ],
            crew=[
                CrewMember(
                    id=90 + i, name=n, job="Director", department="Directing", credit_id=f"d{i}"
                )
                for i, n in enumerate(film.directors)
            ],
        ),
    )


class FakeBrave:
    """Brave, answering by the words after the site filter. Counts every call."""

    def __init__(self, pages: dict[str, list[str]] | None = None) -> None:
        self.pages = pages or {}
        self.queries: list[str] = []
        self.search_calls = 0

    @property
    def configured(self) -> bool:
        return True

    async def search(self, query: str, *, count: int = 20, country: str = "GB") -> list[SearchHit]:
        del count, country
        self.search_calls += 1
        self.queries.append(query)
        for words, urls in self.pages.items():
            if words in query:
                return [SearchHit(url=url, title="", description="") for url in urls]
        return []


async def _identify(
    tmdb: FakeTmdb,
    title: str,
    grouping: str | None = None,
    *,
    brave: FakeBrave | None = None,
    budget: int = 10,
    held: Holder | None = None,
) -> tuple[Proposal, Identifier]:
    identifier = Identifier(tmdb, brave, brave_budget=budget)
    proposal = await identifier.identify(parse_title(title, grouping), held=held)
    return proposal, identifier


def _pick(proposal: Proposal) -> tuple[str, int | None] | None:
    return (proposal.chosen.title, proposal.chosen.year) if proposal.chosen else None


# ---------------------------------------------------------------------------
# One strong match, and when a year or a person must agree
# ---------------------------------------------------------------------------


async def test_a_typo_is_found_by_one_web_search_and_confirmed_by_tmdb() -> None:
    tmdb = FakeTmdb(
        [
            Film(11167, "Peeping Tom", 1960, votes=900, directors=("Michael Powell",)),
            Film(22, "Peeping Toms", 1997, votes=3),
        ]
    )
    brave = FakeBrave({"Peepiing Tom": ["https://www.themoviedb.org/movie/11167-peeping-tom"]})

    proposal, identifier = await _identify(
        tmdb, "Peepiing Tom", "Powell & Pressburger", brave=brave
    )

    assert proposal.outcome == "identify", proposal.reason
    assert _pick(proposal) == ("Peeping Tom", 1960)
    assert brave.queries == ["site:themoviedb.org Peepiing Tom"]
    assert identifier.counters.brave_searches == 1
    assert any("web search found its TMDB page" in line for line in proposal.evidence)
    assert any("Michael Powell" in line for line in proposal.evidence)


async def test_the_same_title_with_nothing_to_choose_between_them_waits_for_craig() -> None:
    tmdb = FakeTmdb([Film(1, "Argo", 2012, votes=9201), Film(2, "Argo", 2004, votes=24)])

    proposal, _ = await _identify(tmdb, "Argo")

    assert proposal.outcome == "ask"
    assert "another film of this title (2004)" in proposal.reason
    assert [c.year for c in proposal.candidates] == [2012, 2004]


async def test_a_year_that_agrees_with_one_of_them_decides_it() -> None:
    tmdb = FakeTmdb([Film(1, "Cape Fear", 1991, votes=3000), Film(2, "Cape Fear", 1962, votes=600)])

    proposal, _ = await _identify(tmdb, "Cape Fear 1962")

    assert proposal.outcome == "identify", proposal.reason
    assert _pick(proposal) == ("Cape Fear", 1962)


async def test_a_year_that_agrees_with_none_of_them_waits() -> None:
    tmdb = FakeTmdb([Film(1, "The Spy in Black", 1939, votes=60)])

    proposal, _ = await _identify(tmdb, "Spy in Black, The 1937")

    assert proposal.outcome == "ask"
    assert "says 1937" in proposal.reason


async def test_a_grouping_that_names_the_director_decides_it() -> None:
    tmdb = FakeTmdb(
        [
            Film(1, "The Beguiled", 2017, votes=2273, cast=("Nicole Kidman",)),
            Film(2, "The Beguiled", 1971, votes=520, cast=("Clint Eastwood",)),
            Film(3, "The Beguiled: The Storyteller", 1971, votes=4, cast=("Clint Eastwood",)),
        ]
    )

    proposal, _ = await _identify(tmdb, "Beguiled the", "Clint Eastwood")

    assert proposal.outcome == "identify", proposal.reason
    assert _pick(proposal) == ("The Beguiled", 1971)


async def test_a_person_the_title_names_must_be_in_the_film() -> None:
    tmdb = FakeTmdb([Film(1, "The Enforcer", 1976, votes=900, cast=("Clint Eastwood",))])

    proposal, _ = await _identify(tmdb, "Enforcer, The (Humphrey Bogart}")

    assert proposal.outcome == "ask"
    assert "Humphrey Bogart" in proposal.reason


async def test_a_full_name_is_checked_against_the_persons_own_films_however_many_namesakes() -> (
    None
):
    namesakes = [Film(100 + i, "The Letter", 1900 + i, votes=1) for i in range(60)]
    tmdb = FakeTmdb([*namesakes, Film(7, "The Letter", 1940, votes=250, cast=("Bette Davis",))])

    proposal, _ = await _identify(tmdb, "Letter, The (The Bette Davis collection)")

    assert proposal.outcome == "identify", proposal.reason
    assert _pick(proposal) == ("The Letter", 1940)


async def test_a_surname_cannot_decide_past_the_namesakes_it_can_check() -> None:
    namesakes = [Film(100 + i, "Blackmail", 1930 + i, votes=1) for i in range(45)]
    tmdb = FakeTmdb(
        [*namesakes, Film(7, "Blackmail", 1929, votes=289, directors=("Alfred Hitchcock",))]
    )

    proposal, _ = await _identify(tmdb, "Blackmail", "Hitchcock Early Collection")

    assert proposal.outcome == "ask"


async def test_a_surname_decides_among_namesakes_it_can_check() -> None:
    tmdb = FakeTmdb(
        [
            Film(1, "Blackmail", 1929, votes=289, directors=("Alfred Hitchcock",)),
            Film(2, "Blackmail", 2018, votes=111),
            Film(3, "Blackmail", 1947, votes=13),
        ]
    )

    proposal, _ = await _identify(tmdb, "Blackmail", "Hitchcock Early Collection")

    assert proposal.outcome == "identify", proposal.reason
    assert _pick(proposal) == ("Blackmail", 1929)


async def test_the_only_film_of_its_title_is_identified_when_every_page_was_read() -> None:
    tmdb = FakeTmdb([Film(1, "Where Eagles Dare", 1968, votes=1031)])

    proposal, _ = await _identify(tmdb, "Where Eagles Dare (With Kelly's Heroes)")

    assert proposal.outcome == "identify", proposal.reason
    assert "no other film of this title" in " ".join(proposal.evidence)


async def test_too_many_results_to_read_means_no_certainty_there_is_no_namesake() -> None:
    crowd = [Film(100 + i, f"Speed Racer {i}", 2000, votes=1) for i in range(130)]
    tmdb = FakeTmdb([*crowd, Film(1, "Speed", 1994, votes=7070)])

    proposal, _ = await _identify(tmdb, "Speed")

    assert proposal.outcome == "ask"
    assert "too many films" in proposal.reason


# ---------------------------------------------------------------------------
# What a title that is only part of TMDB's is worth
# ---------------------------------------------------------------------------


async def test_a_making_of_featurette_is_not_a_rival_and_cannot_hide_the_year() -> None:
    tmdb = FakeTmdb(
        [
            Film(1, "Death on the Nile", 2022, votes=4368),
            Film(2, "Death on the Nile", 1978, votes=954),
            Film(3, "Death on the Nile: Making of Featurette", 1978, votes=1),
        ]
    )

    proposal, _ = await _identify(tmdb, "Death on the Nile [1978]")

    assert proposal.outcome == "identify", proposal.reason
    assert _pick(proposal) == ("Death on the Nile", 1978)


async def test_the_end_of_a_title_is_never_taken_on_its_own() -> None:
    tmdb = FakeTmdb([Film(1, "INXS: Live Baby Live", 1991, votes=40)])

    proposal, _ = await _identify(tmdb, "Live Baby Live")

    assert proposal.outcome == "ask"
    assert "Only the end of TMDB's title" in proposal.reason


async def test_a_documentary_about_the_film_loses_to_the_films_own_alternative_title() -> None:
    tmdb = FakeTmdb(
        [
            Film(1, "Unseen + Untold: National Lampoon's Animal House", 2003, votes=3),
            Film(2, "Animal House", 1978, votes=1732, alt=("National Lampoon's Animal House",)),
        ]
    )

    proposal, _ = await _identify(tmdb, "National Lampoons Animal House")

    assert proposal.outcome == "identify", proposal.reason
    assert _pick(proposal) == ("Animal House", 1978)


async def test_a_number_in_a_foreign_alternative_title_is_not_seven() -> None:
    tmdb = FakeTmdb([Film(1, "Furious 7", 2015, votes=11499, alt=("A todo gas: 7",))])

    proposal, _ = await _identify(tmdb, "Seven", budget=0)

    assert proposal.outcome == "ask"
    assert proposal.chosen is None


async def test_a_franchise_after_a_dash_is_not_a_person_who_must_agree() -> None:
    tmdb = FakeTmdb(
        [Film(1, "Indiana Jones and the Kingdom of the Crystal Skull", 2008, votes=9255)]
    )

    proposal, _ = await _identify(tmdb, "Kingdom of the Crystal Skull, The - Indiana Jones")

    assert proposal.outcome == "identify", proposal.reason


# ---------------------------------------------------------------------------
# Merges, TV and not a film
# ---------------------------------------------------------------------------


async def test_a_film_the_collection_already_has_waits_with_both_shown() -> None:
    tmdb = FakeTmdb([Film(1, "Misery", 1990, votes=5000)])

    def held(tmdb_id: int) -> tuple[str, str, int | None] | None:
        return ("existing-id", "Misery", 1990) if tmdb_id == 1 else None

    proposal, _ = await _identify(tmdb, "Misery", held=held)

    assert proposal.outcome == "ask"
    assert proposal.merge_into == ("existing-id", "Misery", 1990)
    assert "merges the two" in proposal.reason


async def test_tv_words_set_a_title_aside_without_asking_tmdb() -> None:
    tmdb = FakeTmdb([])

    proposal, _ = await _identify(tmdb, "Steptoe & Son - Complete Series")

    assert proposal.outcome == "set_aside"
    assert proposal.set_aside_as == "tv"
    assert tmdb.calls == 0


async def test_a_title_only_tmdbs_tv_index_knows_is_set_aside_as_tv() -> None:
    tmdb = FakeTmdb([], shows=[Show(1, "Dynasties", 2018)])

    proposal, _ = await _identify(tmdb, "Dynasties", budget=0)

    assert proposal.outcome == "set_aside"
    assert "TV series" in proposal.reason


async def test_a_film_that_shares_its_name_with_a_better_known_series_waits() -> None:
    tmdb = FakeTmdb([Film(1, "Bonekickers", 2011, votes=2)], shows=[Show(1, "Bonekickers", 2008)])

    proposal, _ = await _identify(tmdb, "Bonekickers")

    assert proposal.outcome == "ask"
    assert "TV series" in proposal.reason


async def test_a_test_row_is_not_a_film() -> None:
    proposal, _ = await _identify(FakeTmdb([]), "Test 15.04.26")

    assert proposal.outcome == "set_aside"
    assert proposal.set_aside_as == "not_film"


# ---------------------------------------------------------------------------
# Brave is the last resort, and it is counted
# ---------------------------------------------------------------------------


async def test_no_web_search_past_the_budget() -> None:
    brave = FakeBrave({"Campaigh": ["https://www.themoviedb.org/movie/1"]})
    tmdb = FakeTmdb([Film(1, "The Campaign", 2012, votes=2000)])

    proposal, identifier = await _identify(tmdb, "Campaigh, The", brave=brave, budget=0)

    assert brave.search_calls == 0
    assert identifier.counters.brave_searches == 0
    assert proposal.brave_query is None
    assert proposal.outcome == "ask"


async def test_no_web_search_when_tmdb_finds_the_film() -> None:
    brave = FakeBrave()
    tmdb = FakeTmdb([Film(1, "Where Eagles Dare", 1968, votes=1031)])

    await _identify(tmdb, "Where Eagles Dare", brave=brave)

    assert brave.search_calls == 0


async def test_a_surname_matches_only_the_people_who_made_the_film() -> None:
    credits = (
        Credit("Glen Powell", "cast", 40),
        Credit("Michael Powell", "director"),
        Credit("Sam Powell", "catering"),
    )
    found = person_credited("Powell", credits)
    assert found is not None and found.name == "Michael Powell"
    assert person_credited("Powell", (Credit("Sam Powell", "catering"),)) is None
    assert person_credited("Alec Guiness", (Credit("Alec Guinness", "cast", 0),)) is not None
