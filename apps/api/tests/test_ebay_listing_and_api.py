"""Phase 4.3's listing link, and both endpoints — Batch 28.

The listing-URL tests are short because the mechanism is: eBay's prelist form reads
``?title=`` and ignores ``?keyword=``, ``?q=`` and ``?sugKw=``. That was established in a
browser on 2026-09-12 and is the entire reason Phase 4.3 still has a path at all — so a
test pins the parameter name. A silent rename would leave the button working, the form
opening, and the box empty.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

import src.routers.ebay as ebay_router
from src.auth import get_current_user
from src.database import get_db
from src.ebay.client import SEARCH_PATH, TOKEN_PATH
from src.ebay.listing import MAX_TITLE_LENGTH, PRELIST_URL, prelist_url, suggested_title
from src.main import app
from src.models.profile import Profile, UserRole

FIXTURES = Path(__file__).parent / "fixtures"
BLADE_RUNNER = json.loads((FIXTURES / "ebay_browse_blade_runner_2049.json").read_text())


# ---------------------------------------------------------------------------
# The pre-filled listing URL — Phase 4.3
# ---------------------------------------------------------------------------


def test_the_prefill_parameter_is_title() -> None:
    """The finding this phase turns on.

    ``keyword``, ``q`` and ``sugKw`` all render the form with an **empty** box — they fail
    silently, which is the worst way for a listing link to be wrong.
    """
    url = prelist_url("Jaws", year=1975, format_code="blu_ray")
    parsed = urlparse(url)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == PRELIST_URL
    query = parse_qs(parsed.query)
    assert list(query) == ["title"]
    assert query["title"] == ["Jaws (1975) Blu-ray"]


def test_the_title_carries_year_format_and_condition() -> None:
    assert (
        suggested_title("Jaws", year=1975, format_code="4k_uhd", condition="new")
        == "Jaws (1975) 4K UHD Blu-ray New & Sealed"
    )


def test_a_long_film_title_keeps_its_name_and_drops_the_trimmings() -> None:
    """eBay truncates past 80 characters silently, so the film's name must never be what
    goes over the edge."""
    long_title = "The Assassination of Jesse James by the Coward Robert Ford Special Feature"
    built = suggested_title(long_title, year=2007, format_code="4k_uhd", condition="new")
    assert len(built) <= MAX_TITLE_LENGTH
    assert built.startswith(long_title)


def test_a_damaged_disc_gets_no_euphemism() -> None:
    """ "Damaged" needs a description, not a one-word grade in the title."""
    assert suggested_title("Jaws", condition="damaged") == "Jaws"


def test_the_url_is_escaped() -> None:
    url = prelist_url("Fast & Furious", format_code="blu_ray")
    assert " " not in url
    assert parse_qs(urlparse(url).query)["title"] == ["Fast & Furious Blu-ray"]


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------

pytestmark_asyncio = pytest.mark.asyncio

ADMIN = Profile(display_name="Craig", role=UserRole.admin)
VIEWER = Profile(display_name="Mark", role=UserRole.viewer)


def _as(profile: Profile) -> Any:
    async def override() -> Profile:
        return profile

    app.dependency_overrides[get_current_user] = override
    yield
    app.dependency_overrides.pop(get_current_user, None)


class _NoStoredValues:
    """A session holding no stored values, so the used-to-New factor is the fallback.

    Batch X6: both routes read the factor from ``disc_valuations``. These tests are about
    the routes, not the table (``test_valuation_runs.py`` measures the factor in Postgres),
    so they keep running without a database.
    """

    async def execute(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return []


@pytest.fixture(autouse=True)
def no_stored_values() -> Any:
    async def override() -> Any:
        yield _NoStoredValues()

    app.dependency_overrides[get_db] = override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_admin() -> Any:
    yield from _as(ADMIN)


@pytest.fixture
def as_viewer() -> Any:
    """Batch S4 (`DECISIONS.md` #155).

    These two endpoints were ``AdminUser``; the fixture overrode ``require_admin``, which
    is the dependency that no longer guards them. Overriding ``get_current_user`` instead
    is both what the endpoints now read *and* what makes a viewer expressible at all — the
    old shape could not describe the caller this batch exists to admit.
    """
    yield from _as(VIEWER)


@pytest.fixture
def fake_ebay(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scripted eBay returning the captured Blade Runner payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKEN_PATH:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 7200})
        assert request.url.path == SEARCH_PATH
        return httpx.Response(200, json=BLADE_RUNNER)

    original = ebay_router.EbayClient.__aenter__

    async def patched(self: Any) -> Any:
        await original(self)
        self._client = httpx.AsyncClient(  # noqa: SLF001
            base_url="https://api.ebay.com", transport=httpx.MockTransport(handler)
        )
        self._client_id = "id"
        self._client_secret = "secret"
        return self

    monkeypatch.setattr(ebay_router.EbayClient, "__aenter__", patched)


async def _post(path: str, payload: dict[str, Any]) -> httpx.Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(path, json=payload)


@pytest.mark.asyncio
async def test_a_viewer_gets_a_price_estimate_rather_than_a_403(
    as_viewer: None, fake_ebay: None
) -> None:
    """Batch S4's criterion, stated as **200, not 403** — `DECISIONS.md` #155.

    Snag 7 was never about capability: Batch 29 built the whole upgrade → sell offer and
    it worked. It was about reach. Mark could not open the add page, and both eBay
    endpoints behind the "List for sale" button refused him, so the feature existed and
    was invisible to half the people it was for.
    """
    response = await _post(
        "/api/v1/ebay/price-estimate",
        {"filmTitle": "Blade Runner 2049", "formatCode": "blu_ray"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["segments"]


@pytest.mark.asyncio
async def test_a_viewer_gets_a_listing_url_rather_than_a_403(
    as_viewer: None, fake_ebay: None
) -> None:
    response = await _post(
        "/api/v1/ebay/listing-url",
        {"filmTitle": "Blade Runner 2049", "formatCode": "blu_ray"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["url"].startswith(PRELIST_URL)


@pytest.mark.asyncio
async def test_price_estimate_refuses_an_unauthenticated_caller() -> None:
    """It spends a unit of a finite daily quota. Nothing unauthenticated may.

    **Batch S4 widened this to any signed-in person, not to the public.** The endpoint was
    admin-only and is now ``CurrentUser``; what it must never be is open, because the quota
    is finite and the keyset is Craig's.
    """
    response = await _post("/api/v1/ebay/price-estimate", {"filmTitle": "Jaws"})
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_price_estimate_returns_segments_with_sample_sizes(
    as_admin: None, fake_ebay: None
) -> None:
    response = await _post(
        "/api/v1/ebay/price-estimate",
        {"filmTitle": "Blade Runner 2049", "formatCode": "blu_ray"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["considered"] == 200
    assert body["basis"] == "current asking prices"
    assert body["marketplaceId"] == "EBAY_GB"
    assert body["headline"]["formatCode"] == "blu_ray"
    assert body["headline"]["edition"] == "standard"
    assert body["headline"]["sampleSize"] >= 10
    # Money crosses the wire as a string, never a float.
    assert isinstance(body["headline"]["median"], str)
    assert body["rejected"], "the rejections are part of the answer, not diagnostics"
    # Batch X6: the disc's value as a used copy, from the 24 used listings, beside the table.
    assert body["usedValue"] == {
        "price": "7.05",
        "currency": "GBP",
        "basis": "used_quartile",
        "sampleSize": 24,
        "low": "3.72",
        "high": "65.99",
        "factor": None,
        "valuedAs": "as used copies",
    }


@pytest.mark.asyncio
async def test_a_dvd_with_too_few_used_listings_is_valued_from_new_at_the_factor(
    as_admin: None, fake_ebay: None
) -> None:
    """One used DVD and four New at £9.13 median: New times the fallback factor, 0.60."""
    response = await _post(
        "/api/v1/ebay/price-estimate", {"filmTitle": "Blade Runner 2049", "formatCode": "dvd"}
    )
    assert response.status_code == 200, response.text
    value = response.json()["usedValue"]
    assert (value["price"], value["basis"], value["factor"], value["sampleSize"]) == (
        "5.48",
        "new_scaled",
        "0.60",
        4,
    )


@pytest.mark.asyncio
async def test_a_series_flag_lets_a_tv_titles_own_box_sets_count(
    as_admin: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Batch X6: "Complete Series" is another product for a film, and the thing itself for a
    TV title (``mediaType`` tv)."""
    listing = {
        "itemId": "v1|1|0",
        "title": "Blue Planet II The Complete Series 4K UHD",
        "price": {"value": "20.00", "currency": "GBP"},
        "conditionId": "3000",
        "buyingOptions": ["FIXED_PRICE"],
        "leafCategoryIds": ["617"],
        "itemLocation": {"country": "GB"},
    }
    payload = {"itemSummaries": [{**listing, "itemId": f"v1|{i}|0"} for i in range(3)]}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKEN_PATH:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 7200})
        return httpx.Response(200, json=payload)

    original = ebay_router.EbayClient.__aenter__

    async def patched(self: Any) -> Any:
        await original(self)
        self._client = httpx.AsyncClient(  # noqa: SLF001
            base_url="https://api.ebay.com", transport=httpx.MockTransport(handler)
        )
        self._client_id = "id"
        self._client_secret = "secret"
        return self

    monkeypatch.setattr(ebay_router.EbayClient, "__aenter__", patched)
    asked = {"filmTitle": "Blue Planet II", "formatCode": "4k_uhd"}

    as_film = (await _post("/api/v1/ebay/price-estimate", asked)).json()
    as_series = (await _post("/api/v1/ebay/price-estimate", {**asked, "isSeries": True})).json()

    assert as_film["usedValue"] is None and as_film["matched"] == 0
    assert as_series["usedValue"]["price"] == "20.00"


