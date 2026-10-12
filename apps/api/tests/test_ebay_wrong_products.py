"""The 25 wrong products the deal scan found, refused — Batch X1's guard (MK47-01).

`docs/reviews/BATCH_43-48_EVIDENCE.md`, section 1, lists the stored deals of 26 Sep–9 Oct
that were another product: another film of the same name, a disc with no case, a Blu-ray
filed as a 4K, a Region A disc. Each title here is **crafted** around the tell the evidence
quotes, not copied from eBay, and goes through the scan's own path (`Catalogue.named_in`,
which calls the matcher) for the film it was filed under. Each fails when its rule is
reverted.

**Three carry nothing a title rule can use** (*Maggie* and the two *Titanic* 3D sets). For
them the defence is the push and the card naming the listing's own title and condition,
which the last tests pin.

Alongside them, the titles the rules must still let through: the film's own year, a
Region B or region-free disc, a film whose title holds one of the rules' words.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from src.ebay.matching import Listing, match
from src.services.ebay_watch.catalogue import Catalogue, CatalogueFilm
from src.services.ebay_watch.listings import ScanListing
from src.services.ebay_watch.refs import Yardstick
from src.services.ebay_watch.runs import deal_alert
from src.services.ebay_watch.scan import Find


def _film(title: str, year: int) -> CatalogueFilm:
    # Owned on DVD, so either disc format would be an upgrade the scan considers.
    return CatalogueFilm(
        movie_id=uuid.uuid4(),
        tmdb_id=1,
        title=title,
        year=year,
        wanted=False,
        preferred_format=None,
        best_owned=2,
    )


def _listing(title: str, *, condition_id: str = "1000") -> Listing:
    return Listing(
        item_id="v1|1|0",
        title=title,
        price=Decimal("5.00"),
        currency="GBP",
        condition_id=condition_id,
        web_url="https://www.ebay.co.uk/itm/1",
        leaf_category_ids=("617",),
        country="GB",
        item_group_type=None,
    )


def _named(film: CatalogueFilm, title: str) -> tuple[CatalogueFilm, str] | None:
    catalogue = Catalogue()
    catalogue.add(film)
    return catalogue.named_in(_listing(title))


# (filed under, its year, a crafted title carrying the evidence's tell, the rule that refuses it)
REFUSED = [
    ("Dunkirk", 1958, "Dunkirk (2017) 4K Ultra HD Blu-ray Nolan", "year"),
    ("We're No Angels", 1955, "We're No Angels Blu-ray REGION A Bogart", "region"),
    ("Halloween", 1978, "Halloween 2018 4K UHD Steelbook damaged base", "year"),
    ("if....", 1968, "IF Blu-ray (2024) family film", "year, past a format word"),
    ("X-Men: Days of Future Past", 2014, "X-Men Days of Future Past 4K UHD NO CASE", "incomplete"),
    ("Contagion", 2011, "Contagion 4K UHD DISC ONLY NO CASE", "incomplete"),
    ("Halloween", 1978, "Halloween (2018) 4K Ultra HD DISC ONLY", "year, incomplete"),
    ("Despicable Me", 2010, "Despicable Me 4K UHD Disc Only No Case", "incomplete"),
    ("Air Force One", 1997, "Air Force One 4K UHD Blu-ray US disc NO CASE", "incomplete"),
    ("Source Code", 2011, "Source Code 4K Ultra HD no case", "incomplete"),
    ("San Andreas", 2015, "San Andreas 4K UHD no case", "incomplete"),
    ("Road House", 1948, "Road House 1989 4K UHD", "year"),
    (
        "Invasion of the Body Snatchers",
        1956,
        "Invasion of the Body Snatchers (1978) Blu-ray",
        "year",
    ),
    ("Night of the Living Dead", 1968, "Night of the Living Dead (1990) 4K Ultra HD", "year"),
    ("Wonder Woman", 2017, "Wonder Woman 1984 4K UHD Disc Only", "year, incomplete"),
    ("My Fair Lady", 1964, "My Fair Lady 1964 4K UHD DISC ONLY", "incomplete"),
    ("Mary, Queen of Scots", 1971, "Mary Queen of Scots Blu-ray (2019) new", "year, past a format"),
    ("The Monster Squad", 1987, "The Monster Squad Blu-ray Region A", "region"),
    (
        "The Day the Earth Stood Still",
        1951,
        "The Day the Earth Stood Still [Blu-ray] [2008]",
        "year",
    ),
]


@pytest.mark.parametrize(("film_title", "year", "title", "rule"), REFUSED)
def test_a_wrong_product_is_refused(film_title: str, year: int, title: str, rule: str) -> None:
    assert _named(_film(film_title, year), title) is None, rule


@pytest.mark.parametrize(
    ("film_title", "year", "title"),
    [
        ("A Clockwork Orange", 1971, "A Clockwork Orange Blu-ray Not a 4K Blu-ray release"),
        ("Army of Darkness", 1992, "Army of Darkness Blu-ray REMASTERED IN 4K"),
        ("The Thing", 1982, "The Thing Blu-ray 4K Restoration"),
        ("Jaws", 1975, "Jaws Blu-ray not 4K"),
    ],
)
def test_a_blu_ray_that_names_4k_is_not_a_4k(film_title: str, year: int, title: str) -> None:
    film = _film(film_title, year)
    assert _named(film, title) == (film, "blu_ray")


@pytest.mark.parametrize(
    ("film_title", "year", "title", "format_code"),
    [
        # The film's own year, or one either side (a UK disc's year is often its release).
        ("Halloween", 1978, "Halloween (1978) 4K UHD Steelbook", "4k_uhd"),
        ("Wonder Woman", 2017, "Wonder Woman 4K UHD (2017)", "4k_uhd"),
        (
            "Star Wars: The Force Awakens",
            2015,
            "Star Wars: The Force Awakens Blu-Ray (2016)",
            "blu_ray",
        ),
        # A year past an edition word is not read: it may be when the steelbook came out.
        ("Halloween", 1978, "Halloween 4K UHD Steelbook 2018", "4k_uhd"),
        # Region B plays in the UK, and so does a disc for every region.
        ("Suspiria", 1977, "Suspiria Blu-ray German import Region B", "blu_ray"),
        ("The Monster Squad", 1987, "The Monster Squad Blu-ray Region A B C", "blu_ray"),
        ("The Monster Squad", 1987, "The Monster Squad Blu-ray Region Free", "blu_ray"),
        # A 4K disc plays anywhere, whatever region its bundled Blu-ray is.
        ("The Monster Squad", 1987, "The Monster Squad 4K UHD Region A", "4k_uhd"),
        # A rule's word inside the film's own title is the title.
        ("The Empty Man", 2020, "The Empty Man Blu-ray", "blu_ray"),
        ("Fargo", 1996, "Fargo Blu-ray Coen brothers", "blu_ray"),
        # A US import that states no region is passed (X1's call, DECISIONS #258).
        ("Near Dark", 1987, "Near Dark Blu-ray US import", "blu_ray"),
    ],
)
def test_the_right_disc_still_matches(
    film_title: str, year: int, title: str, format_code: str
) -> None:
    film = _film(film_title, year)
    assert _named(film, title) == (film, format_code)


@pytest.mark.parametrize(
    "title",
    [
        "Fargo Season 1 Blu-ray",
        "Fargo The Complete Series Blu-ray",
        "Fargo Series 3 Blu-ray",
    ],
)
def test_television_is_not_the_film(title: str) -> None:
    assert _named(_film("Fargo", 1996), title) is None


def test_the_year_rule_applies_only_when_a_year_is_known() -> None:
    """The film page's estimator passes no year, and keeps its answers (fixtures unchanged)."""
    listing = _listing("Halloween (2018) 4K UHD")
    assert match(listing, film_title="Halloween").ok
    assert not match(listing, film_title="Halloween", film_year=1978).ok


