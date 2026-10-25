"""AA6: one read-only owned-film deal, with caller-scoped history and night access."""

import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utcnow
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    MovieNightSuggestion,
    new_invite_token,
)
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    try:
        async with AsyncSession(
            bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
    finally:
        app.dependency_overrides.clear()


async def person(db: AsyncSession) -> Profile:
    p = Profile(
        id=uuid.uuid4(),
        display_name=uuid.uuid4().hex,
        role=UserRole.viewer,
        pin_hash="not-a-real-pin",
    )
    db.add(p)
    await db.flush()
    return p


async def film(db: AsyncSession, *, owned: bool = True, **kwargs: object) -> Movie:
    m = Movie(id=uuid.uuid4(), title=uuid.uuid4().hex, year=1994, **kwargs)
    db.add(m)
    await db.flush()
    if owned:
        db.add(
            CollectionItem(
                id=uuid.uuid4(), movie_id=m.id, formats=["bluray"], section="Front", shelf="2nd"
            )
        )
        await db.flush()
    return m


def client_for(db: AsyncSession, p: Profile) -> AsyncClient:
    async def database() -> AsyncIterator[AsyncSession]:
        yield db

    async def current() -> Profile:
        return p

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def night_for(db: AsyncSession, p: Profile) -> MovieNightSession:
    n = MovieNightSession(
        id=uuid.uuid4(),
        created_by=p.id,
        invite_token=new_invite_token(),
        filters={"decadeFrom": 1990, "decadeTo": 1999, "minRating": 7},
    )
    db.add(n)
    await db.flush()
    db.add(MovieNightParticipant(id=uuid.uuid4(), session_id=n.id, user_id=p.id))
    await db.flush()
    return n


async def test_each_owned_film_once_then_exhausted_and_deal_does_not_write(
    db: AsyncSession,
) -> None:
    p = await person(db)
    seen = [str(x) for x in await db.scalars(select(Movie.id))]
    a, b = await film(db), await film(db)
    # Two copies do not give a film two chances in a run.
    db.add(CollectionItem(id=uuid.uuid4(), movie_id=a.id, formats=["dvd"]))
    await film(db, owned=False)
    await film(db, media_type="tv")
    await film(db, media_type="other")
    await film(db, deleted_at=utcnow())
    sold = await film(db)
    copy = await db.scalar(select(CollectionItem).where(CollectionItem.movie_id == sold.id))
    assert copy is not None
    copy.listing_status = "sold"
    await db.flush()
    counts_before = [
        await db.scalar(select(func.count()).select_from(t))
        for t in (WatchLog, MovieNightSuggestion)
    ]
    dealt = []
    async with client_for(db, p) as c:
        for _ in range(2):
            r = await c.post("/api/v1/feeling-lucky", json={"excludedIds": seen})
            assert r.status_code == 200, r.text
            card = r.json()["film"]
            dealt.append(card["id"])
            seen.append(card["id"])
            assert card["locations"][0]["label"] == "Front 2nd"
        assert (await c.post("/api/v1/feeling-lucky", json={"excludedIds": seen})).json() == {
            "film": None
        }
    assert set(dealt) == {str(a.id), str(b.id)}
    assert counts_before == [
        await db.scalar(select(func.count()).select_from(t))
        for t in (WatchLog, MovieNightSuggestion)
    ]


async def test_unwatched_means_callers_own_live_history(db: AsyncSession) -> None:
    p, other = await person(db), await person(db)
    a, b = await film(db), await film(db)
    db.add_all(
        [
            WatchLog(id=uuid.uuid4(), movie_id=a.id, user_id=p.id, watched_at=date(2026, 10, 20)),
            WatchLog(
                id=uuid.uuid4(), movie_id=b.id, user_id=other.id, watched_at=date(2026, 10, 21)
            ),
            WatchLog(
                id=uuid.uuid4(),
                movie_id=b.id,
                user_id=p.id,
                watched_at=date(2026, 10, 22),
                deleted_at=utcnow(),
            ),
        ]
    )
    await db.flush()
    excluded = [
        str(x) for x in await db.scalars(select(Movie.id).where(Movie.id.not_in([a.id, b.id])))
    ]
    async with client_for(db, p) as c:
        r = await c.post(
            "/api/v1/feeling-lucky", json={"excludedIds": excluded, "unwatchedOnly": True}
        )
        assert r.status_code == 200, r.text
        assert r.json()["film"]["id"] == str(b.id)
        assert r.json()["film"]["watched"] is False
    async with client_for(db, other) as c:
        r = await c.post(
            "/api/v1/feeling-lucky", json={"excludedIds": excluded, "unwatchedOnly": True}
        )
        assert r.json()["film"]["id"] == str(a.id)


async def test_night_filters_existing_picks_and_seed_promotion_pool(db: AsyncSession) -> None:
    p = await person(db)
    n = await night_for(db, p)
    seed = await film(db, tmdb_rating=8)
    already = await film(db, tmdb_rating=8, tmdb_id=998877)
    low = await film(db, tmdb_rating=6)
    old = await film(db, tmdb_rating=8)
    old.year = 1989
    future = await film(db, tmdb_rating=8)
    future.year = 2000
    absent = await film(db, owned=False, tmdb_rating=8)
    db.add_all(
        [
            MovieNightSuggestion(
                id=uuid.uuid4(), session_id=n.id, movie_id=seed.id, title=seed.title
            ),
            MovieNightSuggestion(
                id=uuid.uuid4(),
                session_id=n.id,
                tmdb_id=already.tmdb_id,
                title=already.title,
                suggested_by=p.id,
            ),
        ]
    )
    await db.flush()
    # Keep only this scenario's films eligible: every exclusion above must work in SQL.
    relevant = [seed.id, already.id, low.id, old.id, future.id, absent.id]
    excluded = [str(x) for x in await db.scalars(select(Movie.id).where(Movie.id.not_in(relevant)))]
    async with client_for(db, p) as c:
        r = await c.post(
            "/api/v1/feeling-lucky", json={"sessionId": str(n.id), "excludedIds": excluded}
        )
        assert r.status_code == 200, r.text
        assert r.json()["film"]["id"] == str(seed.id)
        assert (
            await db.scalar(
                select(func.count())
                .select_from(MovieNightSuggestion)
                .where(MovieNightSuggestion.session_id == n.id)
            )
            == 2
        )
        r = await c.post(
            "/api/v1/feeling-lucky",
            json={"sessionId": str(n.id), "excludedIds": [*excluded, str(seed.id)]},
        )
        assert r.json() == {"film": None}


async def test_night_is_private_and_must_be_open(db: AsyncSession) -> None:
    p, other = await person(db), await person(db)
    n = await night_for(db, p)
    async with client_for(db, other) as c:
        assert (
            await c.post("/api/v1/feeling-lucky", json={"sessionId": str(n.id)})
        ).status_code == 404
        assert (
            await c.post("/api/v1/feeling-lucky", json={"sessionId": str(uuid.uuid4())})
        ).status_code == 404
    n.status = "ended"
    await db.flush()
    async with client_for(db, p) as c:
        assert (
            await c.post("/api/v1/feeling-lucky", json={"sessionId": str(n.id)})
        ).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"excludedIds": ["bad-id"]},
        {"excludedIds": [str(uuid.uuid4())] * 10001},
        {"sessionId": "bad-id"},
    ],
)
async def test_invalid_draw_request_is_refused(db: AsyncSession, body: dict[str, object]) -> None:
    async with client_for(db, await person(db)) as c:
        assert (await c.post("/api/v1/feeling-lucky", json=body)).status_code == 422


async def test_anonymous_cannot_deal() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post("/api/v1/feeling-lucky", json={})).status_code == 401
