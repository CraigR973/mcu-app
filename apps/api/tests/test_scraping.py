"""Batch 19's scraper framework — roadmap §5.3 and §5.4.

**Nothing in this file makes a live request, and that is not a shortcut.** §5.3's
acceptance is that "each built-in scraper runs against the **live** retailer", which
`group-start.md` names as a hard stop: *"a batch whose acceptance requires live
third-party requests ... stops before those runs. The owner performs them. Fixture-backed
tests may run unattended; live ones may not."*

So what is tested here is everything that can be: the SSRF guard, the extraction, and —
most of all — the **shape assertion**, which is the thing this batch exists for. The
ledger's risk note is that a wrong selector *"does not error — it selects the wrong node and
persists a plausible wrong number, which then feeds price-drop alerts and aggregates"*. A
success/fail counter cannot see that. Each check below is one way it has actually looked.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from src.models.wanted import Retailer
from src.services.scraping.builtins import BUILT_IN_SCRAPERS, unverified_names
from src.services.scraping.extract import (
    MAX_PLAUSIBLE,
    ScrapeCandidate,
    check_shape,
    edition_matches,
    extract,
    looks_like_physical_media,
    parse_price,
    primary_format,
    select_one_text,
    split_selectors,
)
from src.services.scraping.fetcher import UnsafeUrlError, assert_fetchable, fetch_page
from src.services.scraping.runner import (
    ScrapeOutcome,
    ScrapeRunResult,
    _record_failure,
    _record_success,
    apply_search_template,
    scrape_one,
    search_url_for,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Price parsing
# ---------------------------------------------------------------------------


def test_a_price_is_read_with_its_currency() -> None:
    assert parse_price("£12.99") == (Decimal("12.99"), "GBP")
    assert parse_price("  £1,299.00  ") == (Decimal("1299.00"), "GBP")
    assert parse_price("Price: $24.99") == (Decimal("24.99"), "USD")
    assert parse_price("19.99 GBP") == (Decimal("19.99"), "GBP")


def test_a_bare_number_has_no_currency_and_that_is_the_signal() -> None:
    """A `.price` node yielding "12" is usually a rating, a quantity or a running time.

    The number parses; the absence of a currency marker is what says it is not a price.
    """
    amount, currency = parse_price("12")
    assert amount == Decimal("12")
    assert currency is None


def test_nothing_numeric_yields_nothing() -> None:
    assert parse_price("Out of stock") == (None, None)
    assert parse_price("") == (None, None)
    assert parse_price(None) == (None, None)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

SHOP_PAGE = """
<html><body>
  <div class="result">
    <h3><a class="title" href="https://store.hmv.com/product/heat-4k">Heat [4K UHD]</a></h3>
    <span class="price">£19.99</span>
    <span class="save">Save £5.00</span>
  </div>
</body></html>
"""


def test_selectors_pull_title_price_and_link() -> None:
    candidate = extract(SHOP_PAGE, {"title": "a.title", "price": ".price", "url": "a.title"})
    assert candidate.title == "Heat [4K UHD]"
    assert candidate.price == Decimal("19.99")
    assert candidate.currency == "GBP"
    assert candidate.url == "https://store.hmv.com/product/heat-4k"


def test_a_selector_matching_the_wrong_node_returns_the_wrong_node() -> None:
    """The failure this whole batch is about, demonstrated.

    `.save` is a perfectly valid selector that yields a perfectly valid price. Extraction
    cannot tell — only `check_shape` can, and only because it is told what film was asked
    for. Nothing about `£5.00` on its own is suspicious.
    """
    candidate = extract(SHOP_PAGE, {"title": "a.title", "price": ".save"})
    assert candidate.price == Decimal("5.00"), "extraction is not where this is caught"


def test_a_missing_or_invalid_selector_does_not_raise() -> None:
    """Selectors are admin input. A typo is a bad result, not a 500."""
    assert extract(SHOP_PAGE, {"price": ".does-not-exist"}).price is None
    assert extract(SHOP_PAGE, {"price": "]]not a selector[["}).price is None
    assert extract(SHOP_PAGE, {}).price is None


# ---------------------------------------------------------------------------
# The shape assertion — the point of the batch
# ---------------------------------------------------------------------------


def _candidate(**kwargs: object) -> ScrapeCandidate:
    base: dict[str, object] = {
        "title": "Heat [4K UHD]",
        "price": Decimal("19.99"),
        "currency": "GBP",
        "url": "https://store.hmv.com/product/heat",
        "raw_price_text": "£19.99",
    }
    base.update(kwargs)
    return ScrapeCandidate(**base)  # type: ignore[arg-type]


def test_a_good_result_passes() -> None:
    verdict = check_shape(_candidate(), expected_title="Heat", retailer_host="store.hmv.com")
    assert verdict.ok, verdict.reasons


def test_no_price_is_reported_as_a_reason_not_a_silent_skip() -> None:
    verdict = check_shape(_candidate(price=None, raw_price_text=None))
    assert not verdict.ok
    assert "no price found" in verdict.reasons[0]


def test_a_number_with_no_currency_marker_is_refused() -> None:
    """The strongest single signal that a number is not a price."""
    verdict = check_shape(_candidate(currency=None, raw_price_text="12"))
    assert not verdict.ok
    assert any("no currency marker" in reason for reason in verdict.reasons)


def test_the_wrong_currency_is_refused_rather_than_converted() -> None:
    """A shop switching to a US storefront would otherwise report dollars as pounds, and
    every price alert would fire at once. Converting would be inventing data."""
    verdict = check_shape(_candidate(currency="USD", raw_price_text="$19.99"))
    assert not verdict.ok
    assert any("USD" in reason for reason in verdict.reasons)


def test_an_implausible_price_is_refused_at_both_ends() -> None:
    """Under 50p is a postage line or a "£0.00" placeholder; over £500 is a television,
    a bundle, or two numbers run together."""
    low = check_shape(_candidate(price=Decimal("0.01"), raw_price_text="£0.01"))
    high = check_shape(_candidate(price=MAX_PLAUSIBLE + 1, raw_price_text="£501.00"))
    assert not low.ok and not high.ok


def test_a_page_about_a_different_film_is_refused() -> None:
    """The **quiet** failure: the selectors work perfectly, on the wrong page.

    Nothing about the extracted values looks wrong — a real title, a real price, a real
    link. Only the comparison with what was asked for catches it.
    """
    verdict = check_shape(
        _candidate(title="Frozen II [Blu-ray]"),
        expected_title="North by Northwest",
    )
    assert not verdict.ok
    assert any("nothing in common" in reason for reason in verdict.reasons)


def test_a_title_that_differs_only_by_edition_still_passes() -> None:
    """Retailers append "[Blu-ray]", "(4K UHD)", edition names and years. The check has to
    be generous enough to survive that, or every real result is rejected."""
    for title in (
        "Heat [4K UHD Blu-ray]",
        "Heat (1995) - Limited Edition Steelbook",
        "HEAT 4K",
    ):
        verdict = check_shape(_candidate(title=title), expected_title="Heat")
        assert verdict.ok, (title, verdict.reasons)


def test_a_listing_on_another_domain_is_refused() -> None:
    """An advert, or a "customers also bought" block."""
    verdict = check_shape(
        _candidate(url="https://ads.example.com/x"), retailer_host="store.hmv.com"
    )
    assert not verdict.ok
    assert any("ads.example.com" in reason for reason in verdict.reasons)


def test_a_subdomain_of_the_same_shop_is_fine() -> None:
    verdict = check_shape(
        _candidate(url="https://www.hmv.com/product/heat"), retailer_host="store.hmv.com"
    )
    assert verdict.ok, verdict.reasons


def test_a_listing_on_an_unrelated_co_uk_domain_is_refused() -> None:
    """Two `.co.uk` shops are not one shop.

    The guard compares registrable domains, so it must not read `co.uk` as the domain and
    wave through every host on the TLD. Batch 19 had no `.co.uk` retailer whose selectors
    ran, so this was latent; the supported UK labels are the first that arm it.
    """
    verdict = check_shape(
        _candidate(url="https://someoneelse.co.uk/product/heat"),
        retailer_host="secondsightfilms.co.uk",
    )
    assert not verdict.ok
    assert any("someoneelse.co.uk" in reason for reason in verdict.reasons)


def test_a_subdomain_of_the_same_co_uk_shop_is_still_fine() -> None:
    verdict = check_shape(
        _candidate(url="https://shop.powerhousefilms.co.uk/product/heat"),
        retailer_host="www.powerhousefilms.co.uk",
    )
    assert verdict.ok, verdict.reasons


def test_every_reason_is_collected_not_just_the_first() -> None:
    """A scraper that has gone wrong is usually wrong in several ways at once, and the
    person reading the report needs all of them."""
    verdict = check_shape(
        _candidate(price=Decimal("9999"), currency=None, title="Something Else"),
        expected_title="Heat",
        retailer_host="store.hmv.com",
    )
    assert not verdict.ok
    assert len(verdict.reasons) >= 3


# ---------------------------------------------------------------------------
# The SSRF guard
# ---------------------------------------------------------------------------


async def test_a_loopback_or_private_url_is_refused() -> None:
    """The realistic failure is a paste, not malice — but the server can reach things the
    admin's browser cannot, including whatever is bound inside the container."""
    for hostile in (
        "http://127.0.0.1:8000/api/v1/auth/me",
        "http://localhost:8000/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
    ):
        with pytest.raises(UnsafeUrlError):
            await assert_fetchable(hostile)


