from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.matching import (
    HIGH_CONFIDENCE,
    MatchingEngine,
    extract_year,
    normalise_query,
    rotate_trailing_article,
    score,
    strip_annotations,
    strip_edition_suffix,
    title_similarity,
)
from src.tmdb.client import TMDBClient
from src.tmdb.models import SearchResult, SearchResults

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _result(
    id_: int,
    title: str,
    year: int | None,
    *,
    original_title: str | None = None,
    pop: float = 10.0,
) -> SearchResult:
    return SearchResult(
        id=id_,
        title=title,
        original_title=original_title or title,
        release_date=f"{year}-01-01" if year else None,
        popularity=pop,
    )


def _results(*results: SearchResult) -> SearchResults:
    return SearchResults(
        page=1,
        results=list(results),
        total_pages=1,
        total_results=len(results),
    )


# ---------------------------------------------------------------------------
# Year extraction
# ---------------------------------------------------------------------------


def test_extract_year_trailing_parens() -> None:
    title, year = extract_year("20,000 Leagues Under the Sea (1954)")
    assert title == "20,000 Leagues Under the Sea"
    assert year == 1954


def test_extract_year_no_year() -> None:
    title, year = extract_year("The Matrix")
    assert title == "The Matrix"
    assert year is None


def test_extract_year_year_in_middle_ignored() -> None:
    title, year = extract_year("2001: A Space Odyssey")
    assert title == "2001: A Space Odyssey"
    assert year is None


def test_extract_year_strips_whitespace() -> None:
    title, year = extract_year("  Dune (1984)  ")
    assert title == "Dune"
    assert year == 1984


def test_extract_year_handles_extra_spaces_before_parens() -> None:
    title, year = extract_year("Dune  (2021)")
    assert title == "Dune"
    assert year == 2021


# ---------------------------------------------------------------------------
# Annotation stripping
# ---------------------------------------------------------------------------


def test_strip_annotations_square_brackets() -> None:
    raw = "Champagne Charlie [Ealing Classics Collection]"
    assert strip_annotations(raw) == "Champagne Charlie"


def test_strip_annotations_parentheses() -> None:
    assert strip_annotations("Alfie (Boxset with The Italian Job)") == "Alfie"


def test_strip_annotations_foreign_title() -> None:
    assert strip_annotations("Witness (Unico Testigo)") == "Witness"


def test_strip_annotations_keeps_clean_title() -> None:
    assert strip_annotations("Avengers: Infinity War") == "Avengers: Infinity War"


def test_strip_annotations_collapses_internal_whitespace() -> None:
    assert strip_annotations("Foo [tag] Bar") == "Foo Bar"


# ---------------------------------------------------------------------------
# Trailing-article rotation
# ---------------------------------------------------------------------------


def test_rotate_trailing_article_with_comma() -> None:
    assert rotate_trailing_article("Eiger Sanction, The") == "The Eiger Sanction"


def test_rotate_trailing_article_without_comma() -> None:
    assert rotate_trailing_article("Hitman's Bodyguard The") == "The Hitman's Bodyguard"


def test_rotate_trailing_article_lowercase() -> None:
    assert rotate_trailing_article("Meg the") == "The Meg"


def test_rotate_trailing_article_handles_a_and_an() -> None:
    assert rotate_trailing_article("Star is Born, A") == "A Star is Born"
    assert rotate_trailing_article("Officer and a Gentleman, An") == "An Officer and a Gentleman"


def test_rotate_trailing_article_leaves_normal_titles_alone() -> None:
    # Trailing word is not an article
    assert rotate_trailing_article("Star Wars: The Last Jedi") == "Star Wars: The Last Jedi"
    assert rotate_trailing_article("The Matrix") == "The Matrix"
    assert rotate_trailing_article("I Am Legend") == "I Am Legend"


# ---------------------------------------------------------------------------
# Edition suffix stripping
# ---------------------------------------------------------------------------


def test_strip_edition_suffix_final_cut() -> None:
    assert strip_edition_suffix("Blade Runner The Final Cut") == "Blade Runner"


