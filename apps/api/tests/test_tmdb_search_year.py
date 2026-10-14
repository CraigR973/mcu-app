"""The add form's TMDB search reads a year, and shows all of TMDB's first page — 14 Oct.

Mark could not find the 1974 Texas Chain Saw Massacre. TMDB spells it "Chain Saw"; his
"The Texas Chainsaw massacre" put it 14th, behind the sequels and remakes, and the form
showed ten. Adding "1974" or "(1974)" found nothing, because TMDB reads every word as title.
Checked against TMDB on 14 Oct: the title filtered to 1974 answers with that film alone.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from src.routers.collection import (
    TMDB_SEARCH_LIMIT,
    _search_tmdb_films,
    _split_trailing_year,
)
from src.tmdb.models import SearchResult, SearchResults


def _film(tmdb_id: int, title: str, year: int | None) -> SearchResult:
    return SearchResult(
        id=tmdb_id,
        title=title,
        original_title=title,
        release_date=f"{year}-06-01" if year else None,
    )


class _Tmdb:
    """Answers each (query, year) it is given, and records what it was asked."""

    def __init__(self, answers: dict[tuple[str, int | None], list[SearchResult]]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, int | None]] = []

    async def search_movie(self, query: str, year: int | None = None) -> SearchResults:
        self.calls.append((query, year))
        results = self.answers.get((query, year), [])
        return SearchResults(page=1, total_pages=1, total_results=len(results), results=results)


async def _search(tmdb: _Tmdb, query: str) -> list[tuple[int, str]]:
    found = await _search_tmdb_films(cast(Any, tmdb), query)
    return [(result.id, result.title) for result in found]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("The Texas Chainsaw Massacre 1974", ("The Texas Chainsaw Massacre", 1974)),
        ("The Texas Chainsaw Massacre (1974)", ("The Texas Chainsaw Massacre", 1974)),
        ("Halloween(1978)", ("Halloween", 1978)),
        ("Halloween - 1978", ("Halloween", 1978)),
        ("  Blade Runner 2049  ", ("Blade Runner", 2049)),
        # Titles that are, or end in, a number that is not a year.
        ("1917", None),
        ("Apollo 13", None),
        ("Room 237", None),
        ("2001: A Space Odyssey", None),
        ("Halloween", None),
        # A year glued to the word is part of the word.
        ("Halloween1978", None),
    ],
)
def test_a_year_ending_the_search_is_read_as_a_year(
    query: str, expected: tuple[str, int] | None
) -> None:
    assert _split_trailing_year(query) == expected


async def test_marks_search_finds_the_1974_film_when_he_adds_the_year() -> None:
    chain_saw = _film(30497, "The Texas Chain Saw Massacre", 1974)
    tmdb = _Tmdb({("The Texas Chainsaw massacre", 1974): [chain_saw]})

    assert await _search(tmdb, "The Texas Chainsaw massacre (1974)") == [
        (30497, "The Texas Chain Saw Massacre")
    ]
    assert sorted(tmdb.calls, key=str) == [
        ("The Texas Chainsaw massacre (1974)", None),
        ("The Texas Chainsaw massacre", 1974),
    ]


async def test_all_twenty_of_tmdbs_first_page_are_shown() -> None:
    """Mark's search without a year: the 1974 film is TMDB's 14th."""
    page = [_film(1000 + n, f"Texas Chainsaw {n}", 2000 + n) for n in range(19)]
    page.insert(13, _film(30497, "The Texas Chain Saw Massacre", 1974))
    tmdb = _Tmdb({("The Texas Chainsaw massacre", None): page})

    found = await _search(tmdb, "The Texas Chainsaw massacre")

    assert TMDB_SEARCH_LIMIT == 20
    assert len(found) == 20
    assert found[13] == (30497, "The Texas Chain Saw Massacre")
    assert tmdb.calls == [("The Texas Chainsaw massacre", None)]


async def test_films_released_that_year_come_first_then_the_search_as_typed() -> None:
    """TMDB's year filter matches a re-release too: the 1940 Fantasia answers 2000."""
    fantasia = _film(756, "Fantasia", 1940)
    fantasia_2000 = _film(12230, "Fantasia 2000", 2000)
    legacy = _film(55000, "The Fantasia Legacy", 2000)
    imagine = _film(77000, "Just Imagine", 1930)
    tmdb = _Tmdb(
        {
            ("Fantasia", 2000): [fantasia, fantasia_2000, legacy],
            ("Fantasia 2000", None): [fantasia_2000, imagine],
        }
    )

    assert await _search(tmdb, "Fantasia 2000") == [
        (12230, "Fantasia 2000"),
        (55000, "The Fantasia Legacy"),
        (756, "Fantasia"),
        (77000, "Just Imagine"),
    ]


async def test_a_title_ending_in_a_year_is_still_found_as_typed() -> None:
    blade_runner = _film(335984, "Blade Runner 2049", 2017)
    tmdb = _Tmdb({("Blade Runner 2049", None): [blade_runner]})

    assert await _search(tmdb, "Blade Runner 2049") == [(335984, "Blade Runner 2049")]