async def test_a_non_http_scheme_is_refused() -> None:
    for hostile in ("file:///etc/passwd", "gopher://x/", "ftp://example.com/"):
        with pytest.raises(UnsafeUrlError):
            await assert_fetchable(hostile)


async def test_a_public_url_is_allowed() -> None:
    # A literal public address, so this needs no DNS and cannot flake on a resolver.
    await assert_fetchable("https://93.184.216.34/")


async def test_a_redirect_into_a_private_address_is_refused() -> None:
    """httpx would follow a 302 anywhere. Redirects are followed by hand precisely so
    every hop is re-checked — otherwise a safe-looking URL becomes an unsafe request."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "93.184.216.34":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:8000/secret"})
        return httpx.Response(200, text="<html></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        with pytest.raises(UnsafeUrlError):
            await fetch_page("https://93.184.216.34/start", client=client)


async def test_a_page_is_returned_when_everything_is_fine() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, text=SHOP_PAGE)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        page = await fetch_page("https://93.184.216.34/search", client=client)
    assert "Heat [4K UHD]" in page.html


# ---------------------------------------------------------------------------
# The built-in configurations
# ---------------------------------------------------------------------------


def test_supported_replacements_are_built_in_and_only_live_checked_ones_are_verified() -> None:
    """Verification records actual live acceptance, not merely a retailer's presence."""
    assert set(BUILT_IN_SCRAPERS) == {
        "HMV",
        "Amazon UK",
        "Blu-ray.com",
        "Zavvi",
        "Arrow Video",
        "CEX",
        "101 Films",
        "Second Sight",
        "Powerhouse Films",
    }
    assert {name for name, entry in BUILT_IN_SCRAPERS.items() if entry["verified"]} == {
        "Arrow Video",
        "Zavvi",
        "101 Films",
        "Second Sight",
        "Powerhouse Films",
    }
    assert set(unverified_names()) == {"HMV", "Amazon UK", "Blu-ray.com", "CEX"}


def test_every_built_in_has_a_search_template_with_a_query_placeholder() -> None:
    for name, entry in BUILT_IN_SCRAPERS.items():
        assert "{query}" in entry["search"], name
        assert str(entry["search"]).startswith("https://"), name
        assert entry["config"].get("price"), name


def test_every_verified_built_in_reads_product_cards_rather_than_the_whole_page() -> None:
    """Without an ``item`` selector each field is selected independently across the page,
    so a title can be paired with another product's price. Every built-in anyone actually
    runs must name its card."""
    for name, entry in BUILT_IN_SCRAPERS.items():
        if entry["verified"]:
            assert entry["config"].get("item"), name


def test_zavvi_built_in_matches_its_current_search_result_markup() -> None:
    """The live site moved from ``/search/{query}.list`` and renamed every product class.

    Keep a representative result here so the repaired built-in cannot quietly drift back
    to selectors that match nothing.
    """
    html = """
    <div class="product-card" data-testid="product-item">
      <a href="/p/blu-ray/heat-and-dust/12044695/"
         data-testid="product-title">Heat and Dust</a>
      <div data-testid="product-price">
        <span class="product-variant-price" content="£20.99">£20.99</span>
      </div>
    </div>
    """
    entry = BUILT_IN_SCRAPERS["Zavvi"]
    candidate = extract(html, entry["config"])

    assert entry["search"] == "https://www.zavvi.com/search?q={query}%20{format}"
    assert candidate.title == "Heat and Dust"
    assert candidate.price == Decimal("20.99")
    assert candidate.currency == "GBP"
    assert candidate.url == "/p/blu-ray/heat-and-dust/12044695/"