def test_strip_edition_suffix_directors_cut() -> None:
    assert strip_edition_suffix("Apocalypse Now Director's Cut") == "Apocalypse Now"


def test_strip_edition_suffix_extended_edition() -> None:
    assert strip_edition_suffix("Lord of the Rings - Extended Edition") == "Lord of the Rings"


def test_strip_edition_suffix_remastered() -> None:
    assert strip_edition_suffix("Star Wars: Remastered") == "Star Wars"


def test_strip_edition_suffix_no_match() -> None:
    assert strip_edition_suffix("Cut") == "Cut"
    assert strip_edition_suffix("The Director") == "The Director"


# ---------------------------------------------------------------------------
# normalise_query — combines extract_year, strip_annotations, rotate_trailing_article
# ---------------------------------------------------------------------------


def test_normalise_query_strips_year_then_brackets() -> None:
    q, y = normalise_query("Champagne Charlie [Ealing Classics Collection]")
    assert q == "Champagne Charlie"
    assert y is None


def test_normalise_query_year_then_rotates_article() -> None:
    q, y = normalise_query("Hill, The (1965)")
    assert q == "The Hill"
    assert y == 1965


def test_normalise_query_handles_all_three() -> None:
    q, y = normalise_query("Eiger Sanction, The (Special Edition) (1975)")
    assert q == "The Eiger Sanction"
    assert y == 1975


def test_normalise_query_strips_edition_then_rotates() -> None:
    q, y = normalise_query("Blade Runner The Final Cut")
    assert q == "Blade Runner"
    assert y is None


# ---------------------------------------------------------------------------
# Title similarity
# ---------------------------------------------------------------------------


def test_title_similarity_exact_match() -> None:
    assert title_similarity("The Matrix", "The Matrix") == 1.0


def test_title_similarity_case_insensitive() -> None:
    assert title_similarity("the matrix", "The Matrix") == 1.0


def test_title_similarity_punctuation_ignored() -> None:
    assert title_similarity("Avengers: Infinity War", "Avengers Infinity War") > 0.95


def test_title_similarity_low_for_unrelated() -> None:
    assert title_similarity("Dune", "Toy Story") < 0.4


def test_title_similarity_apostrophe_collapsed() -> None:
    # Spreadsheet often drops apostrophes — match should still be exact
    a = "National Lampoons Animal House"
    b = "National Lampoon's Animal House"
    assert title_similarity(a, b) == 1.0


def test_title_similarity_substring_floor() -> None:
    # Query fully contained in result subtitle should clear the matched threshold
    sim = title_similarity("Vampire's Assistant", "Cirque du Freak: The Vampire's Assistant")
    assert sim >= 0.9


def test_title_similarity_no_substring_floor_when_unrelated() -> None:
    # Sanity: floor only applies when substring relation actually holds
    assert title_similarity("Dune", "Toy Story") < 0.5


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def test_score_exact_title_and_year() -> None:
    conf, sim, label = score("Dune", 1984, _result(1, "Dune", 1984))
    assert sim == 1.0
    assert label == "exact"
    assert conf == 1.0  # capped at 1.0 even with year bonus


def test_score_year_mismatch_penalty() -> None:
    conf, sim, label = score("Dune", 1984, _result(1, "Dune", 2021))
    assert sim == 1.0
    assert label == "mismatch"
    assert conf == pytest.approx(0.7)


def test_score_close_year_small_bonus() -> None:
    # Use a fuzzy title so the cap at 1.0 doesn't hide the year bonus
    close_conf, _, close_label = score("Foo Bar", 1985, _result(1, "Foo Baz", 1984))
    unknown_conf, _, _ = score("Foo Bar", None, _result(1, "Foo Baz", 1984))
    assert close_label == "close"
    assert close_conf == pytest.approx(unknown_conf + 0.05)


def test_score_unknown_year_returns_raw_similarity() -> None:
    conf, sim, label = score("Foo", 1984, _result(1, "Foo", None))
    assert label == "unknown"
    assert conf == sim


