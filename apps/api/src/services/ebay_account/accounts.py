"""A person's connection to eBay: starting it, finishing it, using it, ending it — T8b, #245.

**The ``state`` is what keeps one person's sign-in on their own profile.** "Connect eBay"
makes 32 random bytes, sends them to eBay, and keeps only their SHA-256 hash, tied to the
person who pressed it. When eBay sends the person back with a code, the hash must match a
state that person started, unused and under ten minutes old, and it is spent before the
code is swapped, so a code replayed or carried to another profile fails.

**A token eBay will not accept is deleted.** A refresh eBay answers ``invalid_grant`` (the
account closed, or access revoked on eBay), a refresh token past its 18 months, or a sealed
token the current key cannot open all end the connection, and the person is asked to
connect again. A list eBay refuses with an access token it just issued is not treated that
way: it is reported, since that would be the app asking for something eBay will not give.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

import httpx
import structlog
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ebay_account import EbayAccount, EbayConnectState
from src.services.audit import record_action
from src.services.ebay_account import oauth, trading
from src.services.ebay_account.crypto import SealBroken, key_from_settings, open_sealed, seal

logger = structlog.get_logger(__name__)

STATE_LIFETIME = timedelta(minutes=10)
#: Refresh an access token this long before eBay's two hours run out.
REFRESH_MARGIN = timedelta(minutes=5)
TABLE = "ebay_accounts"


class NotConnected(RuntimeError):
    """This person has no usable eBay connection; the message says why, for them."""


class ConnectError(RuntimeError):
    """A sign-in could not be finished; the message says what to do, for the person."""


def state_hash(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


async def get_account(db: AsyncSession, profile_id: uuid.UUID) -> EbayAccount | None:
    return (
        await db.execute(select(EbayAccount).where(EbayAccount.profile_id == profile_id))
    ).scalar_one_or_none()


async def start(db: AsyncSession, profile_id: uuid.UUID, *, now: datetime) -> str:
    """Begin a sign-in: keep a one-time state, and return eBay's consent address."""
    oauth.require_configured()
    key_from_settings()  # A bad key is found before anyone is sent to eBay.
    await db.execute(
        delete(EbayConnectState).where(
            or_(
                EbayConnectState.expires_utc <= now,
                EbayConnectState.used_utc.is_not(None),
                EbayConnectState.profile_id == profile_id,
            )
        )
    )
    state = secrets.token_urlsafe(32)
    db.add(
        EbayConnectState(
            id=uuid.uuid4(),
            profile_id=profile_id,
            state_hash=state_hash(state),
            created_utc=now,
            expires_utc=now + STATE_LIFETIME,
        )
    )
    await db.commit()
    return oauth.authorize_url(state)


