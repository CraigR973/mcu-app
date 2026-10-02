"""The deals feed — Batch 22, phases 5.9 and 5.10.

**§5.9's acceptance cannot be met here and is not pretended to be.** It requires a live
run against real retailer sale pages, which `docs/agent-commands/group-start.md` puts in
the owner's hands — the same footing as Batch 19's checkpoint and Batch 23's §3.7.

**Batch 22 shipped with no captured sale-page fixture, and that absence was the honest
option then.** Capturing one meant fetching a real retailer page, which is owner-gated.
Inventing one would have been worse: `DECISIONS.md` #122 is the standing account of what an
invented fixture costs — eleven tests passing for weeks against markup a site had never
served.

**Batch 22b has three, captured read-only on 28-30 Sep at Craig's word** with the scraper's
own fetcher: the first page of Zavvi's "2 for £30 4K" listing (`zavvi_2_for_30_4k.html`),
which is Zavvi's sale page now; Zavvi's flash-deals landing page it replaced
(`zavvi_flash_deals_film.html`); and the first page of Second Sight's sale collection
(`secondsight_sale_collection.html`). Each file's header says what was trimmed. They
reproduce the 13 Sep refusal with Batch 22's selectors and are read correctly with 22b's.

- :func:`extract_deals` is also tested against `zavvi_search_two_price_shapes.html`,
  verbatim captured markup from a Zavvi search page.
- The judgement rules are tested against `DealCandidate` values directly. A dataclass is
  not a fixture — there is no markup to be wrong about.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import pytest

from src.services.scraping.builtins import (
    BUILT_IN_SCRAPERS,
    applied_scraper_config,
    deals_config_for,
    unverified_deals_names,
)
from src.services.scraping.deals import (
    MAX_DISCOUNT_PERCENT,
    MIN_CARDS_FOR_POPULATION_CHECKS,
    REJECTED_REASON_EXAMPLES,
    DealCandidate,
    check_deal_shape,
    check_page_shape,
    extract_deals,
    judge_cards,
)
from src.services.scraping.deals_runner import narrowing_words, title_year

FIXTURES = Path(__file__).parent / "fixtures"
ZAVVI_HTML = (FIXTURES / "zavvi_search_two_price_shapes.html").read_text()
ZAVVI_DEALS_HTML = (FIXTURES / "zavvi_2_for_30_4k.html").read_text()
ZAVVI_FLASH_HTML = (FIXTURES / "zavvi_flash_deals_film.html").read_text()
SECOND_SIGHT_DEALS_HTML = (FIXTURES / "secondsight_sale_collection.html").read_text()

ZAVVI_DEALS_URL = "https://www.zavvi.com/c/offers/2-for-30-4k/"
ZAVVI_FLASH_URL = "https://www.zavvi.com/c/offers/flash-deals/film/"
SECOND_SIGHT_DEALS_URL = "https://secondsightfilms.co.uk/collections/sale"

#: The `was` selectors Batch 22 shipped, kept so the captured pages can show they fail.
BATCH_22_ZAVVI_WAS = "[data-testid='product-price'] .product-price__rrp, .rrp"
BATCH_22_SECOND_SIGHT_WAS = ".price-item--regular, s .money"


def _applied(name: str) -> dict[str, object]:
    """A retailer's `scraper_config` exactly as `apply-built-ins` writes it.

    *Until Batch 22b the helper here merged the whole sale-page entry*, whose `url` is the
    page's address, over the card's `url` selector. An address matches no element, so
    every test ran the anchor fallback, and `DECISIONS.md` #153 concluded that Zavvi's
    title is a heading. It is a link; production never merged that key.
    """
    config = applied_scraper_config(name)
    assert config is not None, name
    return config


def _zavvi_config() -> dict[str, object]:
    return _applied("Zavvi")


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
    """A deal's link is the whole point of its card, and `deals` is unique on
    `(retailer_id, url)`, so every card needs its own absolute URL.

    *Corrected in Batch 22b:* this once said Zavvi's `product-title` is a heading. It is a
    link; the helper had overwritten the `url` selector with the sale page's address.
    """
    cards = extract_deals(ZAVVI_HTML, _zavvi_config(), page_url="https://www.zavvi.com/sale.list")

    assert cards[0].url == "https://www.zavvi.com/p/blu-ray/cross-of-iron/10369739/"
    assert all(card.url and card.url.startswith("https://www.zavvi.com/p/") for card in cards)
    # Distinct, which is what the uniqueness key depends on.
    assert len({card.url for card in cards}) == len(cards)


def test_a_title_that_is_not_a_link_falls_back_to_the_cards_anchor() -> None:
    """The fallback #153 added, on markup where it is needed: a heading for a title, and
    the link on the card's image. Without it the deal has no URL, and every such deal from
    one shop would collide on `''` under the uniqueness key."""
    html = (
        '<div class="card"><a href="/p/blu-ray/jaws/1/"><img src="/i.jpg"></a>'
        '<h3 class="t">Jaws [Blu-ray]</h3><span class="p">£9.99</span></div>'
    )
    config = {"item": ".card", "title": ".t", "price": ".p", "url": ".t"}

    (card,) = extract_deals(html, config, page_url="https://shop.example/sale")

    assert card.url == "https://shop.example/p/blu-ray/jaws/1/"


def test_a_page_with_no_card_selector_yields_nothing_rather_than_guessing() -> None:
    """Without `item`, every selector runs over the whole page independently and the
    title comes from one product while the price comes from another. On a deals page
    there is no expected title to catch that, so it would be silent."""
    assert extract_deals(ZAVVI_HTML, {"title": "h3", "price": ".price"}, page_url="https://x") == []


# ---------------------------------------------------------------------------
# Batch 22b — the sale pages as captured on 28-30 Sep
# ---------------------------------------------------------------------------


def test_zavvis_sale_page_is_its_2_for_30_4k_listing() -> None:
    """Craig's pick, 30 Sep: the larger of the two listings the flash-deals carousels lead
    to. The flash-deals page itself had become six discs, five of them already owned."""
    deals = deals_config_for("Zavvi")
    assert deals is not None
    assert deals["url"] == ZAVVI_DEALS_URL


def test_zavvis_listing_is_read_with_each_discs_price_and_rrp() -> None:
    """Twelve discs as served, eleven with a Current price / RRP pair and one (Harvey) at a
    single price. The cards are THG's own product card, so Batch 19's card selectors read
    them unchanged; the RRP is the span tagged `data-product-price="rrp"`."""
    cards = extract_deals(ZAVVI_DEALS_HTML, _applied("Zavvi"), page_url=ZAVVI_DEALS_URL)

    assert [(card.price, card.was_price) for card in cards] == [
        (Decimal(price), Decimal(was) if was else None)
        for price, was in (
            ("22.99", "29.99"),
            ("17.99", "34.99"),
            ("17.99", "33.99"),
            ("22.99", "39.99"),
            ("22.99", "34.99"),
            ("19.99", "29.99"),
            ("22.99", None),
            ("19.99", "29.99"),
            ("19.99", "26.99"),
            ("21.99", "26.99"),
            ("19.99", "26.99"),
            ("19.99", "29.99"),
        )
    ]
    assert cards[0].title == "Jurassic World - Ultra HD 4K"
    assert cards[6].title == "Harvey 4K Ultra HD"
    assert all(card.currency == "GBP" for card in cards)
    assert all(card.url and card.url.startswith("https://www.zavvi.com/p/4k/") for card in cards)
    assert len({card.url for card in cards}) == len(cards)
    assert all(
        card.image_url and card.image_url.startswith("https://www.zavvi.com/images?url=")
        for card in cards
    )


def test_zavvis_listing_passes_the_page_check_and_its_single_price_disc_is_no_deal() -> None:
    cards = extract_deals(ZAVVI_DEALS_HTML, _applied("Zavvi"), page_url=ZAVVI_DEALS_URL)

    assert check_page_shape(cards).ok
    judged = judge_cards(cards, retailer_host="www.zavvi.com")
    assert (len(judged.deals), judged.not_discounted, judged.rejected) == (11, 1, 0)
    assert "Harvey 4K Ultra HD" not in {card.title for card in judged.deals}


def test_zavvis_flash_deals_carousels_read_the_same_way() -> None:
    """The page Zavvi's check read until Craig's pick. Its carousel cards are the same THG
    card, so the same selectors read all six pairs: if that page is ever pasted back on
    /retailers, it works."""
    cards = extract_deals(ZAVVI_FLASH_HTML, _applied("Zavvi"), page_url=ZAVVI_FLASH_URL)

    assert [(card.title, card.price, card.was_price, card.discount_percent) for card in cards] == [
        ("Jurassic World - Ultra HD 4K", Decimal("22.99"), Decimal("29.99"), 23),
        ("Ambulance - 4K Ultra HD", Decimal("17.99"), Decimal("34.99"), 49),
        ("Spectre - 4K Ultra HD (Includes 2D Blu-ray)", Decimal("17.99"), Decimal("33.99"), 47),
        ("Life of Pi - 4K Ultra HD", Decimal("19.99"), Decimal("29.99"), 33),
        ("Fantastic Beasts and Where To Find Them", Decimal("9.99"), Decimal("26.99"), 63),
        ("The Deer Hunter - 40th Anniversary Edition", Decimal("9.99"), Decimal("22.99"), 57),
    ]
    assert check_page_shape(cards).ok
    judged = judge_cards(cards, retailer_host="www.zavvi.com")
    assert (len(judged.deals), judged.not_discounted, judged.rejected) == (6, 0, 0)


def test_second_sights_sale_page_is_read_with_its_one_real_pair() -> None:
    """Sixteen cards and one discount: Dog Soldiers 4K, £24.99 → £17.99, the pair the owner
    saw on 13 Sep. The other fifteen have an empty compare-at price, so no `was` at all,
    where Batch 22's selector read each card's own price a second time."""
    cards = extract_deals(
        SECOND_SIGHT_DEALS_HTML, _applied("Second Sight"), page_url=SECOND_SIGHT_DEALS_URL
    )

    assert len(cards) == 16
    assert all(card.price is not None and card.currency == "GBP" for card in cards)
    discounted = [card for card in cards if card.was_price is not None]
    assert [(c.title, c.price, c.was_price, c.discount_percent) for c in discounted] == [
        ("Dog Soldiers Standard Edition 4K UHD", Decimal("17.99"), Decimal("24.99"), 28),
    ]
    assert discounted[0].url == (
        "https://secondsightfilms.co.uk/products/"
        "dog-soldiers-standard-edition-4k-uhd-pre-order-available-july-26th"
    )
    assert (discounted[0].image_url or "").startswith("https://secondsightfilms.co.uk/cdn/shop/")


def test_second_sights_page_passes_and_only_its_discounted_disc_is_a_deal() -> None:
    """The page check passes (varied prices, one discount among sixteen), and the fifteen
    cards at a single price are counted as not discounted rather than kept or rejected.

    The host is passed as the runner passed it until 22b, the whole base URL: that failed
    every one of this shop's own listings, and now matches them.
    """
    cards = extract_deals(
        SECOND_SIGHT_DEALS_HTML, _applied("Second Sight"), page_url=SECOND_SIGHT_DEALS_URL
    )

    assert check_page_shape(cards).ok
    for host in ("https://secondsightfilms.co.uk", "secondsightfilms.co.uk"):
        judged = judge_cards(cards, retailer_host=host)
        assert [card.title for card in judged.deals] == ["Dog Soldiers Standard Edition 4K UHD"]
        assert (judged.not_discounted, judged.rejected) == (15, 0)


@pytest.mark.parametrize(
    "name", ["Zavvi", "Arrow Video", "101 Films", "Second Sight", "Powerhouse Films"]
)
def test_a_shops_own_listing_is_on_its_own_site_however_its_address_is_given(
    name: str,
) -> None:
    """Batch 22's deals runner passed the retailer's whole base URL as the host. For a shop
    with no `www.` (Second Sight, 101 Films) that failed every one of its own listings."""
    base = str(BUILT_IN_SCRAPERS[name]["base"])
    own = _candidate(url=f"{base}/products/jaws-blu-ray")

    for host in (base, urlparse(base).hostname):
        assert check_deal_shape(own, retailer_host=host).ok, (name, host)


def test_a_listing_on_another_co_uk_site_is_still_refused_given_a_url() -> None:
    verdict = check_deal_shape(
        _candidate(url="https://someoneelse.co.uk/products/jaws-blu-ray"),
        retailer_host="https://secondsightfilms.co.uk",
    )
    assert not verdict.ok
    assert any("someoneelse.co.uk" in reason for reason in verdict.reasons)


@pytest.mark.parametrize(
    ("title", "words"),
    [
        # Titles on the captured pages whose longest word is the shop's own.
        ("Spectre - 4K Ultra HD (Includes 2D Blu-ray)", ["spectre"]),
        ("The Deer Hunter - 40th Anniversary Edition", ["hunter", "40th", "deer"]),
        ("Life of Pi - 4K Ultra HD", ["life"]),
        ("Dog Soldiers Standard Edition 4K UHD", ["soldiers", "dog"]),
        # A shop's word no list names ("download"): tried, then passed over for "mummy".
        (
            "The Mummy (2017) - 4K Ultra HD (Includes Digital Download)",
            ["download", "digital", "mummy"],
        ),
        # And one that was already right.
        ("Jurassic World - Ultra HD 4K", ["jurassic", "world"]),
    ],
)
def test_the_film_search_tries_every_word_a_title_could_hold(title: str, words: list[str]) -> None:
    """Batch 22 narrowed on the longest word alone, which for these was *includes*,
    *anniversary*, *ultra*, *standard* or *download*: no film matched, so an owned copy was
    not skipped and the deal had no poster."""
    assert narrowing_words(title) == words


@pytest.mark.parametrize(
    ("title", "year"),
    [
        ("The Mummy (2017) - 4K Ultra HD (Includes Digital Download)", 2017),
        ("Bad Lieutenant (1992) (4K-UHD)", 1992),
        ("Heat [1995] [Blu-ray]", 1995),
        # A bare number is often the title itself, so only a bracketed year counts.
        ("2001: A Space Odyssey", None),
        ("Blade Runner 2049 - 4K Ultra HD", None),
        ("1917 (2019)", 2019),
        # Two different years say nothing about which film.
        ("Double Feature (1999) (2001)", None),
    ],
)
def test_a_year_in_brackets_tells_a_remake_from_its_original(title: str, year: int | None) -> None:
    """Zavvi's "The Mummy (2017)" matched the 1999 film by its words alone (Batch 22b)."""
    assert title_year(title) == year


