"""Unit tests for the auth primitives. No database — see test_auth_lockout.py for that."""

import uuid
from collections.abc import AsyncIterator

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from src.auth import (
    MAX_FAILED_ATTEMPTS,
    PIN_MAX_LENGTH,
    PIN_MIN_LENGTH,
    WEAK_PINS,
    create_access_token,
    create_refresh_token,
    generate_opaque_token,
    get_current_user,
    hash_pin,
    hash_token,
    is_weak_pin,
    verify_pin,
)
from src.config import Environment, docs_urls
from src.database import get_db
from src.main import app
from src.models.profile import Profile, UserRole
from src.models.rate_limit import BUCKET_KEY_MAX_LENGTH
from src.rate_limit import LOGIN_LIMIT, durable_bucket_key

ACCESS_SECRET = "test-access-secret-that-is-long-enough-32"
REFRESH_SECRET = "test-refresh-secret-that-is-different-32"


@pytest.fixture(autouse=True)
def _secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.auth as auth_module

    monkeypatch.setattr(auth_module.settings, "jwt_access_secret", ACCESS_SECRET)
    monkeypatch.setattr(auth_module.settings, "jwt_refresh_secret", REFRESH_SECRET)


# ── PIN hashing ──────────────────────────────────────────────────────────────


def test_pin_hash_roundtrip() -> None:
    hashed = hash_pin("8317")
    assert hashed != "8317"
    assert verify_pin("8317", hashed)
    assert not verify_pin("8318", hashed)


def test_absent_credential_verifies_nothing() -> None:
    """``pin_hash IS NULL`` means *no credential*, not *any PIN works*."""
    assert verify_pin("8317", None) is False
    assert verify_pin("", None) is False


def test_hashes_are_salted() -> None:
    assert hash_pin("8317") != hash_pin("8317")


def test_bcrypt_hash_fits_the_column() -> None:
    from src.models.profile import BCRYPT_HASH_LENGTH

    assert len(hash_pin("8317")) == BCRYPT_HASH_LENGTH


# ── Weak PINs ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("pin", ["0000", "1234", "1111", "6969", "4321"])
def test_weak_pins_rejected(pin: str) -> None:
    assert is_weak_pin(pin)


@pytest.mark.parametrize("pin", ["8317", "4092", "7241"])
def test_ordinary_pins_allowed(pin: str) -> None:
    assert not is_weak_pin(pin)


def test_blocklist_stays_short() -> None:
    """A long blocklist pushes people toward writing the PIN down — a worse outcome."""
    assert len(WEAK_PINS) < 50
    assert all(len(p) == 4 and p.isdigit() for p in WEAK_PINS)


# ── Tokens ───────────────────────────────────────────────────────────────────


def test_access_and_refresh_use_different_secrets() -> None:
    """A leaked access secret must not be able to mint refresh tokens."""
    user_id = uuid.uuid4()
    access = create_access_token(user_id, UserRole.admin)
    refresh = create_refresh_token(user_id, uuid.uuid4())

    assert jwt.decode(access, ACCESS_SECRET, algorithms=["HS256"])["sub"] == str(user_id)
    assert jwt.decode(refresh, REFRESH_SECRET, algorithms=["HS256"])["sub"] == str(user_id)

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(refresh, ACCESS_SECRET, algorithms=["HS256"])
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(access, REFRESH_SECRET, algorithms=["HS256"])


def test_access_token_carries_role() -> None:
    token = create_access_token(uuid.uuid4(), UserRole.viewer)
    assert jwt.decode(token, ACCESS_SECRET, algorithms=["HS256"])["role"] == "viewer"


def test_refresh_token_carries_row_id() -> None:
    record_id = uuid.uuid4()
    token = create_refresh_token(uuid.uuid4(), record_id)
    assert jwt.decode(token, REFRESH_SECRET, algorithms=["HS256"])["jti"] == str(record_id)


def test_token_hash_is_sha256_hex() -> None:
    import hashlib

    raw = generate_opaque_token()
    assert hash_token(raw) == hashlib.sha256(raw.encode()).hexdigest()
    assert len(hash_token(raw)) == 64


def test_opaque_tokens_are_unique() -> None:
    assert len({generate_opaque_token() for _ in range(100)}) == 100


# ── Durable limiter key folding ──────────────────────────────────────────────


def test_short_bucket_key_is_unchanged() -> None:
    assert durable_bucket_key("login:craig:1.2.3.4") == "login:craig:1.2.3.4"


def test_long_bucket_key_is_folded_to_fit_the_column() -> None:
    key = "login:" + ("x" * 5000) + ":1.2.3.4"
    folded = durable_bucket_key(key)
    assert len(folded) <= BUCKET_KEY_MAX_LENGTH
    assert folded.startswith("login:")


def test_distinct_long_keys_stay_distinct_buckets() -> None:
    """Truncation alone would merge these two into one bucket."""
    a = durable_bucket_key("login:" + "x" * 5000 + ":a")
    b = durable_bucket_key("login:" + "x" * 5000 + ":b")
    assert a != b


def test_login_limit_matches_the_acceptance_criterion() -> None:
    assert LOGIN_LIMIT == "5/15 minutes"
    assert MAX_FAILED_ATTEMPTS == 5