def test_arrow_built_in_uses_the_uk_storefront_and_current_markup() -> None:
    html = """
    <div class="product-card" data-testid="product-item">
      <a href="/p/night-of-the-big-heat-blu-ray/10945421/"
         data-testid="product-title">Night Of The Big Heat Blu-ray</a>
      <div data-testid="product-price">
        <span class="product-variant-price" content="£10.00">£10.00</span>
      </div>
    </div>
    """
    entry = BUILT_IN_SCRAPERS["Arrow Video"]
    candidate = extract(html, entry["config"])

    assert entry["base"] == "https://www.arrowfilms.com"
    assert entry["search"] == "https://www.arrowfilms.com/search?q={query}%20{format}"
    assert candidate.title == "Night Of The Big Heat Blu-ray"
    assert candidate.price == Decimal("10.00")
    assert candidate.currency == "GBP"
    assert candidate.url == "/p/night-of-the-big-heat-blu-ray/10945421/"


@pytest.mark.parametrize(
    ("name", "html", "expected_title", "expected_price", "expected_url"),
    [
        (
            "101 Films",
            '<div class="product-info-inner"><a href="/products/bad-lieutenant">'
            '<span class="prod-title">Bad Lieutenant (1992) (4K-UHD)</span></a>'
            '<div class="price"><span class="money">£22.00</span></div></div>',
            "Bad Lieutenant (1992) (4K-UHD)",
            Decimal("22.00"),
            "/products/bad-lieutenant",
        ),
        (
            "Second Sight",
            '<h3 class="card__heading"><a href="/products/name-of-the-rose">'
            "The Name of the Rose 4K UHD</a></h3>"
            '<span class="price-item--regular">£24.99 GBP</span>',
            "The Name of the Rose 4K UHD",
            Decimal("24.99"),
            "/products/name-of-the-rose",
        ),
        (
            "Powerhouse Films",
            '<a class="list-view-item" href="/products/the-last-detail-bd">'
            '<div class="list-view-item__title">THE LAST DETAIL - BD</div>'
            '<span class="product-price__price">£9.99</span></a>',
            "THE LAST DETAIL - BD",
            Decimal("9.99"),
            "/products/the-last-detail-bd",
        ),
    ],
)
def test_supported_replacement_markup(
    name: str,
    html: str,
    expected_title: str,
    expected_price: Decimal,
    expected_url: str,
) -> None:
    candidate = extract(html, BUILT_IN_SCRAPERS[name]["config"])

    assert candidate.title == expected_title
    assert candidate.price == expected_price
    assert candidate.currency == "GBP"
    assert candidate.url == expected_url


# ---------------------------------------------------------------------------
# Merchandise, and the film the shop does not actually stock
# ---------------------------------------------------------------------------


def _zavvi_card(href: str, title: str, price: str) -> str:
    return f"""
    <div class="product-card" data-testid="product-item">
      <a href="{href}" data-testid="product-title">{title}</a>
      <div data-testid="product-price">
        <span class="product-variant-price">{price}</span>
      </div>
    </div>
    """


#: What Zavvi really returned for "Jaws" on 2026-09-09, in order. Nine more T-shirts and a
#: resin statue followed; three are enough to make the point.
JAWS_MERCH_PAGE = "".join(
    [
        _zavvi_card(
            "/p/home-accessories/jaws-amity-welcome-sign-beach-towel/17376588/",
            "Jaws Amity Welcome Sign Beach Towel",
            "£17.99",
        ),
        _zavvi_card(
            "/p/clothing/jaws-classic-poster-t-shirt-white/11716106/",
            "Jaws Classic Poster T-Shirt - White",
            "£16.99",
        ),
        _zavvi_card(
            "/p/4k/jaws-4k-ultra-hd-includes-2d-blu-ray/12541038/",
            "Jaws - 4K Ultra HD (Includes 2D Blu-ray)",
            "£19.99",
        ),
    ]
)


def test_a_beach_towel_is_not_the_price_of_the_film() -> None:
    """The reported defect. Searching Zavvi for "Jaws" returns a beach towel first, and it
    passes every one of the original five shape rules — the film's name is in the title,
    £17.99 is a plausible disc price, the currency is right and the URL is Zavvi's own.

    Reading card by card and requiring a disc format lets the 4K further down the page win.
    """
    candidate = extract(
        JAWS_MERCH_PAGE, BUILT_IN_SCRAPERS["Zavvi"]["config"], expected_title="Jaws"
    )

    assert candidate.title == "Jaws - 4K Ultra HD (Includes 2D Blu-ray)"
    assert candidate.price == Decimal("19.99")
    assert candidate.url == "/p/4k/jaws-4k-ultra-hd-includes-2d-blu-ray/12541038/"


def test_a_page_of_nothing_but_merchandise_is_refused_with_that_reason() -> None:
    """And when no disc is on the page at all, the towel must not become the answer. The
    reported reason has to name the real problem, so the first card is still returned for
    `check_shape` to judge rather than an empty candidate reporting "no price found"."""
    towels_only = JAWS_MERCH_PAGE[: JAWS_MERCH_PAGE.index('<div class="product-card"', 100)]
    candidate = extract(towels_only, BUILT_IN_SCRAPERS["Zavvi"]["config"], expected_title="Jaws")
    verdict = check_shape(candidate, expected_title="Jaws", retailer_host="www.zavvi.com")

    assert candidate.price is not None, "the candidate must survive to be judged"
    assert not verdict.ok
    assert any("no disc format" in reason for reason in verdict.reasons)


@pytest.mark.parametrize(
    "title",
    [
        "Jaws Amity Welcome Sign Beach Towel",
        "Jaws Fairisle Men's Christmas Jumper - Black",
        "McFarlane Jaws 50th Anniversary 1/48 Scale Resin Statue",
    ],
)
def test_merchandise_titles_name_no_disc_format(title: str) -> None:
    assert not looks_like_physical_media(title, None)


@pytest.mark.parametrize(
    ("title", "url"),
    [
        ("Jaws - 4K Ultra HD (Includes 2D Blu-ray)", None),
        ("Bad Lieutenant (1992) (Standard Edition) (Blu-ray)", None),
        ("THE LAST DETAIL - BD", None),
        ("Thousand Plane Raid (1969) (DVD)", None),
        # Zavvi puts the format in the path rather than the title.
        ("Heat and Dust", "/p/blu-ray/heat-and-dust/12044695/"),
    ],
)
def test_real_disc_listings_are_recognised_as_media(title: str, url: str | None) -> None:
    assert looks_like_physical_media(title, url)


