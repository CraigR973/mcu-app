"""Login, refresh, logout, and PIN management.

**There is no sign-up route and there must never be one** (`DECISIONS.md` #11). The two
profiles are created by migration `002` with ``pin_hash = NULL``; each person sets their
own PIN through ``POST /api/v1/auth/pin``, which is the only path that writes a hash.
"""

import uuid
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    ACCESS_TTL,
    LOCKOUT_DURATION,
    MAX_FAILED_ATTEMPTS,
    PIN_MAX_LENGTH,
    PIN_MIN_LENGTH,
    REFRESH_TTL,
    CurrentUser,
    _utcnow,
    create_access_token,
    create_refresh_token,
    generate_opaque_token,
    hash_pin,
    hash_token,
    is_weak_pin,
    verify_pin,
)
from src.database import get_db, get_limiter_db
from src.models.profile import (
    DISPLAY_NAME_MAX_LENGTH,
    Profile,
    RefreshToken,
    UserRole,
)
from src.rate_limit import DurableLoginLimit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: A real bcrypt hash of a value nothing can supply, checked against when the display
#: name is unknown. Without it, an unknown name returns before bcrypt runs and a known
#: one returns after — roughly 100 ms of difference that enumerates the two accounts.
_DUMMY_HASH = hash_pin("0" * PIN_MAX_LENGTH)

#: Identical text for "no such name" and "wrong PIN". The distinction is deliberately
#: not offered; the two cases differ only in whether the timing padding above ran.
_BAD_CREDENTIALS = "Invalid display name or PIN"


def _validate_pin(pin: str) -> str:
    if not pin.isdigit():
        raise ValueError("PIN must be digits only")
    if not PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH:
        raise ValueError(f"PIN must be {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} digits")
    if is_weak_pin(pin):
        raise ValueError("PIN is too common — choose another")
    return pin


class LoginRequest(BaseModel):
    displayName: str = Field(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)
    pin: str = Field(min_length=PIN_MIN_LENGTH, max_length=PIN_MAX_LENGTH)