def test_a_card_at_a_single_price_is_not_discounted_not_rejected() -> None:
    judged = judge_cards([_candidate(was=None)])
    assert (judged.deals, judged.not_discounted, judged.rejected) == ([], 1, 0)


def test_a_card_with_no_price_at_all_is_still_rejected() -> None:
    """A broken read, not a listing at its normal price."""
    judged = judge_cards([_candidate(price=None, was=None)])
    assert (judged.not_discounted, judged.rejected) == (0, 1)
    assert "no sale price" in judged.rejected_reasons[0]


def test_a_was_no_higher_than_the_price_is_still_rejected() -> None:
    """The same node read twice stays a rejection; only an absent `was` is undiscounted."""
    judged = judge_cards([_candidate(price="9.99", was="9.99")])
    assert (judged.not_discounted, judged.rejected) == (0, 1)
    assert "reading one node" in judged.rejected_reasons[0]


def test_a_rejected_cards_reason_is_reported_and_capped() -> None:
    towels = [
        _candidate(title=f"Beach Towel {index}", url=f"https://www.zavvi.com/p/clothing/{index}/")
        for index in range(REJECTED_REASON_EXAMPLES + 2)
    ]
    judged = judge_cards(towels)

    assert judged.rejected == REJECTED_REASON_EXAMPLES + 2
    assert len(judged.rejected_reasons) == REJECTED_REASON_EXAMPLES
    assert all("merchandise" in reason for reason in judged.rejected_reasons)


