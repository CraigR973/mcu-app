"""AG9 (DS50-02): a guess of the current PIN on PIN change is a login attempt.

Before, ``POST /auth/pin`` took unlimited guesses of the current PIN: whoever held a stolen
access token could try every PIN, set a new one and sign the owner out for good, and the daily
check's lockout row never saw it. These drive the real routes against Postgres, sharing the
test's rolled-back transaction as ``test_auth_refresh`` does.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import MAX_FAILED_ATTEMPTS, _utcnow, hash_pin, verify_pin
from src.database import get_db, get_limiter_db
from src.main import app
from src.models.profile import Profile, UserRole
from src.rate_limit import LOGIN_LIMIT
from tests.test_auth_refresh import ACCESS_SECRET, PIN, REFRESH_SECRET

NEW_PIN = "4826"
WRONG = "5150"


@pytest.fixture(autouse=True)
def _secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.auth as auth_module

    monkeypatch.setattr(auth_module.settings, "jwt_access_secret", ACCESS_SECRET)
    monkeypatch.setattr(auth_module.settings, "jwt_refresh_secret", REFRESH_SECRET)


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def person(api_session: AsyncSession) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Changer {uuid.uuid4().hex[:8]}",
        pin_hash=hash_pin(PIN),
        role=UserRole.viewer,
    )
    api_session.add(profile)
    await api_session.flush()
    return profile


@pytest_asyncio.fixture
async def client(api_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_limiter_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


async def _signed_in(client: AsyncClient, person: Profile) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"displayName": person.display_name, "pin": PIN}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


async def _change(client: AsyncClient, auth: dict[str, str], current: str, *, ip: str) -> int:
    response = await client.post(
        "/api/v1/auth/pin",
        json={"currentPin": current, "newPin": NEW_PIN},
        headers={**auth, "X-Forwarded-For": ip},
    )
    return response.status_code


async def test_a_wrong_current_pin_counts_toward_the_login_lockout(
    client: AsyncClient, api_session: AsyncSession, person: Profile
) -> None:
    auth = await _signed_in(client, person)
    # One address per guess, so this is the lockout at work, not the rate limit.
    for guess in range(MAX_FAILED_ATTEMPTS - 1):
        assert await _change(client, auth, WRONG, ip=f"203.0.113.{guess}") == 401
    await api_session.refresh(person)
    assert person.failed_login_count == MAX_FAILED_ATTEMPTS - 1
    assert person.locked_until_utc is None

    assert await _change(client, auth, WRONG, ip="203.0.113.50") == 401
    await api_session.refresh(person)
    assert person.locked_until_utc is not None and person.locked_until_utc > _utcnow()
    assert person.lockout_count == 1, "the daily check names it, as any login lock"

    # Locked: the right current PIN changes nothing, and login is refused too.
    assert await _change(client, auth, PIN, ip="203.0.113.51") == 423
    await api_session.refresh(person)
    assert person.pin_hash is not None and verify_pin(PIN, person.pin_hash)
    login = await client.post(
        "/api/v1/auth/login",
        json={"displayName": person.display_name, "pin": PIN},
        headers={"X-Forwarded-For": "203.0.113.52"},
    )
    assert login.status_code == 423


async def test_wrong_pins_at_login_and_on_change_share_one_count(
    client: AsyncClient, api_session: AsyncSession, person: Profile
) -> None:
    auth = await _signed_in(client, person)
    for guess in range(2):
        await client.post(
            "/api/v1/auth/login",
            json={"displayName": person.display_name, "pin": WRONG},
            headers={"X-Forwarded-For": f"198.51.100.{guess}"},
        )
    for guess in range(MAX_FAILED_ATTEMPTS - 2):
        assert await _change(client, auth, WRONG, ip=f"198.51.100.{10 + guess}") == 401
    await api_session.refresh(person)
    assert person.locked_until_utc is not None


async def test_pin_change_carries_the_login_s_rate_limit(
    client: AsyncClient, person: Profile
) -> None:
    auth = await _signed_in(client, person)
    allowed = int(LOGIN_LIMIT.split("/")[0])
    # The right PIN would succeed and revoke the session, so a wrong-format current PIN
    # (still a guess the bucket charges) is sent past the limit from one address.
    statuses = [await _change(client, auth, WRONG, ip="192.0.2.7") for _ in range(allowed + 1)]
    assert statuses[-1] == 429


async def test_the_right_current_pin_still_changes_it_and_clears_the_count(
    client: AsyncClient, api_session: AsyncSession, person: Profile
) -> None:
    auth = await _signed_in(client, person)
    assert await _change(client, auth, WRONG, ip="192.0.2.20") == 401
    assert await _change(client, auth, PIN, ip="192.0.2.21") == 204
    await api_session.refresh(person)
    assert person.pin_hash is not None and verify_pin(NEW_PIN, person.pin_hash)
    assert person.failed_login_count == 0


async def test_a_first_pin_needs_no_current_one_and_charges_nothing(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The seeded no-credential state: set through an admin-minted token, as before."""
    from src.auth import create_access_token

    fresh = Profile(
        id=uuid.uuid4(), display_name=f"Seed {uuid.uuid4().hex[:6]}", role=UserRole.viewer
    )
    api_session.add(fresh)
    await api_session.flush()
    token = create_access_token(fresh.id, fresh.role)
    response = await client.post(
        "/api/v1/auth/pin",
        json={"newPin": NEW_PIN},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204, response.text
    await api_session.refresh(fresh)
    assert fresh.failed_login_count == 0 and fresh.pin_hash is not None
