"""§5.11's sale-season calendar — the dates worth knowing about before they arrive.

These land in ``release_calendar`` as ``sale_event`` rows rather than in a table of their
own. §3.26 already designs that vocabulary and Batch 17 already ships the feed, the
listing and the iCal export, so a sale season seeded here shows up in the calendar the
owner already reads and subscribes to. A parallel table would have needed all of it again.

**Generated per year rather than seeded by migration.** Every one of these recurs, so a
migration freezing 2026 and 2027 is stale by 2028 and cannot be re-run to fix itself. The
generator is idempotent on ``(title, release_date)``, so calling it twice for the same
year is a no-op and calling it for a new year is how next year's dates arrive.

**Two of these are estimates and say so.** Black Friday, Cyber Monday and Boxing Day are
derivable exactly. Amazon announces Prime Day about three weeks ahead, and Criterion's
flash sales are announced on the day — so those two carry an explicit "expected" in the
title. A reminder that admits it is approximate is useful; one that states a wrong date as
fact is worse than nothing.
"""

from __future__ import annotations

from calendar import THURSDAY
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.release_calendar import ReleaseCalendarEntry

#: ``release_calendar.release_type`` for everything this module writes.
SALE_EVENT_TYPE = "sale_event"


@dataclass(frozen=True)
class SaleSeason:
    """One dated sale, ready to become a calendar row."""

    title: str
    on: date
    label: str
    url: str | None = None
    #: ``True`` when the date is inferred rather than announced. Surfaced in the title so
    #: it survives into the calendar app, which shows nothing else.
    estimated: bool = False

    @property
    def display_title(self) -> str:
        return f"{self.title} (expected)" if self.estimated else self.title


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The ``n``-th ``weekday`` of a month — ``_nth_weekday(2026, 11, THURSDAY, 4)``."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def black_friday(year: int) -> date:
    """The day after US Thanksgiving, which is the fourth Thursday of November."""
    return _nth_weekday(year, 11, THURSDAY, 4) + timedelta(days=1)


def seasons_for(year: int) -> list[SaleSeason]:
    """Every sale season this app knows about in ``year``, in date order."""
    friday = black_friday(year)
    seasons = [
        SaleSeason(
            title="Amazon Spring Sale",
            on=_nth_weekday(year, 3, 1, 3),  # third Tuesday of March
            label="Amazon",
            url="https://www.amazon.co.uk/deals",
            estimated=True,
        ),
        SaleSeason(
            title="Amazon Prime Day",
            on=_nth_weekday(year, 7, 1, 2),  # second Tuesday of July
            label="Amazon",
            url="https://www.amazon.co.uk/primeday",
            estimated=True,
        ),
        SaleSeason(
            title="Criterion Flash Sale",
            on=_nth_weekday(year, 7, 2, 3),  # a mid-July Wednesday
            label="Criterion",
            url="https://www.criterion.com/shop",
            estimated=True,
        ),
        SaleSeason(
            title="Black Friday",
            on=friday,
            label="Retail",
            estimated=False,
        ),
        SaleSeason(
            title="Cyber Monday",
            on=friday + timedelta(days=3),
            label="Retail",
            estimated=False,
        ),
        SaleSeason(
            title="Criterion Winter Sale",
            on=_nth_weekday(year, 11, 2, 2),  # a mid-November Wednesday
            label="Criterion",
            url="https://www.criterion.com/shop",
            estimated=True,
        ),
        SaleSeason(
            title="Boxing Day Sales",
            on=date(year, 12, 26),
            label="Retail",
            estimated=False,
        ),
    ]
    return sorted(seasons, key=lambda season: season.on)


async def seed_year(
    db: AsyncSession, year: int, *, region: str = "GB"
) -> list[ReleaseCalendarEntry]:
    """Insert ``year``'s seasons that are not already there; return the new rows.

    Idempotent on title and date together, which is what lets the reminder pass call it
    without checking first. A season whose *date* moved — an estimate corrected once
    Amazon announces — inserts a second row rather than editing the first, because the
    two are genuinely different events and the old one may already have been notified.
    """
    seasons = seasons_for(year)
    existing = set(
        (
            await db.execute(
                select(ReleaseCalendarEntry.title, ReleaseCalendarEntry.release_date).where(
                    ReleaseCalendarEntry.release_type == SALE_EVENT_TYPE,
                    ReleaseCalendarEntry.release_date.between(date(year, 1, 1), date(year, 12, 31)),
                )
            )
        ).all()
    )

    created: list[ReleaseCalendarEntry] = []
    for season in seasons:
        if (season.display_title, season.on) in existing:
            continue
        entry = ReleaseCalendarEntry(
            title=season.display_title,
            release_type=SALE_EVENT_TYPE,
            release_date=season.on,
            label=season.label,
            region=region,
            url=season.url,
            overview=(
                "Date estimated from previous years; retailers announce the exact day "
                "closer to the time."
                if season.estimated
                else None
            ),
        )
        db.add(entry)
        created.append(entry)

    await db.flush()
    return created
