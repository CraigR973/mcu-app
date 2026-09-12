"""The deals feed — Batch 22, phases 5.9 and 5.10.

**§5.9's acceptance cannot be met here and is not pretended to be.** It requires a live
run against real retailer sale pages, which `docs/agent-commands/group-start.md` puts in
the owner's hands — the same footing as Batch 19's checkpoint and Batch 23's §3.7.

**There is deliberately no captured sale-page fixture, and that absence is the honest
option.** Capturing one means fetching a real retailer page, which is the same owner-gated
act. Inventing one would be worse: `DECISIONS.md` #122 is the standing account of what an
invented fixture costs — eleven tests passing for weeks against markup a site had never
served. So:

- :func:`extract_deals` is tested against `zavvi_search_two_price_shapes.html`, which is
  **verbatim captured markup** from a real Zavvi page. It is a search page rather than a
  sale page, and that turns out to be the most useful thing about it: its cards carry no
  struck-through price, so it exercises the "no card has a `was` price" drift rule on real
  HTML rather than on something written to make the rule fire.
- The judgement rules are tested against `DealCandidate` values directly. A dataclass is
  not a fixture — there is no markup to be wrong about.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.services.scraping.builtins import (
    BUILT_IN_SCRAPERS,
    deals_config_for,
    unverified_deals_names,
)
from src.services.scraping.deals import (
    MAX_DISCOUNT_PERCENT,
    MIN_CARDS_FOR_POPULATION_CHECKS,
    DealCandidate,
    check_deal_shape,
    check_page_shape,
    extract_deals,
)

FIXTURES = Path(__file__).parent / "fixtures"
ZAVVI_HTML = (FIXTURES / "zavvi_search_two_price_shapes.html").read_text()


def _zavvi_config() -> dict[str, object]:
    config = dict(BUILT_IN_SCRAPERS["Zavvi"]["config"])
    config.update(deals_config_for("Zavvi") or {})
    return config


def _candidate(
    *,
    title: str = "Jaws [Blu-ray]",
    price: str | None = "9.99",
    was: str | None = "19.99",
    currency: str | None = "GBP",
    url: str | None = "https://www.zavvi.com/p/blu-ray/jaws/1/",
) -> DealCandidate:
    return DealCandidate(
        title=title,
        price=Decimal(price) if price is not None else None,
        was_price=Decimal(was) if was is not None else None,
        currency=currency,
        url=url,
        raw_price_text=f"£{price}" if price else None,
        raw_was_text=f"£{was}" if was else None,
    )


# ---------------------------------------------------------------------------
# Reading real markup
# ---------------------------------------------------------------------------


def test_real_captured_cards_are_read_whole() -> None:
    """Two verbatim Zavvi cards, both figures the ones `DECISIONS.md` #125 measured.

    Reading card by card rather than selector by selector is what stops a title coming
    from one product and a price from another — and #125 is the record of the second card
    being silently discarded when only one price markup was understood.
    """
    cards = extract_deals(ZAVVI_HTML, _zavvi_config(), page_url="https://www.zavvi.com/sale.list")

    assert [card.title for card in cards] == ["Cross Of Iron", "Castle Freak Limited Edition"]
    assert [card.price for card in cards] == [Decimal("12.99"), Decimal("16.99")]
    assert all(card.currency == "GBP" for card in cards)


def test_a_deal_gets_a_clickable_absolute_url() -> None:
    """The defect this found in real markup.

    Zavvi's configured `url` selector points at `product-title`, which is a **heading**,
    not a link — so the configured selector yields no href at all. A wanted-item scrape
    survives that (it still has a price and a title, and the same-site guard simply does
    not run, which is why it was never noticed); a deal does not. Without the anchor
    fallback every Zavvi deal arrives unclickable and they all collide on `''` under the
    `(retailer_id, url)` uniqueness key.
    """
    cards = extract_deals(ZAVVI_HTML, _zavvi_config(), page_url="https://www.zavvi.com/sale.list")

    assert cards[0].url == "https://www.zavvi.com/p/blu-ray/cross-of-iron/10369739/"
    assert all(card.url and card.url.startswith("https://www.zavvi.com/p/") for card in cards)
    # Distinct, which is what the uniqueness key depends on.
    assert len({card.url for card in cards}) == len(cards)


def test_a_page_with_no_card_selector_yields_nothing_rather_than_guessing() -> None:
    """Without `item`, every selector runs over the whole page independently and the
    title comes from one product while the price comes from another. On a deals page
    there is no expected title to catch that, so it would be silent."""
    assert extract_deals(ZAVVI_HTML, {"title": "h3", "price": ".price"}, page_url="https://x") == []


# ---------------------------------------------------------------------------
# The page-level assertion — Batch 22's extension of #79
# ---------------------------------------------------------------------------


def test_a_page_where_no_card_has_a_was_price_is_refused() -> None:
    """Fired by **real markup**: the captured cards are search results and carry no
    struck-through price.

    On a sale page that is the shape of the sale-price selector having moved, which turns
    a sale page into a price list and makes every discount null. Every individual card
    still looks entirely reasonable.
    """
    cards = extract_deals(ZAVVI_HTML, _zavvi_config(), page_url="https://www.zavvi.com/sale.list")
    # Padded to the population threshold with the same real cards — below it the rule is
    # deliberately silent, because a small sale is a real thing.
    verdict = check_page_shape(cards * 3)

    assert not verdict.ok
    assert any("no card on the page has a 'was' price" in reason for reason in verdict.reasons)


def test_every_card_showing_the_same_discount_is_refused() -> None:
    """A shared node read forty times — an "up to 70% off" banner matched by the `was`
    selector. Each row is plausible; the set is impossible, and only a population check
    can see it."""
    verdict = check_page_shape([_candidate(price="10.00", was="20.00") for _ in range(8)])

    assert not verdict.ok
    assert any("same 50% discount" in reason for reason in verdict.reasons)


def test_every_card_showing_the_same_price_is_refused() -> None:
    verdict = check_page_shape(
        [_candidate(price="10.00", was=str(15 + index)) for index in range(8)]
    )

    assert not verdict.ok
    assert any("same price" in reason for reason in verdict.reasons)


def test_an_empty_page_is_refused() -> None:
    verdict = check_page_shape([])
    assert not verdict.ok
    assert "no product cards" in verdict.reasons[0]


def test_a_small_sale_is_not_treated_as_drift() -> None:
    """Below the population threshold "every card is the same" is a coincidence.

    A shop with three discs on offer is an ordinary Tuesday, and refusing it would make
    the feed empty for the smallest retailers — which are three of the five enabled.
    """
    few = [_candidate(price="10.00", was="20.00")] * (MIN_CARDS_FOR_POPULATION_CHECKS - 1)
    assert check_page_shape(few).ok


def test_a_healthy_page_passes() -> None:
    varied = [_candidate(price=str(5 + index), was=str(20 + index * 2)) for index in range(8)]
    assert check_page_shape(varied).ok


# ---------------------------------------------------------------------------
# The per-card rules
# ---------------------------------------------------------------------------


def test_the_discount_is_arithmetic_not_a_badge() -> None:
    assert _candidate(price="10.00", was="20.00").discount_percent == 50
    assert _candidate(price="9.99", was="19.99").discount_percent == 50
    # No `was` means no discount claim at all, rather than a zero.
    assert _candidate(was=None).discount_percent is None


def test_a_was_price_that_is_not_higher_is_the_same_node_read_twice() -> None:
    """The layout failure unique to a two-price card, and the most likely one.

    Both figures parse, both are plausible, both are in the right currency — and the
    discount is zero. Nothing except comparing them catches it.
    """
    verdict = check_deal_shape(_candidate(price="9.99", was="9.99"))
    assert not verdict.ok
    assert any("reading one node" in reason for reason in verdict.reasons)


def test_an_implausible_discount_is_refused() -> None:
    """A 98% discount is a `was` price belonging to a bundle, or a "from £1" placeholder
    read as the sale price — never a real disc."""
    verdict = check_deal_shape(_candidate(price="1.00", was="100.00"))
    assert not verdict.ok
    assert any("implausible" in reason for reason in verdict.reasons)
    assert _candidate(price="1.00", was="100.00").discount_percent >= MAX_DISCOUNT_PERCENT


def test_a_rounding_difference_is_not_an_offer() -> None:
    verdict = check_deal_shape(_candidate(price="19.99", was="20.00"))
    assert not verdict.ok
    assert any("rounding" in reason for reason in verdict.reasons)


def test_the_wrong_currency_is_refused() -> None:
    """The failure #92 found on Arrow: the US storefront returns USD, and without this
    every dollar price is filed as pounds."""
    verdict = check_deal_shape(
        DealCandidate(
            title="Jaws [Blu-ray]",
            price=Decimal("9.99"),
            was_price=Decimal("19.99"),
            currency="USD",
            url="https://www.arrowfilms.com/p/1",
            raw_price_text="$9.99",
        )
    )
    assert not verdict.ok
    assert any("USD" in reason for reason in verdict.reasons)


def test_merchandise_is_refused() -> None:
    """Zavvi's sale page sells a great deal that is not a disc. The same allowlist the
    wanted-item scrapers use, for the same reason: a beach towel has a title, a price and
    a zavvi.com URL."""
    # The URL matters as much as the title: Zavvi puts the category in the path, so a
    # towel is `/p/clothing/…` and a disc is `/p/blu-ray/…`. The allowlist reads both,
    # which is why this helper's default URL has to be changed as well as its title —
    # an earlier revision of this test left `/p/blu-ray/` in place and the towel passed.
    verdict = check_deal_shape(
        _candidate(title="Jaws Beach Towel", url="https://www.zavvi.com/p/clothing/jaws-towel/1/")
    )
    assert not verdict.ok
    assert any("merchandise" in reason for reason in verdict.reasons)

    # And the same title *is* accepted when the path says disc, because that is a real
    # listing shape rather than a mistake.
    assert check_deal_shape(_candidate(title="Jaws Beach Towel")).ok


def test_a_link_off_the_retailers_domain_is_refused() -> None:
    verdict = check_deal_shape(
        _candidate(url="https://ads.example.com/x"), retailer_host="https://www.zavvi.com"
    )
    assert not verdict.ok
    assert any("not" in reason and "zavvi" in reason for reason in verdict.reasons)


def test_a_healthy_card_passes() -> None:
    verdict = check_deal_shape(_candidate(), retailer_host="https://www.zavvi.com")
    assert verdict.ok, verdict.reasons


# ---------------------------------------------------------------------------
# What ships, and what has not been checked
# ---------------------------------------------------------------------------


def test_every_shipped_sale_page_is_marked_unverified() -> None:
    """**The selectors are Batch 19's, verified live; the sale-page URLs are not.**

    An unverified selector is a guess, and `builtins` already says so for search pages.
    The run that verifies these is the same owner-run that satisfies §5.9's acceptance —
    Batch 19 shipped on exactly this footing and its owner-run checkpoint found three real
    defects (#91, #92, #94), which is the argument for the arrangement rather than
    against it.
    """
    assert set(unverified_deals_names()) == {
        "Zavvi",
        "Arrow Video",
        "101 Films",
        "Second Sight",
        "Powerhouse Films",
    }


@pytest.mark.parametrize(
    "name", ["Zavvi", "Arrow Video", "101 Films", "Second Sight", "Powerhouse Films"]
)
def test_each_enabled_retailer_has_a_sale_page_and_a_was_selector(name: str) -> None:
    """§5.9 wants deals from **≥ 3 retailers**, and before this batch only one enabled
    shop had a `deals_url` at all — Zavvi. Four had none, so three was unreachable."""
    config = deals_config_for(name)
    assert config is not None
    assert str(config["url"]).startswith("https://")
    assert config["was"]


def test_no_ruled_out_shop_gained_a_sale_page() -> None:
    """Amazon, HMV, CEX and Blu-ray.com were ruled out permanently by `DECISIONS.md` #91.
    A deals config for one of them would quietly put it back in the rotation."""
    for name in ("Amazon UK", "HMV", "CEX", "Blu-ray.com"):
        assert deals_config_for(name) is None, name
