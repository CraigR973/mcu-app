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
