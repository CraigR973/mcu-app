"""Reading a spreadsheet title — Batch T9. Pure functions, so these run anywhere.

**What this proves:** the kinds of title the 25 Sep dry run met are read into what TMDB can
use — a year in or out of brackets, a person in brackets, a franchise after a dash,
brackets that never close, library order, TV series and a test row — and the folding that
decides "the same title" treats typos, numbers and punctuation as the batch intends.
Every title here is a real one from the collection.
"""

from __future__ import annotations

import pytest

from src.services.identify.titles import (
    compare,
    fix_brackets,
    fold,
    grouping_people,
    leading_words,
    parse_title,
    simplified,
    without_article,
)

# ---------------------------------------------------------------------------
# Brackets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "fixed"),
    [
        ("Kings Row (1942", "Kings Row (1942)"),
        ("Long Voyage Home, The (1940}", "Long Voyage Home, The (1940)"),
        ("Likely Lads, The [Movie}", "Likely Lads, The [Movie]"),
        ("Enforcer, The (Humphrey Bogart}", "Enforcer, The (Humphrey Bogart)"),
        ("A stray) closer", "A stray closer"),
    ],
)
def test_brackets_close_the_way_they_opened(raw: str, fixed: str) -> None:
    assert fix_brackets(raw) == fixed


# ---------------------------------------------------------------------------
# Years
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "main", "year", "bare"),
    [
        ("Beaue Geste (1939)", "Beaue Geste", 1939, False),
        ("Death on the Nile [1978]", "Death on the Nile", 1978, False),
        ("I walked with a Zombie (1943", "I walked with a Zombie", 1943, False),
        ("Murder by Decree 1979", "Murder by Decree", 1979, True),
        ("Cape Fear 1962", "Cape Fear", 1962, True),
        ("Spy in Black, The 1937", "The Spy in Black", 1937, True),
        ("Fugitive Kind. The 1960", "The Fugitive Kind", 1960, True),
        ("Alias Nick Beal [The Contact Man] 1949", "Alias Nick Beal", 1949, True),
        ("Wanted for Murder (A Voice in the Night) 1946", "Wanted for Murder", 1946, True),
        ("M (1931) - English Version", "M", 1931, False),
        ("Dune 2", "Dune 2", None, False),
    ],
)
def test_a_year_is_read_in_or_out_of_brackets(
    raw: str, main: str, year: int | None, bare: bool
) -> None:
    parsed = parse_title(raw)
    assert parsed.main == main
    assert parsed.year == year
    assert parsed.year_is_bare is bare


def test_a_number_past_the_years_a_film_can_have_stays_in_the_title() -> None:
    assert parse_title("Blade Runner 2049").year is None
    assert parse_title("Blade Runner 2049").main == "Blade Runner 2049"


def test_a_year_with_words_beside_it_is_still_a_year() -> None:
    parsed = parse_title("ABC Murders (BBC 2018)")
    assert parsed.year == 2018
    assert parsed.tv_hint is not None
    assert parsed.tv is None


def test_brackets_that_hold_another_title_become_a_reading() -> None:
    parsed = parse_title("Alias Nick Beal [The Contact Man] 1949")
    assert "The Contact Man" in [reading.text for reading in parsed.readings]
    assert parsed.alternates == ("The Contact Man",)


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "people"),
    [
        ("Enforcer, The (Humphrey Bogart}", ("Humphrey Bogart",)),
        ("Mummy, The  (Brendan Fraser)", ("Brendan Fraser",)),
        ("Mummy, The (Tom Cruise)", ("Tom Cruise",)),
        ("Dark Victory (The Bette Davis collection)", ("Bette Davis",)),
        ("King Kong - Peter Jackson Remake", ("Peter Jackson",)),
    ],
)
def test_a_person_the_title_names_is_its_own(raw: str, people: tuple[str, ...]) -> None:
    assert parse_title(raw).people == people


def test_a_name_after_a_dash_is_weaker_because_it_is_often_a_franchise() -> None:
    parsed = parse_title("Kingdom of the Crystal Skull, The - Indiana Jones")
    assert parsed.people == ()
    assert parsed.weak_people == ("Indiana Jones",)
    assert parse_title("Captain Ameica - Civil War").people == ()
    assert parse_title("I'm Only Looking - INXS").weak_people == ("INXS",)


