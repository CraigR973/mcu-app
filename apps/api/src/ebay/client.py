"""An eBay Browse API client — Batch 28, Phase 4.1.

Modelled on ``src/tmdb/client.py``, which is the shape this project already knows how to
operate: an async ``httpx`` client behind a context manager, a token-bucket rate limiter,
and exponential backoff on 429 and 5xx. `docs/phase-batches.md` puts it here rather than in
Batch 19's scraper framework on purpose — eBay is a fixed host with a typed API, the
framework's ``check_shape`` exists for HTML drift, and #16's accepted ToS exposure covers
retailers rather than eBay.

**One thing has no equivalent in ``src/tmdb/`` and is therefore where the bugs live: the
token.** TMDB's read token is a static string from configuration. eBay's is minted from
client credentials and expires — ``expires_in`` is **7200** seconds, verified against
production on 2026-09-10 (`DECISIONS.md` #126) and again on 2026-09-11. So this client
caches a token and re-mints it, and the cache is the net-new mechanism:

- it refreshes **early**, at :data:`TOKEN_REFRESH_MARGIN` seconds before expiry, so a
  request never races the boundary;
- it is guarded by a lock, so twenty concurrent searches on a cold cache mint **one**
  token rather than twenty — eBay counts token mints against the same daily quota;
- and a 401 on a search invalidates it once and retries, because the other way a token
  stops working is eBay revoking it early, which no clock can predict.

**Credentials are optional at import and checked at use.** The API must boot without them,
exactly as it boots without ``TMDB_READ_TOKEN`` — see ``config.Settings``. What must *not*
happen is the TMDB outage of 2026-09-09, where a missing variable produced
``Authorization: Bearer `` and a 502 that read as "temporarily unavailable" for days. So
:class:`EbayClient` raises :class:`EbayNotConfigured` before sending anything, and
``/api/v1/health/ready`` reports ``ebay`` so the absence is visible without anyone trying a
search first.
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx
import structlog

from ..config import settings
from ..tmdb.client import RateLimiter

#: Production hosts. The sandbox equivalents exist but its GB catalogue is empty, which is
#: why `docs/phase-batches.md` says 4.1's acceptance has to be a live production call.
EBAY_API_BASE = "https://api.ebay.com"
TOKEN_PATH = "/identity/v1/oauth2/token"  # noqa: S105 - a URL path, not a credential
SEARCH_PATH = "/buy/browse/v1/item_summary/search"
#: One listing by the number in its web address — Batch T8a's price targets.
ITEM_BY_LEGACY_ID_PATH = "/buy/browse/v1/item/get_item_by_legacy_id"

#: The only scope a client-credentials token can hold, and all Browse needs.
APP_SCOPE = "https://api.ebay.com/oauth/api_scope"

#: Re-mint this long before the token expires. eBay's tokens last 7200s; five minutes of
#: margin costs one extra mint every two hours at worst and removes the boundary race.
TOKEN_REFRESH_MARGIN = 300.0

#: eBay's default self-service quota is 5,000 Browse calls a day (`DECISIONS.md` #126).
#: Two per second is far below anything that would trip a burst limit while still letting
#: a page of results arrive promptly.
DEFAULT_RATE = 2.0

#: Retries after a 429, a 5xx or a revoked token. Each is a call against the allowance.
DEFAULT_MAX_RETRIES = 2

#: Browse caps ``limit`` at 200, and 200 is what the segmentation wants: #129's measurement
#: needed the whole result set to show that a naive median was 149% high.
MAX_LIMIT = 200

logger = structlog.get_logger()


class EbayNotConfigured(RuntimeError):
    """No eBay client credentials in this deployment.

    Raised before any request, so the failure names the missing configuration instead of
    surfacing as an opaque 401 from eBay.
    """


class EbayError(RuntimeError):
    """eBay answered, and the answer was not usable."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class EbayClient:
    """Async Browse client with a cached application token.

    Used as an async context manager, like :class:`~src.tmdb.client.TMDBClient`::

        async with EbayClient() as client:
            payload = await client.search("Blade Runner 2049 Blu-ray")
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        marketplace_id: str | None = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        rate: float = DEFAULT_RATE,
    ) -> None:
        self._client_id = client_id if client_id is not None else settings.ebay_client_id
        self._client_secret = (
            client_secret if client_secret is not None else settings.ebay_client_secret
        )
        self._marketplace_id = marketplace_id or settings.ebay_marketplace_id
        self._max_retries = max_retries
        self._rate_limiter = RateLimiter(rate)
        self._client: httpx.AsyncClient | None = None
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        #: Browse requests sent, retries included, because eBay counts every one against
        #: the daily allowance. Batch T6's valuation run budgets on this.
        self.search_calls = 0

    @property
    def marketplace_id(self) -> str:
        return self._marketplace_id

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    @property
    def attempts_per_search(self) -> int:
        """The most Browse requests one :meth:`search` can send, counting its retries."""
        return self._max_retries + 1

    async def __aenter__(self) -> EbayClient:
        self._client = httpx.AsyncClient(base_url=EBAY_API_BASE, timeout=30.0)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _require(self) -> httpx.AsyncClient:
        if not self.configured:
            raise EbayNotConfigured(
                "EBAY_CLIENT_ID and EBAY_CLIENT_SECRET are not set in this deployment"
            )
        if self._client is None:
            raise RuntimeError("EbayClient must be used as an async context manager")
        return self._client

    async def _access_token(self, *, force: bool = False) -> str:
        """A valid application token, minting one only when there isn't one.

        The lock is the point. Without it, a cold cache plus concurrent searches mints a
        token per request — each of which counts against the same daily quota the searches
        do, and each of which invalidates nothing, so the waste is silent.
        """
        client = self._require()
        async with self._token_lock:
            if not force and self._token and time.monotonic() < self._token_expires_at:
                return self._token

            basic = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
            response = await client.post(
                TOKEN_PATH,
                data={"grant_type": "client_credentials", "scope": APP_SCOPE},
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            if response.status_code != 200:
                logger.error("ebay_token_mint_failed", status=response.status_code)
                raise EbayError(
                    f"eBay refused the credentials (HTTP {response.status_code})",
                    response.status_code,
                )
            payload: dict[str, Any] = response.json()
            token = payload.get("access_token")
            if not isinstance(token, str) or not token:
                raise EbayError("eBay returned no access token")
            expires_in = float(payload.get("expires_in") or 0)
            self._token = token
            self._token_expires_at = time.monotonic() + max(expires_in - TOKEN_REFRESH_MARGIN, 0.0)
            logger.info("ebay_token_minted", expires_in=expires_in)
            return token

    async def search(
        self,
        query: str,
        *,
        limit: int = MAX_LIMIT,
        category_ids: str | None = None,
        sort: str | None = None,
        filter: str | None = None,  # noqa: A002 - Browse's own parameter name
        offset: int = 0,
    ) -> dict[str, Any]:
        """One ``item_summary/search`` call, returned verbatim.

        Verbatim on purpose: :mod:`src.ebay.matching` reads the payload and is tested
        against captured copies of it, so this layer must not reshape anything on the way
        past. Reshaping here is how ``test_specs.py``'s invented fixture happened — the
        test agreed with the parser and neither agreed with the site (`DECISIONS.md` #122).

        ``sort``, ``filter`` and ``offset`` are Batch T8a's: the deal scan reads the newest
        UK listings first (``sort=newlyListed``) a page at a time.
        """
        params: dict[str, Any] = {"q": query, "limit": str(min(limit, MAX_LIMIT))}
        if category_ids:
            params["category_ids"] = category_ids
        if sort:
            params["sort"] = sort
        if filter:
            params["filter"] = filter
        if offset:
            params["offset"] = str(offset)
        payload = await self._get(SEARCH_PATH, params, what="search")
        if payload is None:  # pragma: no cover - a search never answers 404
            raise EbayError("eBay search failed (HTTP 404)", 404)
        return payload

    async def get_item_by_legacy_id(self, legacy_item_id: str) -> dict[str, Any] | None:
        """One listing, by the number in its web address — Batch T8a's price targets.

        ``None`` when eBay answers 404: the listing has ended or been removed, which is an
        answer about the listing rather than a failure. Returned verbatim, like
        :meth:`search`.
        """
        return await self._get(
            ITEM_BY_LEGACY_ID_PATH,
            {"legacy_item_id": legacy_item_id},
            what="item",
            not_found_is_none=True,
        )

    async def _get(
        self,
        path: str,
        params: dict[str, Any],
        *,
        what: str,
        not_found_is_none: bool = False,
    ) -> dict[str, Any] | None:
        """One Browse GET with the token, the retries and the count every call shares."""
        client = self._require()
        last_status: int | None = None
        for attempt in range(self._max_retries + 1):
            await self._rate_limiter.acquire()
            try:
                token = await self._access_token(force=attempt > 0 and last_status == 401)
                self.search_calls += 1
                response = await client.get(
                    path,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
                        "Accept": "application/json",
                    },
                )
            except httpx.TransportError as exc:
                # A dropped connection or a timeout says nothing about the query, so it is
                # retried like a 5xx. Before 24 Sep it escaped as a raw httpx error: the
                # film page answered 500, and the first valuation run died at call 574 of 750.
                last_status = None
                if attempt < self._max_retries:
                    wait = 2**attempt
                    logger.warning(
                        f"ebay_{what}_network_retrying",
                        error=type(exc).__name__,
                        attempt=attempt,
                        wait=wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"ebay_{what}_network_failed", error=type(exc).__name__)
                raise EbayError(f"eBay could not be reached ({type(exc).__name__})") from exc
            last_status = response.status_code

            if response.status_code == 200:
                payload: dict[str, Any] = response.json()
                return payload

            if response.status_code == 404 and not_found_is_none:
                return None

            if response.status_code == 401 and attempt < self._max_retries:
                # The clock said the token was good and eBay disagrees. Mint once more
                # before giving up — a revoked token is the case no expiry can predict.
                logger.warning("ebay_token_rejected", attempt=attempt)
                continue

            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self._max_retries:
                wait = 2**attempt
                logger.warning(
                    f"ebay_{what}_retrying",
                    status=response.status_code,
                    attempt=attempt,
                    wait=wait,
                )
                await asyncio.sleep(wait)
                continue

            logger.error(f"ebay_{what}_failed", status=response.status_code)
            raise EbayError(f"eBay {what} failed (HTTP {response.status_code})", last_status)

        raise EbayError(f"eBay {what} failed (HTTP {last_status})", last_status)