async def finish(
    db: AsyncSession,
    profile_id: uuid.UUID,
    *,
    code: str,
    state: str,
    client: httpx.AsyncClient,
    now: datetime,
) -> EbayAccount:
    """Finish a sign-in this person started: spend the state, swap the code, seal the tokens."""
    oauth.require_configured()
    key = key_from_settings()
    held = (
        await db.execute(
            select(EbayConnectState)
            .where(EbayConnectState.state_hash == state_hash(state))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if held is None or held.profile_id != profile_id:
        raise ConnectError(
            "This eBay sign-in was not started from your Settings. Press Connect eBay again."
        )
    if held.used_utc is not None:
        raise ConnectError("This eBay sign-in has already been used. Press Connect eBay again.")
    if held.expires_utc <= now:
        raise ConnectError("This eBay sign-in took over ten minutes. Press Connect eBay again.")
    held.used_utc = now
    await db.commit()

    grant = await oauth.exchange_code(client, code)
    account = await get_account(db, profile_id)
    action = "update" if account is not None else "create"
    if account is None:
        account = EbayAccount(id=uuid.uuid4(), profile_id=profile_id)
        db.add(account)
    account.access_token_sealed = seal(grant.access_token, owner=profile_id, key=key)
    account.access_expires_utc = now + timedelta(seconds=grant.access_expires_in)
    account.refresh_token_sealed = seal(grant.refresh_token, owner=profile_id, key=key)
    account.refresh_expires_utc = now + timedelta(seconds=grant.refresh_expires_in)
    account.scopes = " ".join(oauth.SCOPES)
    account.connected_utc = now
    account.refreshed_utc = None
    account.last_used_utc = None
    await db.flush()
    record_action(
        db,
        user_id=profile_id,
        action_type=action,
        target_table=TABLE,
        target_id=account.id,
        changes={"connected": True, "scopes": account.scopes},
    )
    await db.commit()
    logger.info("ebay_connected", profile=str(profile_id))
    return account


async def _forget(db: AsyncSession, account: EbayAccount, reason: str) -> None:
    """End a connection eBay, or the key, will no longer honour."""
    record_action(
        db,
        user_id=account.profile_id,
        action_type="delete",
        target_table=TABLE,
        target_id=account.id,
        changes={"connected": False, "reason": reason},
    )
    await db.delete(account)
    await db.commit()
    logger.warning("ebay_connection_ended", profile=str(account.profile_id), reason=reason)


async def disconnect(db: AsyncSession, profile_id: uuid.UUID) -> bool:
    """Delete this person's tokens. True when there was a connection to end."""
    account = await get_account(db, profile_id)
    await db.execute(delete(EbayConnectState).where(EbayConnectState.profile_id == profile_id))
    if account is None:
        await db.commit()
        return False
    await _forget(db, account, "disconnected by its owner")
    return True


async def access_token(
    db: AsyncSession,
    account: EbayAccount,
    client: httpx.AsyncClient,
    *,
    now: datetime,
    force_refresh: bool = False,
) -> str:
    """A usable access token for this account, refreshed first when it is nearly spent."""
    key = key_from_settings()
    owner = account.profile_id
    if account.refresh_expires_utc <= now:
        await _forget(db, account, "eBay's 18-month sign-in lapsed")
        raise NotConnected("Your eBay sign-in has lapsed after 18 months. Connect eBay again.")
    try:
        if not force_refresh and account.access_expires_utc - REFRESH_MARGIN > now:
            return open_sealed(account.access_token_sealed, owner=owner, key=key)
        refresh_token = open_sealed(account.refresh_token_sealed, owner=owner, key=key)
    except SealBroken:
        await _forget(db, account, "the sealed token would not open with this key")
        raise NotConnected(
            "This app's key for eBay sign-ins has changed, so your connection cannot be used. "
            "Connect eBay again."
        ) from None
    try:
        refreshed = await oauth.refresh_access(client, refresh_token, account.scopes)
    except oauth.EbayAuthError as exc:
        if exc.refused:
            await _forget(db, account, "eBay refused the refresh token")
            raise NotConnected(
                "eBay no longer accepts this connection: the account was closed, or access was "
                "removed on eBay. Connect eBay again."
            ) from exc
        raise
    account.access_token_sealed = seal(refreshed.access_token, owner=owner, key=key)
    account.access_expires_utc = now + timedelta(seconds=refreshed.access_expires_in)
    account.refreshed_utc = now
    await db.commit()
    return refreshed.access_token


async def read[T](
    db: AsyncSession,
    profile_id: uuid.UUID,
    client: httpx.AsyncClient,
    reader: Callable[[httpx.AsyncClient, str], Awaitable[T]],
    *,
    now: datetime,
) -> T:
    """One of this person's lists, refreshing once if eBay rejects the access token."""
    account = await get_account(db, profile_id)
    if account is None:
        raise NotConnected("Connect eBay in Settings to see your eBay lists here.")
    token = await access_token(db, account, client, now=now)
    try:
        result = await reader(client, token)
    except trading.TradingError as exc:
        if not exc.token_rejected:
            raise
        token = await access_token(db, account, client, now=now, force_refresh=True)
        try:
            result = await reader(client, token)
        except trading.TradingError as again:
            # A token eBay has just issued and still refuses: the app is asking for something
            # its sign-in does not cover. Reported, not "fixed" by deleting the connection.
            raise trading.TradingError(f"{again} even with a fresh sign-in") from again
    account.last_used_utc = now
    await db.commit()
    return result


async def account_name(
    db: AsyncSession, account: EbayAccount, client: httpx.AsyncClient, *, now: datetime
) -> str | None:
    """The connected account's eBay name, read live and never stored; None if unreadable."""
    try:
        return await trading.user_id(client, await access_token(db, account, client, now=now))
    except (trading.TradingError, oauth.EbayAuthError):
        return None
