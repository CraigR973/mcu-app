"""Settling doubts from an agreed plan, against Postgres — `DECISIONS.md` #278. These run in CI.

**What this proves:** each kind of entry settles its doubt through the app's own action,
audited as the person named: a keep, a correction to a film, a correction to a series, one
copy moved and one copy binned; an entry whose doubt was settled since, or whose film was
identified as another since, is skipped and changes nothing; a correction that would merge
into a film the collection holds fails without changing anything; and the dry run's check
reads only.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, cast

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.services.identify.doubts import raise_doubt
from src.services.identify.settle import PlanEntry, check, run_entry
from src.tmdb.client import TMDBClient
from src.tmdb.models import Movie as TmdbMovie
from src.tmdb.models import TvShow


def _ids() -> int:
    return 6_000_000 + uuid.uuid4().int % 900_000


class FakeTmdb:
    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        return TmdbMovie(
            id=movie_id,
            title=f"Film {movie_id}",
            original_title="x",
            overview="",
            release_date="1944-09-01",
        )

    async def get_tv_full(self, tv_id: int, language: str = "en-US") -> TvShow:
        return TvShow(id=tv_id, name=f"Series {tv_id}", first_air_date="2016-11-06")


TMDB = cast(TMDBClient, FakeTmdb())


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def craig(db: AsyncSession) -> Profile:
    person = Profile(
        id=uuid.uuid4(), display_name=f"Craig {uuid.uuid4().hex[:6]}", role=UserRole.admin
    )
    db.add(person)
    await db.flush()
    return person


async def _doubted(
    db: AsyncSession, title: str, *, copies: int = 1
) -> tuple[Movie, list[CollectionItem], IdentifyDoubt]:
    film = Movie(
        id=uuid.uuid4(), title=title, original_title=title, tmdb_id=_ids(), media_type="film"
    )
    db.add(film)
    await db.flush()
    discs = []
    for _ in range(copies):
        disc = CollectionItem(id=uuid.uuid4(), movie_id=film.id, formats=["blu_ray"])
        db.add(disc)
        discs.append(disc)
    await db.flush()
    doubt = await raise_doubt(
        db, film, source="recheck", note="T9 cannot tell.", collection_item_id=discs[0].id
    )
    assert doubt is not None
    await db.commit()
    return film, discs, doubt


def _entry(film: Movie, doubt: IdentifyDoubt, action: str, **extra: Any) -> PlanEntry:
    assert film.tmdb_id is not None
    return PlanEntry.model_validate(
        {"doubt": doubt.id, "expect": film.tmdb_id, "action": action, "title": film.title, **extra}
    )


async def _audits_by(db: AsyncSession, person: Profile) -> int:
    rows = await db.scalars(select(AdminAction).where(AdminAction.user_id == person.id))
    return len(rows.all())


async def test_each_kind_of_entry_settles_its_doubt_as_the_person_named(
    db: AsyncSession, craig: Profile
) -> None:
    kept_film, _, kept = await _doubted(db, "Point Blank")
    wrong_film, _, wrong = await _doubted(db, "Arsenic & Old Lace")
    series_film, _, series = await _doubted(db, "Planet Earth II")
    shared_film, shared_discs, shared = await _doubted(db, "French Connection II", copies=2)
    dup_film, dup_discs, dup = await _doubted(db, "Time Is But a Window")
    film_target, tv_target, move_target = _ids(), _ids(), _ids()

    results = [
        await run_entry(db, _entry(kept_film, kept, "keep"), TMDB, by=craig.id),
        await run_entry(
            db, _entry(wrong_film, wrong, "correct", tmdbId=film_target), TMDB, by=craig.id
        ),
        await run_entry(
            db,
            _entry(series_film, series, "correct", tmdbId=tv_target, media="tv"),
            TMDB,
            by=craig.id,
        ),
        await run_entry(
            db, _entry(shared_film, shared, "move", tmdbId=move_target), TMDB, by=craig.id
        ),
        await run_entry(db, _entry(dup_film, dup, "bin"), TMDB, by=craig.id),
    ]

    assert [state for state, _ in results] == ["done"] * 5, results
    for doubt in (kept, wrong, series, shared):
        await db.refresh(doubt)
    assert [d.status for d in (kept, wrong, series, shared)] == [
        "kept",
        "corrected",
        "corrected",
        "moved",
    ]
    assert {d.decided_by for d in (kept, wrong, series, shared)} == {craig.id}
    await db.refresh(wrong_film)
    await db.refresh(series_film)
    assert wrong_film.tmdb_id == film_target
    assert (series_film.tmdb_id, series_film.tmdb_tv_id) == (None, tv_target)
    await db.refresh(shared_discs[0])
    await db.refresh(shared_discs[1])
    assert shared_discs[0].movie_id != shared_film.id and shared_discs[1].movie_id == shared_film.id
    await db.refresh(dup_discs[0])
    assert dup_discs[0].deleted_at is not None
    assert await _audits_by(db, craig) >= 5


async def test_an_entry_overtaken_since_the_plan_is_skipped_and_changes_nothing(
    db: AsyncSession, craig: Profile
) -> None:
    film, _, doubt = await _doubted(db, "Carrie")
    planned = _entry(film, doubt, "correct", tmdbId=_ids())
    film.tmdb_id = _ids()  # identified as another since the plan
    await db.commit()

    assert await run_entry(db, planned, TMDB, by=craig.id) == (
        "skipped",
        "its film was identified as another since the plan",
    )
    other_film, _, settled = await _doubted(db, "Fright Night")
    settled_entry = _entry(other_film, settled, "keep")
    assert (await run_entry(db, settled_entry, TMDB, by=craig.id))[0] == "done"
    assert await run_entry(db, settled_entry, TMDB, by=craig.id) == (
        "skipped",
        "already settled (kept)",
    )
    await db.refresh(doubt)
    assert doubt.status == "open"


async def test_a_correction_into_a_film_the_collection_holds_fails_and_changes_nothing(
    db: AsyncSession, craig: Profile
) -> None:
    held, _, _ = await _doubted(db, "Holiday (1938)")
    film, _, doubt = await _doubted(db, "The Holiday")
    held_id = held.tmdb_id
    assert held_id is not None
    state, why = await run_entry(
        db, _entry(film, doubt, "correct", tmdbId=held_id), TMDB, by=craig.id
    )

    assert state == "failed" and "merges the two" in why
    await db.refresh(doubt)
    await db.refresh(film)
    assert doubt.status == "open" and film.tmdb_id != held_id


async def test_the_check_reads_only_and_names_a_missing_copy(
    db: AsyncSession, craig: Profile
) -> None:
    film, discs, doubt = await _doubted(db, "Ghostbusters 2")
    discs[0].deleted_at = datetime(2026, 10, 17)
    await db.commit()

    checked = await check(db, _entry(film, doubt, "bin"))
    assert checked.skip == "the copy it names has moved or gone"
    assert await _audits_by(db, craig) == 0


def test_a_plan_entry_names_a_target_exactly_when_it_needs_one() -> None:
    doubt = uuid.uuid4()
    with pytest.raises(ValueError):
        PlanEntry.model_validate({"doubt": doubt, "expect": 1, "action": "correct"})
    with pytest.raises(ValueError):
        PlanEntry.model_validate({"doubt": doubt, "expect": 1, "action": "keep", "tmdbId": 5})