@pytest.mark.parametrize(
    ("grouping", "people"),
    [
        ("Clint Eastwood", ("Clint Eastwood",)),
        ("Powell & Pressburger", ("Powell", "Pressburger")),
        ("Hitchcock Early Collection", ("Hitchcock",)),
        (
            "The Alfred Hitcchcock Classics Coll Vol 3 / House of Hitchcock",
            ("Alfred Hitcchcock", "Hitchcock"),
        ),
        ("Stanley Kubrick - Kubrick Box Set", ("Stanley Kubrick", "Kubrick")),
        ("Universal Noir #2", ()),
        ("Marvel", ()),
        ("Ealing", ()),
        ("TV", ()),
        (None, ()),
    ],
)
def test_a_grouping_names_the_people_its_shelf_is_built_round(
    grouping: str | None, people: tuple[str, ...]
) -> None:
    assert grouping_people(grouping) == people


# ---------------------------------------------------------------------------
# Dashes, commas and library order
# ---------------------------------------------------------------------------


def test_a_franchise_after_a_dash_is_read_both_ways_round() -> None:
    readings = parse_title("Kingdom of the Crystal Skull, The - Indiana Jones").readings
    whole = [reading.text for reading in readings if reading.tier == 1]
    assert "Indiana Jones The Kingdom of the Crystal Skull" in whole
    assert all(reading.tier > 1 for reading in readings if reading.text == "Indiana Jones")


def test_an_edition_after_a_dash_is_dropped() -> None:
    assert parse_title("Alien - 40th Anniversary edition").main == "Alien"
    assert parse_title("Thing, The - Arrow Blu Ray").main == "The Thing"
    assert parse_title("Stalag 17 Blu Ray").main == "Stalag 17"
    assert parse_title("Shrek The Third 3rd 3d").main == "Shrek The Third"


def test_original_and_remake_are_hints_not_part_of_the_title() -> None:
    parsed = parse_title("Clash of the Titans Original")
    assert parsed.main == "Clash of the Titans"
    assert parsed.hints == ("original",)
    assert parse_title("Karate Kid Remake").hints == ("remake",)
    assert parse_title("Thing, The Prequel").main == "The Thing"


@pytest.mark.parametrize(
    ("raw", "main"),
    [
        ("Mummy, The  (Brendan Fraser)", "The Mummy"),
        ("Karate Kid The", "The Karate Kid"),
        ("Advetures of Sherlock Holmes , The", "The Advetures of Sherlock Holmes"),
        ("Time Machine. The", "The Time Machine"),
        ("Brave,", "Brave"),
        ("Godfather, The Part II", "The Godfather Part II"),
        ("Clockwork Orange, A", "A Clockwork Orange"),
    ],
)
def test_library_order_is_undone(raw: str, main: str) -> None:
    assert parse_title(raw).main == main


def test_a_comma_joining_two_halves_is_read_in_both_orders() -> None:
    whole = [r.text for r in parse_title("Jurassic Park, The Lost World").readings if r.tier == 1]
    assert "The Lost World Jurassic Park" in whole
    mad_max = [r.text for r in parse_title("Mad Max 3, Beyond Thunderdrome").readings]
    assert "Mad Max Beyond Thunderdrome" in mad_max


# ---------------------------------------------------------------------------
# TV and not a film
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "Steptoe & Son - Complete Series",
        "Broadchurch Season 1 - 3",
        "Alfred Hitchcock Presents - Seasons 1 -7",
        "Walking Dead, The - Complete 1st Season",
        "Shetland - Series 5",
        "Idiot Abroad - Series 1 & 2",
        "Some Mothers Do Ave em  [Complete TV Series]",
        "Smiley's People (TV)",
    ],
)
def test_the_words_a_box_of_episodes_is_sold_under_mean_tv(raw: str) -> None:
    assert parse_title(raw).tv is not None


def test_a_series_number_alone_is_only_a_hint_because_films_have_them_too() -> None:
    assert parse_title("Open Season 2").tv is None
    assert parse_title("Open Season 2").tv_hint is not None
    game = parse_title("Game of Thrones Season 1")
    assert game.tv is None
    assert game.tv_title == "Game of Thrones"