class TokenPair(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: Literal["bearer"] = "bearer"
    expiresIn: int


class RefreshRequest(BaseModel):
    refreshToken: str


class LogoutRequest(BaseModel):
    refreshToken: str


class ProfileResponse(BaseModel):
    id: uuid.UUID
    displayName: str
    role: UserRole
    hasPin: bool


class SetPinRequest(BaseModel):
    #: ``None`` when the profile has no credential yet — the seeded state. Supplying the
    #: wrong current PIN is rejected; omitting it when one exists is also rejected.
    currentPin: str | None = None
    newPin: str

    @field_validator("newPin")
    @classmethod
    def _check_new_pin(cls, value: str) -> str:
        return _validate_pin(value)


async def _issue_tokens(db: AsyncSession, profile: Profile) -> TokenPair:
    """Mint an access token and a fresh refresh row.

    The raw refresh token is returned here and never stored — only its SHA-256 digest
    reaches the database.
    """
    raw_refresh = generate_opaque_token()
    record = RefreshToken(
        id=uuid.uuid4(),
        user_id=profile.id,
        token_hash=hash_token(raw_refresh),
        expires_at_utc=_utcnow() + REFRESH_TTL,
        created_at_utc=_utcnow(),
    )
    db.add(record)
    await db.commit()

    return TokenPair(
        accessToken=create_access_token(profile.id, profile.role),
        # Signed with the refresh secret and carrying the row id, so a token whose row
        # has been revoked is rejected even though its signature is still valid.
        refreshToken=create_refresh_token(profile.id, record.id) + "." + raw_refresh,
        expiresIn=int(ACCESS_TTL.total_seconds()),
    )


async def _record_failed_attempt(limiter_db: AsyncSession, profile_id: uuid.UUID) -> None:
    """Charge a failed attempt against the profile and lock it at the threshold.

    On ``limiter_db`` — a session of its own — and committed immediately, because the
    login handler's own transaction rolls back on a bad PIN and an attempt has to be
    counted either way. This is the half `app-starter` declares and never enforces
    (`DECISIONS.md` #11), and the reason the lock survives a process restart: the count
    is a Postgres row, not a number in RAM.
    """
    profile = await limiter_db.get(Profile, profile_id)
    if profile is None:  # pragma: no cover - profile was read moments earlier
        return

    profile.failed_login_count += 1
    if profile.failed_login_count >= MAX_FAILED_ATTEMPTS:
        profile.locked_until_utc = _utcnow() + LOCKOUT_DURATION
        # Reset the count with the lock so the window after it starts clean rather than
        # locking again on the first subsequent mistake.
        profile.failed_login_count = 0
        log.warning("profile locked", profile_id=str(profile_id), minutes=15)
    await limiter_db.commit()


@router.post("/login", response_model=TokenPair)
async def login(
    request: Request,
    payload: LoginRequest,
    _limit: DurableLoginLimit,
    db: Annotated[AsyncSession, Depends(get_db)],
    limiter_db: Annotated[AsyncSession, Depends(get_limiter_db)],
) -> TokenPair:
    result = await db.execute(
        select(Profile).where(
            func.lower(Profile.display_name) == payload.displayName.lower(),
            Profile.deleted_at.is_(None),
            Profile.is_active.is_(True),
        )
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        # Pay the same bcrypt cost an existing profile would, then fail identically.
        verify_pin(payload.pin, _DUMMY_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_BAD_CREDENTIALS)

    now = _utcnow()
    if profile.locked_until_utc is not None and profile.locked_until_utc > now:
        remaining = int((profile.locked_until_utc - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked. Try again in {remaining // 60 + 1} minutes.",
            headers={"Retry-After": str(remaining)},
        )

    if profile.pin_hash is None:
        # Distinguished from a wrong PIN on purpose: with no sign-up flow, the seeded
        # "no credential yet" state is otherwise indistinguishable from a broken login,
        # and only two people can ever reach this message.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No PIN has been set for this profile yet.",
        )

    if not verify_pin(payload.pin, profile.pin_hash):
        await _record_failed_attempt(limiter_db, profile.id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_BAD_CREDENTIALS)

    profile.failed_login_count = 0
    profile.locked_until_utc = None
    profile.last_login_at_utc = now
    tokens = await _issue_tokens(db, profile)
    log.info("login succeeded", profile_id=str(profile.id))
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    """Exchange a refresh token for a new pair, revoking the one presented.

    Rotation on every use: the presented row is revoked before the replacement is
    issued, so a token used twice fails the second time even within its 30-day life.
    """
    raw = payload.refreshToken
    _, _, opaque = raw.partition(".")
    if not opaque:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(opaque))
    )
    record = result.scalar_one_or_none()
    now = _utcnow()
    if record is None or record.revoked_at_utc is not None or record.expires_at_utc <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    profile = await db.get(Profile, record.user_id)
    if profile is None or profile.deleted_at is not None or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    record.revoked_at_utc = now
    return await _issue_tokens(db, profile)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Revoke a refresh token. Idempotent — an unknown token is not an error."""
    _, _, opaque = payload.refreshToken.partition(".")
    if not opaque:
        return
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(opaque))
    )
    record = result.scalar_one_or_none()
    if record is not None and record.revoked_at_utc is None:
        record.revoked_at_utc = _utcnow()
        await db.commit()


@router.get("/me", response_model=ProfileResponse)
async def me(user: CurrentUser) -> ProfileResponse:
    return ProfileResponse(
        id=user.id,
        displayName=user.display_name,
        role=user.role,
        hasPin=user.pin_hash is not None,
    )


@router.post("/pin", status_code=status.HTTP_204_NO_CONTENT)
async def set_pin(
    payload: SetPinRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Set or change the caller's own PIN. Never anybody else's.

    Reachable only with a valid access token, which for a profile in the seeded
    ``pin_hash = NULL`` state means the first PIN is set through an admin-minted token
    rather than by anyone who knows the display name.
    """
    if user.pin_hash is not None and (
        payload.currentPin is None or not verify_pin(payload.currentPin, user.pin_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Current PIN is incorrect"
        )

    profile = await db.get(Profile, user.id)
    if profile is None:  # pragma: no cover - the dependency just loaded it
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    profile.pin_hash = hash_pin(payload.newPin)
    profile.failed_login_count = 0
    profile.locked_until_utc = None

    # Every existing session is invalidated: a PIN change is what someone does when they
    # think a credential is compromised, and leaving 30-day refresh rows alive would make
    # the change cosmetic.
    existing = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at_utc.is_(None)
        )
    )
    for record in existing.scalars():
        record.revoked_at_utc = _utcnow()

    await db.commit()
    log.info("pin changed", profile_id=str(user.id))
