"""§9.7 — per-person daily caps, and the graceful refusal when one is reached.

**Two ceilings, not one.** A message count alone does not bound spend: the same question
asked at the end of a long conversation costs many times what it costs at the start,
because the whole history is re-sent. §9.7 names both ("daily message / cost cap") and both
are enforced.

**The day is the person's day, not UTC's.** *"Resets next day"* is a promise to a person
holding a phone, and gotcha 26 is this project's standing record of what happens when a
local question is answered in UTC — a cap that resets at 01:00 on a British summer evening
has not reset "next day" to the person waiting for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.config import settings
from src.models.ai import AiSettings, AiUsageLogEntry
from src.models.notification import NotificationPreference

logger = structlog.get_logger(__name__)

DEFAULT_TIMEZONE = "Europe/London"


async def get_or_create_settings(db: AsyncSession, user_id: object) -> AiSettings:
    """This person's caps, seeded from config the first time they are read.

    Created on read rather than by migration, for the reason Batch 11 gives about
    notification preferences: a row seeded now goes missing for any profile added later,
    and the bug surfaces as "the cap does nothing for Mark".
    """
    existing = (
        await db.execute(select(AiSettings).where(AiSettings.user_id == user_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    created = AiSettings(
        user_id=user_id,
        daily_message_cap=settings.ai_daily_message_cap,
        daily_cost_cap_usd=Decimal(str(settings.ai_daily_cost_cap_usd)),
    )
    db.add(created)
    await db.flush()
    return created


async def _person_timezone(db: AsyncSession, user_id: object) -> ZoneInfo:
    """Where this person's day starts and ends.

    Read from `notification_preferences.quiet_hours_timezone`, which is already "this
    person's timezone" in everything but its name — Batch 11 stores an IANA zone there for
    exactly this class of question. **A dedicated column on `profiles` would be the tidier
    home** and is worth doing the moment a third feature needs it; adding one now would
    mean two sources of truth for the same fact and a migration to reconcile them later.
    """
    row = (
        await db.execute(
            select(NotificationPreference.quiet_hours_timezone).where(
                NotificationPreference.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    try:
        return ZoneInfo(row) if row else ZoneInfo(DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def local_day_bounds(now_utc: datetime, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """The naive-UTC instants bracketing the local day containing ``now_utc``."""

    def to_naive_utc(value: datetime) -> datetime:
        return value.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    local = now_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone)
    start_local = datetime.combine(local.date(), time.min, tzinfo=zone)
    end_local = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=zone)
    return to_naive_utc(start_local), to_naive_utc(end_local)


@dataclass(frozen=True)
class UsageToday:
    """What this person has spent today, and what they are allowed."""

    messages: int
    cost_usd: Decimal
    message_cap: int
    cost_cap_usd: Decimal
    #: When the counters go back to zero, as a UTC instant.
    resets_at_utc: datetime

    @property
    def messages_remaining(self) -> int:
        return max(self.message_cap - self.messages, 0)

    @property
    def over_message_cap(self) -> bool:
        return self.messages >= self.message_cap

    @property
    def over_cost_cap(self) -> bool:
        # A zero cost cap means "no cost ceiling", not "spend nothing" — the message cap
        # is the ceiling in that configuration.
        return self.cost_cap_usd > 0 and self.cost_usd >= self.cost_cap_usd

    @property
    def blocked(self) -> bool:
        return self.over_message_cap or self.over_cost_cap

    def refusal_message(self) -> str | None:
        """§9.7's "graceful limit reached message".

        Names which ceiling was hit and when it lifts. "You have reached your limit" with
        neither is the version that generates a support question rather than answering one.
        """
        if not self.blocked:
            return None
        local_reset = self.resets_at_utc.replace(tzinfo=ZoneInfo("UTC"))
        when = local_reset.strftime("%H:%M UTC")
        if self.over_message_cap:
            return (
                f"You have used all {self.message_cap} of today's messages. "
                f"Your allowance resets at {when}."
            )
        return (
            f"Today's spending limit of ${self.cost_cap_usd:.2f} has been reached. "
            f"It resets at {when}."
        )


async def usage_today(
    db: AsyncSession, user_id: object, *, now: datetime | None = None
) -> UsageToday:
    """Count this person's calls and spend inside their own local day."""
    now = now or utcnow()
    zone = await _person_timezone(db, user_id)
    start, end = local_day_bounds(now, zone)
    limits = await get_or_create_settings(db, user_id)

    totals = (
        await db.execute(
            select(
                func.count().label("messages"),
                func.coalesce(func.sum(AiUsageLogEntry.cost_usd), 0).label("cost"),
            ).where(
                AiUsageLogEntry.user_id == user_id,
                AiUsageLogEntry.created_at_utc >= start,
                AiUsageLogEntry.created_at_utc < end,
                # A call that failed is logged but does not count against the allowance:
                # being charged a message for an outage is the wrong way round.
                AiUsageLogEntry.error.is_(None),
            )
        )
    ).one()

    return UsageToday(
        messages=totals.messages,
        cost_usd=Decimal(totals.cost),
        message_cap=limits.daily_message_cap,
        cost_cap_usd=Decimal(limits.daily_cost_cap_usd),
        resets_at_utc=end,
    )
