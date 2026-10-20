"""Every naive-UTC column's default is UTC, whatever the session's time zone (migration ``063``).

A bare ``now()`` default is cast to a naive timestamp in the session's time zone, so on a
database not set to UTC it wrote local time, while ``set_updated_at`` writes UTC. The stale-edit
guard compares the two and let a stale edit through under Europe/London. CI's Postgres and Neon
run in UTC, which is why only a local server found it; these tests set a zone ahead of UTC
themselves, so they fail on the old defaults wherever they run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

#: How Postgres prints ``timezone('utc', now())`` back from the catalogue.
UTC_DEFAULT = "timezone('utc'::text, now())"

#: Any default that reads the clock, in any of Postgres's spellings.
READS_THE_CLOCK = (
    r"(now|clock_timestamp|statement_timestamp|transaction_timestamp)\("
    r"|current_timestamp|localtimestamp"
)


async def test_no_naive_timestamp_column_defaults_to_local_time(db_conn: AsyncConnection) -> None:
    """The guard for the next migration: a new column written ``server_default=func.now()``.

    ``src.models.base.UTC_NOW`` is the default to use instead.
    """
    rows = (
        await db_conn.execute(
            text(
                """
                SELECT table_name || '.' || column_name, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND data_type = 'timestamp without time zone'
                  AND column_default ~* :reads_the_clock
                  AND column_default <> :utc
                ORDER BY 1
                """
            ),
            {"reads_the_clock": READS_THE_CLOCK, "utc": UTC_DEFAULT},
        )
    ).all()

    assert [tuple(row) for row in rows] == []


async def test_a_default_written_in_a_zone_ahead_of_utc_is_utc(db_conn: AsyncConnection) -> None:
    """The behaviour itself, on the column the stale-edit guard reads."""
    await db_conn.execute(text("SET LOCAL TIME ZONE 'Asia/Tokyo'"))
    before = datetime.now(UTC).replace(tzinfo=None)

    created, updated = (
        await db_conn.execute(
            text(
                "INSERT INTO movies (id, title) VALUES (:id, 'Defaulted Abroad') "
                "RETURNING created_at, updated_at"
            ),
            {"id": uuid.uuid4()},
        )
    ).one()

    after = datetime.now(UTC).replace(tzinfo=None)
    slack = timedelta(seconds=5)
    for stamp in (created, updated):
        assert before - slack <= stamp <= after + slack, (stamp, before)
