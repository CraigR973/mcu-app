"""Wire-level annotations shared by the response schemas.

``AGENTS.md`` states the convention this implements: *"UTC everywhere ... correct at the
wire with a ``UtcDatetime`` annotation, not at each call site."* Until Batch 7 nothing
implemented it, and nothing needed to — `DECISIONS.md` #14 is the standing warning that
a convention asserted in prose is not a convention in the code.

**Batch 7 is the first batch to put a timestamp on the wire at all.** Batch 6's
``watchedAt`` is a ``DATE``, which carries no offset to get wrong; ``conditionUpdatedAt``,
``deletedAt`` and the audit log's ``createdAt`` are instants, and every one of them is
rendered by the browser.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer


def _as_utc_iso(value: datetime) -> str:
    """Serialise a naive-UTC column as an unambiguous instant.

    Every domain timestamp in this app is stored ``DateTime(timezone=False)`` holding
    UTC, so a plain ``.isoformat()`` emits ``2026-09-08T14:00:00`` — which
    ``new Date()`` in the browser reads as *local* time. West of Greenwich that renders
    an hour or more in the past, and it does so silently: nothing errors, the timestamp
    is simply wrong. Stamping the offset here fixes it once for every field rather than
    at each of the places that display one.
    """
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")


#: A domain timestamp, serialised with an explicit ``Z``. Use this rather than a bare
#: ``datetime`` on anything a client will render.
UtcDatetime = Annotated[datetime, PlainSerializer(_as_utc_iso, return_type=str)]
