"""Session renewal and sign-out, end to end — `DECISIONS.md` #200.

**These are the tests that did not exist.** Batch 3 shipped rotating refresh tokens and
nothing ever renewed one. ``/auth/refresh`` split the token at its first dot, hashed the
wrong string and found no row, so every session ended when its 24-hour access token did:
production recorded 30 sign-ins and zero renewals between 8 and 22 Sep 2026. Sign-out
split the same way and never revoked anything.

The first group needs no database and runs everywhere. The second drives the real routes
against Postgres and is skipped when ``DATABASE_URL`` is unset — CI always sets it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import (
    create_refresh_token,
    generate_opaque_token,
    hash_pin,
    split_refresh_token,
)
from src.database import get_db, get_limiter_db
from src.main import app
from src.models.profile import Profile, UserRole

ACCESS_SECRET = "test-access-secret-that-is-long-enough-32"
REFRESH_SECRET = "test-refresh-secret-that-is-different-32"
PIN = "8317"


@pytest.fixture(autouse=True)
def _secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.auth as auth_module

    monkeypatch.setattr(auth_module.settings, "jwt_access_secret", ACCESS_SECRET)
    monkeypatch.setattr(auth_module.settings, "jwt_refresh_secret", REFRESH_SECRET)


# ── The token's shape — no database ──────────────────────────────────────────


def test_a_refresh_token_splits_at_its_last_dot() -> None:
    record_id, user_id = uuid.uuid4(), uuid.uuid4()
    opaque = generate_opaque_token()
    token = create_refresh_token(user_id, record_id) + "." + opaque

    # The whole defect in one line: a JWT carries two dots of its own, so the first dot
    # in the token is inside the signed half, not between the halves.
    assert token.count(".") == 3
    parts = split_refresh_token(token)
    assert parts is not None
    signed, tail = parts
    assert tail == opaque
    assert jwt.decode(signed, REFRESH_SECRET, algorithms=["HS256"])["jti"] == str(record_id)


@pytest.mark.parametrize("token", ["", "no-dot-at-all", ".opaque-only", "signed-only."])
def test_a_token_without_both_halves_does_not_split(token: str) -> None:
    assert split_refresh_token(token) is None


class _UnusedSession:
    """A database that fails the test if anything reaches it."""

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("a bad signature must be refused before any lookup")


async def test_a_forged_signature_is_refused_before_any_lookup() -> None:
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "jti": str(uuid.uuid4())},
        "a-different-secret-entirely-and-long-enough",
        algorithm="HS256",
    )

    async def unused_db() -> AsyncIterator[_UnusedSession]:
        yield _UnusedSession()

    app.dependency_overrides[get_db] = unused_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/api/v1/auth/refresh",
                json={"refreshToken": f"{forged}.{generate_opaque_token()}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


# ── The real routes, against Postgres ────────────────────────────────────────


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
        display_name=f"Renewal {uuid.uuid4().hex[:8]}",
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

    # In production the login limiter charges its bucket on a session of its own. Here it
    # shares the test's rolled-back transaction, so the charge leaves with the test.
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_limiter_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


async def _sign_in(client: AsyncClient, person: Profile) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"displayName": person.display_name, "pin": PIN}
    )
    assert response.status_code == 200, response.text
    body: dict[str, str] = response.json()
    return body


async def _renew(client: AsyncClient, refresh_token: str) -> Response:
    return await client.post("/api/v1/auth/refresh", json={"refreshToken": refresh_token})


async def test_a_session_renews_and_renews_again(client: AsyncClient, person: Profile) -> None:
    signed_in = await _sign_in(client, person)

    renewed = await _renew(client, signed_in["refreshToken"])
    assert renewed.status_code == 200, renewed.text
    renewed_again = await _renew(client, renewed.json()["refreshToken"])
    assert renewed_again.status_code == 200, renewed_again.text

    access = renewed_again.json()["accessToken"]
    assert jwt.decode(access, ACCESS_SECRET, algorithms=["HS256"])["sub"] == str(person.id)


async def test_a_refresh_token_works_once(client: AsyncClient, person: Profile) -> None:
    signed_in = await _sign_in(client, person)
    assert (await _renew(client, signed_in["refreshToken"])).status_code == 200

    replayed = await _renew(client, signed_in["refreshToken"])
    assert replayed.status_code == 401


async def test_signing_out_revokes_the_session(client: AsyncClient, person: Profile) -> None:
    signed_in = await _sign_in(client, person)

    signed_out = await client.post(
        "/api/v1/auth/logout", json={"refreshToken": signed_in["refreshToken"]}
    )
    assert signed_out.status_code == 204
    assert (await _renew(client, signed_in["refreshToken"])).status_code == 401


async def test_one_rows_signature_cannot_carry_another_rows_secret(
    client: AsyncClient, person: Profile
) -> None:
    first = await _sign_in(client, person)
    second = await _sign_in(client, person)
    first_parts = split_refresh_token(first["refreshToken"])
    second_parts = split_refresh_token(second["refreshToken"])
    assert first_parts is not None and second_parts is not None

    spliced = f"{first_parts[0]}.{second_parts[1]}"
    assert (await _renew(client, spliced)).status_code == 401

    # The refusal revoked nothing: the genuine second token still renews.
    assert (await _renew(client, second["refreshToken"])).status_code == 200
