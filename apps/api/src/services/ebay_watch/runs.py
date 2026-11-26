"""One scheduled pass of price targets and the deal scan — Batch T8a.

Every two hours a job (`.railway/railway.ts`, ``cron-ebay``) runs
``python -m src.scripts.ebay_watch``: the targets first, because each is something a person
asked for, then the newest listings. The pass spends at most what is left of
:data:`DAILY_SHARE` eBay calls in the UTC day, on top of the valuation's 750 (#209), so
the film page's checks and barcode lookups keep the rest of eBay's 5,000.

**Pushes** (AG6, #383, agreed by both people on 24 Nov). A met target tells the person who
set it. A deal is pushed **at once** only when it is on the Wanted list or 40% or more under a
figure firm enough to carry a percentage (:data:`AT_ONCE_DISCOUNT`), at most
:data:`MAX_DEAL_PUSHES_PER_DAY` a person a day, Wanted-list finds first. **Every other find
waits for one summary a day** (:func:`queue_upgrade_summaries`), sent by the first pass at or
after 18:00 in the person's own time, naming the day's best finds not already pushed. A person
who chose Wanted-only (``deals_wanted_only``) hears only of Wanted-list finds. Before AG6, 121
of 124 deal pushes were upgrades sent as the night's passes found them, about a quarter of
them between midnight and 06:00 (MK53-05). All are in the ``deals`` category, sent at the end
of the pass, and quiet hours still hold: 22:00–07:00 by default since AG6.

**A find is re-checked before it is pushed** (Batch X1, MK47-04's bound, #254): one item
call, and a listing that has ended or sold out is not pushed and leaves the Deals page. The
push names the listing's own title and condition, so a wrong product the matcher could not
tell apart (*Maggie* for *The 'Maggie'*) reads as what it is.

**An expired find loses the listing's title and image** (eBay API licence §8.1.2, §3.1(b)),
keeping its price, dates and film: :func:`clear_ended_finds`, every pass. **So do its pushes**
(AG6, MK53-06): each push about it is rewritten in the film's words, and one still waiting to
be sent is not sent. The upgrade summary names films, never listings, so it keeps nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import Row, Select, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.ebay.client import DEFAULT_MAX_RETRIES, EbayError, EbayNotConfigured
from src.models.deal import Deal
from src.models.ebay_watch import EbayWatchRun
from src.models.movie import Movie
from src.models.notification import (
    SUPPRESSED_DEAL_ENDED,
    Notification,
    NotificationCategory,
    NotificationStatus,
)
from src.models.profile import Profile
from src.models.wanted import WantedItem
from src.services.ebay_watch.client import WatchClient
from src.services.ebay_watch.links import legacy_item_id
from src.services.ebay_watch.listings import item_state
from src.services.ebay_watch.scan import EBAY, FIRST_LOOK_BACK, Find, deal_backed, scan
from src.services.ebay_watch.targets import FORMAT_LABELS, Alert, check_targets, pounds, short
from src.services.notifications import (
    deliver_pending,
    get_or_create_preferences,
    person_zone,
    queue_notification,
)
from src.services.push_transport import push_sender

logger = structlog.get_logger(__name__)

#: eBay calls a UTC day's passes may make between them: 10% of eBay's 5,000.
DAILY_SHARE = 500
RUN_STALE_AFTER = timedelta(minutes=30)
#: Too few calls to be worth starting on: one call and its retries.
MIN_RUN_BUDGET = DEFAULT_MAX_RETRIES + 1
#: Deal pushes a person gets at once in a UTC day, at most. Since AG6 only Wanted-list finds
#: and finds of :data:`AT_ONCE_DISCOUNT` or more come at once, so this is a backstop.
MAX_DEAL_PUSHES_PER_DAY = 5
DEAL_KEY_PREFIX = "ebay-deal:"
#: AG6 (#383): a find this far under a backed figure is pushed at once, upgrade or not.
AT_ONCE_DISCOUNT = 40
#: AG6 (#383): the local hour of the day's one summary of the other finds. The pass runs at
#: twenty past every second UTC hour, so in winter it comes at 18:20, and in British Summer
#: Time, when 18:00 falls between passes, at 19:20.
SUMMARY_HOUR = 18
SUMMARY_KEY_PREFIX = "ebay-summary:"
#: Finds the summary names; the rest are counted and wait on the Deals page.
SUMMARY_LINES = 5

StartReason = Literal["started", "running", "budget_spent"]


@dataclass(frozen=True)
class StartOutcome:
    reason: StartReason
    run: EbayWatchRun | None
    budget_left: int


def day_start(now: datetime) -> datetime:
    return datetime.combine(now.date(), time.min)


async def budget_left(db: AsyncSession, *, now: datetime) -> int:
    """Calls today's passes may still make, or 0 if too few to start one."""
    spent = await db.scalar(
        select(func.coalesce(func.sum(EbayWatchRun.calls), 0)).where(
            EbayWatchRun.started_utc >= day_start(now)
        )
    )
    left = DAILY_SHARE - int(spent or 0)
    return left if left >= MIN_RUN_BUDGET else 0


