"""Batch X12c (DS44-06): TMDB's data on a film is fetched again once it is 150 days old.

TMDB's terms bar caching its data for longer than six months, and nothing fetched a film
again after it was identified: 1,051 films were last synced on 8 Sep. What is pinned here is
which films qualify, what a refresh writes and leaves alone, and that one failure stops
nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.collection_item import CollectionItem
from src.models.movie import Movie, MovieCredit
from src.services.tmdb_refresh import BATCH_SIZE, STALE_AFTER, refresh_stale_fields
from src.tmdb.models import CastMember, Credits, Genre
from src.tmdb.models import Movie as TmdbMovie

NOW = datetime(2027, 2, 10, 4, 0)


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


class FakeTmdb:
    def __init__(self, *, failing: set[int] | None = None) -> None:
        self.asked: list[int] = []
        self._failing = failing or set()

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        del language
        self.asked.append(movie_id)
        if movie_id in self._failing:
            raise RuntimeError("TMDB removed this film")
        return TmdbMovie(
            id=movie_id,
            title="The Title Now",
            original_title="The Title Now",
            overview="Fresh overview.",
            release_date="1979-05-25",
            runtime=117,
            vote_average=8.1,
            vote_count=12000,
            poster_path="/fresh.jpg",
            genres=[Genre(id=27, name="Horror")],
            credits=Credits(
                cast=[
                    CastMember(id=1, name="Fresh Actor", character="Lead", order=0, credit_id="c1")
                ],
                crew=[],
            ),
        )


async def _film(
    db: AsyncSession, tmdb_id: int, synced: datetime | None, *, title: str = "Old Title"
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=1979,
        overview="Stale overview.",
        last_tmdb_sync_utc=synced,
    )
    db.add(movie)
    await db.flush()
    db.add(CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["blu_ray"]))
    db.add(
        MovieCredit(
            id=uuid.uuid4(),
            movie_id=movie.id,
            person_name="Stale Actor",
            tmdb_person_id=99,
            role="cast",
            display_order=0,
        )
    )
    await db.flush()
    return movie


async def test_only_a_film_older_than_150_days_is_refreshed_and_its_data_is_replaced(
    db: AsyncSession,
) -> None:
    old = await _film(db, 7_700_001, NOW - STALE_AFTER - timedelta(days=1))
    fresh = await _film(db, 7_700_002, NOW - timedelta(days=149))
    never = await _film(db, 7_700_003, None)

    tmdb = FakeTmdb()
    result = await refresh_stale_fields(db, tmdb, now=NOW)  # type: ignore[arg-type]

    assert tmdb.asked == [7_700_001], "a film with no sync date is unknown, not old"
    assert (result.refreshed, result.failed) == (1, 0)
    await db.refresh(old)
    assert old.title == "The Title Now" and old.overview == "Fresh overview."
    assert old.last_tmdb_sync_utc == NOW
    credits = (
        await db.scalars(select(MovieCredit.person_name).where(MovieCredit.movie_id == old.id))
    ).all()
    assert list(credits) == ["Fresh Actor"]
    for untouched in (fresh, never):
        await db.refresh(untouched)
        assert untouched.overview == "Stale overview."


async def test_a_refresh_leaves_the_copies_alone(db: AsyncSession) -> None:
    old = await _film(db, 7_700_011, NOW - timedelta(days=200))
    await refresh_stale_fields(db, FakeTmdb(), now=NOW)  # type: ignore[arg-type]
    copies = (
        await db.scalars(select(CollectionItem).where(CollectionItem.movie_id == old.id))
    ).all()
    assert len(copies) == 1 and copies[0].formats == ["blu_ray"]


async def test_one_film_tmdb_has_removed_does_not_stop_the_rest(db: AsyncSession) -> None:
    gone = await _film(db, 7_700_021, NOW - timedelta(days=300), title="Gone From TMDB")
    stays = await _film(db, 7_700_022, NOW - timedelta(days=200))

    result = await refresh_stale_fields(db, FakeTmdb(failing={7_700_021}), now=NOW)  # type: ignore[arg-type]

    assert (result.refreshed, result.failed) == (1, 1)
    assert "Gone From TMDB" in result.errors[0]
    await db.refresh(gone)
    await db.refresh(stays)
    assert gone.overview == "Stale overview." and stays.overview == "Fresh overview."
    assert result.remaining == 1, "the failed film is tried again next time"


async def test_the_stalest_go_first_and_a_batch_is_capped(db: AsyncSession) -> None:
    films = [await _film(db, 7_700_100 + n, NOW - timedelta(days=200 + n)) for n in range(5)]
    tmdb = FakeTmdb()
    result = await refresh_stale_fields(db, tmdb, now=NOW, limit=2)  # type: ignore[arg-type]

    assert tmdb.asked == [7_700_104, 7_700_103], "oldest first"
    assert result.refreshed == 2 and result.remaining == 3
    assert BATCH_SIZE == 100
    del films
