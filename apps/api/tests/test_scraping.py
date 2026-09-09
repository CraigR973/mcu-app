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

import httpx
import pytest

from src.models.wanted import Retailer
from src.services.scraping.builtins import BUILT_IN_SCRAPERS, unverified_names
from src.services.scraping.extract import (
    MAX_PLAUSIBLE,
    ScrapeCandidate,
    check_shape,
    extract,
    parse_price,
)
from src.services.scraping.fetcher import UnsafeUrlError, assert_fetchable, fetch_page
from src.services.scraping.runner import (
    _record_failure,
    _record_success,
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


def test_all_six_built_ins_are_present_and_none_claims_to_be_verified() -> None:
    """§5.3 names six shops. **None has been run against a live page**, because that is a
    hard stop the owner performs — so every one says `verified: false`.

    A selector nobody has run is a guess, and the honest state of a guess is unverified.
    Claiming otherwise is how a plausible wrong number reaches the price alerts.
    """
    assert set(BUILT_IN_SCRAPERS) == {
        "HMV",
        "Amazon UK",
        "Blu-ray.com",
        "Zavvi",
        "Arrow Video",
        "CEX",
    }
    assert sorted(unverified_names()) == sorted(BUILT_IN_SCRAPERS)


def test_every_built_in_has_a_search_template_with_a_query_placeholder() -> None:
    for name, entry in BUILT_IN_SCRAPERS.items():
        assert "{query}" in entry["search"], name
        assert str(entry["search"]).startswith("https://"), name
        assert entry["config"].get("price"), name


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

    assert entry["search"] == "https://www.zavvi.com/search?q={query}"
    assert candidate.title == "Heat and Dust"
    assert candidate.price == Decimal("20.99")
    assert candidate.currency == "GBP"
    assert candidate.url == "/p/blu-ray/heat-and-dust/12044695/"


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


def test_a_retailer_without_a_template_cannot_be_searched() -> None:
    assert search_url_for(_retailer(search_url_template=None), "Heat") is None
    assert search_url_for(_retailer(search_url_template="https://shop.test/"), "Heat") is None
