"""AA10a's weekly used-listing pass against a throwaway Postgres and scripted eBay."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.models.collection_item import CollectionItem
from src.models.ebay_sold import EbayUsedListing, EbayUsedRun
from src.models.movie import Movie
from src.models.valuation import DiscValuation
from src.routers.valuation import copy_valuation
from src.services.ebay_sold import (
    DAILY_SHARE,
    TrackedDisc,
    end_verdict,
    observed,
    purge_ended,
    start_run,
    work_run,
)
from src.services.valuation import collection_value

NOW = datetime(2026, 10, 21, 12)


def summary(item_id: str, price: str) -> dict[str, Any]:
    return {
        "itemId": f"v1|{item_id}|0",
        "legacyItemId": item_id,
        "title": "Jaws Blu-ray used",
        "leafCategoryIds": ["617"],
        "price": {"value": price, "currency": "GBP"},
        "conditionId": "5000",
        "buyingOptions": ["FIXED_PRICE"],
        "itemLocation": {"country": "GB"},
        "shippingOptions": [{"shippingCost": {"value": "2.00", "currency": "GBP"}}],
        "image": {"imageUrl": "https://example.invalid/never-store.jpg"},
    }


def sold_detail(when: datetime, count: int) -> dict[str, Any]:
    return {
        "itemEndDate": when.isoformat() + "Z",
        "estimatedAvailabilities": [
            {"estimatedAvailabilityStatus": "OUT_OF_STOCK", "estimatedSoldQuantity": count}
        ],
    }


class FakeEbay:
    marketplace_id = "EBAY_GB"
    attempts_per_search = 1

    def __init__(self) -> None:
        self.search_calls = 0
        self.results: list[dict[str, Any]] = []
        self.details: dict[str, dict[str, Any] | None] = {}
        self.searches = 0
        self.checked: list[str] = []

    async def search(self, query: str, **kwargs: object) -> dict[str, Any]:
        assert query == "Jaws Blu-ray"
        assert kwargs["filter"] == "buyingOptions:{FIXED_PRICE}"
        self.search_calls += 1
        self.searches += 1
        return {"itemSummaries": self.results}

    async def get_item_by_legacy_id(self, legacy_item_id: str) -> dict[str, Any] | None:
        self.search_calls += 1
        self.checked.append(legacy_item_id)
        return self.details[legacy_item_id]


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        yield session


async def film_with_disc(db: AsyncSession) -> Movie:
    film = Movie(
        id=uuid.uuid4(),
        tmdb_id=990_001_975,
        title="Jaws",
        original_title="Jaws",
        year=1975,
        media_type="film",
    )
    db.add(film)
    await db.flush()
    db.add(
        CollectionItem(
            id=uuid.uuid4(), movie_id=film.id, formats=["blu_ray"], listing_status="in_collection"
        )
    )
    await db.flush()
    return film


def test_only_comparable_used_listings_are_observed() -> None:
    disc = TrackedDisc(uuid.uuid4(), "blu_ray", "Jaws", True, 1975, False)
    good = summary("1", "10.00")
    assert observed(good, disc) is not None
    for changed in (
        {"conditionId": "1000"},
        {"itemLocation": {"country": "US"}},
        {"title": "Jaws Blu-ray limited edition"},
        {"buyingOptions": ["AUCTION"]},
        {"shippingOptions": []},
    ):
        assert observed(good | changed, disc) is None
    assert "title" not in EbayUsedListing.__table__.columns
    assert "image" not in EbayUsedListing.__table__.columns


def test_sold_requires_out_of_stock_and_positive_sold_count() -> None:
    assert end_verdict(sold_detail(NOW, 2), now=NOW).status == "sold"
    assert end_verdict(sold_detail(NOW, 0), now=NOW).status == "ended"
    assert end_verdict(None, now=NOW).status == "ended"
    assert end_verdict({"estimatedAvailabilities": []}, now=NOW).status == "active"


async def test_weekly_pass_values_three_sales_and_relisted_item(db: AsyncSession) -> None:
    film = await film_with_disc(db)
    client = FakeEbay()
    client.results = [
        summary("1", "10.00"),
        summary("2", "14.00"),
        summary("3", "20.00"),
        summary("4", "25.00"),
    ]

    reason, run = await start_run(db, trigger="job", now=NOW)
    assert reason == "inactive" and run is None
    reason, run = await start_run(db, trigger="admin", now=NOW)
    assert reason == "started" and run is not None
    first = await work_run(db, client, run.id, clock=lambda: NOW)
    assert first.status == "finished" and first.searched == 1 and first.checked == 0
    assert client.searches == 1
    assert len((await db.scalars(select(EbayUsedListing))).all()) == 4

    next_week = NOW + timedelta(days=8)
    client.results = []
    client.details = {
        "1": sold_detail(next_week, 1),
        "2": sold_detail(next_week, 5),
        "3": sold_detail(next_week, 1),
        "4": None,  # Withdrawn: an absent item cannot be called sold.
    }
    reason, run = await start_run(db, trigger="job", now=next_week)
    assert reason == "started" and run is not None
    second = await work_run(db, client, run.id, clock=lambda: next_week)
    assert (second.searched, second.checked, second.sold, second.ended) == (1, 4, 3, 1)
    assert sorted(client.checked) == ["1", "2", "3", "4"]
    valuation = await db.scalar(select(DiscValuation).where(DiscValuation.movie_id == film.id))
    assert valuation is not None
    assert valuation.sales_count == 3  # one observed listing, not five unknowable unit prices
    assert valuation.sales_price == Decimal("16.00")  # 12, 16, 22 postage in
    assert valuation.effective_price == Decimal("16.00")
    total = await collection_value(db, now=next_week)
    assert (total.total, total.priced, total.sales_backed) == (Decimal("16.00"), 1, 1)
    copy = copy_valuation(valuation)
    assert (copy.price, copy.valueBasis, copy.sampleSize) == ("16.00", "sales", 3)

    another_week = next_week + timedelta(days=8)
    client.results = [summary("5", "11.00")]  # Seller relisted with a new item number.
    reason, run = await start_run(db, trigger="job", now=another_week)
    assert reason == "started" and run is not None
    await work_run(db, client, run.id, clock=lambda: another_week)
    relisted = await db.scalar(select(EbayUsedListing).where(EbayUsedListing.legacy_item_id == "5"))
    assert relisted is not None and relisted.status == "active"
    assert valuation.sales_count == 3  # A new ask does not erase three observed sales.

    assert await purge_ended(db, now=next_week + timedelta(days=91)) == 4
    assert valuation.sales_count == 0 and valuation.sales_price is None
    assert valuation.effective_price is None
    left = (await db.scalars(select(EbayUsedListing))).all()
    assert [listing.legacy_item_id for listing in left] == ["5"]


async def test_daily_share_blocks_another_pass(db: AsyncSession) -> None:
    db.add(
        EbayUsedRun(
            id=uuid.uuid4(),
            trigger="admin",
            status="finished",
            started_utc=NOW,
            heartbeat_utc=NOW,
            finished_utc=NOW,
            budget=DAILY_SHARE,
            calls=DAILY_SHARE,
            searched=1,
            checked=0,
            sold=0,
            ended=0,
        )
    )
    await db.commit()
    reason, run = await start_run(db, trigger="job", now=NOW + timedelta(hours=1))
    assert reason == "budget_spent" and run is None