# ---------------------------------------------------------------------------
# The page-level assertion — Batch 22's extension of #79
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "old_config", "page_url"),
    [
        # Batch 22's Zavvi `was` selector matched nothing on THG's card, on either page.
        (
            "zavvi_2_for_30_4k.html",
            {**BUILT_IN_SCRAPERS["Zavvi"]["config"], "was": BATCH_22_ZAVVI_WAS},
            ZAVVI_DEALS_URL,
        ),
        (
            "zavvi_flash_deals_film.html",
            {**BUILT_IN_SCRAPERS["Zavvi"]["config"], "was": BATCH_22_ZAVVI_WAS},
            ZAVVI_FLASH_URL,
        ),
        # Batch 22's Second Sight `was` selector read the card's own price a second time.
        (
            "secondsight_sale_collection.html",
            {**BUILT_IN_SCRAPERS["Second Sight"]["config"], "was": BATCH_22_SECOND_SIGHT_WAS},
            SECOND_SIGHT_DEALS_URL,
        ),
    ],
)
def test_a_page_where_no_card_has_a_was_price_is_refused(
    fixture: str, old_config: dict[str, object], page_url: str
) -> None:
    """Fired by **real markup**: the 13 Sep refusal, reproduced on the pages captured on
    28-30 Sep with the selectors Batch 22 shipped.

    On a sale page that is the shape of the sale-price selector having moved, which turns
    a sale page into a price list and makes every discount null. Every individual card
    still looks entirely reasonable. *Until Batch 22b this was fired by the Zavvi search
    fixture, on the belief that its cards carried no struck-through price; its first card
    carries an RRP, which the old selector could not see.*
    """
    cards = extract_deals((FIXTURES / fixture).read_text(), old_config, page_url=page_url)
    assert len(cards) >= MIN_CARDS_FOR_POPULATION_CHECKS
    verdict = check_page_shape(cards)

    assert not verdict.ok
    assert any("no card on the page has a 'was' price" in reason for reason in verdict.reasons)


