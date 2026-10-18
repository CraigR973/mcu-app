"""Leftover film rows — Batch X10 (CT46-04, `DECISIONS.md` #280). Postgres-backed.

The 18 Sep refresh left rows holding only a binned copy. They are listed, and put in the Trash
only when nothing a person did is on them.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from src.services.leftover_films import leftover_films, remove


@pytest_asyncio.fixture
async def db_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _film(
    db: AsyncSession, title: str, *, tmdb_id: int | None = None, copies: tuple[bool, ...] = (True,)
) -> Movie:
    """A film with one copy per entry, binned when the entry is True."""
    movie = Movie(id=uuid.uuid4(), title=title, original_title=title, tmdb_id=tmdb_id)
    db.add(movie)
    await db.flush()
    for binned in copies:
        db.add(
            CollectionItem(
                id=uuid.uuid4(),
                movie_id=movie.id,
                formats=["dvd"],
                deleted_at=_now() if binned else None,
            )
        )
    await db.flush()
    return movie


async def _craig(db: AsyncSession) -> Profile:
    craig = Profile(
        id=uuid.uuid4(), display_name=f"Craig {uuid.uuid4().hex[:6]}", role=UserRole.admin
    )
    db.add(craig)
    await db.flush()
    return craig


async def _ids(db: AsyncSession) -> set[uuid.UUID]:
    return {row.movie_id for row in await leftover_films(db)}


async def test_a_row_holding_only_binned_copies_is_a_leftover(db_session: AsyncSession) -> None:
    dunkirk = await _film(db_session, "Dunkirk", copies=(True,))
    owned = await _film(db_session, "Titanic", copies=(True, False))
    identified = await _film(db_session, "Halloween", tmdb_id=948, copies=(True,))
    empty = await _film(db_session, "Carjackers", copies=())

    found = await _ids(db_session)

    assert dunkirk.id in found
    assert owned.id not in found  # one copy still on the shelf
    assert identified.id not in found  # a TMDB film is a film, copies or not
    assert empty.id not in found  # never had a copy: not something binning left


async def test_a_watch_or_a_want_keeps_the_row(db_session: AsyncSession) -> None:
    watched = await _film(db_session, "Misery")
    wanted = await _film(db_session, "Sorcerer, The (1977)")
    craig = await _craig(db_session)
    db_session.add(
        WatchLog(
            id=uuid.uuid4(), user_id=craig.id, movie_id=watched.id, watched_at=date(2026, 9, 1)
        )
    )
    db_session.add(WantedItem(id=uuid.uuid4(), movie_id=wanted.id))
    await db_session.flush()

    found = await _ids(db_session)

    assert watched.id not in found
    assert wanted.id not in found


async def test_removing_puts_it_in_the_trash_audited(db_session: AsyncSession) -> None:
    edge = await _film(db_session, "Edge of Darkness")
    craig = await _craig(db_session)

    assert await remove(db_session, edge.id, by=craig.id) is True

    await db_session.refresh(edge)
    assert edge.deleted_at is not None
    audit = (
        await db_session.execute(select(AdminAction).where(AdminAction.target_id == str(edge.id)))
    ).scalar_one()
    assert (audit.action_type, audit.target_table, audit.user_id) == ("delete", "movies", craig.id)
    assert edge.id not in await _ids(db_session)


async def test_a_row_that_changed_since_the_listing_is_skipped(db_session: AsyncSession) -> None:
    ghost = await _film(db_session, "Ghostbusters")
    craig = await _craig(db_session)
    # A copy restored from the Trash after the dry run.
    copy = (
        await db_session.execute(select(CollectionItem).where(CollectionItem.movie_id == ghost.id))
    ).scalar_one()
    copy.deleted_at = None
    await db_session.flush()

    assert await remove(db_session, ghost.id, by=craig.id) is False
    await db_session.refresh(ghost)
    assert ghost.deleted_at is None
