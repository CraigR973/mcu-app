"""Batch Y5's pieces that need no database (#277).

**What this proves:** a full TMDB record's keywords become ``tmdb_keyword_ids`` (null when the
record carries none, an empty list when TMDB has none), for a film and a series; the series
search reads a second page only when TMDB has one, and ranks the exact names first; an undo of
an identification snapshotted before Y5 leaves the keywords unknown rather than the undone
film's; a move with no media type is a film's; and the add body names exactly one film.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from src.models.movie import Movie
from src.schemas.collection import CollectionItemCreateRequest
from src.schemas.identify import MoveCopyRequest
from src.services.identification import _restore, snapshot
from src.services.identify.matcher import find_series
from src.services.movie_metadata import movie_metadata_values, tv_metadata_values
from src.tmdb.models import (
    Keyword,
    MovieKeywords,
    TvKeywords,
    TvSearchResult,
    TvSearchResults,
    TvShow,
)
from src.tmdb.models import Movie as TmdbMovie


def _film(keywords: MovieKeywords | None) -> TmdbMovie:
    return TmdbMovie(
        id=1,
        title="Out of the Past",
        original_title="Out of the Past",
        overview="",
        keywords=keywords,
    )


def test_a_films_keywords_are_stored_and_unknown_when_not_fetched() -> None:
    noir = MovieKeywords(
        keywords=[Keyword(id=9807, name="film noir"), Keyword(id=818), Keyword(id=9807)]
    )
    assert movie_metadata_values(_film(noir))["tmdb_keyword_ids"] == [9807, 818]
    assert movie_metadata_values(_film(MovieKeywords()))["tmdb_keyword_ids"] == []
    assert movie_metadata_values(_film(None))["tmdb_keyword_ids"] is None


def test_a_series_keywords_are_read_from_its_results() -> None:
    show = TvShow(id=2, name="Life", keywords=TvKeywords(results=[Keyword(id=221)]))
    assert tv_metadata_values(show)["tmdb_keyword_ids"] == [221]
    assert tv_metadata_values(TvShow(id=2, name="Life"))["tmdb_keyword_ids"] is None


def test_a_full_film_record_reads_keywords_as_tmdb_appends_them() -> None:
    record = TmdbMovie.model_validate(
        {
            "id": 3,
            "title": "Gilda",
            "original_title": "Gilda",
            "overview": "",
            "keywords": {"keywords": [{"id": 9807, "name": "film noir"}]},
        }
    )
    show = TvShow.model_validate(
        {"id": 4, "name": "Life", "keywords": {"results": [{"id": 221, "name": "nature"}]}}
    )
    assert movie_metadata_values(record)["tmdb_keyword_ids"] == [9807]
    assert tv_metadata_values(show)["tmdb_keyword_ids"] == [221]


class PagedSeries:
    def __init__(self, pages: dict[int, list[TvSearchResult]]) -> None:
        self.pages = pages
        self.asked: list[tuple[str, int]] = []

    async def search_tv(self, query: str, page: int = 1) -> TvSearchResults:
        self.asked.append((query, page))
        return TvSearchResults(page=page, results=self.pages[page], total_pages=len(self.pages))


async def test_the_series_search_reads_a_second_page_and_ranks_exact_names_first() -> None:
    first = [TvSearchResult(id=10 + n, name=f"Life Goes On {n}", vote_count=900) for n in range(19)]
    first.append(TvSearchResult(id=3797, name="Life", first_air_date="2007-09-26", vote_count=280))
    second = [
        TvSearchResult(id=150, name="This Life", vote_count=50),
        TvSearchResult(id=16946, name="Life", first_air_date="2009-10-12", vote_count=180),
        TvSearchResult(id=3797, name="Life", first_air_date="2007-09-26", vote_count=280),
    ]
    tmdb = PagedSeries({1: first, 2: second})

    _, ranked = await find_series(tmdb, "Life", limit=5)

    assert tmdb.asked == [("Life", 1), ("Life", 2)]
    assert [show.id for show, _ in ranked][:2] == [3797, 16946]
    assert len(ranked) == 5
    assert len({show.id for show, _ in ranked}) == 5


async def test_the_series_search_asks_for_the_title_as_a_series_is_sold_and_one_page_only() -> None:
    tmdb = PagedSeries({1: [TvSearchResult(id=86343, name="The Name of the Rose")]})

    _, ranked = await find_series(tmdb, "Name of the Rose, The (TV)", limit=5)

    assert tmdb.asked == [("The Name of the Rose", 1)]
    assert [show.id for show, _ in ranked] == [86343]


def test_an_undo_snapshotted_before_y5_leaves_the_keywords_unknown() -> None:
    film = Movie(id=uuid.uuid4(), title="Life", tmdb_id=1, tmdb_keyword_ids=[221])
    before_y5 = {
        name: value for name, value in snapshot(film).items() if name != "tmdb_keyword_ids"
    }
    _restore(film, before_y5)
    assert film.tmdb_keyword_ids is None

    film.tmdb_keyword_ids = [9807]
    _restore(film, snapshot(film))
    assert film.tmdb_keyword_ids == [9807]


def test_a_move_without_a_media_type_is_a_films() -> None:
    assert MoveCopyRequest(tmdbId=5).mediaType == "film"
    assert MoveCopyRequest(tmdbId=5, mediaType="tv").mediaType == "tv"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"tmdbId": 1, "tmdbTvId": 2},
        {"title": "A Day in the Life", "movieId": str(uuid.uuid4())},
        {"title": "  "},
    ],
)
def test_the_add_body_names_exactly_one_film(body: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CollectionItemCreateRequest.model_validate({**body, "formats": ["dvd"]})


def test_a_title_is_tidied_before_it_names_a_film() -> None:
    body = CollectionItemCreateRequest.model_validate(
        {"title": "  A Day in the  Life ", "formats": ["blu_ray"]}
    )
    assert body.title == "A Day in the Life"
