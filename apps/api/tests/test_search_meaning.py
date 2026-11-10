"""AE7 (#355): search that finds what you mean, on real Postgres with migration 077.

Each search below failed on 8 Nov. A title answers first (the same, then starting so, then close),
then a person (a director or a billed part, or a character), then the full-text match on cast,
crew, genre and plot, which alone answered before.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.movie import Movie, MovieCredit
from tests.test_movies_api import _add_owned_movie
from tests.test_movies_api import api_session as api_session
from tests.test_movies_api import client as client
from tests.test_movies_api import viewer as viewer


async def credit(
    db: AsyncSession,
    movie: Movie,
    name: str,
    role: str,
    *,
    character: str | None = None,
    order: int | None = None,
) -> None:
    db.add(
        MovieCredit(
            id=uuid.uuid4(),
            movie_id=movie.id,
            person_name=name,
            role=role,
            character_name=character,
            display_order=order,
        )
    )
    await db.flush()


@pytest_asyncio.fixture
async def shelf(api_session: AsyncSession) -> dict[str, Movie]:
    """The films the 8 Nov examples should find, and what used to come first instead."""
    db = api_session
    films: dict[str, Movie] = {}
    for title, year, overview in [
        ("The Godfather", 1972, None),
        ("The Godfather Part II", 1974, None),
        ("Mob Story", 1990, "An ageing godfather plans his last job."),
        ("Jurassic Park", 1993, None),
        ("Spider-Man", 2002, None),
        ("Spider-Man 2", 2004, None),
        ("Léon: The Professional", 1994, None),
        ("The Lord of the Rings: The Fellowship of the Ring", 2001, None),
        ("Psycho", 1960, None),
        ("Vertigo", 1958, None),
        ("GoldenEye", 1995, "James Bond takes on a rogue agent."),
        ("Moonraker", 1979, "Bond follows a space shuttle."),
        ("Joan of Arc", 1948, None),
        ("The Thing", 1982, None),
        ("The Thing", 2011, None),
    ]:
        movie, _ = await _add_owned_movie(
            db, title=title, tmdb_id=None, year=year, overview=overview
        )
        films[f"{title} ({year})"] = movie
    for film in ("Psycho (1960)", "Vertigo (1958)"):
        await credit(db, films[film], "Alfred Hitchcock", "director")
    await credit(
        db, films["GoldenEye (1995)"], "Pierce Brosnan", "cast", character="James Bond", order=0
    )
    await credit(
        db, films["GoldenEye (1995)"], "Samantha Bond", "cast", character="Moneypenny", order=11
    )
    await credit(
        db, films["Moonraker (1979)"], "Roger Moore", "cast", character="James Bond", order=0
    )
    await credit(db, films["Joan of Arc (1948)"], "Ward Bond", "cast", character="La Hire", order=3)
    return films


async def titles(client: AsyncClient, query: str, limit: int = 20) -> list[str]:
    response = await client.get("/api/v1/search", params={"q": query, "limit": limit})
    assert response.status_code == 200, response.text
    return [f"{item['title']} ({item['year']})" for item in response.json()["items"]]


@pytest.mark.parametrize(
    ("query", "first"),
    [
        ("godf", ["The Godfather (1972)", "The Godfather Part II (1974)"]),
        ("godfathr", ["The Godfather (1972)", "The Godfather Part II (1974)"]),
        ("jurasic", ["Jurassic Park (1993)"]),
        ("hitchcok", ["Psycho (1960)", "Vertigo (1958)"]),
        ("spiderman", ["Spider-Man (2002)", "Spider-Man 2 (2004)"]),
        ("leon", ["Léon: The Professional (1994)"]),
        ("lotr", ["The Lord of the Rings: The Fellowship of the Ring (2001)"]),
    ],
)
async def test_each_8_nov_search_finds_the_film_first(
    client: AsyncClient, shelf: dict[str, Movie], query: str, first: list[str]
) -> None:
    assert (await titles(client, query))[: len(first)] == first


async def test_bond_lists_the_bond_films_before_joan_of_arc(
    client: AsyncClient, shelf: dict[str, Movie]
) -> None:
    """James Bond is the lead's character in both; Ward Bond plays a supporting part."""
    found = await titles(client, "bond")
    assert found.index("Joan of Arc (1948)") > max(
        found.index("GoldenEye (1995)"), found.index("Moonraker (1979)")
    )


async def test_a_title_ranks_before_a_person_and_both_before_the_plot(
    client: AsyncClient, shelf: dict[str, Movie]
) -> None:
    found = await titles(client, "godfather")
    assert found == ["The Godfather (1972)", "The Godfather Part II (1974)", "Mob Story (1990)"]


@pytest.mark.parametrize("query", ["Léon", "LEON", "léon the professional", "leon:"])
async def test_accents_and_case_do_not_matter(
    client: AsyncClient, shelf: dict[str, Movie], query: str
) -> None:
    assert (await titles(client, query))[0] == "Léon: The Professional (1994)"


@pytest.mark.parametrize("query", ["spider man", "spider-man", "Spider-Man", "SPIDERMAN"])
async def test_hyphens_and_spaces_do_not_matter(
    client: AsyncClient, shelf: dict[str, Movie], query: str
) -> None:
    assert (await titles(client, query))[0] == "Spider-Man (2002)"


async def test_ties_read_the_same_every_time(client: AsyncClient, shelf: dict[str, Movie]) -> None:
    """Two films of one title rank equal; the year breaks the tie, then the id."""
    for _ in range(3):
        assert (await titles(client, "the thing"))[:2] == ["The Thing (1982)", "The Thing (2011)"]


async def test_an_empty_or_one_letter_query_is_refused_as_before(client: AsyncClient) -> None:
    for query in ("", " ", "a"):
        response = await client.get("/api/v1/search", params={"q": query})
        assert response.status_code == 422, query


async def test_punctuation_alone_finds_nothing_rather_than_everything(
    client: AsyncClient, shelf: dict[str, Movie]
) -> None:
    response = await client.get("/api/v1/search", params={"q": "--"})
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "query": "--", "total": 0}


async def test_the_limit_pages_and_the_total_counts_every_match(
    client: AsyncClient, shelf: dict[str, Movie]
) -> None:
    response = await client.get("/api/v1/search", params={"q": "godfather", "limit": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["The Godfather"]
    assert body["total"] == 3
