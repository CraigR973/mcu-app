"""The Browse client and its token cache — Batch 28, Phase 4.1.

**The token is the only thing here with no equivalent in ``src/tmdb/``**, so it is where
the tests go. TMDB's read token is a static configuration string; eBay's is minted from
client credentials, expires in 7200 seconds, and is counted against the same daily quota
the searches are. Every failure mode below is silent in production if it is not tested:
minting per request wastes quota with nothing to show for it, minting late fails one
request in every few thousand, and an unconfigured deployment sends
``Authorization: Basic`` over an empty pair and reads eBay's 401 as an outage — which is
the shape of the TMDB outage of 2026-09-09.

No live calls. The transport is an ``httpx.MockTransport``, so these run in CI.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from src.ebay.client import (
    ITEM_BY_LEGACY_ID_PATH,
    SEARCH_PATH,
    TOKEN_PATH,
    EbayClient,
    EbayError,
    EbayNotConfigured,
)

pytestmark = pytest.mark.asyncio


class _Recorder:
    """A scripted eBay, counting what it was asked for."""

    def __init__(
        self,
        *,
        token_expires_in: int = 7200,
        search_statuses: list[int | Exception] | None = None,
        token_status: int = 200,
    ) -> None:
        self.token_mints = 0
        self.searches = 0
        self.search_headers: list[httpx.Headers] = []
        self._expires_in = token_expires_in
        self._statuses = search_statuses or []
        self._token_status = token_status

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKEN_PATH:
            self.token_mints += 1
            if self._token_status != 200:
                return httpx.Response(self._token_status, json={"error": "invalid_client"})
            return httpx.Response(
                200,
                json={
                    "access_token": f"token-{self.token_mints}",
                    "expires_in": self._expires_in,
                    "token_type": "Application Access Token",
                },
            )
        if request.url.path == SEARCH_PATH:
            self.searches += 1
            self.search_headers.append(request.headers)
            status = self._statuses.pop(0) if self._statuses else 200
            if isinstance(status, Exception):
                raise status
            if status != 200:
                return httpx.Response(status, json={"errors": []})
            return httpx.Response(200, json={"total": 1, "itemSummaries": []})
        raise AssertionError(f"unexpected request to {request.url}")


def _client(recorder: _Recorder, **kwargs: Any) -> EbayClient:
    client = EbayClient(client_id="id", client_secret="secret", rate=1000.0, **kwargs)
    client._client = httpx.AsyncClient(  # noqa: SLF001 - injecting the transport is the point
        base_url="https://api.ebay.com",
        transport=httpx.MockTransport(recorder.handler),
    )
    return client


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


async def test_an_unconfigured_deployment_refuses_before_sending_anything() -> None:
    """Named, not opaque.

    Sending ``Basic ``-over-nothing produces eBay's 401, which reads as "eBay is down"
    rather than "nobody set the variable" — the exact confusion that let every TMDB-backed
    feature answer 502 for days.
    """
    async with EbayClient(client_id="", client_secret="") as client:
        assert client.configured is False
        with pytest.raises(EbayNotConfigured):
            await client.search("Jaws Blu-ray")


async def test_the_marketplace_header_is_sent_on_every_search() -> None:
    """Without it eBay answers for the US site, in dollars, and nothing says so."""
    recorder = _Recorder()
    client = _client(recorder, marketplace_id="EBAY_GB")
    await client.search("Jaws Blu-ray")
    assert recorder.search_headers[0]["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"


# ---------------------------------------------------------------------------
# The token cache
# ---------------------------------------------------------------------------


async def test_a_second_search_reuses_the_token() -> None:
    recorder = _Recorder()
    client = _client(recorder)
    await client.search("Jaws Blu-ray")
    await client.search("Blade Runner 2049 Blu-ray")
    assert recorder.token_mints == 1
    assert recorder.searches == 2


async def test_concurrent_searches_on_a_cold_cache_mint_one_token() -> None:
    """The lock, and the reason it exists.

    Twenty searches racing a cold cache would otherwise mint twenty tokens, each counting
    against the same 5,000-a-day quota as the searches, and none of them invalidating the
    others. Nothing about that failure is visible from outside.
    """
    recorder = _Recorder()
    client = _client(recorder)
    await asyncio.gather(*(client.search(f"film {index}") for index in range(20)))
    assert recorder.token_mints == 1
    assert recorder.searches == 20


async def test_a_token_close_to_expiry_is_re_minted_rather_than_raced() -> None:
    """``expires_in`` of 60s is inside the five-minute refresh margin, so it is never used
    twice — the boundary is not something a request should be allowed to sit on."""
    recorder = _Recorder(token_expires_in=60)
    client = _client(recorder)
    await client.search("Jaws Blu-ray")
    await client.search("Jaws Blu-ray")
    assert recorder.token_mints == 2


async def test_a_revoked_token_is_re_minted_once_and_the_search_retried() -> None:
    """The case no clock predicts. eBay can revoke a token before it expires; the cache
    believes it is valid and every search 401s until something re-mints."""
    recorder = _Recorder(search_statuses=[401, 200])
    client = _client(recorder)
    await client.search("Jaws Blu-ray")
    assert recorder.token_mints == 2
    assert recorder.searches == 2
    assert recorder.search_headers[1]["Authorization"] == "Bearer token-2"


async def test_refused_credentials_raise_rather_than_return_an_empty_result() -> None:
    recorder = _Recorder(token_status=401)
    client = _client(recorder)
    with pytest.raises(EbayError) as caught:
        await client.search("Jaws Blu-ray")
    assert caught.value.status_code == 401


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


async def test_a_server_error_is_retried_then_raised() -> None:
    recorder = _Recorder(search_statuses=[503, 503, 503])
    client = _client(recorder, max_retries=2)
    with pytest.raises(EbayError):
        await client.search("Jaws Blu-ray")
    assert recorder.searches == 3


async def test_a_transient_server_error_recovers() -> None:
    recorder = _Recorder(search_statuses=[500, 200])
    client = _client(recorder)
    payload = await client.search("Jaws Blu-ray")
    assert payload["total"] == 1


async def test_a_bad_request_is_not_retried() -> None:
    """A 400 is our query being wrong. Retrying it spends quota to be told so again."""
    recorder = _Recorder(search_statuses=[400])
    client = _client(recorder)
    with pytest.raises(EbayError):
        await client.search("Jaws Blu-ray")
    assert recorder.searches == 1


async def test_the_payload_is_returned_verbatim() -> None:
    """`DECISIONS.md` #122: a layer that reshapes on the way past is a layer the fixtures
    stop describing."""
    recorder = _Recorder()
    client = _client(recorder)
    assert await client.search("Jaws Blu-ray") == {"total": 1, "itemSummaries": []}


async def test_every_request_is_counted_retries_included() -> None:
    """Batch T6 budgets valuation runs on this count, and eBay charges each retry too."""
    recorder = _Recorder(search_statuses=[500, 200])
    client = _client(recorder, max_retries=2)
    await client.search("Jaws Blu-ray")
    await client.search("Heat Blu-ray")
    assert client.search_calls == recorder.searches == 3
    assert client.attempts_per_search == 3


async def test_a_dropped_connection_is_retried() -> None:
    """The first valuation run died at call 574 of 750 on one of these (24 Sep)."""
    recorder = _Recorder(search_statuses=[httpx.ReadError("connection reset"), 200])
    client = _client(recorder)
    payload = await client.search("Jaws Blu-ray")
    assert payload["total"] == 1
    assert client.search_calls == recorder.searches == 2


async def test_a_connection_that_keeps_dropping_is_an_ebay_error() -> None:
    """Named, so callers that handle eBay failing handle this too, rather than a 500."""
    recorder = _Recorder(search_statuses=[httpx.ConnectTimeout("slow")] * 3)
    client = _client(recorder, max_retries=2)
    with pytest.raises(EbayError) as caught:
        await client.search("Jaws Blu-ray")
    assert caught.value.status_code is None
    assert "ConnectTimeout" in str(caught.value)
    assert recorder.searches == 3


# ---------------------------------------------------------------------------
# Batch T8a — one listing by number, and the newest-first search
# ---------------------------------------------------------------------------


class _ItemRecorder:
    """eBay answering ``get_item_by_legacy_id`` with scripted statuses."""

    def __init__(self, statuses: list[int]) -> None:
        self.statuses = statuses
        self.calls: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKEN_PATH:
            return httpx.Response(200, json={"access_token": "token", "expires_in": 7200})
        if request.url.path == ITEM_BY_LEGACY_ID_PATH:
            self.calls.append(request)
            status = self.statuses.pop(0)
            if status == 200:
                return httpx.Response(200, json={"legacyItemId": "168722516953"})
            return httpx.Response(status, json={"errors": [{"errorId": 11001}]})
        raise AssertionError(f"unexpected request to {request.url}")


def _item_client(recorder: _ItemRecorder) -> EbayClient:
    client = EbayClient(client_id="id", client_secret="secret", rate=1000.0)
    client._client = httpx.AsyncClient(  # noqa: SLF001 - injecting the transport is the point
        base_url="https://api.ebay.com", transport=httpx.MockTransport(recorder.handler)
    )
    return client


async def test_a_listing_is_read_by_its_number() -> None:
    recorder = _ItemRecorder([200])
    client = _item_client(recorder)
    assert await client.get_item_by_legacy_id("168722516953") == {"legacyItemId": "168722516953"}
    assert recorder.calls[0].url.params["legacy_item_id"] == "168722516953"
    assert recorder.calls[0].headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"


async def test_a_listing_eBay_no_longer_has_is_none_not_an_error() -> None:
    client = _item_client(_ItemRecorder([404]))
    assert await client.get_item_by_legacy_id("168722516953") is None
    assert client.search_calls == 1


async def test_a_listing_lookup_is_retried_and_counted_like_a_search() -> None:
    recorder = _ItemRecorder([503, 200])
    client = _item_client(recorder)
    assert await client.get_item_by_legacy_id("168722516953") is not None
    assert client.search_calls == len(recorder.calls) == 2


async def test_the_newest_first_search_sends_its_sort_filter_and_page() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKEN_PATH:
            return httpx.Response(200, json={"access_token": "token", "expires_in": 7200})
        seen.append(request)
        return httpx.Response(200, json={"itemSummaries": []})

    client = EbayClient(client_id="id", client_secret="secret", rate=1000.0)
    client._client = httpx.AsyncClient(  # noqa: SLF001 - injecting the transport is the point
        base_url="https://api.ebay.com", transport=httpx.MockTransport(handler)
    )
    await client.search(
        "(blu-ray,bluray,4k,uhd)",
        category_ids="617",
        sort="newlyListed",
        filter="itemLocationCountry:GB,buyingOptions:{FIXED_PRICE}",
        offset=400,
    )
    params = seen[0].url.params
    assert (params["sort"], params["offset"], params["category_ids"]) == (
        "newlyListed",
        "400",
        "617",
    )
    assert params["filter"] == "itemLocationCountry:GB,buyingOptions:{FIXED_PRICE}"