async def abandon_stale_runs(db: AsyncSession, *, now: datetime) -> None:
    await db.execute(
        update(EbayWatchRun)
        .where(EbayWatchRun.status == "running", EbayWatchRun.heartbeat_utc < now - RUN_STALE_AFTER)
        .values(
            status="abandoned",
            finished_utc=now,
            last_error="Nothing heard from it for 30 minutes; its process probably stopped.",
        )
    )
    await db.commit()


async def latest_run(db: AsyncSession) -> EbayWatchRun | None:
    result = await db.execute(
        select(EbayWatchRun).order_by(EbayWatchRun.started_utc.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def scanned_up_to(db: AsyncSession, *, before: datetime) -> datetime | None:
    """Where the last pass that read listings got to, ignoring any mark after ``before``.

    ``before`` is the reading pass's own start. A mark later than that cannot be a place a
    pass got to; it is one a listing dated in the future set before Batch X1 (21 Oct 16:35,
    stored on 9 Oct). Ignoring it is what lets the next pass read again, with no data write.
    """
    return await db.scalar(
        select(func.max(EbayWatchRun.newest_listing_utc)).where(
            EbayWatchRun.newest_listing_utc.is_not(None),
            EbayWatchRun.newest_listing_utc <= before,
        )
    )


def _film_title_or_default() -> object:
    return func.coalesce(
        select(Movie.title).where(Movie.id == Deal.movie_id).scalar_subquery(), "eBay listing"
    )


@dataclass(frozen=True)
class EndedFind:
    """What an ended find's pushes may still say: its film, format and price, no listing."""

    url: str
    film: str
    year: int | None
    format_code: str | None
    price: Decimal


def ended_push_title(find: EndedFind) -> str:
    year = f" ({find.year})" if find.year else ""
    label = FORMAT_LABELS.get(find.format_code or "", "disc")
    return short(f"{find.film}{year} on {label}, on eBay", 200)


def ended_push_body(find: EndedFind) -> str:
    year = f" ({find.year})" if find.year else ""
    label = FORMAT_LABELS.get(find.format_code or "", "disc")
    return (
        f"An eBay find that has ended: {pounds(find.price)} with postage, filed as "
        f"{find.film}{year} on {label}. The listing's own words are not kept once it ends."
    )


async def _pushes_of(db: AsyncSession, find: EndedFind) -> Sequence[Notification]:
    return (
        await db.scalars(
            select(Notification).where(
                Notification.dedupe_key.like(f"{DEAL_KEY_PREFIX}%"),
                Notification.url == find.url,
            )
        )
    ).all()


def _still_words(row: Notification, find: EndedFind) -> bool:
    """The push still holds the listing's words, or is waiting to be sent."""
    return (
        row.title != ended_push_title(find)
        or row.body != ended_push_body(find)
        or row.status == NotificationStatus.queued.value
    )


async def pushes_to_forget(db: AsyncSession, ended: list[EndedFind]) -> int:
    """How many push rows :func:`forget_pushed_listings` would change. Reads only."""
    count = 0
    for find in ended:
        count += sum(1 for row in await _pushes_of(db, find) if _still_words(row, find))
    return count


async def forget_pushed_listings(db: AsyncSession, ended: list[EndedFind]) -> int:
    """Rewrite each push about these ended finds in the film's words (AG6, MK53-06).

    A push still waiting (quiet hours) is not sent: it would name a listing that has gone.
    Returns how many push rows changed; a row already in the film's words is left alone.
    """
    changed = 0
    for find in ended:
        for row in await _pushes_of(db, find):
            if not _still_words(row, find):
                continue
            waiting = row.status == NotificationStatus.queued.value
            row.title, row.body = ended_push_title(find), ended_push_body(find)
            if waiting:
                row.status = NotificationStatus.suppressed.value
                row.suppressed_reason = SUPPRESSED_DEAL_ENDED
            changed += 1
    await db.flush()
    return changed


#: An outer join: the film's title is ``None`` for a find no film was filed under.
_EndedRow = tuple[str, str, int | None, str | None, Decimal]


def _ended_finds_query() -> Select[_EndedRow]:
    query: Select[_EndedRow] = select(
        Deal.url, Movie.title, Movie.year, Deal.format_code, Deal.price
    ).outerjoin(Movie, Movie.id == Deal.movie_id)
    return query


def _ended(
    rows: Sequence[Row[_EndedRow]],
) -> list[EndedFind]:
    return [
        EndedFind(url=url, film=title or "eBay listing", year=year, format_code=code, price=price)
        for url, title, year, code, price in rows
    ]


async def clear_ended_finds(db: AsyncSession, *, now: datetime) -> None:
    """An expired eBay find keeps its price, dates and film, and loses the listing's words.

    eBay's API licence lets an app keep a listing's content only while it is current
    (§8.1.2, §3.1(b)). The title becomes the film's, the image and condition go, and since
    AG6 its pushes are rewritten too (:func:`forget_pushed_listings`). Only the finds ending
    in this pass are touched, so push rows stored before AG6 wait for the owner's word
    (`src.scripts.deal_pushes_owner_step`).
    """
    film_title = _film_title_or_default()
    ending = (
        Deal.retailer_id.is_(None),
        Deal.retailer_name_snapshot == EBAY,
        Deal.expires_at_utc <= now,
        or_(
            Deal.image_url.is_not(None),
            Deal.listing_condition.is_not(None),
            Deal.title_snapshot != film_title,
        ),
    )
    # The same finds, read with the film joined rather than through the correlated title.
    reading = (
        *ending[:3],
        or_(
            Deal.image_url.is_not(None),
            Deal.listing_condition.is_not(None),
            Deal.title_snapshot != func.coalesce(Movie.title, "eBay listing"),
        ),
    )
    ended = _ended((await db.execute(_ended_finds_query().where(*reading))).all())
    await db.execute(
        update(Deal)
        .where(*ending)
        .values(title_snapshot=film_title, image_url=None, listing_condition=None)
        .execution_options(synchronize_session=False)
    )
    await forget_pushed_listings(db, ended)
    await db.commit()


async def stored_ended_finds(db: AsyncSession, *, now: datetime) -> list[EndedFind]:
    """Every eBay find that has ended and has a push: the owner-word pass's set (AG6)."""
    pushed = select(Notification.url).where(Notification.dedupe_key.like(f"{DEAL_KEY_PREFIX}%"))
    rows = await db.execute(
        _ended_finds_query().where(
            Deal.retailer_id.is_(None),
            Deal.retailer_name_snapshot == EBAY,
            Deal.expires_at_utc <= now,
            Deal.url.in_(pushed),
        )
    )
    return _ended(rows.all())


async def start_run(
    db: AsyncSession,
    *,
    trigger: Literal["job", "admin"],
    started_by: uuid.UUID | None = None,
    now: datetime | None = None,
) -> StartOutcome:
    """Claim the one running slot, if today's share has calls left."""
    now = now or utcnow()
    await abandon_stale_runs(db, now=now)
    left = await budget_left(db, now=now)
    running = await db.scalar(select(EbayWatchRun.id).where(EbayWatchRun.status == "running"))
    if running is not None:
        return StartOutcome("running", None, left)
    if left == 0:
        return StartOutcome("budget_spent", None, left)
    run = EbayWatchRun(
        id=uuid.uuid4(),
        trigger=trigger,
        status="running",
        started_by=started_by,
        started_utc=now,
        heartbeat_utc=now,
        budget=left,
        calls=0,
        targets_checked=0,
        target_alerts=0,
        pages=0,
        listings_seen=0,
        candidates=0,
        refs_fetched=0,
        deals_found=0,
        deals_pushed=0,
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return StartOutcome("running", None, left)
    return StartOutcome("started", run, left)


# ---------------------------------------------------------------------------
# Pushes
# ---------------------------------------------------------------------------


async def _queue_alert(db: AsyncSession, alert: Alert, *, now: datetime) -> bool:
    written = await queue_notification(
        db,
        user_id=alert.user_id,
        category=NotificationCategory.deals,
        title=alert.title,
        body=alert.body,
        url=alert.url,
        dedupe_key=alert.dedupe_key,
        now=now,
    )
    return written is not None


async def _deal_pushes_today(db: AsyncSession, user_id: uuid.UUID, *, now: datetime) -> int:
    count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.dedupe_key.like(f"{DEAL_KEY_PREFIX}%"),
            Notification.created_at_utc >= day_start(now),
        )
    )
    return int(count or 0)


def _under(find_total: Decimal, figure: Decimal, *, percent: int, backed: bool) -> str:
    """ "45% under £X", or, on a thin figure, "under the few asks seen, £X" (AG6, MK53-04)."""
    if backed:
        return f"{percent}% under {pounds(figure)}"
    return f"under the few asks seen, {pounds(figure)}"


def deal_alert(find: Find, user_id: uuid.UUID) -> Alert:
    """The push: the listing's own title and condition first, then the film it was filed as.

    Since Batch X1 the title is the listing's, not the film's: of the 60 deal pushes before
    9 Oct, 14 were another product under a film's name, and three of those no title rule
    can tell apart. The usual price says what it is: asking prices, and how many. Since AG6
    a percentage is given only on a figure of 5 or more asks or 3 or more sales.
    """
    label = FORMAT_LABELS.get(find.format_code, find.format_code)
    why = (
        "It's on the Wanted list."
        if find.wanted
        else "It would be an upgrade on the copy on the shelf."
    )
    year = f" ({find.film.year})" if find.film.year else ""
    judged_against = find.figure.sources()[0]["source"].lower()
    under = _under(
        find.listing.total, find.figure.amount, percent=find.discount_percent, backed=find.backed
    )
    return Alert(
        user_id=user_id,
        title=short(find.listing.listing.title, 80),
        body=(
            f"{find.condition}, {pounds(find.listing.total)} with postage on eBay: "
            f"{under} ({judged_against}). "
            f"Filed as {short(find.film.title)}{year} on {label}. {why}"
        ),
        url=find.listing.url,
        dedupe_key=f"{DEAL_KEY_PREFIX}{find.listing.legacy_id}:{user_id}",
    )


def pushed_at_once(find: Find) -> bool:
    """A Wanted-list find, or one 40% or more under a backed figure (AG6, #383)."""
    return find.wanted or (find.backed and find.discount_percent >= AT_ONCE_DISCOUNT)


#: Answers whether a listing, by its number, can still be bought: ``True``, ``False`` when
#: it has ended or sold out, ``None`` when that could not be asked (no budget, or eBay failed).
Recheck = Callable[[str], Awaitable[bool | None]]


async def _already_told(db: AsyncSession, alert: Alert) -> bool:
    found = await db.scalar(
        select(Notification.id).where(Notification.dedupe_key == alert.dedupe_key).limit(1)
    )
    return found is not None


async def end_find(db: AsyncSession, url: str, *, now: datetime) -> None:
    """Take a find that has ended or sold out off the Deals page now."""
    await db.execute(
        update(Deal)
        .where(
            Deal.retailer_id.is_(None),
            Deal.retailer_name_snapshot == EBAY,
            Deal.url == url,
        )
        .values(expires_at_utc=now)
        .execution_options(synchronize_session=False)
    )


def item_rechecker(
    client: WatchClient, run: EbayWatchRun, *, clock: Callable[[], datetime]
) -> Recheck:
    """One item call per listing, within the pass's budget."""

    async def still_for_sale(legacy_id: str) -> bool | None:
        if client.search_calls + client.attempts_per_search > run.budget:
            return None
        try:
            payload = await client.get_item_by_legacy_id(legacy_id)
        except EbayError as exc:
            logger.warning("ebay_deal_recheck_failed", item=legacy_id, error=str(exc))
            return None
        state = item_state(payload) if payload is not None else None
        if state is None or not state.available:
            return False
        return state.ends_at is None or state.ends_at > clock()

    return still_for_sale


async def _people(db: AsyncSession) -> list[uuid.UUID]:
    return list(
        (
            await db.scalars(
                select(Profile.id).where(Profile.deleted_at.is_(None), Profile.is_active.is_(True))
            )
        ).all()
    )


async def queue_deal_pushes(
    db: AsyncSession, finds: list[Find], *, now: datetime, recheck: Recheck
) -> int:
    """Tell each person at once of the finds worth it, within their daily limit (AG6).

    Only :func:`pushed_at_once` finds, and for a person who chose Wanted-only only the
    Wanted list's. The rest wait for :func:`queue_upgrade_summaries`. Each find is
    re-checked once, just before its first push: one that has ended or sold out is not
    pushed and leaves the Deals page; one that could not be checked is not pushed and stays
    there. Returns how many finds were pushed to anyone.
    """
    at_once = [find for find in finds if pushed_at_once(find)]
    if not at_once:
        return 0
    ordered = sorted(at_once, key=lambda find: (not find.wanted, -find.discount_percent))
    pushed: set[str] = set()
    checked: dict[str, bool | None] = {}
    for person in await _people(db):
        wanted_only = (await get_or_create_preferences(db, person)).deals_wanted_only
        room = MAX_DEAL_PUSHES_PER_DAY - await _deal_pushes_today(db, person, now=now)
        for find in ordered:
            if room <= 0:
                break
            if wanted_only and not find.wanted:
                continue
            alert = deal_alert(find, person)
            if await _already_told(db, alert):
                continue
            key = find.listing.legacy_id
            if key not in checked:
                checked[key] = await recheck(key)
                if checked[key] is False:
                    await end_find(db, find.listing.url, now=now)
            if not checked[key]:
                continue
            if await _queue_alert(db, alert, now=now):
                room -= 1
                pushed.add(key)
    return len(pushed)


# ---------------------------------------------------------------------------
# The day's summary (AG6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SummaryLine:
    """One find in the summary, in the film's words: a summary keeps no listing's."""

    url: str
    film: str
    year: int | None
    format_code: str | None
    price: Decimal
    percent: int | None
    backed: bool

    def text(self) -> str:
        year = f" ({self.year})" if self.year else ""
        label = FORMAT_LABELS.get(self.format_code or "", "disc")
        under = (
            f"{self.percent}% under"
            if self.backed and self.percent is not None
            else "under the few asks seen"
        )
        return f"• {short(self.film)}{year} on {label}: {pounds(self.price)}, {under}"


def summary_due(zone: ZoneInfo, now: datetime) -> date | None:
    """The local day whose summary is due at ``now``, or ``None`` before 18:00 there."""
    local = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone)
    return local.date() if local.hour >= SUMMARY_HOUR else None


