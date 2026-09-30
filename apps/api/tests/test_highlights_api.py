"""Home's Highlights — Batch V5, `DECISIONS.md` #228 ("a mix of all").

Three rows in one request: films on the shelf rated 4½ or 5 and whose ratings those are,
the most rewatched films across both diaries, and the most valuable discs at their stored
value. Every test runs inside a rolled-back transaction, beside the two people the
migrations create, so lists of people are checked by membership rather than equality.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.valuation import DiscValuation
from src.models.watch_log import WatchLog

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _person(session: AsyncSession, name: str, role: UserRole) -> Profile:
    profile = Profile(id=uuid.uuid4(), display_name=f"{name} {uuid.uuid4().hex[:6]}", role=role)
    session.add(profile)
    await session.flush()
    return profile


@pytest_asyncio.fixture
async def rater(api_session: AsyncSession) -> Profile:
    return await _person(api_session, "Rater", UserRole.admin)


@pytest_asyncio.fixture
async def other(api_session: AsyncSession) -> Profile:
    return await _person(api_session, "Other", UserRole.viewer)


@pytest_asyncio.fixture
async def client(api_session: AsyncSession, other: Profile) -> AsyncIterator[AsyncClient]:
    """Signed in as the viewer: the panel is for both people."""

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user() -> Profile:
        return other

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


async def _film(
    session: AsyncSession,
    title: str,
    *,
    formats: list[str] | None = None,
    listing_status: str = "in_collection",
    copies: int = 1,
) -> Movie:
    """A film, with ``copies`` discs of it on the shelf unless ``formats`` is empty."""
    movie = Movie(id=uuid.uuid4(), title=title, original_title=title, year=1990)
    session.add(movie)
    await session.flush()
    if formats != []:
        for _ in range(copies):
            session.add(
                CollectionItem(
                    id=uuid.uuid4(),
                    movie_id=movie.id,
                    formats=formats or ["blu_ray"],
                    listing_status=listing_status,
                )
            )
        await session.flush()
    return movie


async def _watch(
    session: AsyncSession,
    movie: Movie,
    person: Profile,
    on: date,
    rating: str | None = None,
    *,
    deleted: bool = False,
) -> None:
    session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=movie.id,
            user_id=person.id,
            watched_at=on,
            personal_rating=Decimal(rating) if rating is not None else None,
            deleted_at=datetime(2026, 9, 9) if deleted else None,
        )
    )
    await session.flush()


async def _value(
    session: AsyncSession, movie: Movie, fmt: str, price: str | None, *, sample: int = 7
) -> None:
    session.add(
        DiscValuation(
            id=uuid.uuid4(),
            movie_id=movie.id,
            format_code=fmt,
            status="priced" if price is not None else "not_priced",
            price=Decimal(price) if price is not None else None,
            sample_size=sample,
            basis="current asking prices",
            search_query=movie.title,
            checked_utc=datetime(2026, 9, 26, 3, 0),
        )
    )
    await session.flush()


async def _highlights(client: AsyncClient) -> dict[str, object]:
    response = await client.get("/api/v1/highlights")
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def test_every_row_is_empty_when_there_is_nothing_to_show(client: AsyncClient) -> None:
    body = await _highlights(client)
    top = body["topRated"]
    assert isinstance(top, dict)
    assert top["items"] == []
    assert body["mostRewatched"] == []
    assert body["mostValuable"] == []


async def test_top_rated_is_films_on_the_shelf_rated_four_and_a_half_or_five(
    client: AsyncClient, api_session: AsyncSession, rater: Profile, other: Profile
) -> None:
    five = await _film(api_session, "Five Stars")
    four_half = await _film(api_session, "Four And A Half")
    four = await _film(api_session, "Only Four")
    unowned = await _film(api_session, "Not On The Shelf", formats=[])
    sold = await _film(api_session, "Sold On", listing_status="sold")
    changed_mind = await _film(api_session, "Rated Twice")
    deleted = await _film(api_session, "Deleted Viewing")

    await _watch(api_session, five, rater, date(2026, 5, 1), "5.0")
    await _watch(api_session, four_half, rater, date(2026, 6, 1), "4.5")
    await _watch(api_session, four, rater, date(2026, 6, 1), "4.0")
    await _watch(api_session, unowned, rater, date(2026, 6, 1), "5.0")
    await _watch(api_session, sold, rater, date(2026, 6, 1), "5.0")
    # A person's highest rating of a film counts, as "Worth a rewatch" reads it.
    await _watch(api_session, changed_mind, rater, date(2026, 1, 1), "3.0")
    await _watch(api_session, changed_mind, rater, date(2026, 7, 1), "5.0")
    await _watch(api_session, deleted, rater, date(2026, 6, 1), "5.0", deleted=True)

    top = (await _highlights(client))["topRated"]
    assert isinstance(top, dict)
    # Best rating first, then the most recently watched.
    assert [film["title"] for film in top["items"]] == [
        "Rated Twice",
        "Five Stars",
        "Four And A Half",
    ]
    assert top["items"][0]["ratings"] == [{"personName": rater.display_name, "rating": 5.0}]
    assert top["items"][2]["ratings"] == [{"personName": rater.display_name, "rating": 4.5}]
    # Whose ratings these are: #159, Craig rates and Mark does not.
    assert rater.display_name in top["ratedBy"]
    assert other.display_name in top["notRatedBy"]
    assert rater.display_name not in top["notRatedBy"]


async def test_a_film_both_people_rated_names_both(
    client: AsyncClient, api_session: AsyncSession, rater: Profile, other: Profile
) -> None:
    shared = await _film(api_session, "Both Loved It")
    await _watch(api_session, shared, rater, date(2026, 5, 1), "5.0")
    await _watch(api_session, shared, other, date(2026, 5, 2), "4.5")

    top = (await _highlights(client))["topRated"]
    assert isinstance(top, dict)
    (film,) = top["items"]
    assert sorted((r["personName"], r["rating"]) for r in film["ratings"]) == sorted(
        [(rater.display_name, 5.0), (other.display_name, 4.5)]
    )
    assert other.display_name in top["ratedBy"]


async def test_most_rewatched_counts_both_diaries_and_says_whose(
    client: AsyncClient, api_session: AsyncSession, rater: Profile, other: Profile
) -> None:
    thrice = await _film(api_session, "Watched Three Times")
    twice = await _film(api_session, "Watched Twice")
    once = await _film(api_session, "Watched Once")
    not_owned = await _film(api_session, "Seen Twice Elsewhere", formats=[])

    await _watch(api_session, thrice, rater, date(2025, 1, 1))
    await _watch(api_session, thrice, rater, date(2026, 1, 1))
    await _watch(api_session, thrice, other, date(2026, 2, 1))
    await _watch(api_session, twice, other, date(2026, 3, 1))
    await _watch(api_session, twice, other, date(2026, 4, 1))
    await _watch(api_session, twice, other, date(2026, 4, 2), deleted=True)
    await _watch(api_session, once, rater, date(2026, 4, 1))
    await _watch(api_session, not_owned, rater, date(2026, 5, 1))
    await _watch(api_session, not_owned, rater, date(2026, 5, 2))

    rows = (await _highlights(client))["mostRewatched"]
    assert isinstance(rows, list)
    # Across both diaries, not only what is on the shelf; a deleted viewing does not count.
    assert [(row["title"], row["viewings"]) for row in rows] == [
        ("Watched Three Times", 3),
        ("Seen Twice Elsewhere", 2),
        ("Watched Twice", 2),
    ]
    assert sorted((p["personName"], p["viewings"]) for p in rows[0]["byPerson"]) == sorted(
        [(rater.display_name, 2), (other.display_name, 1)]
    )


async def test_most_valuable_is_owned_discs_at_their_stored_value_with_its_basis(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    uhd = await _film(api_session, "Dear 4K", formats=["4k_uhd"], copies=2)
    bluray = await _film(api_session, "Middling Blu-ray", formats=["blu_ray"])
    combo = await _film(api_session, "Combo Pack", formats=["4k_uhd", "blu_ray"])
    unowned = await _film(api_session, "Priced Not Owned", formats=[])
    unpriced = await _film(api_session, "Too Few Listings", formats=["dvd"])

    await _value(api_session, uhd, "4k_uhd", "40.00")
    await _value(api_session, bluray, "blu_ray", "25.50")
    # A combo disc is valued as its best format, so its Blu-ray price is not its value.
    await _value(api_session, combo, "blu_ray", "60.00")
    await _value(api_session, unowned, "4k_uhd", "99.00")
    await _value(api_session, unpriced, "dvd", None)

    rows = (await _highlights(client))["mostValuable"]
    assert isinstance(rows, list)
    assert [(row["title"], row["price"], row["formatCode"]) for row in rows] == [
        ("Dear 4K", "40.00", "4k_uhd"),
        ("Middling Blu-ray", "25.50", "blu_ray"),
    ]
    first = rows[0]
    assert first["basis"] == "current asking prices"
    assert first["sampleSize"] == 7
    assert first["currency"] == "GBP"
    assert first["copies"] == 2
    assert first["checkedAt"].startswith("2026-09-26T03:00:00")


async def test_each_row_is_short(
    client: AsyncClient, api_session: AsyncSession, rater: Profile
) -> None:
    for number in range(15):
        film = await _film(api_session, f"Film {number:02d}")
        await _watch(api_session, film, rater, date(2026, 1, 1 + number), "5.0")
        await _watch(api_session, film, rater, date(2026, 2, 1 + number))
        await _value(api_session, film, "blu_ray", f"{10 + number}.00")

    body = await _highlights(client)
    top = body["topRated"]
    assert isinstance(top, dict)
    assert len(top["items"]) == 12
    assert isinstance(body["mostRewatched"], list) and len(body["mostRewatched"]) == 12
    assert isinstance(body["mostValuable"], list) and len(body["mostValuable"]) == 12


async def test_it_needs_a_signed_in_person(api_session: AsyncSession) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
            response = await anon.get("/api/v1/highlights")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401
