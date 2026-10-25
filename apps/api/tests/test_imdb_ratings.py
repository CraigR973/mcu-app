"""The real gzip/TSV path and atomic cache, with no request to IMDb."""

from __future__ import annotations

import asyncio
import gzip
import io
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.movie import Movie
from src.models.movie_night import MovieNightSession, MovieNightSuggestion, new_invite_token
from src.models.profile import Profile, UserRole
from src.services.imdb_ratings import read_ratings, refresh_ratings

HEADER = "tconst\taverageRating\tnumVotes\n"
GOOD = HEADER + "tt0000001\t7.8\t42\ntt0000002\t8.2\t1234\ntt9999999\t3.0\t1\n"
NOW = datetime(2026, 10, 25, 2)


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        yield session


def parse(text: str) -> tuple:
    return read_ratings(io.BytesIO(gzip.compress(text.encode())), {"tt0000001"})


def test_reads_the_documented_columns_and_keeps_only_stored_ids() -> None:
    ratings, rows = parse(GOOD)
    assert rows == 3
    assert set(ratings) == {"tt0000001"}
    assert (ratings["tt0000001"].score, ratings["tt0000001"].votes) == (Decimal("7.8"), 42)


@pytest.mark.parametrize(
    "text",
    [
        "wrong\theader\n",
        HEADER,
        HEADER + "tt0000001\tNaN\t2\n",
        HEADER + "tt0000001\t11\t2\n",
        HEADER + "tt0000001\t7\t-1\n",
        HEADER + "not-an-id\t7\t2\n",
        HEADER + "tt0000001\t7\t2\tmore\n",
        HEADER + "tt0000001\t7\t2\ntt0000001\t8\t3\n",
    ],
)
def test_rejects_changed_empty_invalid_or_ambiguous_files(text: str) -> None:
    with pytest.raises(ValueError):
        parse(text)


def test_rejects_a_truncated_gzip_even_after_a_matching_row() -> None:
    with pytest.raises((EOFError, gzip.BadGzipFile)):
        read_ratings(io.BytesIO(gzip.compress(GOOD.encode())[:-8]), {"tt0000001"})


async def seed(db: AsyncSession) -> tuple[Movie, MovieNightSuggestion]:
    person = Profile(
        id=uuid.uuid4(), display_name=f"imdb-{uuid.uuid4().hex[:8]}", role=UserRole.admin
    )
    db.add(person)
    await db.flush()
    session = MovieNightSession(
        id=uuid.uuid4(), created_by=person.id, invite_token=new_invite_token(), filters={}
    )
    db.add(session)
    await db.flush()
    movie = Movie(
        id=uuid.uuid4(),
        title="Shelf film",
        imdb_id="tt0000001",
        imdb_ratings_id="tt0000001",
        imdb_rating=Decimal("6.0"),
        imdb_vote_count=50,
        imdb_ratings_checked_utc=NOW - timedelta(days=1),
    )
    pick = MovieNightSuggestion(
        id=uuid.uuid4(),
        session_id=session.id,
        tmdb_id=99,
        title="Outside film",
        imdb_id="tt0000002",
        imdb_ratings_id="tt0000002",
        imdb_rating=Decimal("5.0"),
        imdb_vote_count=20,
        imdb_ratings_checked_utc=NOW - timedelta(days=1),
    )
    db.add_all([movie, pick])
    await db.commit()
    return movie, pick


async def test_updates_both_caches_and_releases_the_read_transaction_for_the_download(
    db: AsyncSession,
) -> None:
    movie, pick = await seed(db)

    def answer(request: httpx.Request) -> httpx.Response:
        assert not db.in_transaction()
        assert str(request.url) == "https://datasets.imdbws.com/title.ratings.tsv.gz"
        return httpx.Response(200, content=gzip.compress(GOOD.encode()))

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        result = await refresh_ratings(db, client, now=NOW)
    assert (result.rows, result.matched, result.updated) == (3, 2, 2)
    await db.refresh(movie)
    await db.refresh(pick)
    assert (movie.imdb_rating, movie.imdb_vote_count, movie.imdb_ratings_checked_utc) == (
        Decimal("7.8"),
        42,
        NOW,
    )
    assert (pick.imdb_rating, pick.imdb_vote_count, pick.imdb_ratings_id) == (
        Decimal("8.2"),
        1234,
        "tt0000002",
    )