def _summary_window_start(day: date, zone: ZoneInfo) -> datetime:
    """The previous summary's moment: 18:00 local the day before, as naive UTC."""
    local = datetime.combine(day - timedelta(days=1), time(SUMMARY_HOUR), tzinfo=zone)
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


async def _summary_candidates(
    db: AsyncSession, person: uuid.UUID, *, since: datetime, now: datetime, wanted_only: bool
) -> list[SummaryLine]:
    """The window's live eBay finds this person has not been pushed, best first."""
    told = select(Notification.url).where(
        Notification.user_id == person,
        Notification.dedupe_key.like(f"{DEAL_KEY_PREFIX}%"),
        Notification.url.is_not(None),
    )
    query = (
        select(Deal, Movie.title, Movie.year)
        .join(Movie, Movie.id == Deal.movie_id)
        .where(
            Deal.retailer_id.is_(None),
            Deal.retailer_name_snapshot == EBAY,
            Deal.first_seen_at_utc > since,
            Deal.expires_at_utc > now,
            Deal.dismissed_at_utc.is_(None),
            Deal.url.not_in(told),
        )
    )
    if wanted_only:
        query = query.where(
            Deal.movie_id.in_(
                select(WantedItem.movie_id).where(
                    WantedItem.deleted_at.is_(None), WantedItem.is_active.is_(True)
                )
            )
        )
    lines = [
        SummaryLine(
            url=deal.url,
            film=title,
            year=year,
            format_code=deal.format_code,
            price=deal.price,
            percent=deal.discount_percent,
            backed=deal_backed(deal),
        )
        for deal, title, year in (await db.execute(query)).all()
    ]
    return sorted(lines, key=lambda line: (not line.backed, -(line.percent or 0), line.price))


