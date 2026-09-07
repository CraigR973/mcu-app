"""The acceptance criterion, proved against a real Postgres.

    5 failed PINs lock the account for 15 minutes, and the lock **survives a process
    restart** — the defect app-starter ships.

"Survives a process restart" is what makes these tests worth having, and it cannot be
shown with a mock. Each test that claims it disposes the engine entirely and builds a
new one before re-reading, which is the closest thing to a restart available in-process:
every SQLAlchemy pool, session and identity map is discarded, so anything still visible
came back off disk.

Skipped when ``DATABASE_URL`` is unset. CI always sets it and applies migrations first.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.auth import LOCKOUT_DURATION, MAX_FAILED_ATTEMPTS, _utcnow, hash_pin
from src.config import Settings
from src.models.profile import Profile, UserRole
from src.models.rate_limit import RateLimitCounter
from src.rate_limit import LOGIN_LIMIT, charge_durable_limit
from src.routers.auth import _record_failed_attempt
from tests.conftest import DATABASE_URL

pytestmark = pytest.mark.asyncio


def _fresh_engine() -> AsyncEngine:
    """A brand-new engine and pool — the stand-in for a restarted process."""
    assert DATABASE_URL is not None
    return create_async_engine(Settings(database_url=DATABASE_URL).database_url)


@pytest_asyncio.fixture
async def profile_id() -> AsyncIterator[uuid.UUID]:
    """A throwaway profile, removed afterwards.

    Not the seeded Craig/Mark rows: the code under test commits on its own sessions, so
    a rolled-back fixture cannot contain it and mutating a real profile would leave it
    locked.
    """
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set — Postgres-backed tests skipped")

    engine = _fresh_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    new_id = uuid.uuid4()
    async with sessionmaker() as session:
        session.add(
            Profile(
                id=new_id,
                display_name=f"test-{new_id}",
                pin_hash=hash_pin("8317"),
                role=UserRole.viewer,
            )
        )
        await session.commit()
    await engine.dispose()

    yield new_id

    engine = _fresh_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        await session.execute(delete(Profile).where(Profile.id == new_id))
        await session.commit()
    await engine.dispose()


async def _read_profile(profile_id: uuid.UUID) -> Profile:
    """Read through a *new* engine, so nothing cached can answer."""
    engine = _fresh_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            result = await session.execute(select(Profile).where(Profile.id == profile_id))
            return result.scalar_one()
    finally:
        await engine.dispose()


# ── The profile lockout ──────────────────────────────────────────────────────


async def test_five_failed_attempts_lock_the_account(profile_id: uuid.UUID) -> None:
    engine = _fresh_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for _ in range(MAX_FAILED_ATTEMPTS):
            async with sessionmaker() as session:
                await _record_failed_attempt(session, profile_id)
    finally:
        await engine.dispose()

    profile = await _read_profile(profile_id)
    assert profile.locked_until_utc is not None
    assert profile.locked_until_utc > _utcnow()


async def test_four_failed_attempts_do_not_lock(profile_id: uuid.UUID) -> None:
    engine = _fresh_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            async with sessionmaker() as session:
                await _record_failed_attempt(session, profile_id)
    finally:
        await engine.dispose()

    profile = await _read_profile(profile_id)
    assert profile.locked_until_utc is None
    assert profile.failed_login_count == MAX_FAILED_ATTEMPTS - 1


async def test_lockout_lasts_fifteen_minutes(profile_id: uuid.UUID) -> None:
    before = _utcnow()
    engine = _fresh_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for _ in range(MAX_FAILED_ATTEMPTS):
            async with sessionmaker() as session:
                await _record_failed_attempt(session, profile_id)
    finally:
        await engine.dispose()

    profile = await _read_profile(profile_id)
    assert profile.locked_until_utc is not None
    delta = profile.locked_until_utc - before
    assert (
        LOCKOUT_DURATION - timedelta(seconds=30)
        <= delta
        <= LOCKOUT_DURATION + timedelta(seconds=30)
    )


async def test_the_lock_survives_a_process_restart(profile_id: uuid.UUID) -> None:
    """The batch's headline criterion, and the defect app-starter ships.

    Every attempt is recorded through an engine that is then disposed, so by the time
    the assertion runs there is no pool, session or identity map left from the writes —
    a lock still visible here came off disk.
    """
    for _ in range(MAX_FAILED_ATTEMPTS):
        engine = _fresh_engine()
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await _record_failed_attempt(session, profile_id)
        finally:
            await engine.dispose()

    profile = await _read_profile(profile_id)
    assert profile.locked_until_utc is not None, "lockout did not survive the restart"
    assert profile.locked_until_utc > _utcnow()


# ── The durable rate limiter ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def bucket_key() -> AsyncIterator[str]:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set — Postgres-backed tests skipped")
    key = f"login:test-{uuid.uuid4()}:1.2.3.4"
    yield key
    engine = _fresh_engine()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await session.execute(delete(RateLimitCounter).where(RateLimitCounter.bucket_key == key))
        await session.commit()
    await engine.dispose()


async def test_sixth_attempt_in_the_window_is_refused(bucket_key: str) -> None:
    engine = _fresh_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            for attempt in range(5):
                assert await charge_durable_limit(session, bucket_key, LOGIN_LIMIT) is None, (
                    f"attempt {attempt + 1} should have been allowed"
                )
            assert await charge_durable_limit(session, bucket_key, LOGIN_LIMIT) is not None
    finally:
        await engine.dispose()


async def test_the_rate_limit_counter_survives_a_process_restart(bucket_key: str) -> None:
    """An in-memory limiter hands back a fresh window here. That is the whole point.

    This app redeploys on every push to `main`, so a restart is something an attacker can
    *wait for* rather than have to cause.
    """
    for _ in range(5):
        engine = _fresh_engine()
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                assert await charge_durable_limit(session, bucket_key, LOGIN_LIMIT) is None
        finally:
            await engine.dispose()

    engine = _fresh_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            refused = await charge_durable_limit(session, bucket_key, LOGIN_LIMIT)
    finally:
        await engine.dispose()

    assert refused is not None, "the counter reset across the restart"


async def test_one_row_per_bucket_not_one_per_window(bucket_key: str) -> None:
    engine = _fresh_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            for _ in range(3):
                await charge_durable_limit(session, bucket_key, LOGIN_LIMIT)
        async with sessionmaker() as session:
            rows = (
                (
                    await session.execute(
                        select(RateLimitCounter).where(RateLimitCounter.bucket_key == bucket_key)
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()

    assert len(rows) == 1
    assert rows[0].hits == 3


async def test_separate_keys_do_not_share_a_bucket(bucket_key: str) -> None:
    """One person's failed attempts must not spend another's budget."""
    other = f"{bucket_key}-other"
    engine = _fresh_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            for _ in range(6):
                await charge_durable_limit(session, bucket_key, LOGIN_LIMIT)
            assert await charge_durable_limit(session, other, LOGIN_LIMIT) is None
            await session.execute(
                delete(RateLimitCounter).where(RateLimitCounter.bucket_key == other)
            )
            await session.commit()
    finally:
        await engine.dispose()


# ── Seeded profiles ──────────────────────────────────────────────────────────


async def test_migration_seeds_two_profiles_with_no_credential() -> None:
    """`pin_hash IS NULL` — no PIN is ever written into a migration or into git."""
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set — Postgres-backed tests skipped")

    engine = _fresh_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            result = await session.execute(
                select(Profile).where(Profile.display_name.in_(("Craig", "Mark")))
            )
            seeded = {p.display_name: p for p in result.scalars()}
    finally:
        await engine.dispose()

    assert set(seeded) == {"Craig", "Mark"}
    assert seeded["Craig"].role == UserRole.admin
    assert seeded["Mark"].role == UserRole.viewer
    assert all(p.pin_hash is None for p in seeded.values())
