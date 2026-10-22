"""Shared pytest fixtures for the async application spine."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from src.config import Settings


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Keep unit tests in the development validation profile by default."""
    os.environ.setdefault("ENVIRONMENT", "development")


def _async_database_url(value: str) -> str:
    return Settings(database_url=value).database_url


DATABASE_URL = os.environ.get("DATABASE_URL")


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Provide a live Postgres engine, or skip explicitly when none is configured."""
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set — Postgres-backed tests skipped")
    engine = create_async_engine(_async_database_url(DATABASE_URL))
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_conn(db_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Give each database test a connection whose writes are rolled back."""
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


@pytest.fixture(autouse=True)
def _no_background_calendar_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch T5: a stale calendar read starts a refresh on a session of its own.

    In a test that session is a real one, outside the test's rolled-back transaction, so
    a refresh would commit rows (the curated sale events) into the shared test database
    and break whichever test counted them next. CI found exactly that. Tests that are
    about the refresh replace this no-op with a recorder.
    """
    import src.routers.calendar as calendar_router

    async def _skip() -> None:
        return None

    monkeypatch.setattr(calendar_router, "refresh_calendar_if_stale", _skip)


@pytest.fixture(autouse=True)
def _no_background_valuation_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch T6: the Home button's run carries on after the response, the same way.

    It opens a real session and a real eBay client of its own, so in a test it would write
    outside the rolled-back transaction and try to reach eBay. Tests about the button
    replace this no-op with a recorder.
    """
    import uuid

    import src.routers.valuation as valuation_router

    async def _skip(run_id: uuid.UUID) -> None:
        del run_id

    monkeypatch.setattr(valuation_router, "continue_run_in_background", _skip)


@pytest.fixture(autouse=True)
def _no_background_used_sales_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the owner-started eBay pass inside its test transaction and fake client."""
    import uuid

    import src.routers.valuation as valuation_router

    async def _skip(run_id: uuid.UUID) -> None:
        del run_id

    monkeypatch.setattr(valuation_router, "continue_admin_run", _skip)


@pytest.fixture(autouse=True)
def _no_background_bid_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch V6: "Try bid prices" carries on after the response, as the valuation run does.

    It would search eBay from a test and commit outside the rolled-back transaction. Tests
    about the button replace this no-op with a recorder.
    """
    import uuid

    import src.routers.valuation as valuation_router

    async def _skip(run_id: uuid.UUID) -> None:
        del run_id

    monkeypatch.setattr(valuation_router, "continue_trial_in_background", _skip)


@pytest.fixture(autouse=True)
def _no_background_spec_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch T7: the Disc specs page's batch runs after the response, on real clients.

    It would search Brave and fetch Blu-ray.com from a test. Tests about the button replace
    this no-op with a recorder.
    """
    import uuid

    import src.routers.specs as specs_router

    async def _skip(run_id: uuid.UUID) -> None:
        del run_id

    monkeypatch.setattr(specs_router, "continue_run_in_background", _skip)


@pytest.fixture(autouse=True)
def _no_background_review_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch V9: adding a want searches Brave for its reviews after the response.

    It would search Brave from a test and commit outside the rolled-back transaction. Tests
    about the search replace this no-op with a recorder.
    """
    import uuid

    import src.routers.wanted as wanted_router

    async def _skip(movie_id: uuid.UUID) -> None:
        del movie_id

    monkeypatch.setattr(wanted_router, "search_for_want_in_background", _skip)
