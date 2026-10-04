"""`POST /deals/scrape` against Postgres, over the two sale pages captured on 28-30 Sep —
Batch 22b. These run in CI.

**What this proves:** a viewer is refused before any shop is asked; `apply-built-ins` is
what gives Zavvi and Second Sight their sale pages, as in production; the preview reads
both captured pages through the real runner, reports §5.9's three numbers and each shop's
found, kept and not-discounted counts, and saves nothing; saving writes what the preview
reported, skips a film already owned in that format, keeps an upgrade, and a second save
refreshes rather than duplicates.

**What it does not:** a live request. `fetch_page` is replaced by the captured files.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.deal import Deal
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import Retailer
from src.services.scraping import deals_runner
from src.services.scraping.fetcher import FetchedPage, FetchError

FIXTURES = Path(__file__).parent / "fixtures"
ZAVVI_URL = "https://www.zavvi.com/c/offers/2-for-30-4k/"
SECOND_SIGHT_URL = "https://secondsightfilms.co.uk/collections/sale"
PAGES = {
    ZAVVI_URL: (FIXTURES / "zavvi_2_for_30_4k.html").read_text(),
    SECOND_SIGHT_URL: (FIXTURES / "secondsight_sale_collection.html").read_text(),
}


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def fetches(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every sale page the runner asked for, answered from the captures."""
    asked: list[str] = []

    async def from_capture(url: str) -> FetchedPage:
        asked.append(url)
        if url not in PAGES:
            raise FetchError("The page answered 404")
        return FetchedPage(url=url, status=200, html=PAGES[url], final_url=url)

    monkeypatch.setattr(deals_runner, "fetch_page", from_capture)
    return asked


async def _person(db: AsyncSession, role: UserRole) -> uuid.UUID:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"{role.value} {uuid.uuid4().hex[:6]}",
        role=role,
        pin_hash="test-pin-hash",
    )
    db.add(person)
    await db.flush()
    return person.id


def _as(db: AsyncSession, person_id: uuid.UUID) -> AsyncClient:
    # By id, and the profile read again on each request: a refused request rolls the
    # shared session back, which expires every object in it.

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        fresh = await db.get(Profile, person_id)
        assert fresh is not None
        return fresh

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _shops(db: AsyncSession) -> None:
    """The two shops as Batch 18 seeds them: a name and an address, nothing configured."""
    for name, base in (
        ("Zavvi", "https://www.zavvi.com"),
        ("Second Sight", "https://secondsightfilms.co.uk"),
    ):
        db.add(
            Retailer(
                id=uuid.uuid4(),
                name=name,
                base_url=base,
                scraper_type="built_in",
                scraper_config={},
                enabled=True,
                currency="GBP",
            )
        )
    await db.flush()


async def _owned(
    db: AsyncSession, title: str, formats: list[str], *, year: int | None = None
) -> None:
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        year=year,
        media_type="film",
    )
    db.add(film)
    await db.flush()
    db.add(CollectionItem(id=uuid.uuid4(), movie_id=film.id, formats=formats))
    await db.flush()


async def _deal_count(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(Deal)) or 0)


async def test_a_viewer_cannot_check_the_sale_pages_and_no_shop_is_asked(
    db: AsyncSession, fetches: list[str]
) -> None:
    viewer_id = await _person(db, UserRole.viewer)
    await _shops(db)

    async with _as(db, viewer_id) as client:
        response = await client.post("/api/v1/deals/scrape")

    assert response.status_code == 403
    assert fetches == []


async def test_the_preview_reads_both_pages_and_saves_nothing(
    db: AsyncSession, fetches: list[str]
) -> None:
    admin_id = await _person(db, UserRole.admin)
    await _shops(db)

    async with _as(db, admin_id) as client:
        assert (await client.post("/api/v1/scrapers/apply-built-ins")).status_code == 200
        response = await client.post("/api/v1/deals/scrape")

    assert response.status_code == 200
    body = response.json()
    assert body["dryRun"] is True
    # Eleven Zavvi discounts and Second Sight's one; nothing owned in this database.
    assert (body["written"], body["retailersWithDeals"], body["skippedOwned"]) == (12, 2, 0)

    outcomes = {outcome["retailer"]: outcome for outcome in body["outcomes"]}
    zavvi, second_sight = outcomes["Zavvi"], outcomes["Second Sight"]
    assert (zavvi["found"], zavvi["kept"], zavvi["notDiscounted"], zavvi["rejected"]) == (
        12,
        11,
        1,
        0,
    )
    assert (
        second_sight["found"],
        second_sight["kept"],
        second_sight["notDiscounted"],
        second_sight["rejected"],
    ) == (16, 1, 15, 0)
    for outcome in (zavvi, second_sight):
        assert outcome["ok"] is True
        assert outcome["pageReasons"] == []
        assert outcome["rejectedReasons"] == []
        assert outcome["error"] is None

    assert sorted(fetches) == sorted([ZAVVI_URL, SECOND_SIGHT_URL])
    assert await _deal_count(db) == 0


async def test_saving_skips_what_is_owned_keeps_an_upgrade_and_does_not_duplicate(
    db: AsyncSession, fetches: list[str]
) -> None:
    """Jurassic World and the 2017 Mummy are owned on 4K, the format on offer, so both are
    skipped. Spectre is owned on DVD, so the 4K is an upgrade and is kept.

    The Mummy and Spectre are titles whose longest word is the shop's own (*download*,
    *includes*); before Batch 22b neither found its film at all. And the 1999 Mummy, owned
    on Blu-ray, must not take the 2017 listing: by its words alone it would, and the deal
    would come through as an upgrade of a film already on the shelf in 4K.
    """
    admin_id = await _person(db, UserRole.admin)
    await _shops(db)
    await _owned(db, "Jurassic World", ["4k_uhd"])
    await _owned(db, "The Mummy", ["blu_ray"], year=1999)
    await _owned(db, "The Mummy", ["4k_uhd"], year=2017)
    await _owned(db, "Spectre", ["dvd"])

    async with _as(db, admin_id) as client:
        assert (await client.post("/api/v1/scrapers/apply-built-ins")).status_code == 200
        saved = (await client.post("/api/v1/deals/scrape?dryRun=false")).json()
        again = (await client.post("/api/v1/deals/scrape?dryRun=false")).json()
        feed = (await client.get("/api/v1/deals")).json()

    assert saved["dryRun"] is False
    assert (saved["written"], saved["retailersWithDeals"], saved["skippedOwned"]) == (10, 2, 2)
    assert await _deal_count(db) == 10
    # A second run refreshes the same rows rather than adding ten more.
    assert again["written"] == 10
    assert await _deal_count(db) == 10

    titles = {item["title"]: item for item in feed["items"]}
    assert "Jurassic World - Ultra HD 4K" not in titles
    assert "The Mummy (2017) - 4K Ultra HD (Includes Digital Download)" not in titles
    assert "Harvey 4K Ultra HD" not in titles
    spectre = titles["Spectre - 4K Ultra HD (Includes 2D Blu-ray)"]
    assert (spectre["formatCode"], spectre["discountPercent"]) == ("4k_uhd", 47)
    assert spectre["movieId"] is not None
    dog_soldiers = titles["Dog Soldiers Standard Edition 4K UHD"]
    assert (dog_soldiers["retailer"], dog_soldiers["price"], dog_soldiers["wasPrice"]) == (
        "Second Sight",
        "17.99",
        "24.99",
    )