@pytest.mark.parametrize(
    "found_title",
    [
        "Heat and Dust",
        "The Big Heat (Standard Edition)",
        "Red Heat - 4K Ultra HD",
        "Night of the Big Heat",
        "Step Up 4: Miami Heat",
    ],
)
def test_a_shop_that_does_not_stock_the_film_is_refused(found_title: str) -> None:
    """Zavvi has no Michael Mann *Heat*, and its search returns these instead. Every one
    shares a significant word, so the generous one-word rule passes all of them and would
    price a different film as *Heat*."""
    verdict = check_shape(
        _candidate(title=found_title, url="https://store.hmv.com/p/x"),
        expected_title="Heat",
        retailer_host="store.hmv.com",
    )

    assert not verdict.ok
    assert any("different film" in reason for reason in verdict.reasons)


@pytest.mark.parametrize(
    ("wanted", "found"),
    [
        ("Deep Red", "Deep Red Blu-ray"),
        ("Jaws", "Jaws - 4K Ultra HD (Includes 2D Blu-ray)"),
        ("Bad Lieutenant", "Bad Lieutenant (1992) (Standard Edition) (Blu-ray)"),
        ("The Babadook", "The Babadook Standard Edition 4K UHD"),
        ("The Last Detail", "THE LAST DETAIL - BD"),
        ("Carnal Knowledge", "CARNAL KNOWLEDGE - 4K UHD LE"),
    ],
)
def test_format_and_edition_wording_is_not_a_different_film(wanted: str, found: str) -> None:
    """The strictness above must not reject the real listings it has to accept. Everything
    a shop legitimately appends — format, edition, packaging, the release year — is noise.
    """
    verdict = check_shape(
        _candidate(title=found, url="https://store.hmv.com/p/x"),
        expected_title=wanted,
        retailer_host="store.hmv.com",
    )
    assert verdict.ok, verdict.reasons


def test_the_wanted_format_decides_which_edition_is_priced() -> None:
    """101 Films lists Bad Lieutenant on 4K, on Blu-ray, and as a limited edition of both.
    `preferred_format` is the wanted item's own answer to which of those to price, and was
    unused until now."""
    html = """
    <div class="product-info-inner"><a href="/products/bad-lieutenant-4k-uhd">
      <span class="prod-title">Bad Lieutenant (1992) (Standard Edition) (4K-UHD)</span></a>
      <div class="price"><span class="money">£22.00</span></div></div>
    <div class="product-info-inner"><a href="/products/bad-lieutenant-blu-ray">
      <span class="prod-title">Bad Lieutenant (1992) (Standard Edition) (Blu-ray)</span></a>
      <div class="price"><span class="money">£17.00</span></div></div>
    """
    config = BUILT_IN_SCRAPERS["101 Films"]["config"]

    blu_ray = extract(html, config, expected_title="Bad Lieutenant", preferred_format="blu_ray")
    uhd = extract(html, config, expected_title="Bad Lieutenant", preferred_format="4k_uhd")
    unstated = extract(html, config, expected_title="Bad Lieutenant")

    assert blu_ray.price == Decimal("17.00")
    assert uhd.price == Decimal("22.00")
    # No preference stated: the shop's own first result, not an arbitrary one.
    assert unstated.price == Decimal("22.00")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Jaws - 4K Ultra HD (Includes 2D Blu-ray)", "4k_uhd"),
        ("Bad Lieutenant (1992) (Limited Edition) (4K-UHD & Blu-ray)", "4k_uhd"),
        ("Bad Lieutenant (1992) (Standard Edition) (Blu-ray)", "blu_ray"),
        ("Deep Red Blu-ray", "blu_ray"),
        ("Deep Red DVD", "dvd"),
        ("Jaws Amity Welcome Sign Beach Towel", None),
    ],
)
def test_a_combo_pack_is_the_higher_format_it_contains(title: str, expected: str | None) -> None:
    """Every 4K combo also says "Blu-ray", so matching on mention alone let a £25 4K disc
    satisfy a want for a Blu-ray whenever it ranked first. What is in the box decides."""
    assert primary_format(title) == expected


def test_a_blu_ray_want_is_not_answered_with_the_4k_combo_above_it() -> None:
    html = _zavvi_card(
        "/p/4k/jaws-4k/1/", "Jaws - 4K Ultra HD (Includes 2D Blu-ray)", "£19.99"
    ) + _zavvi_card("/p/blu-ray/jaws-bd/2/", "Jaws Blu-ray", "£9.99")
    config = BUILT_IN_SCRAPERS["Zavvi"]["config"]

    blu_ray = extract(html, config, expected_title="Jaws", preferred_format="blu_ray")
    uhd = extract(html, config, expected_title="Jaws", preferred_format="4k_uhd")

    assert blu_ray.price == Decimal("9.99")
    assert uhd.price == Decimal("19.99")


async def test_a_format_substitution_is_reported_rather_than_passed_off() -> None:
    """A fallback is allowed — the shop plainly sells the film — but never silently. A
    `max_price` alert compares against whatever was priced, so a Blu-ray want answered with
    a 4K disc has to say which format it actually found."""
    page = RUNNER_PAGE.replace("Heat [4K UHD]", "Heat 4K Ultra HD (Includes Blu-ray)")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        _c, wanted_dvd = await scrape_one(
            _retailer(), "Heat", preferred_format="dvd", client=client
        )
        _c2, wanted_uhd = await scrape_one(
            _retailer(), "Heat", preferred_format="4k_uhd", client=client
        )

    assert wanted_dvd.ok
    assert wanted_dvd.substituted_format == "4k_uhd"
    # The format asked for was found, so there is nothing to flag.
    assert wanted_uhd.ok and wanted_uhd.substituted_format is None


