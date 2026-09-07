"""The durable half of the rate limiter — one row per live bucket.

The acceptance criterion for this batch is that five failed PINs lock the account for
fifteen minutes **and that the lock survives a process restart**. An in-process counter
cannot satisfy that: `slowapi` reaches `limits`' `MemoryStorage`, so every Railway
redeploy hands each bucket a fresh window. This app redeploys on every push to `main`,
which makes a restart something an attacker can *wait for* rather than have to cause.

Only the limits where a reset is a **security** event live here. Anything protecting a
spend or a quota stays in memory, where it is fast and free.

**One row per bucket, not one per window.** The upsert in
:func:`src.rate_limit.charge_durable_limit` rolls ``window_start_utc`` forward in place,
so a key hit every fifteen minutes for a year occupies one row rather than thousands.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base

#: Widest ``bucket_key`` the table stores. ``login:<name>:<ip>`` is at most
#: ``6 + 100 + 1 + 45`` for a *valid* name, but the key is built from the raw request
#: body before pydantic has rejected anything, so
#: :func:`src.rate_limit.durable_bucket_key` folds anything longer into a digest rather
#: than letting a 10 MB display name reach a ``String`` column — or a btree index — and
#: 500 the endpoint an attacker is already probing.
BUCKET_KEY_MAX_LENGTH = 200


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"

    #: The limiter key — ``login:<name>:<ip>``.
    bucket_key: Mapped[str] = mapped_column(String(BUCKET_KEY_MAX_LENGTH), primary_key=True)

    #: ``RateLimitItem.key_for()`` — the canonical descriptor of the window, e.g.
    #: ``LIMITER/5/15/minute``. Part of the primary key so two limits on one route
    #: cannot share a counter.
    limit_item: Mapped[str] = mapped_column(String(64), primary_key=True)

    window_start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    hits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    #: Indexed so the nightly prune is a range scan rather than a sequential one.
    expires_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )
