"""The shared slowapi limiter, per-request key helpers, and the durable half.

Two stores, on purpose. :data:`limiter` keeps its counters in process memory, which is
right for limits that protect a *spend*. The limit that protects a *credential* —
``/auth/login`` — lives in Postgres instead, through :func:`charge_durable_limit`,
because a restart there is a security event and this app redeploys on every push to
``main``.
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import Depends, Request
from limits import RateLimitItem, parse_many
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_limiter_db
from src.models.rate_limit import BUCKET_KEY_MAX_LENGTH, RateLimitCounter

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def client_address(request: Request) -> str:
    """The client IP, counted from the **end** of ``X-Forwarded-For``, not the start.

    ``X-Forwarded-For`` is ``client, proxy1, proxy2 …``: each proxy *appends* the address
    it received the connection from, so entries on the left are whatever the caller chose
    to send and only the rightmost were written by infrastructure we control.

    Reading the leftmost entry would let every IP-keyed limit be defeated by sending a
    different ``X-Forwarded-For`` on each request. The durable per-profile lockout would
    still bound PIN guessing, which is the only reason that would not be fatal.

    ``settings.trusted_proxy_count`` is how many hops in front of the app are ours —
    exactly one on Railway. Counting that many from the right lands on the address the
    closest trusted proxy observed, which is the furthest left an attacker cannot forge.
    A header with fewer hops than configured falls back to its leftmost entry rather than
    indexing past the end.
    """
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
        if hops:
            depth = min(max(settings.trusted_proxy_count, 1), len(hops))
            return hops[-depth]
    return get_remote_address(request)


#: In-process counters, reset on restart. Nothing security-critical lives here — the
#: login limit is durable (below). Kept so ordinary per-IP ceilings on future read
#: endpoints do not need a database round trip.
limiter = Limiter(key_func=client_address)


def login_key(request: Request) -> str:
    """``login:<display_name>:<ip>`` — per-credential *and* per-IP.

    Keyed on both so one person's failed attempts do not spend another's budget, and one
    IP cannot work through a list of names from a single bucket.

    FastAPI reads and caches the body in ``request._body`` before solving dependencies,
    so reading it synchronously here is safe. The name is taken from the **unvalidated**
    body — pydantic has not seen it yet — which is why
    :func:`durable_bucket_key` exists.
    """
    try:
        body_bytes: bytes = getattr(request, "_body", b"") or b""
        data = json.loads(body_bytes)
        name = str(data.get("displayName", "")).lower()
    except Exception:
        name = ""
    return f"login:{name}:{client_address(request)}"


# ── The durable half ─────────────────────────────────────────────────────────
#
# Kept imperative rather than decorated because the store is Postgres and the write is
# awaited — slowapi's `Limiter.hit` is synchronous, and a synchronous database call on
# the login path would block the event loop for every other request in flight.

#: ``/auth/login``. The batch's acceptance criterion, expressed as a limit.
LOGIN_LIMIT = "5/15 minutes"


def durable_bucket_key(key: str) -> str:
    """Fold a limiter key into something a ``String(200)`` column and a btree can hold.

    :func:`login_key` reads ``displayName`` out of the raw request body, so the key is as
    long as the caller wants it to be. In memory that was merely wasteful; against a
    column it is a ``DataError`` and a 500 on the endpoint an attacker is already probing.

    Long keys keep their readable prefix and end in a digest of the whole key, so two
    different long keys stay two different buckets rather than being merged by truncation.
    """
    if len(key) <= BUCKET_KEY_MAX_LENGTH:
        return key
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"{key[: BUCKET_KEY_MAX_LENGTH - len(digest) - 1]}:{digest}"


def _window_bounds(item: RateLimitItem) -> tuple[datetime, datetime]:
    """The fixed window ``now`` falls in, as naive UTC to match every other timestamp.

    Fixed windows aligned to the epoch — slowapi's default strategy, so moving the store
    does not change how the limit behaves.
    """
    span = item.get_expiry()
    now = int(time.time())
    start = now - (now % span)
    return (
        datetime.fromtimestamp(start, UTC).replace(tzinfo=None),
        datetime.fromtimestamp(start + span, UTC).replace(tzinfo=None),
    )


async def charge_durable_limit(
    session: AsyncSession, key: str, limit_value: str
) -> RateLimitItem | None:
    """Charge one hit and return the window that refused it, or ``None`` if none did.

    Multiple windows (``"2/hour;3/day"``) are charged in order and stop at the first
    refusal, exactly as slowapi charges them: a request the daily window turns away has
    still spent its hourly one.

    The count is committed **before** the caller decides what to do with the answer, and
    on a session of its own (:func:`src.database.get_limiter_db`) rather than the
    request's. That is the whole point: an attempt has to be counted whether or not the
    work behind it commits, and whether or not the process survives the next second.

    One statement per window, and the upsert rolls the window forward in place — so a
    counter that has aged out starts again at 1 without anything having to expire it, and
    the table holds one row per bucket rather than one per window.
    """
    for item in parse_many(limit_value):
        window_start, expires_at = _window_bounds(item)
        insert_stmt = insert(RateLimitCounter).values(
            bucket_key=durable_bucket_key(key),
            limit_item=item.key_for(),
            window_start_utc=window_start,
            hits=1,
            expires_at_utc=expires_at,
        )
        excluded = insert_stmt.excluded
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["bucket_key", "limit_item"],
            set_={
                # The whole of the fixed-window reset, expressed inside the upsert so no
                # read-then-write race can open between noticing the window has rolled
                # and acting on it: an aged-out row starts again at 1, a live one counts.
                "hits": case(
                    (RateLimitCounter.window_start_utc < excluded.window_start_utc, 1),
                    else_=RateLimitCounter.hits + 1,
                ),
                "window_start_utc": excluded.window_start_utc,
                "expires_at_utc": excluded.expires_at_utc,
            },
        ).returning(RateLimitCounter.hits)
        hits = (await session.execute(stmt)).scalar_one()
        await session.commit()
        if hits > item.amount:
            return item
    return None


async def consume_durable_limit(session: AsyncSession, key: str, limit_value: str) -> bool:
    """The boolean face of :func:`charge_durable_limit`. ``False`` when the bucket is spent."""
    return (await charge_durable_limit(session, key, limit_value)) is None


async def enforce_durable_limit(
    request: Request, session: AsyncSession, key: str, limit_value: str
) -> None:
    """Charge the bucket and raise slowapi's own 429 when it is spent.

    Raising ``RateLimitExceeded`` rather than a hand-built ``HTTPException`` is
    deliberate: the app installs ``_rate_limit_exceeded_handler``, which answers
    ``{"error": "Rate limit exceeded: 5 per 15 minute"}``, and the web ``AuthContext``
    reads that shape specifically — a 429 carrying ``detail`` instead would fall through
    to "your details are wrong" and invite the retry the limit just refused.

    ``request.state.view_rate_limit`` is set for the same reason: the handler reads it
    unconditionally, so a route that raises outside the decorator has to leave behind
    what the decorator would have.
    """
    refused_by = await charge_durable_limit(session, key, limit_value)
    if refused_by is None:
        return
    request.state.view_rate_limit = (refused_by, [key, ""])
    log.warning("durable ratelimit exceeded", limit=str(refused_by), path=request.url.path)
    raise RateLimitExceeded(Limit(refused_by, lambda: key, None, False, None, None, None, 1, False))


async def enforce_login_limit(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_limiter_db)],
) -> None:
    """``/auth/login``'s durable ``5/15 minutes``, as a dependency.

    A dependency and not a decorator because the charge is awaited. FastAPI reads and
    caches the request body before it solves dependencies, so :func:`login_key` sees the
    same ``request._body`` here that it would have under ``@limiter.limit``.
    """
    await enforce_durable_limit(request, session, login_key(request), LOGIN_LIMIT)


DurableLoginLimit = Annotated[None, Depends(enforce_login_limit)]