async def test_a_digital_want_is_skipped_without_asking_a_disc_shop() -> None:
    """`download` is in the format vocabulary but no disc shop stocks it. Searching anyway
    used to fall back to "Blu-ray" and price a disc as if it were the digital copy."""

    def explode(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("a digital want must not reach a shop")

    async with httpx.AsyncClient(transport=httpx.MockTransport(explode)) as client:
        candidate, outcome = await scrape_one(
            _retailer(), "Heat", preferred_format="download", client=client
        )

    assert candidate is None
    assert outcome.skipped and not outcome.ok
    assert "digital" in (outcome.error or "")


# ---------------------------------------------------------------------------
# "Not stocked" is an answer, not a breakage
# ---------------------------------------------------------------------------

#: What Second Sight, Powerhouse and 101 Films really returned for "Misery" on 2026-09-09.
#: Each is a real, properly parsed listing — the shops answered, they just have not got it.
NOT_STOCKED_PAGE = "".join(
    [
        _zavvi_card(
            "/p/cold-prey/1/", "Cold Prey Trilogy Limited Edition Blu-ray Boxset", "£45.00"
        ),
        _zavvi_card("/p/bruiser/2/", "BRUISER - 4K UHD LE", "£30.00"),
        _zavvi_card("/p/nemesis/3/", "Nemesis Boxset (Blu-ray)", "£25.00"),
    ]
)

CARD_CONFIG = BUILT_IN_SCRAPERS["Zavvi"]["config"]


async def test_a_shop_that_answered_and_has_not_got_it_is_not_a_failure() -> None:
    """The regression that switched off three working scrapers on 2026-09-09.

    A boutique label asked for a film it does not carry returns a real page of real
    listings and the title guard correctly refuses every one. That is the shop answering,
    not the scraper breaking, and counting it towards auto-disable took 101 Films,
    Powerhouse and Second Sight offline after three runs.
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=NOT_STOCKED_PAGE))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        candidate, outcome = await scrape_one(
            _retailer(scraper_config=CARD_CONFIG),
            "Misery",
            preferred_format="4k_uhd",
            client=client,
        )

    assert candidate is None
    assert not outcome.ok
    assert outcome.not_stocked
    # And it is *not* a skip: the question was put to the shop and answered.
    assert not outcome.skipped
    assert "does not stock" in (outcome.error or "")


async def test_a_priceless_first_card_does_not_hide_a_not_stocked_answer() -> None:
    """Zavvi's real answer for "Nope 4K" led with an out-of-stock *Cujo* carrying no price.

    `check_shape` stops at "no price found" and never reaches its title rules, so reading
    the verdict's reasons would have called this a broken selector. The card counts are
    taken before any price filtering precisely so this case still reads correctly.
    """
    page = """
    <div class="product-card" data-testid="product-item">
      <a href="/p/4k/cujo/1/" data-testid="product-title">Cujo Limited Edition 4K UHD</a>
    </div>
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        _candidate, outcome = await scrape_one(
            _retailer(scraper_config=CARD_CONFIG), "Misery", client=client
        )

    assert not outcome.ok
    assert outcome.not_stocked


async def test_a_selector_that_matched_nothing_is_still_a_failure() -> None:
    """The distinction has to cut both ways, or auto-disable never fires again. A page that
    yields no titled listing at all is the redesign case the counter exists to catch."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="<div class='redesigned'>nothing here</div>")
    )
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        _candidate, outcome = await scrape_one(
            _retailer(scraper_config=CARD_CONFIG), "Misery", client=client
        )

    assert not outcome.ok
    assert not outcome.not_stocked


async def test_the_film_being_present_is_never_read_as_not_stocked() -> None:
    """A page that does name the film is judged on its merits, whatever the verdict."""
    page = NOT_STOCKED_PAGE + _zavvi_card(
        "/p/4k/misery/9/", "Misery Limited Edition 4K UHD", "£25.00"
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        candidate, outcome = await scrape_one(
            _retailer(scraper_config=CARD_CONFIG),
            "Misery",
            preferred_format="4k_uhd",
            client=client,
        )

    assert outcome.ok and not outcome.not_stocked
    assert candidate is not None and candidate.price == Decimal("25.00")


# ---------------------------------------------------------------------------
# Which edition, within a format
# ---------------------------------------------------------------------------

#: Arrow's real 4K shelf for Deep Red: the same film, the same format, three prices.
ARROW_DEEP_RED = "".join(
    [
        _zavvi_card("/p/deep-red-4k/1/", "Deep Red 4K UHD", "£25.00"),
        _zavvi_card("/p/deep-red-le-4k/2/", "Deep Red Limited Edition 4K UHD", "£25.00"),
        _zavvi_card(
            "/p/deep-red-arte-4k/3/",
            "Deep Red | Arte Originale Slipcover | Limited Edition 4K UHD",
            "£35.00",
        ),
    ]
)


def test_the_wanted_edition_stops_being_read_as_a_different_film() -> None:
    """Without the want, *arte* and *originale* are extra words that name another film —
    correctly, since nothing said otherwise. Naming the edition is what makes them
    expected rather than suspicious."""
    title = "Deep Red | Arte Originale Slipcover | Limited Edition 4K UHD"

    unasked = check_shape(_candidate(title=title), expected_title="Deep Red")
    asked = check_shape(
        _candidate(title=title),
        expected_title="Deep Red",
        preferred_edition="Arte Originale Slipcover",
    )

    assert not unasked.ok
    assert asked.ok, asked.reasons


def test_an_edition_must_match_on_every_word() -> None:
    """A partial match is how the £35 disc and the £25 one get confused."""
    slipcover = "Deep Red | Arte Originale Slipcover | Limited Edition 4K UHD"

    assert edition_matches(slipcover, None, "Arte Originale Slipcover")
    assert edition_matches("Deep Red Limited Edition 4K UHD", None, "Limited Edition")
    assert not edition_matches("Deep Red Limited Edition 4K UHD", None, "Arte Originale Slipcover")
    # No edition wanted: every listing qualifies.
    assert edition_matches("Deep Red 4K UHD", None, None)


@pytest.mark.parametrize(
    ("edition", "expected_price"),
    [
        (None, Decimal("25.00")),
        ("Arte Originale Slipcover", Decimal("35.00")),
        ("Limited Edition", Decimal("25.00")),
    ],
)
def test_the_wanted_edition_decides_which_listing_is_priced(
    edition: str | None, expected_price: Decimal
) -> None:
    """Three editions of one film in one format. Page order used to decide, which meant a
    `max_price` alert was about whichever disc the shop happened to rank first."""
    candidate = extract(
        ARROW_DEEP_RED,
        BUILT_IN_SCRAPERS["Zavvi"]["config"],
        expected_title="Deep Red",
        preferred_format="4k_uhd",
        preferred_edition=edition,
    )

    assert candidate.price == expected_price


def test_the_format_wins_when_only_one_of_the_two_can_be_had() -> None:
    """A Steelbook in the wrong format is a disc you cannot play; a plain edition in the
    right one is usable. So format outranks edition when the shelf forces a choice."""
    html = ARROW_DEEP_RED + _zavvi_card(
        "/p/deep-red-steel-bd/4/", "Deep Red Steelbook Blu-ray", "£20.00"
    )
    candidate = extract(
        html,
        BUILT_IN_SCRAPERS["Zavvi"]["config"],
        expected_title="Deep Red",
        preferred_format="4k_uhd",
        preferred_edition="Steelbook",
    )

    assert candidate.title == "Deep Red 4K UHD"


async def test_an_edition_substitution_is_reported_rather_than_passed_off() -> None:
    """Arrow has no Deep Red Steelbook. Pricing the plain 4K instead is allowed — the shop
    plainly sells the film — but a `max_price` alert compares against whatever was priced,
    so the report has to say the edition was not the one asked for."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=RUNNER_PAGE))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        _c, missing = await scrape_one(
            _retailer(), "Heat", preferred_edition="Arte Originale", client=client
        )
        _c2, unasked = await scrape_one(_retailer(), "Heat", client=client)

    assert missing.ok and missing.edition_matched is False
    # No edition wanted, so there is nothing to report either way.
    assert unasked.ok and unasked.edition_matched is None


