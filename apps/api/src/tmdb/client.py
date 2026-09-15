from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from ..config import settings
from .models import (
    Movie,
    PersonMovieCredits,
    ReleaseDates,
    SearchResults,
    WatchProviders,
)

TMDB_BASE_URL = "https://api.themoviedb.org/3"

logger = structlog.get_logger()


class RateLimiter:
    """Token-bucket rate limiter — refills at `rate` tokens/second."""

    def __init__(self, rate: float) -> None:
        self._rate = rate
        self._tokens = rate
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1


class TMDBClient:
    """Async TMDB v3 client with rate limiting and exponential backoff."""

    def __init__(
        self,
        read_token: str | None = None,
        max_retries: int = 3,
        rate: float = 3.0,
    ) -> None:
        self._token = read_token or settings.tmdb_read_token
        self._max_retries = max_retries
        self._rate_limiter = RateLimiter(rate)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> TMDBClient:
        self._client = httpx.AsyncClient(
            base_url=TMDB_BASE_URL,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("TMDBClient must be used as an async context manager")

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            await self._rate_limiter.acquire()
            try:
                response = await self._client.get(path, params=params)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 1))
                    wait = retry_after * (2**attempt)
                    logger.warning("tmdb_rate_limited", path=path, wait=wait, attempt=attempt)
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 500 and attempt < self._max_retries:
                    wait = 2**attempt
                    logger.warning(
                        "tmdb_server_error",
                        path=path,
                        status=response.status_code,
                        attempt=attempt,
                        wait=wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result

            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "tmdb_request_failed",
                    path=path,
                    status=exc.response.status_code,
                    attempt=attempt,
                )
                last_exc = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)

        raise last_exc or RuntimeError(f"TMDB request failed after {self._max_retries} retries")

    async def get_movie(
        self,
        movie_id: int,
        append_to_response: list[str] | None = None,
        language: str = "en-US",
    ) -> Movie:
        params: dict[str, Any] = {"language": language}
        if append_to_response:
            params["append_to_response"] = ",".join(append_to_response)
        data = await self._get(f"/movie/{movie_id}", params=params)
        return Movie.model_validate(data)

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> Movie:
        """Fetch a movie with credits, videos, and watch providers in one call."""
        return await self.get_movie(
            movie_id,
            append_to_response=["credits", "videos", "watch/providers"],
            language=language,
        )

    async def get_upcoming(
        self, region: str = "GB", language: str = "en-US", page: int = 1
    ) -> SearchResults:
        """Films released soon in a given country.

        ``/movie/upcoming`` rather than ``/search/movie`` with an empty query, which TMDB
        rejects — and rather than ``/discover``, whose genre filter would answer with a
        list that cannot say *which* genre matched. Filtering here keeps that explanation.

        ``region`` genuinely changes the answer: cinema release dates differ by country,
        and a UK app listing US dates would be wrong in a way that looks right.
        """
        data = await self._get(
            "/movie/upcoming", {"language": language, "page": page, "region": region}
        )
        return SearchResults.model_validate(data)

    async def get_release_dates(self, movie_id: int) -> ReleaseDates:
        """Every dated release of a film, per country and per type — Batch S6, snag 2.

        No ``language`` parameter: this response is keyed by **country**, and a date does
        not translate.

        **TMDB type 5 is "Physical" and says nothing about format.** A 4K disc and a
        Blu-ray released the same day are one entry, so anything that wants to tell them
        apart has only the free-text ``note`` to go on — see
        :func:`src.services.calendar.classify_physical`.
        """
        data = await self._get(f"/movie/{movie_id}/release_dates")
        return ReleaseDates.model_validate(data)

    async def get_watch_providers(self, movie_id: int) -> WatchProviders:
        """Where a film can be streamed, rented or bought, per country.

        No ``language`` parameter: TMDB keys this response by **region**, and the
        provider names are brand names that do not translate. Passing one would suggest
        the answer varies with it.
        """
        data = await self._get(f"/movie/{movie_id}/watch/providers")
        return WatchProviders.model_validate(data)

    async def get_recommendations(
        self, movie_id: int, language: str = "en-US", page: int = 1
    ) -> SearchResults:
        """TMDB's own "if you liked this" list.

        Returns the same shape as a search, which is what lets the ownership-flagging
        below treat a recommendation and a search hit identically — they are both "a TMDB
        film this collection may or may not already have".
        """
        data = await self._get(
            f"/movie/{movie_id}/recommendations", {"language": language, "page": page}
        )
        return SearchResults.model_validate(data)

    async def get_person_movie_credits(
        self, person_id: int, language: str = "en-US"
    ) -> PersonMovieCredits:
        """Everything TMDB says a person worked on, in one call.

        The whole filmography per person is what makes a completion set answerable at all
        — "you own 12 of the 54 films Hitchcock directed" needs the 54, and there is no
        cheaper way to learn it. One call per set, not one per film.
        """
        data = await self._get(f"/person/{person_id}/movie_credits", {"language": language})
        return PersonMovieCredits.model_validate(data)

    async def search_movie(
        self,
        query: str,
        year: int | None = None,
        page: int = 1,
        language: str = "en-US",
        include_adult: bool = False,
    ) -> SearchResults:
        """Search the TMDB movie index by title (and optional release year)."""
        params: dict[str, Any] = {
            "query": query,
            "page": page,
            "language": language,
            "include_adult": str(include_adult).lower(),
        }
        if year is not None:
            params["year"] = year
        data = await self._get("/search/movie", params=params)
        return SearchResults.model_validate(data)
