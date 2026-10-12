from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tmdb.client import RateLimiter, TMDBClient
from src.tmdb.models import Movie

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOVIE_FIXTURE: dict = {
    "id": 299536,
    "title": "Avengers: Infinity War",
    "original_title": "Avengers: Infinity War",
    "overview": "As the Avengers and their allies have continued to protect the world...",
    "release_date": "2018-04-25",
    "runtime": 149,
    "tagline": "An entire universe. Once and for all.",
    "status": "Released",
    "budget": 316000000,
    "revenue": 2048359754,
    "vote_average": 8.3,
    "vote_count": 26789,
    "popularity": 172.0,
    "adult": False,
    "video": False,
    "imdb_id": "tt4154756",
    "original_language": "en",
    "genres": [{"id": 28, "name": "Action"}, {"id": 12, "name": "Adventure"}],
    "production_companies": [{"id": 420, "name": "Marvel Studios", "origin_country": "US"}],
    "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
    "spoken_languages": [{"iso_639_1": "en", "name": "English", "english_name": "English"}],
}

CREDITS_FIXTURE: dict = {
    "cast": [
        {
            "id": 3223,
            "name": "Robert Downey Jr.",
            "character": "Tony Stark / Iron Man",
            "order": 0,
            "profile_path": "/5qHNjhtjMD4YWH3UP0rm4tKwxCL.jpg",
            "credit_id": "52fe4495c3a368484e02b8a3",
        }
    ],
    "crew": [
        {
            "id": 12891,
            "name": "Anthony Russo",
            "job": "Director",
            "department": "Directing",
            "profile_path": None,
            "credit_id": "56a3d08a9251412e7d0074f4",
        }
    ],
}

VIDEOS_FIXTURE: dict = {
    "results": [
        {
            "id": "5a200c0dc3a3681e7c00e13d",
            "key": "QwievZ1Tx-8",
            "site": "YouTube",
            "type": "Trailer",
            "name": "Official Trailer",
            "official": True,
        }
    ]
}

WATCH_PROVIDERS_FIXTURE: dict = {
    "results": {
        "US": {
            "link": "https://www.themoviedb.org/movie/299536/watch?locale=US",
            "flatrate": [
                {
                    "provider_id": 9,
                    "provider_name": "Amazon Prime Video",
                    "logo_path": "/68MNrwlkpF7WnmNPXLah69CR5cb.jpg",
                }
            ],
            "rent": [],
            "buy": [],
        }
    }
}


@pytest.fixture
def movie_with_appended() -> dict:
    return {
        **MOVIE_FIXTURE,
        "credits": CREDITS_FIXTURE,
        "videos": VIDEOS_FIXTURE,
        "watch/providers": WATCH_PROVIDERS_FIXTURE,
    }


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_movie_model_basic() -> None:
    movie = Movie.model_validate(MOVIE_FIXTURE)
    assert movie.id == 299536
    assert movie.title == "Avengers: Infinity War"
    assert len(movie.genres) == 2
    assert movie.credits is None
    assert movie.videos is None
    assert movie.watch_providers is None


def test_movie_model_with_appended(movie_with_appended: dict) -> None:
    movie = Movie.model_validate(movie_with_appended)

    assert movie.credits is not None
    assert movie.credits.cast[0].name == "Robert Downey Jr."
    assert movie.credits.crew[0].job == "Director"

    assert movie.videos is not None
    assert movie.videos.results[0].key == "QwievZ1Tx-8"
    assert movie.videos.results[0].official is True

    assert movie.watch_providers is not None
    us = movie.watch_providers.results["US"]
    assert us.flatrate[0].provider_name == "Amazon Prime Video"


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_movie_basic() -> None:
    async with TMDBClient() as client:
        client._get = AsyncMock(return_value=MOVIE_FIXTURE)  # type: ignore[method-assign]
        movie = await client.get_movie(299536)

    assert movie.id == 299536
    assert movie.title == "Avengers: Infinity War"
    assert movie.credits is None


@pytest.mark.asyncio
async def test_get_movie_full(movie_with_appended: dict) -> None:
    async with TMDBClient() as client:
        client._get = AsyncMock(return_value=movie_with_appended)  # type: ignore[method-assign]
        movie = await client.get_movie_full(299536)

    assert movie.id == 299536
    assert movie.credits is not None
    assert movie.videos is not None
    assert movie.watch_providers is not None


@pytest.mark.asyncio
async def test_append_to_response_joins_params() -> None:
    async with TMDBClient() as client:
        client._get = AsyncMock(return_value=MOVIE_FIXTURE)  # type: ignore[method-assign]
        await client.get_movie(299536, append_to_response=["credits", "videos"])

    _args, kwargs = client._get.call_args  # type: ignore[union-attr]
    assert kwargs["params"]["append_to_response"] == "credits,videos"


@pytest.mark.asyncio
async def test_get_movie_full_uses_three_appends(movie_with_appended: dict) -> None:
    async with TMDBClient() as client:
        client._get = AsyncMock(return_value=movie_with_appended)  # type: ignore[method-assign]
        await client.get_movie_full(299536)

    _args, kwargs = client._get.call_args  # type: ignore[union-attr]
    appended = kwargs["params"]["append_to_response"]
    assert "credits" in appended
    assert "videos" in appended
    assert "watch/providers" in appended


@pytest.mark.asyncio
async def test_context_manager_opens_and_closes() -> None:
    async with TMDBClient() as client:
        assert client._client is not None
    assert client._client is None


# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limiter_single_acquire() -> None:
    limiter = RateLimiter(rate=3.0)
    await limiter.acquire()  # should not raise or block noticeably


@pytest.mark.asyncio
async def test_rate_limiter_depletes_tokens() -> None:
    limiter = RateLimiter(rate=3.0)
    limiter._tokens = 1.0
    await limiter.acquire()
    assert limiter._tokens == pytest.approx(0.0, abs=1e-3)


# ---------------------------------------------------------------------------
# Retry / backoff tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_on_500_succeeds_second_attempt(movie_with_appended: dict) -> None:
    r500 = MagicMock()
    r500.status_code = 500
    r500.headers = {}

    r200 = MagicMock()
    r200.status_code = 200
    r200.headers = {}
    r200.json.return_value = movie_with_appended
    r200.raise_for_status = MagicMock()

    async with TMDBClient(max_retries=3) as client:
        mock_get = AsyncMock(side_effect=[r500, r200])
        client._client.get = mock_get  # type: ignore[union-attr]
        with patch("src.tmdb.client.asyncio.sleep"):
            movie = await client.get_movie_full(299536)

    assert movie.id == 299536
    assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_retry_on_429_respects_retry_after(movie_with_appended: dict) -> None:
    r429 = MagicMock()
    r429.status_code = 429
    r429.headers = {"Retry-After": "2"}

    r200 = MagicMock()
    r200.status_code = 200
    r200.headers = {}
    r200.json.return_value = movie_with_appended
    r200.raise_for_status = MagicMock()

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    async with TMDBClient(max_retries=3) as client:
        client._client.get = AsyncMock(side_effect=[r429, r200])  # type: ignore[union-attr]
        with patch("src.tmdb.client.asyncio.sleep", side_effect=fake_sleep):
            movie = await client.get_movie_full(299536)

    assert movie.id == 299536
    # retry_after=2, attempt=0 → wait = 2 * 2^0 = 2
    assert sleep_calls[0] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Batch X1 (CR43-06): the scraper's bounded wait, and a final refusal is a 503
# ---------------------------------------------------------------------------


def _refusal(retry_after: str | None) -> MagicMock:
    r429 = MagicMock()
    r429.status_code = 429
    r429.headers = {} if retry_after is None else {"Retry-After": retry_after}
    return r429


def _ok(payload: dict) -> MagicMock:
    r200 = MagicMock()
    r200.status_code = 200
    r200.headers = {}
    r200.json.return_value = payload
    r200.raise_for_status = MagicMock()
    return r200


async def _waits(responses: list[MagicMock], *, max_retries: int = 3) -> list[float]:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    async with TMDBClient(max_retries=max_retries) as client:
        client._client.get = AsyncMock(side_effect=responses)  # type: ignore[union-attr]
        with patch("src.tmdb.client.asyncio.sleep", side_effect=fake_sleep):
            await client.get_movie_full(299536)
    return sleeps


@pytest.mark.asyncio
async def test_a_retry_after_is_honoured_up_to_90_seconds_and_never_doubled(
    movie_with_appended: dict,
) -> None:
    # Before X1: 60 × 2¹ = 120 s on the second refusal, with no ceiling.
    sleeps = await _waits([_refusal("60"), _refusal("60"), _ok(movie_with_appended)])
    assert sleeps == [60.0, 60.0]


@pytest.mark.asyncio
async def test_a_retry_after_over_90_seconds_falls_back_to_the_usual_backoff(
    movie_with_appended: dict,
) -> None:
    sleeps = await _waits([_refusal("3600"), _refusal(None), _ok(movie_with_appended)])
    assert sleeps == [1.0, 2.0]


@pytest.mark.asyncio
async def test_a_retry_after_written_as_a_date_is_read(movie_with_appended: dict) -> None:
    """Before X1 a date-form Retry-After raised an uncaught ValueError."""
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    soon = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
    sleeps = await _waits([_refusal(soon), _ok(movie_with_appended)])
    assert len(sleeps) == 1 and 25.0 <= sleeps[0] <= 31.0


@pytest.mark.asyncio
async def test_a_refusal_on_the_last_try_is_tmdb_refused() -> None:
    from src.tmdb.client import TMDBRefused

    with pytest.raises(TMDBRefused):
        await _waits([_refusal("1"), _refusal("1")], max_retries=1)


@pytest.mark.asyncio
async def test_a_route_answers_tmdbs_refusal_503_in_its_own_words() -> None:
    """Before X1 the RuntimeError reached the person as a 500."""
    import uuid
    from collections.abc import AsyncIterator

    from httpx import ASGITransport, AsyncClient

    from src.auth import get_current_user
    from src.database import get_db
    from src.main import app
    from src.models.profile import Profile, UserRole
    from src.routers.movies import get_tmdb_client
    from src.tmdb.client import TMDBRefused

    class RefusingTmdb:
        async def get_movie_full(self, _tmdb_id: int) -> Movie:
            raise TMDBRefused("TMDB didn't answer. Try again in a moment.")

    async def no_db() -> AsyncIterator[None]:
        yield None

    async def tmdb() -> AsyncIterator[RefusingTmdb]:
        yield RefusingTmdb()

    person = Profile(id=uuid.uuid4(), display_name="Craig", role=UserRole.admin, pin_hash="x")
    app.dependency_overrides[get_current_user] = lambda: person
    app.dependency_overrides[get_db] = no_db
    app.dependency_overrides[get_tmdb_client] = tmdb
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/films/tmdb/603")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "TMDB didn't answer. Try again in a moment."}