async def queue_upgrade_summaries(
    db: AsyncSession, *, now: datetime, recheck: Recheck
) -> set[uuid.UUID]:
    """Each person's one summary of the day's other finds, once it is 18:00 for them (AG6).

    The day runs from 18:00 the day before. Finds already pushed to the person are left out,
    and the best :data:`SUMMARY_LINES` are re-checked and named; one that has ended leaves the
    Deals page and the summary, one that could not be checked is counted but not named.
    Nothing is sent when nothing is left. Returns who has a summary queued.
    """
    told: set[uuid.UUID] = set()
    checked: dict[str, bool | None] = {}
    for person in await _people(db):
        preference = await get_or_create_preferences(db, person)
        zone = person_zone(preference)
        day = summary_due(zone, now)
        if day is None:
            continue
        key = f"{SUMMARY_KEY_PREFIX}{day.isoformat()}:{person}"
        if await db.scalar(select(Notification.id).where(Notification.dedupe_key == key)):
            continue
        candidates = await _summary_candidates(
            db,
            person,
            since=_summary_window_start(day, zone),
            now=now,
            wanted_only=preference.deals_wanted_only,
        )
        named: list[SummaryLine] = []
        waiting = 0
        for line in candidates:
            if len(named) >= SUMMARY_LINES:
                waiting += 1
                continue
            legacy_id = legacy_item_id(line.url)
            if legacy_id is None:
                continue
            if legacy_id not in checked:
                checked[legacy_id] = await recheck(legacy_id)
                if checked[legacy_id] is False:
                    await end_find(db, line.url, now=now)
            if checked[legacy_id] is False:
                continue
            if checked[legacy_id] is None:
                waiting += 1
                continue
            named.append(line)
        if not named:
            continue
        count = len(named) + waiting
        lines = [line.text() for line in named]
        if waiting:
            lines.append(f"…and {waiting} more on the Deals page.")
        written = await queue_notification(
            db,
            user_id=person,
            category=NotificationCategory.deals,
            title=f"Today's eBay finds: {count}",
            body="\n".join(lines),
            url="/deals",
            dedupe_key=key,
            now=now,
        )
        if written is not None:
            told.add(person)
    await db.flush()
    return told