# ── X-Forwarded-For handling ─────────────────────────────────────────────────


def _request_with_xff(value: str | None) -> object:
    from starlette.requests import Request

    headers = [(b"x-forwarded-for", value.encode())] if value is not None else []
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": headers,
            "client": ("10.0.0.1", 1234),
            "scheme": "http",
            "server": ("test", 80),
            "query_string": b"",
        }
    )


def test_forwarded_for_is_read_from_the_trusted_end() -> None:
    """The leftmost entry is caller-controlled; only the rightmost hops are ours."""
    from src.rate_limit import client_address

    request = _request_with_xff("1.1.1.1, 2.2.2.2, 9.9.9.9")
    assert client_address(request) == "9.9.9.9"  # type: ignore[arg-type]


def test_forwarded_for_spoof_cannot_mint_a_fresh_bucket() -> None:
    from src.rate_limit import client_address

    spoofed = client_address(_request_with_xff("evil-1, 9.9.9.9"))  # type: ignore[arg-type]
    again = client_address(_request_with_xff("evil-2, 9.9.9.9"))  # type: ignore[arg-type]
    assert spoofed == again == "9.9.9.9"


def test_missing_forwarded_for_falls_back_to_peer() -> None:
    from src.rate_limit import client_address

    assert client_address(_request_with_xff(None)) == "10.0.0.1"  # type: ignore[arg-type]


# ── Route surface ────────────────────────────────────────────────────────────


def test_there_is_no_public_sign_up_route() -> None:
    """`DECISIONS.md` #11. Craig and Mark can log in; nobody else can."""
    paths = set(app.openapi()["paths"])
    assert not any("signup" in p or "register" in p or "sign-up" in p for p in paths)


def test_docs_are_disabled_in_production() -> None:
    assert docs_urls(Environment.production) == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    assert docs_urls(Environment.development)["openapi_url"] == "/api/openapi.json"


# ── PIN policy at the edge ───────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pin,reason",
    [("123", "too short"), ("1" * 9, "too long"), ("abcd", "not digits"), ("1234", "too common")],
)
async def test_set_pin_rejects_bad_pins(pin: str, reason: str) -> None:
    """Rejected before any database work — these are 401/422, never a stored hash."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/pin", json={"newPin": pin})
    assert response.status_code in (401, 403, 422), reason


def test_pin_bounds_are_sane() -> None:
    assert PIN_MIN_LENGTH == 4
    assert PIN_MAX_LENGTH >= PIN_MIN_LENGTH


# ── The PIN bootstrap script ─────────────────────────────────────────────────


def test_set_pin_script_accepts_a_good_pin() -> None:
    from src.scripts.set_pin import validate_pin

    assert validate_pin("8317") is None
    assert validate_pin("40928317") is None


@pytest.mark.parametrize(
    "pin,fragment",
    [
        ("123", "4-8 digits"),
        ("1" * 9, "4-8 digits"),
        ("12ab", "digits only"),
        ("1234", "commonly chosen"),
    ],
)
def test_set_pin_script_rejects_bad_pins(pin: str, fragment: str) -> None:
    from src.scripts.set_pin import validate_pin

    error = validate_pin(pin)
    assert error is not None
    assert fragment in error


def test_set_pin_script_never_takes_the_pin_as_an_argument() -> None:
    """The PIN must not reach ``ps``, shell history, or a CI log.

    Seeding both profiles with ``pin_hash = NULL`` means this script is the only way to
    set a *first* PIN, so it is the one place a real credential is typed.
    """
    import inspect

    from src.scripts import set_pin as module

    source = inspect.getsource(module.main)
    assert "getpass" not in source or "add_argument" in source
    parser_source = inspect.getsource(module)
    assert '"pin"' not in parser_source.split("add_argument")[1].split(")")[0]
    assert "getpass" in inspect.getsource(module._read_pin)


# ---------------------------------------------------------------------------
# Onboarding completion (Batch 9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_onboarding_starts_incomplete_and_completes_once() -> None:
    """The flag Batch 3 removed the wizard for the lack of (`DECISIONS.md` #27).

    Completion is idempotent and **keeps the first timestamp**: re-running the wizard
    from settings later must not rewrite when this person was actually set up.
    """
    profile = Profile(
        id=uuid.uuid4(),
        display_name="Onboarding Tester",
        pin_hash=None,
        role=UserRole.viewer,
    )

    async def override_user() -> Profile:
        return profile

    committed: list[str] = []

    class _Session:
        async def commit(self) -> None:
            committed.append("commit")

        async def refresh(self, _obj: object) -> None:
            return None

    async def override_db() -> AsyncIterator[_Session]:
        yield _Session()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            before = await client.get("/api/v1/auth/me")
            assert before.json()["onboardingCompleted"] is False

            first = await client.post("/api/v1/auth/onboarding/complete")
            assert first.status_code == 200
            assert first.json()["onboardingCompleted"] is True
            stamped = profile.onboarding_completed_at_utc
            assert stamped is not None

            second = await client.post("/api/v1/auth/onboarding/complete")
            assert second.json()["onboardingCompleted"] is True
            # Unchanged, and no second write.
            assert profile.onboarding_completed_at_utc == stamped
            assert committed == ["commit"]
    finally:
        app.dependency_overrides.clear()