def test_score_uses_original_title_if_higher() -> None:
    # Localised title is wrong for the query, but original_title matches exactly
    r = _result(1, "El Padrino", 1972, original_title="The Godfather")
    conf, sim, label = score("The Godfather", 1972, r)
    assert sim == 1.0
    assert label == "exact"
    assert conf == 1.0


# ---------------------------------------------------------------------------
# Engine — successful matches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_picks_year_match_over_remake() -> None:
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(
                _result(1, "Dune", 1984),
                _result(2, "Dune", 2021, pop=200.0),
            )
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Dune (1984)")

    assert result.query == "Dune"
    assert result.year == 1984
    assert result.matched is True
    assert result.candidates[0].tmdb_id == 1
    assert result.candidates[0].year_match == "exact"


@pytest.mark.asyncio
async def test_engine_sorts_by_confidence_not_popularity() -> None:
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(
                _result(1, "Different Movie", 2000, pop=5000.0),
                _result(2, "Dune", 1984, pop=10.0),
            )
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Dune (1984)")

    assert result.candidates[0].tmdb_id == 2


@pytest.mark.asyncio
async def test_engine_top_n_caps_results() -> None:
    async with TMDBClient() as tmdb:
        many = _results(*[_result(i, f"Foo {i}", 2000) for i in range(20)])
        tmdb.search_movie = AsyncMock(return_value=many)  # type: ignore[method-assign]
        engine = MatchingEngine(tmdb, top_n=3)
        result = await engine.match("Foo 1")

    assert len(result.candidates) == 3


# ---------------------------------------------------------------------------
# Engine — unmatched / low-confidence flagging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_flags_unmatched_when_no_results() -> None:
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(return_value=_results())  # type: ignore[method-assign]
        engine = MatchingEngine(tmdb)
        result = await engine.match("A Title That Does Not Exist On TMDB Anywhere")

    assert result.matched is False
    assert result.candidates == []


@pytest.mark.asyncio
async def test_engine_flags_unmatched_when_top_below_threshold() -> None:
    async with TMDBClient() as tmdb:
        # Return a single, totally unrelated result — title sim should be < HIGH_CONFIDENCE
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(_result(1, "Something Completely Different", 2000))
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Original Query Title")

    assert result.matched is False
    assert result.candidates  # has candidates, just not confident
    assert result.candidates[0].confidence < HIGH_CONFIDENCE


# ---------------------------------------------------------------------------
# Engine — caching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_caches_repeat_queries() -> None:
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(_result(1, "Dune", 1984))
        )
        engine = MatchingEngine(tmdb)
        await engine.match("Dune (1984)")
        await engine.match("Dune (1984)")
        await engine.match("  dune  (1984)  ")  # canonicalised hits same cache key

    assert tmdb.search_movie.call_count == 1
    assert engine.cache_size == 1


@pytest.mark.asyncio
async def test_engine_cache_distinguishes_years() -> None:
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            side_effect=[
                _results(_result(1, "Dune", 1984)),
                _results(_result(2, "Dune", 2021)),
            ]
        )
        engine = MatchingEngine(tmdb)
        await engine.match("Dune (1984)")
        await engine.match("Dune (2021)")

    assert tmdb.search_movie.call_count == 2
    assert engine.cache_size == 2


# ---------------------------------------------------------------------------
# Engine — fallback when year filter empties the result set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_retries_without_year_when_year_filter_empty() -> None:
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            side_effect=[_results(), _results(_result(1, "Dune", 2021))]
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Dune (1984)")

    assert tmdb.search_movie.call_count == 2
    first_call_kwargs = tmdb.search_movie.call_args_list[0].kwargs
    second_call_kwargs = tmdb.search_movie.call_args_list[1].kwargs
    assert first_call_kwargs.get("year") == 1984
    assert second_call_kwargs.get("year") is None
    # The fallback hit, but the year mismatched so confidence drops
    assert result.candidates
    assert result.candidates[0].year_match == "mismatch"


