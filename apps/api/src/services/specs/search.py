"""Finding a disc's Blu-ray.com page with Brave's web search — Batch T7, `DECISIONS.md` #202.

**Why an outside search engine at all.** The fetcher can read a release page but cannot
find one, and #110 bars Blu-ray.com's own search routes. Only 10 discs ever had specs,
because each needed its page address pasted in by hand. A web search engine proposes the
addresses; nothing here touches Blu-ray.com itself.

Shaped like ``src/ebay/client.py``: an async ``httpx`` client behind a context manager, a
rate limiter, retries on a 429, a 5xx or a dropped connection, and a count of every request
sent, because Brave bills each one. **The key is optional at import and checked at use**,
so the API boots without it and :class:`BraveNotConfigured` names the missing variable
before anything is sent.

Built from Brave's documentation (checked 24 Sep 2026: ``GET /res/v1/web/search`` with the
key in ``X-Subscription-Token``, results at ``web.results[]``). The first live search is
where that is confirmed against a real response.
"""

from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from src.config import settings
from src.tmdb.client import RateLimiter

BRAVE_API_BASE = "https://api.search.brave.com"
SEARCH_PATH = "/res/v1/web/search"

#: Brave's largest page. One call then returns every edition a film has on the site.
MAX_COUNT = 20

#: Brave's Search plan allows 50 a second; one a second is plenty for a nightly batch.
DEFAULT_RATE = 1.0

#: Retries after a 429, a 5xx or a dropped connection. Brave bills each attempt.
DEFAULT_MAX_RETRIES = 2

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")

logger = structlog.get_logger(__name__)


class BraveNotConfigured(RuntimeError):
    """No Brave key in this deployment. Raised before any request."""


class BraveError(RuntimeError):
    """Brave answered, and the answer was not usable, or it could not be reached."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class SearchHit:
    """One web result, as plain text."""

    url: str
    title: str
    description: str


def _plain(text: object) -> str:
    """Brave marks matched words with ``<strong>`` and escapes entities. Neither is wanted."""
    if not isinstance(text, str):
        return ""
    return _SPACE.sub(" ", html.unescape(_TAG.sub("", text))).strip()


def hits_from_payload(payload: dict[str, Any]) -> list[SearchHit]:
    """The results Brave returned, skipping any without an address or a title."""
    web = payload.get("web")
    results = web.get("results") if isinstance(web, dict) else None
    hits: list[SearchHit] = []
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, dict):
            continue
        url = result.get("url")
        title = _plain(result.get("title"))
        if isinstance(url, str) and url and title:
            hits.append(
                SearchHit(url=url, title=title, description=_plain(result.get("description")))
            )
    return hits


class BraveSearch:
    """Async Brave web search, used as ``async with BraveSearch() as brave:``."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        rate: float = DEFAULT_RATE,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.brave_search_api_key
        self._max_retries = max_retries
        self._rate_limiter = RateLimiter(rate)
        self._client: httpx.AsyncClient | None = None
        #: Requests sent, retries included, because Brave bills every one.
        self.search_calls = 0

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def attempts_per_search(self) -> int:
        """The most requests one :meth:`search` can send, counting its retries."""
        return self._max_retries + 1

    async def __aenter__(self) -> BraveSearch:
        self._client = httpx.AsyncClient(base_url=BRAVE_API_BASE, timeout=20.0)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _require(self) -> httpx.AsyncClient:
        if not self.configured:
            raise BraveNotConfigured("BRAVE_SEARCH_API_KEY is not set in this deployment")
        if self._client is None:
            raise RuntimeError("BraveSearch must be used as an async context manager")
        return self._client

    async def search(
        self, query: str, *, count: int = MAX_COUNT, country: str = "GB"
    ) -> list[SearchHit]:
        """One web search. Returns the hits, or raises :class:`BraveError`."""
        client = self._require()
        params = {
            "q": query,
            "count": str(min(count, MAX_COUNT)),
            "country": country,
            "search_lang": "en",
            "result_filter": "web",
        }
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
        }
        last_status: int | None = None
        for attempt in range(self._max_retries + 1):
            await self._rate_limiter.acquire()
            self.search_calls += 1
            try:
                response = await client.get(SEARCH_PATH, params=params, headers=headers)
            except httpx.TransportError as exc:
                last_status = None
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise BraveError(f"Brave could not be reached ({type(exc).__name__})") from exc

            last_status = response.status_code
            if response.status_code == 200:
                payload: dict[str, Any] = response.json()
                return hits_from_payload(payload)
            if response.status_code in (401, 403):
                # A wrong or revoked key. Retrying spends nothing useful.
                logger.error("brave_key_refused", status=response.status_code)
                raise BraveError(
                    f"Brave refused the key (HTTP {response.status_code})", response.status_code
                )
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self._max_retries:
                logger.warning("brave_search_retrying", status=response.status_code)
                await asyncio.sleep(2**attempt)
                continue
            raise BraveError(f"Brave search failed (HTTP {response.status_code})", last_status)

        raise BraveError(f"Brave search failed (HTTP {last_status})", last_status)
