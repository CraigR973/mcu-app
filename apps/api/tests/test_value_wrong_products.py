"""Another product never prices a film — Batch X6's guard (MK47-03).

The wave 1 review re-ran twenty live searches through the estimator on 11 Oct and found seven
of the medians mixed with another product: another film whose title holds this one's
(*Spider Labyrinth*, *More American Graffiti*, *On the Town*, *American Psycho*), the TV series
of a film's name (*Westworld*), a Blu-ray titled "Not 4K UHD" on a 4K search, and a two-film
"Steelbooks" set read as a standard edition. Four of the six highest values were among them.

Each title here is **crafted** around the tell the review quotes, not copied from eBay, and
goes through the valuation's own path (``estimate_price`` then ``valuation_from``) as six
listings, three used and three New, so that it would price the film if any one were let
through. Each fails when its rule is reverted. Beside them, the titles the rules must still
let through: a seller's words or a label before the film's own title, and a TV title's own
box set when the film is a series.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from src.ebay.estimate import estimate_price
from src.ebay.matching import Listing, match
from src.services.valuation import FALLBACK_FACTOR, valuation_from


class Answering:
    """An eBay that returns one payload, whatever it is asked."""

    marketplace_id = "EBAY_GB"

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def search(
        self, query: str, *, limit: int = 200, category_ids: str | None = None
    ) -> dict[str, Any]:
        del query, limit, category_ids
        return self.payload


def _six(title: str) -> dict[str, Any]:
    """Three used and three New listings, all with this title."""
    return {
        "itemSummaries": [
            {
                "itemId": f"v1|{index}|0",
                "title": title,
                "price": {"value": f"{20 + index}.00", "currency": "GBP"},
                "conditionId": "3000" if index < 3 else "1000",
                "buyingOptions": ["FIXED_PRICE"],
                "leafCategoryIds": ["617"],
                "itemLocation": {"country": "GB"},
            }
            for index in range(6)
        ]
    }


async def _valued(film: str, format_code: str, title: str, *, is_series: bool = False) -> Any:
    estimate = await estimate_price(
        Answering(_six(title)), film_title=film, format_code=format_code, is_series=is_series
    )
    return valuation_from(estimate, format_code, factor=FALLBACK_FACTOR)


# (the film searched for, its format, a crafted title carrying the review's tell, the rule)
REFUSED = [
    ("Labyrinth", "4k_uhd", "Spider Labyrinth 4K UHD Region A import", "a word before the title"),
    ("Labyrinth", "4k_uhd", "Pan's Labyrinth 4K Ultra HD Guillermo del Toro", "a word before"),
    ("American Graffiti", "blu_ray", "More American Graffiti Blu-ray 1979 sequel", "word before"),
    ("The Town", "blu_ray", "On the Town Blu-ray 1949 Gene Kelly musical", "a word before"),
    ("Psycho", "4k_uhd", "American Psycho 4K UHD Christian Bale", "a word before the title"),
    (
        "The Naked City",
        "blu_ray",
        "Tales from the Urban Jungle Brute Force and The Naked City Blu-ray",
        "a word before the title",
    ),
    ("Westworld", "4k_uhd", "Westworld The Complete Series 4K UHD box set", "television"),
    ("Westworld", "4k_uhd", "Westworld Series 2 Complete 4K UHD", "television"),
    ("Westworld", "4k_uhd", "Westworld 4K Staffel 1 UHD Blu-ray", "television, in German"),
    ("Back to the Future", "4k_uhd", "Back to the Future Blu-ray BTTF Not 4K UHD", "not a 4K"),
    ("Dune: Part Two", "4k_uhd", "Dune: Part Two 4K UHD Steelbooks HMV", "collector, plural"),
    ("Dune: Part Two", "4k_uhd", "Dune + Dune: Part Two 4K UHD two film set", "a word before"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("film", "format_code", "title", "rule"), REFUSED, ids=[case[2] for case in REFUSED]
)
async def test_another_product_never_prices_the_film(
    film: str, format_code: str, title: str, rule: str
) -> None:
    del rule
    valuation = await _valued(film, format_code, title)
    assert valuation.status == "not_priced"
    assert (valuation.price, valuation.used_count, valuation.new_count) == (None, 0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("film", "format_code", "title"),
    [
        ("Labyrinth", "4k_uhd", "Labyrinth 4K UHD 1986 Jim Henson David Bowie"),
        ("Labyrinth", "4k_uhd", "NEW Sealed 4K UHD Blu-ray Labyrinth"),
        ("Young Frankenstein", "blu_ray", "20th Century Fox Young Frankenstein Blu-ray"),
        (
            "Star Wars: The Rise of Skywalker",
            "4k_uhd",
            "Lucasfilm Star Wars: The Rise of Skywalker 4K",
        ),
        (
            "Star Wars: The Rise of Skywalker",
            "4k_uhd",
            "4K Ultra HD + Blu Ray Star Wars: The Rise of Skywalker",
        ),
        ("Christine", "4k_uhd", "New EU Import Christine 4K UHD"),
        ("The Town", "blu_ray", "The Town Blu-ray Ben Affleck"),
    ],
)
async def test_the_film_itself_still_prices(film: str, format_code: str, title: str) -> None:
    """The same six listings under the film's own title, with what sellers put before it."""
    valuation = await _valued(film, format_code, title)
    assert (valuation.status, valuation.value_basis, valuation.price) == (
        "priced",
        "used_quartile",
        Decimal("20.50"),
    )


@pytest.mark.asyncio
async def test_a_tv_titles_own_box_set_prices_it() -> None:
    title = "Blue Planet II The Complete Series 4K UHD"
    assert (await _valued("Blue Planet II", "4k_uhd", title)).status == "not_priced"
    assert (await _valued("Blue Planet II", "4k_uhd", title, is_series=True)).status == "priced"


def _listing(title: str) -> Listing:
    return Listing(
        item_id="v1|1|0",
        title=title,
        price=Decimal("10.00"),
        currency="GBP",
        condition_id="3000",
        web_url="",
        leaf_category_ids=("617",),
        country="GB",
        item_group_type=None,
    )


@pytest.mark.parametrize(
    ("film", "title", "reason"),
    [
        ("Labyrinth", "Spider Labyrinth 4K UHD", "'spider' before 'Labyrinth'"),
        ("Mystic River", "Warner Home Video Mystic River Blu-ray", "'home' before"),
        ("Jaws", "New Sealed 4K UHD Blu-ray Steelbook Edition Jaws", "starts too far"),
        ("Westworld", "Westworld 4K Staffel 1", "television, not the film ('staffel')"),
        ("Dune: Part Two", "Dune: Part Two 4K UHD Steelbooks", None),
    ],
)
def test_each_rule_names_itself(film: str, title: str, reason: str | None) -> None:
    """A refusal says why, so a person reading the rejections can tell the rules apart."""
    verdict = match(_listing(title), film_title=film, format_code="4k_uhd")
    if reason is None:
        # Not refused: a collector's edition, kept apart from the standard one.
        assert (verdict.ok, verdict.edition) == (True, "collector")
    else:
        assert not verdict.ok
        assert reason in (verdict.reason or "")