def test_the_search_fixtures_rrp_is_read_now() -> None:
    """The Zavvi search cards captured on 10 Sep: the first carries a Current price / RRP
    pair, the second a single price. Batch 22's selector missed the first card's RRP."""
    cards = extract_deals(ZAVVI_HTML, _zavvi_config(), page_url="https://www.zavvi.com/sale.list")

    assert [(card.price, card.was_price) for card in cards] == [
        (Decimal("12.99"), Decimal("19.99")),
        (Decimal("16.99"), None),
    ]


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


def test_only_the_sale_pages_checked_against_live_markup_are_verified() -> None:
    """**A sale page is verified once someone has read it, and not before.**

    Batch 22 shipped all five unverified: the run that checks them was the owner's, and
    it found defects, as Batch 19's checkpoint had (#91, #92, #94). Batch 22b fixed Zavvi
    and Second Sight against pages captured on 28-30 Sep, and the tests above read those
    captures. The other three are as Batch 22 left them.
    """
    assert set(unverified_deals_names()) == {"Arrow Video", "101 Films", "Powerhouse Films"}


def test_arrow_powerhouse_and_101_films_sale_pages_are_as_batch_22_left_them() -> None:
    """Craig's choice (28 Sep): Arrow and Powerhouse sell bundles ("2 for £40", "3 for 20%
    off"), which a feed of one disc's was/now price cannot hold, and 101 Films' page was
    right but had nothing on sale. Pinned, so a change to them is a decision, not a drift."""
    assert deals_config_for("Arrow Video") == {
        "url": "https://www.arrowfilms.com/collections/sale",
        "was": "[data-testid='product-price'] .product-price__rrp, s .money, .price-item--regular",
        "image": "img",
        "verified": False,
    }
    assert deals_config_for("Powerhouse Films") == {
        "url": "https://www.powerhousefilms.co.uk/collections/sale",
        "was": ".product-price__compare, s .money",
        "image": "img",
        "verified": False,
    }
    assert deals_config_for("101 Films") == {
        "url": "https://101-films-store.com/collections/sale",
        "was": "s .money, .price--compare, .compare-at",
        "image": "img",
        "verified": False,
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


def test_applying_the_built_ins_would_give_every_enabled_shop_a_sale_page() -> None:
    """The wiring `apply-built-ins` needs, asserted as a property rather than a run.

    Without it, four of the five enabled shops keep the `deals_url: NULL` they were
    seeded with in Batch 18 and §5.9's *"≥ 3 retailers"* is unreachable however well the
    scraper behaves — which was nearly shipped: `deals_config_for` existed and nothing
    called it.

    The `was` and `image` selectors merge into the same `scraper_config` the wanted-item
    scrapers use, because a sale card and a search card are the same markup.
    """
    enabled = ("Zavvi", "Arrow Video", "101 Films", "Second Sight", "Powerhouse Films")
    for name in enabled:
        entry = BUILT_IN_SCRAPERS[name]
        deals = deals_config_for(name)
        assert deals is not None, name

        merged = _applied(name)

        # Everything the deals extractor reads has to survive the merge.
        for key in ("item", "title", "price", "url", "was"):
            assert merged.get(key), f"{name} is missing {key}"
        # The card's selectors are the search page's own, untouched: the page's address
        # never lands on the `url` selector, and the wanted-item scraper reads what it did.
        assert {key: merged[key] for key in entry["config"]} == entry["config"], name
        assert merged["was"] == deals["was"], name


# ---------------------------------------------------------------------------
# Batch 20b, second half: a refused sale page waits for the shop, then is asked once more
# ---------------------------------------------------------------------------


class _SalePageAnswers:
    """Stands in for `fetch_page`, answering each request with the next of its replies."""

    def __init__(self, *replies: object) -> None:
        self.replies = list(replies)
        self.asked = 0

    async def __call__(self, url: str) -> object:
        del url
        self.asked += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _sale_page_clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    from src.services.scraping import deals_runner

    waits: list[float] = []

    async def pause(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(deals_runner, "_pause", pause)
    return waits


def _sale_refusal(retry_after: str | None = "60") -> Exception:
    from src.services.scraping.fetcher import RefusedError

    evidence = f"retry-after {retry_after}" if retry_after else ""
    return RefusedError(429, retry_after=retry_after, evidence=evidence)


async def test_a_refused_sale_page_waits_for_the_shop_then_gets_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services.scraping import deals_runner
    from src.services.scraping.fetcher import FetchedPage

    page = FetchedPage(url="u", status=200, html="<html></html>", final_url="u")
    answers = _SalePageAnswers(_sale_refusal("60"), page)
    monkeypatch.setattr(deals_runner, "fetch_page", answers)
    waits = _sale_page_clock(monkeypatch)

    assert await deals_runner._fetch_sale_page("Second Sight", "u") is page
    assert answers.asked == 2
    assert waits == [60.0]


async def test_a_sale_page_refused_again_says_how_long_it_waited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services.scraping import deals_runner
    from src.services.scraping.fetcher import RefusedError

    answers = _SalePageAnswers(_sale_refusal("60"), _sale_refusal("60"))
    monkeypatch.setattr(deals_runner, "fetch_page", answers)
    waits = _sale_page_clock(monkeypatch)

    with pytest.raises(RefusedError) as raised:
        await deals_runner._fetch_sale_page("Second Sight", "u")

    assert waits == [60.0]
    assert answers.asked == 2, "one retry, as the price check"
    assert str(raised.value) == (
        "The page answered 429 (retry-after 60; refused again, waited 60 s, as asked)"
    )


async def test_a_sale_page_asking_for_too_long_gets_the_usual_pause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services.scraping import deals_runner
    from src.services.scraping.fetcher import FetchedPage

    page = FetchedPage(url="u", status=200, html="<html></html>", final_url="u")
    monkeypatch.setattr(deals_runner, "fetch_page", _SalePageAnswers(_sale_refusal("600"), page))
    waits = _sale_page_clock(monkeypatch)

    await deals_runner._fetch_sale_page("Zavvi", "u")

    assert waits == [deals_runner.RETRY_PAUSE_SECONDS]


async def test_a_sale_page_that_fails_another_way_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As before 20b: only a refusal is asked again."""
    from src.services.scraping import deals_runner
    from src.services.scraping.fetcher import FetchError

    answers = _SalePageAnswers(FetchError("The page answered 503"))
    monkeypatch.setattr(deals_runner, "fetch_page", answers)
    waits = _sale_page_clock(monkeypatch)

    with pytest.raises(FetchError):
        await deals_runner._fetch_sale_page("Zavvi", "u")

    assert answers.asked == 1
    assert waits == []
