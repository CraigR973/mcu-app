"""Postgres connectivity proof for the CI service database."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def test_postgres_service_accepts_queries(db_conn: AsyncConnection) -> None:
    assert await db_conn.scalar(text("SELECT 1")) == 1
