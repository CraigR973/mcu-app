"""Reading an edition from a Blu-ray.com page title — Batch U2, `DECISIONS.md` #220.

**No request and no database.** The titles are ones the search returned for discs in this
collection by 26 Sep, except the three marked as made up. They are the brackets Blu-ray.com
actually writes: editions, publishers' lines, alternative titles, packs of formats, brands.
"""

from __future__ import annotations

import pytest

from src.services.specs.editions import MAX_EDITION, edition_from_title


@pytest.mark.parametrize(
    ("title", "edition"),
    [
        (
            "Kill Bill Vol. 1 Blu-ray (Zavvi Exclusive SteelBook) (United Kingdom)",
            "Zavvi Exclusive SteelBook",
        ),
        ("Kick-Ass 2 Blu-ray (SteelBook) (United Kingdom)", "SteelBook"),
        ("Laura Blu-ray (Masters of Cinema) (United Kingdom)", "Masters of Cinema"),
        ("Cash on Demand Blu-ray (Indicator Series) (United Kingdom)", "Indicator Series"),
        ("Giant Blu-ray (HMV Exclusive) (United Kingdom)", "HMV Exclusive"),
        ("Horrible Bosses 2 Blu-ray (Extended Cut) (United Kingdom)", "Extended Cut"),
        ("It's a Wonderful Life 4K Blu-ray (Remastered) (United Kingdom)", "Remastered"),
        ("Morocco Blu-ray (DigiPack) (United Kingdom)", "DigiPack"),
        (
            "Magnum Force Blu-ray (The Dirty Harry Collection) (United Kingdom)",
            "The Dirty Harry Collection",
        ),
        ("Good Luck Chuck Blu-ray (Fruity Edition!) (United Kingdom)", "Fruity Edition!"),
        (
            "Knocked Up Blu-ray (Extended and Unprotected) (United Kingdom)",
            "Extended and Unprotected",
        ),
        # Several parts of one bracket, kept in the page's order.
        (
            "Easy Rider Blu-ray (Special Edition | Sony Collector's Edition #5) (United Kingdom)",
            "Special Edition · Sony Collector's Edition #5",
        ),
        (
            "Hobson's Choice Blu-ray (Vintage Classics | 60th Anniversary Edition) "
            "(United Kingdom)",
            "Vintage Classics · 60th Anniversary Edition",
        ),
        # An alternative title beside the line: the title goes, the line stays.
        (
            "Ace in the Hole Blu-ray (The Big Carnival / Masters of Cinema) (United Kingdom)",
            "Masters of Cinema",
        ),
        (
            "I Was Monty's Double Blu-ray (Hell, Heaven or Hoboken / Vintage Classics) "
            "(United Kingdom)",
            "Vintage Classics",
        ),
        # A pack of formats beside the edition: the pack goes.
        ("Knight and Day Blu-ray (Extended Cut | Triple Play) (United Kingdom)", "Extended Cut"),
        # "Standard" is what the matcher calls plain; the line beside it stays.
        (
            "Night Has a Thousand Eyes Blu-ray (Indicator Series | Standard Edition) "
            "(United Kingdom)",
            "Indicator Series",
        ),
        # A curly apostrophe reads as a straight one (made up).
        (
            "American Reunion Blu-ray (Deluxe Collector’s Edition) (United Kingdom)",
            "Deluxe Collector’s Edition",
        ),
    ],
)
def test_the_edition_a_page_names_is_read(title: str, edition: str) -> None:
    assert edition_from_title(title) == edition


@pytest.mark.parametrize(
    "title",
    [
        # A plain release names none.
        "Fight Club Blu-ray (United Kingdom)",
        "Blade Runner 2049 4K Blu-ray (4K Ultra HD + Blu-ray) (United Kingdom)",
        # Alternative titles, not editions.
        "Men in Black Blu-ray (MIB) (United Kingdom)",
        "Men in Black II Blu-ray (MIIB / Men in Black 2) (United Kingdom)",
        "12 Angry Men Blu-ray (Twelve Angry Men) (United Kingdom)",
        "American Wedding Blu-ray (American Pie: The Wedding) (United Kingdom)",
        "F/X2 Blu-ray (F/X 2: The Deadly Art of Illusion) (United Kingdom)",
        # Packs of formats and a studio's brand.
        "Hereafter Blu-ray (Triple Play) (United Kingdom)",
        "Megamind Blu-ray (Double Play) (United Kingdom)",
        "Cloudy With a Chance of Meatballs Blu-ray (Combi Pack) (United Kingdom)",
        "Finding Nemo Blu-ray (PIXAR) (United Kingdom)",
        "Eagle Eye Blu-ray (Standard Edition) (United Kingdom)",  # made up
    ],
)
def test_a_page_that_names_no_edition_gives_none(title: str) -> None:
    assert edition_from_title(title) is None


def test_an_edition_longer_than_the_column_is_not_cut_short() -> None:
    """Made up: no page yet names one this long."""
    long_edition = "Limited " + "Special " * 20 + "Edition"
    assert len(long_edition) > MAX_EDITION

    assert edition_from_title(f"Heat Blu-ray ({long_edition}) (United Kingdom)") is None
