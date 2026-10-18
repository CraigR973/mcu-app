"""R1's pair table: one title rule, and every site gives its answer — Batch X10 (CR43-03).

On 11 Oct the review ran the app's four title rules over eight pairs and they disagreed on
seven. Now there is one module with two levels, and this table is both its test and the guard
that keeps a site from growing its own rule again (`DECISIONS.md` #280): each site is run on
every pair and must give the answer of the level it uses.

Columns: the two spellings, then whether they are one title at ``WORDS`` (a page's words) and
at ``TITLE`` (a catalogue entry), then T9's identification verdict, which is ``TITLE`` except
where a match is only weak (a subtitle is not the film) or a typo is allowed for.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.matching.engine import _canonicalise
from src.models.movie import Movie
from src.scripts.import_collection import LiveFilmIndex
from src.services.identify.titles import compare, parse_title
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.matcher import build_index, match_entry
from src.services.lookalike import Unidentified, lookalike
from src.services.reviews.finding import avforums_hits, bluray_com_hits
from src.services.specs.candidates import same_film
from src.services.specs.search import SearchHit
from src.services.title_key import Strictness, same_title, title_key, title_key_and_year

#: (a, b, one title by its words, one catalogue title, identification's strong match)
PAIRS: list[tuple[str, str, bool, bool, bool]] = [
    # R1's eight, 11 Oct.
    ("Fast & Furious", "Fast and Furious", True, True, True),
    ("Léon: The Professional", "Leon: The Professional", True, True, True),
    ("Mummy, The", "The Mummy", False, True, True),
    ("Amélie", "Amelie", True, True, True),
    ("Dune: Part Two", "Dune 2", True, True, True),
    ("Cowboys & Aliens", "Cowboys and Aliens", True, True, True),
    ("Collector, The", "Collector", False, True, True),
    ("Spider-Man: No Way Home", "Spider Man No Way Home", True, True, True),
    # Namesakes and near-misses: never one title.
    ("Speed", "Speed 2: Cruise Control", False, False, False),
    # T9 reads one letter as a typo and leaves "Alien" from "Aliens" to the year (#275).
    ("Alien", "Aliens", False, False, True),
    ("The Collector", "The Collection", False, False, False),
    ("Rocky", "Rocky IV", False, False, False),
    # Articles: one catalogue title; the year tells "The Thing" (1982) from "Thing".
    ("The Thing", "Thing", False, True, True),
    ("Mummy, The (Brendan Fraser)", "The Mummy", False, True, True),
    # Spellings each feature once learned on its own.
    ("National Lampoon's Animal House", "National Lampoons Animal House", True, True, True),
    ("Kill Bill: Vol. 1", "Kill Bill: Volume 1", True, True, True),
    ("Ocean's Eleven", "Ocean's 11", True, True, True),
    ("Star Wars Ep IV A New Hope", "Star Wars: Episode IV - A New Hope", True, True, True),
    ("Batman v Superman", "Batman vs Superman", True, True, True),
    # What a catalogue entry carries beside its title.
    ("Heat (1995)", "Heat", False, True, True),
    ("Blade Runner: The Final Cut", "Blade Runner", False, True, False),
]

IDS = [f"{a} ~ {b}" for a, b, *_ in PAIRS]


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_the_module_gives_the_table_s_answer(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    assert same_title(a, b, Strictness.WORDS) is words
    assert same_title(b, a, Strictness.WORDS) is words
    assert same_title(a, b, Strictness.TITLE) is title
    assert same_title(b, a, Strictness.TITLE) is title


def test_a_title_key_carries_its_year_apart() -> None:
    assert title_key_and_year("Heat (1995)") == ("heat", 1995)
    assert title_key("", Strictness.TITLE) == ""
    assert not same_title("", "", Strictness.TITLE)


# ── Every site, on every pair ────────────────────────────────────────────────


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_identification_reads_the_same_fold(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    del words, title
    ours = parse_title(a).main
    assert compare(ours, parse_title(b).main).same_title is identify


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_search_and_the_add_form_s_lookalike_is_the_catalogue_level(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    del words, identify
    key, year = title_key_and_year(a)
    films = [Unidentified(uuid.uuid4(), a, key, year)]
    assert (lookalike(films, b, None) is not None) is title


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_the_spec_page_check_is_the_catalogue_level(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    del words, identify
    assert same_film(b, a) is title


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_the_diary_index_is_the_catalogue_level(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    del words, identify
    film = Movie(id=uuid.uuid4(), title=a, original_title=a, media_type="film")
    entry = DiaryEntry(
        viewing_id="1",
        watched_at=date(2026, 9, 1),
        title=b,
        year=None,
        rating=None,
        is_rewatch=False,
        tmdb_id=None,
    )
    assert (match_entry(entry, build_index([film])).movie is film) is title


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_the_sheet_refresh_index_is_the_catalogue_level(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    del words, identify
    film_id = uuid.uuid4()
    found, _kind = LiveFilmIndex([(film_id, a)]).resolve(b)
    assert (found == film_id) is title


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_review_finding_is_the_words_level(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    del title, identify
    bluray = SearchHit(
        "https://www.blu-ray.com/movies/Some-Film-Blu-ray/4011/",
        f"{b} Blu-ray (United Kingdom)",
        "",
    )
    avforums = SearchHit(
        "https://www.avforums.com/reviews/some-film-4k-blu-ray-review.1/",
        f"{b} 4K Blu-ray Review | AVForums",
        "",
    )
    assert bool(bluray_com_hits([bluray], a)) is words
    assert bool(avforums_hits([avforums], a)) is words


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_the_retired_engine_compares_by_words(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    del title, identify
    assert (_canonicalise(a) == _canonicalise(b)) is words


def test_a_review_whose_film_ends_in_a_numeral_or_a_kind_word_is_found() -> None:
    """The film's words fold apart from the format words after them (#280)."""
    rocky = SearchHit(
        "https://www.avforums.com/reviews/rocky-iv-4k-blu-ray-review.1/",
        "Rocky IV 4K Blu-ray Review | AVForums",
        "",
    )
    bee = SearchHit(
        "https://www.avforums.com/reviews/bee-movie-blu-ray-review.2/",
        "Bee Movie Blu-ray Review | AVForums",
        "",
    )
    assert [hit.format_code for hit in avforums_hits([rocky], "Rocky IV")] == ["4k_uhd"]
    assert avforums_hits([rocky], "Rocky") == []
    assert [hit.format_code for hit in avforums_hits([bee], "Bee Movie")] == ["blu_ray"]