@pytest.mark.parametrize("fault", ["refused", "truncated", "wrong_header", "no_matches"])
async def test_a_bad_or_refused_file_preserves_all_previous_scores(
    db: AsyncSession, fault: str
) -> None:
    movie, pick = await seed(db)
    data = gzip.compress(GOOD.encode())
    status = 200
    if fault == "refused":
        status = 503
    elif fault == "truncated":
        data = data[:-8]
    elif fault == "wrong_header":
        data = gzip.compress(b"different\n")
    else:
        data = gzip.compress((HEADER + "tt8888888\t9.0\t1\n").encode())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, content=data))
    ) as client:
        expected = (
            httpx.HTTPStatusError
            if fault == "refused"
            else EOFError
            if fault == "truncated"
            else ValueError
        )
        with pytest.raises(expected):
            await refresh_ratings(db, client, now=NOW)
    await db.refresh(movie)
    await db.refresh(pick)
    assert (movie.imdb_rating, pick.imdb_rating) == (Decimal("6.0"), Decimal("5.0"))
    assert movie.imdb_ratings_checked_utc == NOW - timedelta(days=1)


async def test_a_valid_file_clears_only_an_absent_id_and_keeps_a_newer_cache(
    db: AsyncSession,
) -> None:
    movie, pick = await seed(db)
    movie.imdb_ratings_checked_utc = NOW + timedelta(hours=1)
    await db.commit()
    data = gzip.compress((HEADER + "tt0000001\t2.0\t3\n").encode())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=data))
    ) as client:
        await refresh_ratings(db, client, now=NOW)
    await db.refresh(movie)
    await db.refresh(pick)
    assert movie.imdb_rating == Decimal("6.0")
    assert pick.imdb_rating is None and pick.imdb_vote_count is None
    assert pick.imdb_ratings_checked_utc == NOW and pick.imdb_ratings_id == "tt0000002"


def test_the_documented_null_marker_is_not_a_bad_file_or_an_invented_score() -> None:
    found, rows = parse(HEADER + "tt0000001\t\\N\t\\N\n")
    assert rows == 1 and found == {"tt0000001": None}
    found, _ = parse(HEADER + "tt0000001\t7.8\t\\N\n")
    assert found["tt0000001"] is not None
    assert found["tt0000001"].score == Decimal("7.8")
    assert found["tt0000001"].votes is None


def test_the_cache_keeps_source_precision_and_follows_current_identity() -> None:
    from src.services.movie_night.details import imdb_details

    movie = Movie(imdb_id="tt0000001")
    suggestion = MovieNightSuggestion(
        imdb_id="tt0000001",
        imdb_ratings_id="tt0000001",
        imdb_rating=Decimal("8.23"),
        imdb_vote_count=123,
        imdb_ratings_checked_utc=NOW,
    )
    assert imdb_details(movie, suggestion) == ("tt0000001", Decimal("8.23"), 123, NOW)
    movie.imdb_id = "tt0000002"
    assert imdb_details(movie, suggestion) == ("tt0000002", None, None, None)


@pytest.mark.parametrize("score,votes", [("1e-999999999", "2"), ("8.2", "2147483648")])
def test_numeric_values_are_bounded_before_database_encoding(score: str, votes: str) -> None:
    with pytest.raises(ValueError):
        parse(HEADER + f"tt0000001\t{score}\t{votes}\n")


async def test_a_stalled_download_has_a_whole_request_deadline_and_keeps_scores(
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.services.imdb_ratings as ratings

    movie, pick = await seed(db)
    monkeypatch.setattr(ratings, "DOWNLOAD_SECONDS", 0.02)

    class Stalled(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"still waiting"
            await asyncio.Event().wait()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Stalled()))
    ) as client:
        with pytest.raises(TimeoutError):
            await refresh_ratings(db, client, now=NOW)
    await db.refresh(movie)
    await db.refresh(pick)
    assert movie.imdb_rating == Decimal("6.0") and pick.imdb_rating == Decimal("5.0")