# ---------------------------------------------------------------------------
# title_exact tiebreak and ambiguity detection (Batch 4, DECISIONS #31)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_prefers_exact_title_over_original_title_match() -> None:
    """The Amistad case, verified live against TMDB on 2026-09-07.

    TMDB returns "Friendship" (2023) — whose *original* title is "Amistad" — alongside
    the real "Amistad", and it is the most popular of the three. `score` takes the max of
    the title and original-title similarities, so all three tie at 1.000, and before this
    the tiebreak was popularity alone.
    """
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(
                _result(1164273, "Friendship", 2023, original_title="Amistad", pop=1.4423),
                _result(11831, "Amistad", 1997, pop=1.2689),
            )
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Amistad")

    assert result.candidates[0].confidence == pytest.approx(1.0)
    assert result.candidates[0].tmdb_id == 11831
    assert result.candidates[0].title_exact is True


@pytest.mark.asyncio
async def test_engine_flags_same_title_decades_apart_as_ambiguous() -> None:
    """ "Frankenstein" ties at 1.000 across 1910, 1931 and 2025. Nothing in a spreadsheet
    row reading only "Frankenstein" says which one is on the shelf."""
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(
                _result(1, "Frankenstein", 2025, pop=90.0),
                _result(2, "Frankenstein", 1931, pop=20.0),
                _result(3, "Frankenstein", 1910, pop=2.0),
            )
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Frankenstein")

    assert result.matched is True
    assert result.ambiguous is True


@pytest.mark.asyncio
async def test_engine_flags_different_titles_tied_at_the_top_as_ambiguous() -> None:
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(
                _result(1, "The Avengers", 2012, pop=90.0),
                _result(2, "Avengers: Endgame", 2019, pop=80.0),
            )
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Avengers")

    assert result.matched is True
    assert result.ambiguous is True


@pytest.mark.asyncio
async def test_engine_does_not_flag_a_clear_winner_as_ambiguous() -> None:
    """An exact title hit outranks the near-misses, so the leader stands alone."""
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(
                _result(1, "Batman", 1989, pop=50.0),
                _result(2, "Holy Batmania", 1989, pop=1.0),
            )
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Batman (1989)")

    assert result.candidates[0].tmdb_id == 1
    assert result.ambiguous is False


@pytest.mark.asyncio
async def test_engine_tolerates_a_re_release_a_year_apart() -> None:
    """Same title, one year apart — a re-release or disagreeing metadata, not a
    different film. Flagging this would send half the catalogue to review."""
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(
                _result(1, "Solaris", 1972, pop=20.0),
                _result(2, "Solaris", 1973, pop=5.0),
            )
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Solaris")

    assert result.ambiguous is False


@pytest.mark.asyncio
async def test_engine_never_flags_an_unmatched_row_as_ambiguous() -> None:
    """`ambiguous` qualifies a confident match. A row that did not match is already
    heading for review under its own reason and must not be double-counted."""
    async with TMDBClient() as tmdb:
        tmdb.search_movie = AsyncMock(  # type: ignore[method-assign]
            return_value=_results(
                _result(1, "Something Else Entirely", 2000, pop=9.0),
                _result(2, "Another Unrelated Film", 2001, pop=8.0),
            )
        )
        engine = MatchingEngine(tmdb)
        result = await engine.match("Zzzz Nonexistent Qqq")

    assert result.matched is False
    assert result.ambiguous is False


def test_leading_tie_excludes_lower_confidence_candidates() -> None:
    from src.matching import MatchCandidate, leading_tie

    def _c(id_: int, conf: float, exact: bool) -> MatchCandidate:
        return MatchCandidate(
            tmdb_id=id_,
            title=f"T{id_}",
            confidence=conf,
            title_similarity=conf,
            year_match="unknown",
            title_exact=exact,
        )

    tied = leading_tie([_c(1, 1.0, True), _c(2, 1.0, True), _c(3, 1.0, False), _c(4, 0.9, True)])
    assert [c.tmdb_id for c in tied] == [1, 2]


def test_is_ambiguous_ignores_a_single_candidate() -> None:
    from src.matching import MatchCandidate, is_ambiguous

    only = MatchCandidate(
        tmdb_id=1, title="Solo", confidence=1.0, title_similarity=1.0, year_match="unknown"
    )
    assert is_ambiguous([only]) is False
    assert is_ambiguous([]) is False