@pytest.mark.asyncio
async def test_price_estimate_says_so_when_the_deployment_has_no_keyset(
    as_admin: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """503 and a reason, rather than an empty result that looks like a rare disc."""
    monkeypatch.setattr(ebay_router.settings, "ebay_client_id", "")
    monkeypatch.setattr(ebay_router.settings, "ebay_client_secret", "")
    response = await _post("/api/v1/ebay/price-estimate", {"filmTitle": "Jaws"})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_price_estimate_rejects_an_unknown_field(as_admin: None, fake_ebay: None) -> None:
    response = await _post(
        "/api/v1/ebay/price-estimate", {"filmTitle": "Jaws", "soldListings": True}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_listing_url_returns_a_link_and_a_suggested_price(
    as_admin: None, fake_ebay: None
) -> None:
    response = await _post(
        "/api/v1/ebay/listing-url",
        {"filmTitle": "Blade Runner 2049", "year": 2017, "formatCode": "blu_ray"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith(PRELIST_URL + "?title=")
    assert body["suggestedTitle"] == "Blade Runner 2049 (2017) Blu-ray"
    # The sale price starts from the disc's value as a used copy (Batch X6), not New's £9.99.
    assert body["suggestedPrice"] == "7.05"


@pytest.mark.asyncio
async def test_a_missing_keyset_still_yields_a_listing_link(
    as_admin: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The link is the feature; the price is an aid to it. An eBay outage must not stop
    somebody listing a disc."""
    monkeypatch.setattr(ebay_router.settings, "ebay_client_id", "")
    monkeypatch.setattr(ebay_router.settings, "ebay_client_secret", "")
    response = await _post(
        "/api/v1/ebay/listing-url", {"filmTitle": "Jaws", "formatCode": "blu_ray"}
    )
    assert response.status_code == 200
    assert response.json()["suggestedPrice"] is None
    assert response.json()["url"].startswith(PRELIST_URL)