def test_a_format_that_is_out_of_stock_falls_back_rather_than_reporting_nothing() -> None:
    """Arrow lists a Deep Red DVD with no price at all — it is out of stock. A want for a
    DVD must not turn that into a failure when the shop is plainly selling the film."""
    html = """
    <div class="product-card" data-testid="product-item">
      <a href="/p/deep-red-blu-ray/1/" data-testid="product-title">Deep Red Blu-ray</a>
      <div data-testid="product-price"><span class="product-variant-price">£15.00</span></div>
    </div>
    <div class="product-card" data-testid="product-item">
      <a href="/p/deep-red-dvd/2/" data-testid="product-title">Deep Red DVD</a>
      <div data-testid="product-price"><span class="product-variant-price"></span></div>
    </div>
    """
    candidate = extract(
        html,
        BUILT_IN_SCRAPERS["Arrow Video"]["config"],
        expected_title="Deep Red",
        preferred_format="dvd",
    )

    assert candidate.title == "Deep Red Blu-ray"
    assert candidate.price == Decimal("15.00")


def test_a_cards_own_element_can_supply_its_link() -> None:
    """Powerhouse's product card *is* its anchor, so scoping to the card would otherwise
    put the listing URL out of reach — `select_one` searches descendants only."""
    html = """
    <a class="list-view-item" href="/products/the-last-detail-bd">
      <div class="list-view-item__title">THE LAST DETAIL - BD</div>
      <span class="product-price__price">£9.99</span>
    </a>
    """
    candidate = extract(
        html, BUILT_IN_SCRAPERS["Powerhouse Films"]["config"], expected_title="The Last Detail"
    )

    assert candidate.url == "/products/the-last-detail-bd"
    assert candidate.price == Decimal("9.99")


def test_a_title_is_never_paired_with_another_products_price() -> None:
    """The failure card-scoping exists to prevent: the first card has no price node, so
    page-wide selectors pair its title with the *second* card's price."""
    html = """
    <div class="product-card" data-testid="product-item">
      <a href="/p/blu-ray/the-thing/1/" data-testid="product-title">The Thing Blu-ray</a>
    </div>
    <div class="product-card" data-testid="product-item">
      <a href="/p/blu-ray/the-thing-4k/2/" data-testid="product-title">The Thing 4K UHD</a>
      <div data-testid="product-price"><span class="product-variant-price">£29.99</span></div>
    </div>
    """
    config = BUILT_IN_SCRAPERS["Zavvi"]["config"]

    scoped = extract(html, config, expected_title="The Thing")
    page_wide = extract(html, {k: v for k, v in config.items() if k != "item"})

    assert scoped.title == "The Thing 4K UHD" and scoped.price == Decimal("29.99")
    # Without `item`, the first title is reported with the second card's price.
    assert page_wide.title == "The Thing Blu-ray" and page_wide.price == Decimal("29.99")


def test_the_same_product_rendered_twice_does_not_out_rank_a_better_one() -> None:
    """Second Sight renders each product twice, for its grid and list layouts."""
    html = (
        _zavvi_card("/p/4k/alien-4k/1/", "Alien 4K UHD", "£25.00")
        + _zavvi_card("/p/4k/alien-4k/1/", "Alien 4K UHD", "£25.00")
        + _zavvi_card("/p/blu-ray/alien-bd/2/", "Alien Blu-ray", "£12.00")
    )
    candidate = extract(
        html,
        BUILT_IN_SCRAPERS["Zavvi"]["config"],
        expected_title="Alien",
        preferred_format="blu_ray",
    )

    assert candidate.title == "Alien Blu-ray"


# ---------------------------------------------------------------------------
# The runner: retry, auto-disable, and what gets written
# ---------------------------------------------------------------------------


def _retailer(**kwargs: object) -> Retailer:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Test Shop",
        "base_url": "https://93.184.216.34",
        "search_url_template": "https://93.184.216.34/search?q={query}",
        "scraper_config": {"title": "a.title", "price": ".price", "url": "a.title"},
        "scraper_type": "generic_css",
        "scrape_frequency": "weekly",
        "enabled": True,
        "currency": "GBP",
        "region": "GB",
        "consecutive_failures": 0,
    }
    base.update(kwargs)
    return Retailer(**base)  # type: ignore[arg-type]


#: The same page, but with its links on the host the test retailer actually is.
#:
#: The first version of these tests reused `SHOP_PAGE`, whose links point at
#: `store.hmv.com`, against a retailer whose `base_url` is a literal IP — and the
#: cross-domain check caught it. That is the guard working, but it made the *retry* test
#: fail for a reason that had nothing to do with retrying. A literal address is used
#: throughout so `assert_fetchable` needs no DNS and cannot flake on a resolver.
RUNNER_PAGE = SHOP_PAGE.replace("https://store.hmv.com", "https://93.184.216.34")


def _ok_transport() -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(200, text=RUNNER_PAGE))


async def test_a_retailer_with_no_selectors_is_reported_not_attempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A seeded retailer has no `scraper_config` — Batch 18 leaves it empty on purpose.

    That is a configuration gap, and saying so is more useful than making a request that
    was never going to work.
    """
    del monkeypatch
    candidate, outcome = await scrape_one(_retailer(scraper_config={}), "Heat")
    assert candidate is None
    assert outcome.error == "no selectors configured"


async def test_a_retailer_with_no_search_template_is_reported() -> None:
    candidate, outcome = await scrape_one(_retailer(search_url_template=None), "Heat")
    assert candidate is None
    assert outcome.error == "no search URL template configured"


async def test_a_transient_failure_is_retried_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shop that times out once is usually up. Twice, not more — retrying hard against a
    retailer is how an IP gets blocked, which turns a transient failure into a permanent
    one."""
    monkeypatch.setattr("src.services.scraping.runner.RETRY_PAUSE_SECONDS", 0)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectTimeout("first attempt times out")
        return httpx.Response(200, text=RUNNER_PAGE)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        candidate, outcome = await scrape_one(_retailer(), "Heat", client=client)

    assert attempts["n"] == 2
    assert outcome.ok, outcome.reasons
    assert candidate is not None and candidate.price == Decimal("19.99")