async def deliver_now(db: AsyncSession, user_ids: set[uuid.UUID]) -> None:
    """Send what the pass queued, now, rather than at the next morning's pass.

    Quiet hours still defer: a push held by them is not due yet. A failed send never fails
    the pass; the notification stays queued for the next delivery.
    """
    if not user_ids:
        return
    try:
        async with push_sender() as sender:
            for user_id in user_ids:
                await deliver_pending(db, sender=sender, user_id=user_id)
        await db.commit()
    except Exception:  # noqa: BLE001 - see the docstring
        logger.warning("ebay_watch_push_failed", exc_info=True)
        await db.rollback()


async def record_delivered(db: AsyncSession, run: EbayWatchRun) -> int:
    """Set the run's pushed count to finds actually delivered to a phone (Batch X3).

    The pass counts what it queued; a push held by quiet hours, or meeting no live device,
    was not delivered, and before X3 the run counted it anyway, so "5 pushed" could mean
    nobody heard. Counted after delivery, by the finds whose push reached anyone.
    """
    delivered = await db.scalar(
        select(func.count(func.distinct(func.split_part(Notification.dedupe_key, ":", 2)))).where(
            Notification.dedupe_key.like(f"{DEAL_KEY_PREFIX}%"),
            Notification.status == NotificationStatus.sent.value,
            Notification.created_at_utc >= run.started_utc,
        )
    )
    run.deals_pushed = int(delivered or 0)
    await db.commit()
    return run.deals_pushed


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------