def test_a_title_starting_complete_is_a_box_of_a_series() -> None:
    parsed = parse_title("Complete Fingerbobs, The")
    assert parsed.tv is None
    assert parsed.tv_hint is not None
    assert parsed.tv_title == "Fingerbobs"


def test_craigs_tv_grouping_means_tv() -> None:
    assert parse_title("Charles II", "TV").tv is not None
    assert parse_title("Charles II", "Television classics").tv is None


def test_a_test_row_is_not_a_film() -> None:
    assert parse_title("Test 15.04.26").not_film is not None
    assert parse_title("Testament of Youth").not_film is None


# ---------------------------------------------------------------------------
# Folding and comparing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ours", "theirs"),
    [
        ("Cowboys v Aliens", "Cowboys & Aliens"),
        ("US v's John Lennon", "The U.S. vs. John Lennon"),
        ("Dune 2", "Dune: Part Two"),
        ("Star Wars Ep IV A New Hope", "Star Wars: Episode IV - A New Hope"),
        ("Leon", "Léon"),
        ("National Lampoons Animal House", "National Lampoon's Animal House"),
        ("Happy Feet 2", "Happy Feet Two"),
    ],
)
def test_folding_makes_two_spellings_of_one_title_equal(ours: str, theirs: str) -> None:
    assert fold(ours) == fold(theirs) or compare(ours, theirs).how == "exact"


def test_a_typo_is_the_same_title_and_a_different_word_is_not() -> None:
    assert compare("Peepiing Tom", "Peeping Tom").how == "typo"
    assert compare(
        "Lock Stock and Two Smoking Barrles", "Lock, Stock and Two Smoking Barrels"
    ).same_title
    assert not compare(
        "Encounters at the end of the Earth", "Encounters at the End of the World"
    ).same_title
    assert not compare("Scandal Street", "Scandal Sheet").same_title


def test_numbers_must_agree_except_a_first_part_that_does_not_say_so() -> None:
    assert not compare(
        "Harry Potter and the Deathly Hallows Part 1",
        "Harry Potter and the Deathly Hallows: Part 2",
    ).near_exact
    assert compare("The Godfather Part I", "The Godfather").how == "exact"
    assert not compare("Speed", "Speed 2: Cruise Control").near_exact
    assert not compare("Ocean's 12", "Ocean's Eleven").near_exact


def test_a_leading_article_does_not_decide_a_title() -> None:
    assert compare("The Sorcerer", "Sorcerer").how == "exact"
    # Readings are compared, and a reading has its article back at the front.
    assert compare(parse_title("Midnight Cowboy The").main, "Midnight Cowboy").how == "exact"


def test_words_in_another_order_are_the_same_title() -> None:
    assert compare("Dracula Bram Stokers", "Bram Stoker's Dracula").how == "words"


def test_a_subtitle_is_only_part_of_a_title() -> None:
    assert (
        compare(
            "Dr. Strangelove",
            "Dr. Strangelove or: How I Learned to Stop Worrying and Love the Bomb",
        ).how
        == "subtitle"
    )
    assert compare("Bird: The Charlie Parker Story", "Bird").how == "subtitle"
    assert compare("Live Baby Live", "INXS: Live Baby Live").how == "tail"
    assert not compare("Live Baby Live", "INXS: Live Baby Live").same_title


def test_a_number_on_its_own_is_too_little_to_be_a_title() -> None:
    """Furious 7's Spanish title made an early version take "Seven" for Furious 7."""
    assert not compare("Seven", "A todo gas: 7").near_exact


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def test_the_loose_searches_spell_out_what_tmdb_cannot_read() -> None:
    assert simplified("Star Wars Ep IV A New Hope") == "Star Wars Episode IV A New Hope"
    assert simplified("Cowboys v Aliens") == "Cowboys and Aliens"
    assert simplified("The Best Year's of our lives") == "The Best Years of our lives"
    assert without_article("The Marathon Man") == "Marathon Man"
    assert (
        leading_words("Fantastic Beasts and the Crimes of Grindewald") == "Fantastic Beasts and the"
    )
    assert leading_words("Campaigh") is None