# ---------------------------------------------------------------------------
# The three no title rule can tell apart: the push names the listing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("film_title", "year", "title"),
    [
        ("The 'Maggie'", 1954, "Maggie Blu-ray Region Free Schwarzenegger"),
        ("Titanic", 1953, "Titanic Blu-ray 3D Collector's Edition James Cameron 2012 release"),
        ("Titanic", 1953, "Titanic Blu-ray 3D Box Set James Cameron"),
    ],
)
def test_a_wrong_product_no_rule_can_see_is_pushed_under_its_own_title(
    film_title: str, year: int, title: str
) -> None:
    film = _film(film_title, year)
    named = _named(film, title)
    if named is None:
        # Refused after all (another rule caught it): nothing is pushed under the film.
        return
    listing = ScanListing(
        listing=_listing(title, condition_id="4000"),
        legacy_id="1",
        listed_at=None,
        postage=Decimal("1.50"),
        image_url=None,
        buy_now=True,
    )
    find = Find(film, named[1], listing, Yardstick(Decimal("12.00"), 7), False, 46)
    alert = deal_alert(find, uuid.uuid4())
    assert alert.title == title
    assert alert.body.startswith("Very good, £6.50 with postage on eBay")
    assert f"Filed as {film_title} ({year})" in alert.body
