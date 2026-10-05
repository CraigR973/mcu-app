"""The scheduled pass that turns dated facts into notifications.

Three senders live here, and between them they close two debts this batch inherited:
Batch 15 shipped §12.5's lending tracker without its "overdue triggers a push" clause, and
Batch 9 dropped the onboarding wizard's notifications step, both because push did not
exist (`DECISIONS.md` #50). It does now.

**Everything is driven by an ``as_of`` date the caller supplies.** That is Batch 37's
pattern and it is what makes §5.11's acceptance — *"test date set 2 weeks before a seeded
event triggers a reminder"* — a test rather than a fortnight of waiting. It also keeps
gotcha 26 at bay: the date arrives from :func:`src.clock.utc_today`, never from
``date.today()``.

**Each sender marks its source row before returning**, so a pass that runs twice on the
same day sends nothing the second time. The notification's own ``dedupe_key`` is the
second belt: it carries the recipient's id as well as the source row's, because the key is
unique across the whole table and two people are told about the same sale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utc_today, utcnow
from src.models.collection_item import CollectionItem
from src.models.loan import Loan
from src.models.movie import Movie
from src.models.notification import NotificationCategory
from src.models.profile import Profile
from src.models.release_calendar import (
    DISC_RELEASE_TYPES,
    RELEASE_TYPE_LABELS,
    ReleaseCalendarEntry,
)
from src.services.notifications import queue_notification
from src.services.sale_seasons import SALE_EVENT_TYPE, seed_year

logger = structlog.get_logger(__name__)

#: §5.11's "pre-sale push notifications", and the number its acceptance names.
SALE_LEAD_DAYS = 14
#: A week's warning on a disc coming out — long enough to pre-order, short enough that the
#: reminder is still about something imminent.
RELEASE_LEAD_DAYS = 7


@dataclass
class ReminderSummary:
    """What one pass did, by sender. Returned to the admin endpoint and asserted on."""

    as_of: date = field(default_factory=utc_today)
    sale_events: int = 0
    releases: int = 0
    overdue_loans: int = 0
    seasons_seeded: int = 0
    #: Notifications actually written. Lower than the sum above when a category is off,
    #: because a suppressed notification is still a row but a deduplicated one is not.
    queued: int = 0


async def _recipients(db: AsyncSession) -> list[Profile]:
    """Who hears about this: both people. The admin-only case went with Batch W3, whose
    overdue loans were its last user (`DECISIONS.md` #249)."""
    query = select(Profile).where(Profile.deleted_at.is_(None), Profile.is_active.is_(True))
    return list((await db.execute(query)).scalars().all())


async def notify_upcoming_sales(
    db: AsyncSession, *, as_of: date, now: datetime, summary: ReminderSummary
) -> None:
    """§5.11 — tell both people about a sale season inside the lead window.

    ``notified`` is checked and then set, so an event announces itself once however often
    this runs. The window is "between today and today + 14 days" rather than "exactly 14
    days away", because a pass that does not run for three days must still catch what it
    missed rather than skipping it silently.
    """
    horizon = as_of + timedelta(days=SALE_LEAD_DAYS)
    entries = list(
        (
            await db.execute(
                select(ReleaseCalendarEntry)
                .where(
                    ReleaseCalendarEntry.release_type == SALE_EVENT_TYPE,
                    ReleaseCalendarEntry.notified.is_(False),
                    ReleaseCalendarEntry.release_date >= as_of,
                    ReleaseCalendarEntry.release_date <= horizon,
                )
                .order_by(ReleaseCalendarEntry.release_date.asc())
            )
        )
        .scalars()
        .all()
    )
    if not entries:
        return

    people = await _recipients(db)
    for entry in entries:
        days_away = (entry.release_date - as_of).days
        when = "today" if days_away == 0 else f"in {days_away} day{'s' if days_away > 1 else ''}"
        for person in people:
            written = await queue_notification(
                db,
                user_id=person.id,
                category=NotificationCategory.sale_events,
                title=f"{entry.title} starts {when}",
                body=(
                    f"{entry.title} is on {entry.release_date:%A %-d %B}. "
                    "Now is a good time to check your wanted list."
                ),
                url="/wanted",
                dedupe_key=f"sale-event:{entry.id}:{person.id}",
                now=now,
            )
            if written is not None:
                summary.queued += 1
        entry.notified = True
        summary.sale_events += 1


async def notify_upcoming_releases(
    db: AsyncSession, *, as_of: date, now: datetime, summary: ReminderSummary
) -> None:
    """A 4K or Blu-ray about to go on sale: a week's warning, one push per disc.

    **Discs only.** Cinema dates are on the calendar to be looked at, not pushed. This rule
    used to cover every entry except a sale, and was harmless while the calendar was nearly
    empty. Batch T5 filled it with six months of cinema dates, and the first real run, at
    08:04 UTC on 24 Sep, sent Craig 27 pushes, 23 of them for films in cinemas
    (`DECISIONS.md` #210).
    """
    horizon = as_of + timedelta(days=RELEASE_LEAD_DAYS)
    entries = list(
        (
            await db.execute(
                select(ReleaseCalendarEntry)
                .where(
                    ReleaseCalendarEntry.release_type.in_(DISC_RELEASE_TYPES),
                    ReleaseCalendarEntry.notified.is_(False),
                    ReleaseCalendarEntry.release_date >= as_of,
                    ReleaseCalendarEntry.release_date <= horizon,
                )
                .order_by(ReleaseCalendarEntry.release_date.asc())
            )
        )
        .scalars()
        .all()
    )
    if not entries:
        return

    people = await _recipients(db)
    for entry in entries:
        kind = RELEASE_TYPE_LABELS.get(entry.release_type, entry.release_type)
        for person in people:
            written = await queue_notification(
                db,
                user_id=person.id,
                category=NotificationCategory.releases,
                title=f"{entry.title} — {kind}",
                body=f"Out on {entry.release_date:%A %-d %B}.",
                url="/calendar",
                dedupe_key=f"release:{entry.id}:{person.id}",
                now=now,
            )
            if written is not None:
                summary.queued += 1
        entry.notified = True
        summary.releases += 1


async def notify_overdue_loans(
    db: AsyncSession, *, as_of: date, now: datetime, summary: ReminderSummary
) -> None:
    """§12.5's missing half — *"overdue loan triggers a push"*.

    **Both people, each in their own words**, since Batch W3 (`DECISIONS.md` #249): either
    of them lends now, and Craig borrows. Until W3 only the admin heard, because lending was
    an admin action. The borrower, when they are one of the two, reads "You've had …"; the
    other reads the borrower's name, as everyone did before. ``loans.reminder_sent`` is the
    column Batch 15 left for exactly this, and it still makes the reminder a one-off.
    """
    rows = list(
        (
            await db.execute(
                select(Loan, CollectionItem, Movie)
                .join(CollectionItem, CollectionItem.id == Loan.collection_item_id)
                .join(Movie, Movie.id == CollectionItem.movie_id)
                .where(
                    Loan.returned_date.is_(None),
                    Loan.reminder_sent.is_(False),
                    Loan.due_date.is_not(None),
                    Loan.due_date < as_of,
                )
                .order_by(Loan.due_date.asc())
            )
        ).all()
    )
    if not rows:
        return

    people = await _recipients(db)
    for loan, _item, movie in rows:
        assert loan.due_date is not None  # guaranteed by the query's `is_not(None)`
        overdue_days = (as_of - loan.due_date).days
        for person in people:
            who = "You've" if loan.borrower_profile_id == person.id else f"{loan.borrower_name} has"
            written = await queue_notification(
                db,
                user_id=person.id,
                category=NotificationCategory.loans,
                title=f"{movie.title} is overdue",
                body=(
                    f"{who} had it since {loan.lent_date:%-d %B}; "
                    f"it was due back {overdue_days} day{'s' if overdue_days != 1 else ''} ago."
                ),
                url="/loans",
                dedupe_key=f"loan-overdue:{loan.id}:{person.id}",
                now=now,
            )
            if written is not None:
                summary.queued += 1
        loan.reminder_sent = True
        summary.overdue_loans += 1


async def run_reminders(
    db: AsyncSession,
    *,
    as_of: date | None = None,
    now: datetime | None = None,
    seed_seasons: bool = True,
) -> ReminderSummary:
    """Run every sender for one day, and return what each of them did.

    ``as_of`` and ``now`` are separate on purpose: the first is the calendar day the
    reminders are *about*, the second is the instant used for quiet hours and digest
    scheduling. A test that pretends it is a fortnight before Black Friday still wants
    "now" to be a real time of day.
    """
    as_of = as_of or utc_today()
    now = now or utcnow()
    summary = ReminderSummary(as_of=as_of)

    if seed_seasons:
        # This year and next, so a pass running in December still has January's dates.
        for year in (as_of.year, as_of.year + 1):
            summary.seasons_seeded += len(await seed_year(db, year))

    await notify_upcoming_sales(db, as_of=as_of, now=now, summary=summary)
    await notify_upcoming_releases(db, as_of=as_of, now=now, summary=summary)
    await notify_overdue_loans(db, as_of=as_of, now=now, summary=summary)

    logger.info(
        "reminders_run",
        as_of=as_of.isoformat(),
        sale_events=summary.sale_events,
        releases=summary.releases,
        overdue_loans=summary.overdue_loans,
        queued=summary.queued,
    )
    return summary
