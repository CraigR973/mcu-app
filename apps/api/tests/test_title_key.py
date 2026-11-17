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


# ---------------------------------------------------------------------------
# AG7 (CR49-03, CT52-05): the cinema site joins the table
# ---------------------------------------------------------------------------

#: The cinema matcher's pairs: (a, b, one title for a cinema listing). Fifteen crafted pairs, on
#: which the old cinema rule and the shared fold disagreed on twelve, and the table above's
#: spellings, which the cinema rule must answer as every other site does.
CINEMA_PAIRS: list[tuple[str, str, bool]] = [
    ("Cowboys v Aliens", "Cowboys & Aliens", True),
    ("Dune: Part Two", "Dune: Part 2", True),
    ("Dune: Part Two", "Dune 2", True),
    ("Rocky II", "Rocky 2", True),
    ("Kill Bill: Vol. 1", "Kill Bill: Volume 1", True),
    ("Ocean's Eleven", "Ocean's 11", True),
    ("Ocean’s Eleven", "Oceans 11", True),
    ("Spider-Man: No Way Home", "Spiderman: No Way Home", True),
    ("Star Wars Ep IV A New Hope", "Star Wars: Episode IV - A New Hope", True),
    ("Batman v Superman", "Batman vs Superman", True),
    ("Léon: The Professional", "Leon: The Professional", True),
    ("The Thing", "Thing", True),
    ("Speed", "Speed 2: Cruise Control", False),
    ("Rocky", "Rocky IV", False),
    ("The Collector", "The Collection", False),
]


@pytest.mark.parametrize(
    ("a", "b", "same"), CINEMA_PAIRS, ids=[f"{a} ~ {b}" for a, b, _ in CINEMA_PAIRS]
)
def test_the_cinema_rule_gives_the_table_s_answer_in_both_orders(
    a: str, b: str, same: bool
) -> None:
    from src.services.cinemas import identity

    assert len(CINEMA_PAIRS) == 15
    assert identity.same_title(a, b) is same
    assert identity.same_title(b, a) is same
    assert (identity.normal(a) == identity.normal(b)) is (same and "Thing" not in a)


@pytest.mark.parametrize(("a", "b", "words", "title", "identify"), PAIRS, ids=IDS)
def test_the_cinema_rule_agrees_with_the_catalogue_level_where_a_listing_can_say_it(
    a: str, b: str, words: bool, title: bool, identify: bool
) -> None:
    """The cinema rule is the catalogue level less what a listing never carries: library order
    ("Mummy, The") and a catalogue's brackets, year and edition words, which `read_title` and
    the film's own facts deal with first. On every other pair it answers exactly as the
    catalogue level does."""
    from src.services.cinemas import identity

    del words, identify
    carries_what_a_listing_never_does = (
        ", The" in a or ", The" in b or "(" in a or "(" in b or "Final Cut" in a or "Final Cut" in b
    )
    if carries_what_a_listing_never_does:
        return
    assert identity.same_title(a, b) is title or identity.normal(a) == identity.normal(b)


#: The three live listings that slipped the old prefixes and suffixes (16 Nov): a typographic
#: apostrophe, a society's "Curates:", and an unconfirmed certificate. (title, query it reads as,
#: whether it reads as a preview)
LIVE_TITLES = [
    ("Members’ Preview: Focker-In–Law", "Focker-In-Law", True),
    ("RCS Curates: No Country for Old Men + discussion", "No Country for Old Men", False),
    (
        "The Further Mis-adventures of Cliff Booth - IMAX 2D (18 TBC)",
        "The Further Mis-adventures of Cliff Booth",
        False,
    ),
]


@pytest.mark.parametrize(("title", "query", "preview"), LIVE_TITLES)
def test_the_three_live_titles_read_as_the_films_they_are(
    title: str, query: str, preview: bool
) -> None:
    from src.services.cinemas import identity

    read = identity.read_title(title, date(2026, 11, 17))
    assert read.query == query
    assert read.preview is preview
    assert read.event is None
    # And the cleaned title meets the film's own spelling, as a TMDB candidate would give it.
    assert identity.same_title(read.query, query.replace("-", " "))


def test_a_typographic_apostrophe_or_dash_no_longer_hides_a_decoration() -> None:
    from src.services.cinemas import identity

    shown = date(2026, 11, 17)
    for apostrophe in ("'", "’", "‘"):
        assert identity.read_title(f"Members{apostrophe} Preview: Fjord", shown).query == "Fjord"
    assert identity.read_title("Fjord – IMAX 2D (12A)", shown).query == "Fjord"
    assert identity.read_title("Fjord — 4K", shown).query == "Fjord"
    # A film's own apostrophe is kept, written plain, for the search.
    assert (
        identity.read_title("Don’t Cry, Pretty Girls!", shown).query == "Don't Cry, Pretty Girls!"
    )


def test_only_title_key_normalises_unicode() -> None:
    """AG7 (CR49-03): a second rule for "is this the same title?" is how the cinema code came to
    differ from the rest. No module but `title_key.py` may call `unicodedata.normalize`; a site
    that needs it asks `fold`. Nothing is allowed through today."""
    from pathlib import Path

    allowed: set[str] = {"services/title_key.py"}
    src = Path(__file__).resolve().parents[1] / "src"
    offenders = [
        str(path.relative_to(src))
        for path in sorted(src.rglob("*.py"))
        if "unicodedata.normalize" in path.read_text(encoding="utf-8")
        and str(path.relative_to(src)) not in allowed
    ]
    assert offenders == []
