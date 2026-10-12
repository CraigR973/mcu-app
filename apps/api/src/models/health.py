"""What the daily check reads and records — Batch X2 (DS44-01).

:class:`JobHeartbeat` is one row per scheduled job, and one for the API, rewritten each time it
runs whatever it did, so a job that is idle reads differently from one that has stopped.
:class:`HealthCheck` is the daily check's latest result for each check.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class JobHeartbeat(Base):
    __tablename__ = "job_heartbeats"

    #: ``cron-scrape``, ``cron-specs``, ``cron-ebay``, ``cron-values``, ``cron-reminders``, or
    #: ``api`` — the Railway service's own name.
    job: Mapped[str] = mapped_column(Text, primary_key=True)
    beat_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    #: What the run did, in a word or two: ``ran``, ``nothing due``, ``budget spent``…
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    #: The API's readiness at boot; nothing for the jobs so far.
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class HealthCheck(Base):
    __tablename__ = "health_checks"

    check_key: Mapped[str] = mapped_column(Text, primary_key=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: The problem in words, as the Home row shows it; null when ok.
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    #: When this problem first appeared, cleared when it goes.
    failing_since_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: When Craig was pushed about it, once per appearance.
    pushed_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
