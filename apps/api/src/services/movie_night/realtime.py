"""Realtime for movie night — Postgres `LISTEN`/`NOTIFY` with SSE to the browser.

`DECISIONS.md` #113 settled this: §8.4 names Supabase Realtime and there is no Supabase
project, so votes and matches travel over a notify channel the API already has a database
for. No new service, no new credential, no new bill.

**#113's constraint is the whole design of this module.** `LISTEN` occupies a connection
for as long as it is listening, and borrowing one from the request pool for the life of a
movie night exhausts the pool and looks like the entire app hanging — the same silent shape
as Batch 8's paused query. So there is **one** dedicated connection, opened when the first
person starts watching and closed when the last one stops, fanning out in-process to an
`asyncio.Queue` per viewer.

**And it is correct at two containers, which the in-process half alone would not be.** Both
instances `LISTEN` on the same channel, so a vote cast against one is delivered to watchers
on the other. That is the difference between this and #60's cron, where running in two
places is the bug rather than the point.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import asyncpg
import structlog

from src.config import psycopg2_dsn, settings

logger = structlog.get_logger(__name__)

#: One channel for the whole feature; the payload names the session. Postgres identifiers
#: cap at 63 bytes, so a channel per session would also need hashing — and `NOTIFY` fans
#: out cheaply enough that filtering in-process is the simpler correct thing.
CHANNEL = "mcu_movie_night"

#: `NOTIFY` refuses a payload over 8000 bytes. Nothing here is close, but a truncated
#: notification is an event that silently never arrives, so the guard is explicit.
MAX_PAYLOAD_BYTES = 7000

#: How many events a slow viewer may fall behind before their oldest are dropped. A tab
#: that has been backgrounded for an hour must not grow a queue without bound.
QUEUE_LIMIT = 100


class MovieNightBroadcaster:
    """One `LISTEN` connection, many in-process subscribers.

    Started lazily and stopped when the last subscriber leaves, so an app with nobody
    watching holds no extra connection at all.
    """

    def __init__(self) -> None:
        self._connection: asyncpg.Connection[Any] | None = None
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        # Guards start/stop. Two people opening a session at the same instant would
        # otherwise race to open two listening connections.
        self._lock = asyncio.Lock()

    @property
    def listening(self) -> bool:
        return self._connection is not None

    def _dispatch(
        self,
        _connection: asyncpg.Connection[Any] | asyncpg.pool.PoolConnectionProxy[Any],
        _pid: int,
        _channel: str,
        payload: object,
    ) -> None:
        """asyncpg's listener callback. Synchronous, and must never raise.

        An exception here is swallowed by asyncpg and the listener carries on *looking*
        healthy while delivering nothing, so everything below is guarded.

        The signature is asyncpg's own, not a convenient one — `payload` really is typed
        `object`, because a connection in binary mode delivers bytes. Narrowing it here
        rather than assuming `str` is exactly what the stubs bought.
        """
        if not isinstance(payload, str | bytes):  # pragma: no cover - guarded shape
            logger.warning("movie_night_unexpected_payload_type")
            return
        try:
            event = json.loads(payload)
            session_id = str(event.get("sessionId", ""))
        except (ValueError, TypeError, AttributeError):
            logger.warning("movie_night_bad_payload")
            return

        for queue in self._subscribers.get(session_id, set()):
            if queue.full():
                # Drop the oldest rather than block the listener. A backgrounded tab must
                # not be able to stall delivery for everybody else.
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(event)

    async def _ensure_listening(self) -> None:
        if self._connection is not None:
            return
        # The libpq-style DSN: `settings.database_url` is normalised for SQLAlchemy's
        # asyncpg dialect (`postgresql+asyncpg://`, `ssl=`), which `asyncpg.connect` does
        # not accept. `psycopg2_dsn` already converts exactly those two things back.
        self._connection = await asyncpg.connect(psycopg2_dsn(settings.database_url))
        await self._connection.add_listener(CHANNEL, self._dispatch)
        logger.info("movie_night_listening", channel=CHANNEL)

    async def _stop_if_idle(self) -> None:
        if self._connection is None or any(self._subscribers.values()):
            return
        connection, self._connection = self._connection, None
        try:
            await connection.remove_listener(CHANNEL, self._dispatch)
        finally:
            await connection.close()
        logger.info("movie_night_stopped_listening")

    async def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Start watching one session."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_LIMIT)
        async with self._lock:
            self._subscribers.setdefault(session_id, set()).add(queue)
            await self._ensure_listening()
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Stop watching, and release the connection if nobody else is."""
        async with self._lock:
            watchers = self._subscribers.get(session_id)
            if watchers is not None:
                watchers.discard(queue)
                if not watchers:
                    del self._subscribers[session_id]
            await self._stop_if_idle()

    async def close(self) -> None:  # pragma: no cover - shutdown path
        async with self._lock:
            self._subscribers.clear()
            await self._stop_if_idle()


#: One per process. Module-level rather than on `app.state` so the tests can reach it
#: without standing up the whole application.
broadcaster = MovieNightBroadcaster()


def encode(session_id: str, kind: str, data: dict[str, Any]) -> str:
    """The notification payload, bounded."""
    payload = json.dumps({"sessionId": session_id, "kind": kind, **data})
    if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:  # pragma: no cover - guarded shape
        payload = json.dumps({"sessionId": session_id, "kind": kind})
    return payload
