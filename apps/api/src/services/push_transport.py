"""How a caller gets hold of a :class:`PushSender` — and how a test replaces one.

This lived in `routers/notifications.py` until the cron scripts needed it. A scheduled
job importing a *router* to obtain a transport would drag FastAPI, every schema and the
whole route table into a process whose only job is to send some pushes, so the seam moved
down here and the router re-exports it. `DECISIONS.md` #119 is the record.

Production leaves the override ``None`` and gets :class:`HttpPushSender` over a client
opened per call — push is rare enough that a pooled client buys nothing, and a
module-level one would outlive the event loop it was created on.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import httpx

from src.services.notifications import HttpPushSender, PushSender

#: Overridden by the tests, which must never reach a push service.
_sender_override: PushSender | None = None


def set_push_sender(sender: PushSender | None) -> None:
    """Substitute the push transport. Used by tests; never called in production."""
    global _sender_override
    _sender_override = sender


@contextlib.asynccontextmanager
async def push_sender() -> AsyncIterator[PushSender]:
    if _sender_override is not None:
        yield _sender_override
        return
    async with httpx.AsyncClient() as client:
        yield HttpPushSender(client)