@dataclass
class PassResult:
    run: EbayWatchRun
    #: Who has something queued, to be sent now.
    told: set[uuid.UUID]


async def work_run(
    db: AsyncSession,
    client: WatchClient,
    run_id: uuid.UUID,
    *,
    clock: Callable[[], datetime] = utcnow,
) -> PassResult:
    """Check the targets, then scan the newest listings, then queue what they found."""
    run = await db.get(EbayWatchRun, run_id)
    if run is None or run.status != "running":
        raise ValueError(f"eBay watch run {run_id} is not running")
    told: set[uuid.UUID] = set()
    try:
        outcome: str | None = None
        alerts, stopped = await check_targets(db, client, run, clock=clock)
        for alert in alerts:
            # A repeat of a push already sent is dropped by its key and not counted.
            if await _queue_alert(db, alert, now=clock()):
                told.add(alert.user_id)
                run.target_alerts += 1
        await db.commit()
        if stopped == "failed":
            outcome = "stopped"
        elif stopped == "budget":
            outcome = "budget_spent"
        else:
            await clear_ended_finds(db, now=clock())
            since = await scanned_up_to(db, before=run.started_utc) or (
                run.started_utc - FIRST_LOOK_BACK
            )
            ended = await scan(db, client, run, since=since, clock=clock)
            recheck = item_rechecker(client, run, clock=clock)
            run.deals_pushed = await queue_deal_pushes(
                db, ended.finds, now=clock(), recheck=recheck
            )
            told |= await queue_upgrade_summaries(db, now=clock(), recheck=recheck)
            await db.commit()
            await clear_ended_finds(db, now=clock())
            if run.deals_pushed:
                told |= set(await _people(db))
            if ended.stopped == "failed":
                outcome = "stopped"
            elif ended.stopped == "budget":
                outcome = "budget_spent"
        finished = clock()
        run.calls = client.search_calls
        run.status = outcome or "finished"
        run.finished_utc = finished
        run.heartbeat_utc = finished
        await db.commit()
    except EbayNotConfigured:
        await db.rollback()
        run = await _stop(db, run_id, clock(), "eBay is not configured in this deployment.")
    except EbayError as exc:
        await db.rollback()
        run = await _stop(db, run_id, clock(), f"eBay: {exc}", calls=client.search_calls)
    except Exception as exc:
        await db.rollback()
        await _stop(db, run_id, clock(), f"{type(exc).__name__}: {exc}", calls=client.search_calls)
        raise
    return PassResult(run=run, told=told)


async def _stop(
    db: AsyncSession, run_id: uuid.UUID, now: datetime, reason: str, *, calls: int | None = None
) -> EbayWatchRun:
    run = await db.get(EbayWatchRun, run_id)
    if run is None:  # pragma: no cover - the row was committed before any of this
        raise ValueError(f"eBay watch run {run_id} vanished")
    if run.status == "running":
        run.status = "stopped"
        run.finished_utc = now
        run.heartbeat_utc = now
        run.last_error = reason[:500]
        if calls is not None:
            run.calls = calls
        await db.commit()
    return run
