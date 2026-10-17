from __future__ import annotations

import asyncio
import time
from datetime import date
from typing import Any

import httpx
import structlog

from ..config import settings
from ..services.scraping.fetcher import bounded_wait
from .models import (
    Movie,
    MovieKeywords,
    PersonMovieCredits,
    PersonSearchResults,
    ReleaseDates,
    SearchResults,
    TvKeywords,
    TvSearchResults,
    TvShow,
    WatchProviders,
)

TMDB_BASE_URL = "https://api.themoviedb.org/3"

logger = structlog.get_logger()

#: What a person reads when TMDB keeps refusing: the wording the discovery routes use.
TMDB_DID_NOT_ANSWER = "TMDB didn't answer. Try again in a moment."


class TMDBRefused(RuntimeError):
    """TMDB answered ``429`` to the last try — Batch X1 (CR43-06).

    Not an ``httpx`` error, so the routes that turn TMDB's errors into a 404 or a 502 let
    it through, and the app answers it 503 with :data:`TMDB_DID_NOT_ANSWER` (`main.py`).
    Before X1 it ended as a bare ``RuntimeError``, which reached the person as a 500.
    """


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
                    # The scraper's bounded rule (#238): TMDB's Retry-After up to 90 s, a
                    # date read as one, never less than the usual backoff; past 90 s, the
                    # backoff alone. Before X1 the wait was unbounded and doubled each try.
                    if attempt >= self._max_retries:
                        logger.warning("tmdb_refused", path=path, attempt=attempt)
                        raise TMDBRefused(TMDB_DID_NOT_ANSWER)
                    wait = bounded_wait(
                        response.headers.get("Retry-After"), usual_pause=float(2**attempt)
                    )
                    logger.warning(
                        "tmdb_rate_limited",
                        path=path,
                        wait=wait.seconds,
                        note=wait.note,
                        attempt=attempt,
                    )
                    await asyncio.sleep(wait.seconds)
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
        """Fetch a movie with credits, videos, watch providers and, since Batch Y5, its
        keywords in one call. The keywords are what the Archive's Film Noir reads."""
        return await self.get_movie(
            movie_id,
            append_to_response=["credits", "videos", "watch/providers", "keywords"],
            language=language,
        )

    async def get_movie_keywords(self, movie_id: int) -> MovieKeywords:
        """A film's TMDB keywords alone — Batch Y5's backfill, one call a film."""
        data = await self._get(f"/movie/{movie_id}/keywords")
        return MovieKeywords.model_validate(data)

    async def get_tv_keywords(self, tv_id: int) -> TvKeywords:
        """A series' TMDB keywords alone — Batch Y5's backfill."""
        data = await self._get(f"/tv/{tv_id}/keywords")
        return TvKeywords.model_validate(data)

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

    async def discover_by_release_type(
        self,
        *,
        region: str,
        release_types: str,
        date_from: date,
        date_to: date,
        page: int = 1,
        language: str = "en-US",
    ) -> SearchResults:
        """Films with a release of these types in this country between two dates — Batch T5.

        ``release_types`` is TMDB's own syntax: ``"5"`` for physical, ``"2|3"`` for limited
        or wide cinema release. With ``region`` set, TMDB applies the date range to that
        country's releases of those types, not to the film's premiere. That is the whole
        difference from ``/movie/upcoming``, which lists films about to reach cinemas, and
        so almost never has a disc date yet (1 of 58 when measured on 2026-09-15).

        The ``release_date`` on each result is still the film's *primary* date, so the
        country's own date comes from :meth:`get_release_dates`.
        """
        data = await self._get(
            "/discover/movie",
            {
                "region": region,
                "with_release_type": release_types,
                "release_date.gte": date_from.isoformat(),
                "release_date.lte": date_to.isoformat(),
                "sort_by": "popularity.desc",
                "include_adult": "false",
                "language": language,
                "page": page,
            },
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

    async def get_tv_full(self, tv_id: int, language: str = "en-US") -> TvShow:
        """A TV series with its whole-run cast and crew, videos and IMDb id — Batch Y3.

        ``aggregate_credits`` rather than ``credits``: the latter is the latest season's cast
        only, which for a finished series is whoever was in its last episodes. Its keywords
        too since Batch Y5.
        """
        params = {
            "language": language,
            "append_to_response": "aggregate_credits,videos,external_ids,keywords",
        }
        data = await self._get(f"/tv/{tv_id}", params=params)
        return TvShow.model_validate(data)

    async def get_tv_watch_providers(self, tv_id: int) -> WatchProviders:
        """Where a series can be streamed, rented or bought — Batch Y3. The same shape as a
        film's answer, from ``/tv/{id}/watch/providers``."""
        data = await self._get(f"/tv/{tv_id}/watch/providers")
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

    async def search_tv(
        self, query: str, page: int = 1, language: str = "en-US"
    ) -> TvSearchResults:
        """Search TMDB's TV index — Batch T9.

        T9 used it to recognise a TV series among the films TMDB's movie index cannot match,
        so "Dynasties" is set aside as TV rather than asked about as a film. Since Batch Y3 it
        also offers series to identify a title as, and finds series matched as films.
        """
        params: dict[str, Any] = {"query": query, "page": page, "language": language}
        data = await self._get("/search/tv", params=params)
        return TvSearchResults.model_validate(data)

    async def search_person(self, query: str, page: int = 1) -> PersonSearchResults:
        """Search TMDB's people — Batch T9, to read the films of a name a title carries."""
        data = await self._get(
            "/search/person", {"query": query, "page": page, "include_adult": "false"}
        )
        return PersonSearchResults.model_validate(data)