async def test_an_outcome_carries_the_currency_the_price_was_read_in() -> None:
    """A bare number is not a price. `check_shape` refuses a currency the retailer is not
    configured for rather than converting it (#79), so the outcome has to carry the code or
    the report loses the one fact that makes the number checkable."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=RUNNER_PAGE))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        _candidate_out, outcome = await scrape_one(_retailer(), "Heat", client=client)

    assert outcome.ok
    assert outcome.price == Decimal("19.99")
    assert outcome.currency == "GBP"


async def test_a_relative_listing_link_becomes_an_absolute_persistable_url() -> None:
    page = RUNNER_PAGE.replace(
        'href="https://93.184.216.34/product/heat-4k"',
        'href="/product/heat-4k"',
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        candidate, outcome = await scrape_one(_retailer(), "Heat", client=client)

    assert outcome.ok
    assert outcome.url == "https://93.184.216.34/product/heat-4k"
    assert candidate is not None
    assert candidate.url == "https://93.184.216.34/product/heat-4k"


async def test_a_shape_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page that parsed into something implausible will parse the same way again, and
    asking a shop twice for the same wrong answer is just rudeness."""
    monkeypatch.setattr("src.services.scraping.runner.RETRY_PAUSE_SECONDS", 0)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        attempts["n"] += 1
        return httpx.Response(200, text="<html><body>nothing useful</body></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        candidate, outcome = await scrape_one(_retailer(), "Heat", client=client)

    assert attempts["n"] == 1
    assert candidate is None
    assert not outcome.ok


async def test_the_wrong_node_is_caught_before_it_becomes_a_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end: a selector pointing at the "Save £5.00" badge.

    The fetch works, the extraction works, the number is real. Only the shape check stops
    it — and this is exactly the ledger's risk note, tested rather than described.
    """
    monkeypatch.setattr("src.services.scraping.runner.RETRY_PAUSE_SECONDS", 0)
    retailer = _retailer(
        scraper_config={"title": "a.title", "price": ".save", "url": "a.title"},
        currency="USD",  # forces a mismatch, standing in for the real-world signal
    )
    async with httpx.AsyncClient(transport=_ok_transport(), follow_redirects=False) as client:
        candidate, outcome = await scrape_one(retailer, "Heat", client=client)

    assert candidate is None
    assert not outcome.ok
    assert outcome.reasons


async def test_three_consecutive_failures_disable_a_retailer() -> None:
    """§5.3's "auto-disable after 3 fails"."""
    retailer = _retailer(consecutive_failures=2, enabled=True)
    disabled = await _record_failure(_NullSession(), retailer, "still broken")
    assert disabled is True
    assert retailer.enabled is False
    assert retailer.consecutive_failures == 3


async def test_two_failures_do_not_disable() -> None:
    retailer = _retailer(consecutive_failures=1, enabled=True)
    disabled = await _record_failure(_NullSession(), retailer, "broken once more")
    assert disabled is False
    assert retailer.enabled is True


def test_a_success_resets_the_counter_rather_than_decrementing_it() -> None:
    """Three failures **in a row** is the signal. A shop that fails on Monday and works on
    Tuesday has not accumulated anything."""
    retailer = _retailer(consecutive_failures=2)
    _record_success(retailer)
    assert retailer.consecutive_failures == 0
    assert retailer.last_scrape_status == "success"
    assert retailer.last_scrape_error is None


class _NullSession:
    """`_record_failure` only mutates the row; it takes a session for symmetry."""


def test_the_search_url_is_built_by_percent_encoding_the_title() -> None:
    retailer = _retailer(search_url_template="https://shop.test/s?q={query}")
    assert (
        search_url_for(retailer, "North by Northwest")
        == "https://shop.test/s?q=North%20by%20Northwest"
    )
    # A title with a character that would otherwise break the query string.
    assert "%26" in (search_url_for(retailer, "Fast & Furious") or "")


def test_the_search_names_the_format_because_a_bare_title_returns_merchandise() -> None:
    """THG redirects a bare film title to a franchise landing page — on 2026-09-09 the
    first twelve results for "Jaws" were towels, jumpers, T-shirts and a resin statue, with
    no disc at all. Naming a format is what makes the search return the disc grid, so
    `{format}` is part of finding the film rather than a refinement of it.
    """
    retailer = _retailer(search_url_template="https://shop.test/s?q={query}%20{format}")

    assert search_url_for(retailer, "Jaws", "4k_uhd") == "https://shop.test/s?q=Jaws%204K"
    assert search_url_for(retailer, "Jaws", "dvd") == "https://shop.test/s?q=Jaws%20DVD"
    # No preferred format: "Blu-ray" is not a guess at what the owner wants, it is the
    # term that makes the shop return its disc categories — 4K editions included.
    assert search_url_for(retailer, "Jaws") == "https://shop.test/s?q=Jaws%20Blu-ray"
    assert search_url_for(retailer, "Jaws", "download") == "https://shop.test/s?q=Jaws%20Blu-ray"


def test_an_unfilled_placeholder_is_never_sent_to_a_shop() -> None:
    """The reported defect, and the reason template substitution has exactly one home.

    The browser built the test URL itself and knew only about ``{query}``, so the day
    ``{format}`` was added it sent Zavvi ``?q=Jaws%20{format}`` — which matched *The Sheriff
    of Fractured Jaw (**Dual Format Edition**)* on the word "format" and reported it as the
    price of *Jaws*.
    """
    filled = apply_search_template(
        "https://www.zavvi.com/search?q={query}%20{format}", "Jaws", "4k_uhd"
    )

    assert filled == "https://www.zavvi.com/search?q=Jaws%204K"
    assert "{" not in filled and "}" not in filled


def test_the_test_tool_and_the_runner_fill_a_template_identically() -> None:
    """§5.4's tool exists to prove a scraper works. It cannot do that while building its
    request differently from the thing it is proving."""
    template = "https://www.zavvi.com/search?q={query}%20{format}"
    retailer = _retailer(search_url_template=template)

    assert search_url_for(retailer, "Jaws", "blu_ray") == apply_search_template(
        template, "Jaws", "blu_ray"
    )


def test_a_template_without_the_format_placeholder_is_untouched() -> None:
    """Only THG's shops need it; the Shopify labels search their own catalogue fine."""
    retailer = _retailer(search_url_template="https://shop.test/s?q={query}&type=product")
    assert search_url_for(retailer, "Heat", "4k_uhd") == "https://shop.test/s?q=Heat&type=product"


def test_a_retailer_without_a_template_cannot_be_searched() -> None:
    assert search_url_for(_retailer(search_url_template=None), "Heat") is None
    assert search_url_for(_retailer(search_url_template="https://shop.test/"), "Heat") is None


# ---------------------------------------------------------------------------
# What a live run on 2026-09-10 found — `DECISIONS.md` #125
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


class TestSelectorsAreATriedInOrder:
    """A comma-separated selector is a **fallback list**, not a set.

    `select_one("a, b")` returns whichever comes first *in the document*, so
    Second Sight's `".price-item--sale, .price-item--regular"` silently returned the
    regular price whenever the markup put it first — ignoring the sale it was written to
    prefer. Nothing errored; it just quoted the wrong number.
    """

    @pytest.mark.parametrize(
        ("selector", "expected"),
        [
            (".a, .b", [".a", ".b"]),
            # A comma inside brackets or parentheses is not a separator.
            ('[data-x="a,b"], .c', ['[data-x="a,b"]', ".c"]),
            (":is(a, b), .c", [":is(a, b)", ".c"]),
            ("  .a  ,  .b  ", [".a", ".b"]),
            ("a", ["a"]),
        ],
    )
    def test_a_selector_list_splits_only_at_the_top_level(
        self, selector: str, expected: list[str]
    ) -> None:
        assert split_selectors(selector) == expected

    def test_the_first_selector_wins_even_when_the_second_comes_first_in_the_page(self) -> None:
        """The sale price is written second in the DOM and asked for first."""
        html = (
            '<div class="card">'
            '<span class="price-item--regular">£19.99</span>'
            '<span class="price-item--sale">£12.99</span>'
            "</div>"
        )
        soup = BeautifulSoup(html, "html.parser")

        text = select_one_text(soup, ".price-item--sale, .price-item--regular")
        assert parse_price(text) == (Decimal("12.99"), "GBP")

    def test_it_falls_through_to_the_later_selector(self) -> None:
        html = '<div class="card"><span class="price-item--regular">£19.99</span></div>'
        soup = BeautifulSoup(html, "html.parser")

        text = select_one_text(soup, ".price-item--sale, .price-item--regular")
        assert parse_price(text) == (Decimal("19.99"), "GBP")


class TestZavviRendersTwoPriceShapes:
    """`zavvi_search_two_price_shapes.html` — two cards captured from the live site.

    **They disagree about their own markup**, which is why one of them used to be dropped:
    a multi-variant listing wraps the figure in `.product-variant-price`, a single-price
    listing puts it straight in the `product-price` wrapper. The scraper read only the
    first, so a real £16.99 was fetched, parsed and thrown away — three of one live run's
    eleven "failures".
    """

    PAGE = (FIXTURES / "zavvi_search_two_price_shapes.html").read_text(encoding="utf-8")

    def test_the_fixture_really_carries_both_shapes(self) -> None:
        soup = BeautifulSoup(self.PAGE, "html.parser")
        cards = soup.select("[data-testid='product-item']")
        assert len(cards) == 2
        has_variant = [
            c.select_one("[data-testid='product-price'] .product-variant-price") is not None
            for c in cards
        ]
        # One of each. A fixture where both agree could not have caught this.
        assert sorted(has_variant) == [False, True]

    def test_both_shapes_yield_their_price(self) -> None:
        selector = BUILT_IN_SCRAPERS["Zavvi"]["config"]["price"]
        soup = BeautifulSoup(self.PAGE, "html.parser")

        prices = [
            parse_price(select_one_text(card, selector))[0]
            for card in soup.select("[data-testid='product-item']")
        ]
        assert prices == [Decimal("12.99"), Decimal("16.99")]

    def test_the_wrapper_label_is_not_read_as_the_price(self) -> None:
        """The variant wrapper reads "Current price:  £12.99." — the label must not win."""
        soup = BeautifulSoup(self.PAGE, "html.parser")
        card = soup.select("[data-testid='product-item']")[0]

        text = select_one_text(card, BUILT_IN_SCRAPERS["Zavvi"]["config"]["price"])
        assert parse_price(text) == (Decimal("12.99"), "GBP")


EMPTY_RESULTS_PAGE = """
<html><body>
  <h1 id="search-results-heading">Sorry We Couldn't Find Any Results Matching "Cross of Iron"</h1>
  <p>Your search did not yield any results.</p>
</body></html>
"""


class TestAnEmptyResultsPageIsNeitherAFailureNorAClaim:
    """`DECISIONS.md` #125 — the third state.

    Zero cards is what *"we do not stock that"* looks like **and** what a broken selector
    looks like, and nothing in the response tells them apart. A live run on 2026-09-10
    counted eight such pages as scraper failures — Arrow's "Sorry We Couldn't Find Any
    Results" and 101 Films' "0 results found" — which feeds auto-disable.
    """

    async def test_an_empty_page_is_recorded_as_no_results(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text=EMPTY_RESULTS_PAGE)
        )
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            candidate, outcome = await scrape_one(
                _retailer(scraper_config=CARD_CONFIG),
                "Cross of Iron",
                client=client,
            )

        assert candidate is None
        assert not outcome.ok
        assert outcome.no_results
        # It must not claim the shop has not got it — that is the claim it cannot make.
        assert not outcome.not_stocked
        assert not outcome.skipped

    async def test_a_page_of_real_listings_is_still_not_stocked(self) -> None:
        """The distinction the third state must not blur.

        Cards present and none matching *is* the shop answering "no", and stays so.
        """
        transport = httpx.MockTransport(lambda request: httpx.Response(200, text=NOT_STOCKED_PAGE))
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            _, outcome = await scrape_one(
                _retailer(scraper_config=CARD_CONFIG), "Misery", client=client
            )

        assert outcome.not_stocked
        assert not outcome.no_results

    def test_no_results_does_not_count_towards_the_failure_total(self) -> None:
        result = ScrapeRunResult(
            outcomes=[
                ScrapeOutcome(retailer="Arrow", wanted_title="A", ok=False, no_results=True),
                ScrapeOutcome(retailer="Arrow", wanted_title="B", ok=False, no_results=True),
                ScrapeOutcome(retailer="Arrow", wanted_title="C", ok=False, error="503"),
            ]
        )

        assert result.no_results == 2
        # Only the genuine one. Before #125 this read 3, and three runs of it disabled
        # a shop that was merely carrying different films.
        assert result.failed == 1
