"""JWT creation/verification, bcrypt PIN helpers, and the FastAPI auth dependencies.

There is no public sign-up (`DECISIONS.md` #11). Profiles are seeded by migration `002`
with ``pin_hash = NULL`` — *no credential* — and each person sets their own PIN once,
which is the only path that ever writes a hash.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.models.profile import Profile, UserRole

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=True)

ACCESS_TTL = timedelta(hours=24)
REFRESH_TTL = timedelta(days=30)

#: Attempts before the account locks. Enforced against ``profiles.failed_login_count``,
#: which is in Postgres — so the count is not reset by a redeploy.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

#: A PIN is 4–8 digits. Four is the floor because the blocklist below is calibrated to
#: the four-digit distribution; more is allowed because nothing about the scheme needs
#: to stop someone choosing a longer one.
PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 8

#: Four-digit PINs common enough that permitting them shrinks the keyspace to nothing.
#:
#: Published analyses of leaked four-digit PINs put roughly a quarter of all human
#: choices in about twenty values — ``1234`` alone is close to a tenth. Against that
#: distribution a nominal 10,000-value space behaves like a few dozen, and the durable
#: five-attempt lockout would be doing all the work.
#:
#: Kept deliberately short. A long blocklist starts refusing PINs people chose for real
#: reasons and pushes them toward writing it down, which is a worse outcome than a weak
#: PIN behind a lockout. This is the head of the distribution and nothing else.
#:
#: Only four-digit PINs are listed: the distribution flattens sharply beyond four, so a
#: blocklist there would refuse without buying anything.
WEAK_PINS = frozenset(
    {
        "0000",
        "1111",
        "2222",
        "3333",
        "4444",
        "5555",
        "6666",
        "7777",
        "8888",
        "9999",
        "1234",
        "2345",
        "3456",
        "4567",
        "5678",
        "6789",
        "0123",
        "4321",
        "5432",
        "6543",
        "7654",
        "8765",
        "9876",
        "3210",
        "1212",
        "2121",
        "1122",
        "1313",
        "1010",
        "2020",
        "6969",
        "1004",
        "2000",
        "2001",
    }
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def is_weak_pin(pin: str) -> bool:
    """True when a PIN is common enough that it is effectively no PIN at all."""
    return pin in WEAK_PINS


# ---------------------------------------------------------------------------
# Bcrypt helpers
# ---------------------------------------------------------------------------


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, hashed: str | None) -> bool:
    """True when ``pin`` matches the stored hash.

    ``hashed`` is ``None`` for a profile that has never set a PIN, and that verifies
    **nothing** — an absent credential is not a blank one. Handled here as well as at
    the call site so a path that forgets to check cannot fall through to bcrypt with a
    ``None``; the login route still checks first, because "no PIN has been set" and
    "that PIN is wrong" are different things to tell someone.
    """
    if hashed is None:
        return False
    return bcrypt.checkpw(pin.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def create_access_token(user_id: uuid.UUID, role: UserRole) -> str:
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "exp": _utcnow() + ACCESS_TTL,
        "iat": _utcnow(),
    }
    return jwt.encode(payload, settings.jwt_access_secret, algorithm="HS256")


def create_refresh_token(user_id: uuid.UUID, token_record_id: uuid.UUID) -> str:
    """Signed with a **different** secret from the access token.

    Separate secrets mean a leaked access secret cannot mint refresh tokens, and the
    two can be rotated independently. `config.py` refuses to boot if they are equal.
    """
    payload = {
        "sub": str(user_id),
        "jti": str(token_record_id),
        "exp": _utcnow() + REFRESH_TTL,
        "iat": _utcnow(),
    }
    return jwt.encode(payload, settings.jwt_refresh_secret, algorithm="HS256")


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest of a raw token — what ``refresh_tokens.token_hash`` stores.

    The raw token never reaches the database, so a database read cannot mint a session.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_opaque_token() -> str:
    """32 bytes of URL-safe randomness, used as the raw refresh token."""
    return secrets.token_urlsafe(32)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_access_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        # `from None` throughout: the underlying JWT error is not the caller's business
        # and chaining it would put library internals in the traceback of a 401.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from None


def decode_refresh_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_refresh_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Profile:
    payload = decode_access_token(credentials.credentials)

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from None

    result = await db.execute(
        select(Profile).where(
            Profile.id == user_id,
            Profile.deleted_at.is_(None),
            Profile.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        # Deliberately the same 401 as a bad signature: a valid token for a
        # deactivated profile must not be distinguishable from a forged one.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(user: Annotated[Profile, Depends(get_current_user)]) -> Profile:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


CurrentUser = Annotated[Profile, Depends(get_current_user)]
AdminUser = Annotated[Profile, Depends(require_admin)]
