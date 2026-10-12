"""One scheduled pass of price targets and the deal scan — Batch T8a.

Every two hours a job (`.railway/railway.ts`, ``cron-ebay``) runs
``python -m src.scripts.ebay_watch``: the targets first, because each is something a person
asked for, then the newest listings. The pass spends at most what is left of
:data:`DAILY_SHARE` eBay calls in the UTC day, on top of the valuation's 750 (#209), so
the film page's checks and barcode lookups keep the rest of eBay's 5,000.

**Pushes.** A met target tells the person who set it. A deal tells both people, as the
Wanted list's price drops do (Batch 20), Wanted-list finds first, and at most
:data:`MAX_DEAL_PUSHES_PER_DAY` a person a day: about 1,300 owned films can be upgraded, and
the rest wait on the Deals page. Both are in the ``deals`` category, sent at the end of the
pass rather than at the next morning's, and quiet hours still hold.

**A find is re-checked before it is pushed** (Batch X1, MK47-04's bound, #254): one item
call, and a listing that has ended or sold out is not pushed and leaves the Deals page. The
push names the listing's own title and condition, so a wrong product the matcher could not
tell apart (*Maggie* for *The 'Maggie'*) reads as what it is.

**An expired find loses the listing's title and image** (eBay API licence §8.1.2, §3.1(b)),
keeping its price, dates and film: :func:`clear_ended_finds`, every pass.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal

import structlog
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.ebay.client import DEFAULT_MAX_RETRIES, EbayError, EbayNotConfigured
from src.models.deal import Deal
from src.models.ebay_watch import EbayWatchRun
from src.models.movie import Movie
from src.models.notification import Notification, NotificationCategory
from src.models.profile import Profile
from src.services.ebay_watch.client import WatchClient
from src.services.ebay_watch.listings import item_state
from src.services.ebay_watch.scan import EBAY, FIRST_LOOK_BACK, Find, scan
from src.services.ebay_watch.targets import FORMAT_LABELS, Alert, check_targets, pounds, short
from src.services.notifications import deliver_pending, queue_notification
from src.services.push_transport import push_sender

logger = structlog.get_logger(__name__)

#: eBay calls a UTC day's passes may make between them: 10% of eBay's 5,000.
DAILY_SHARE = 500
RUN_STALE_AFTER = timedelta(minutes=30)
#: Too few calls to be worth starting on: one call and its retries.
MIN_RUN_BUDGET = DEFAULT_MAX_RETRIES + 1
#: Deal pushes a person gets in a UTC day, at most.
MAX_DEAL_PUSHES_PER_DAY = 5
DEAL_KEY_PREFIX = "ebay-deal:"

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


async def clear_ended_finds(db: AsyncSession, *, now: datetime) -> None:
    """An expired eBay find keeps its price, dates and film, and loses the listing's words.

    eBay's API licence lets an app keep a listing's content only while it is current
    (§8.1.2, §3.1(b)). The title becomes the film's, the image and condition go.
    """
    film_title = _film_title_or_default()
    await db.execute(
        update(Deal)
        .where(
            Deal.retailer_id.is_(None),
            Deal.retailer_name_snapshot == EBAY,
            Deal.expires_at_utc <= now,
            or_(
                Deal.image_url.is_not(None),
                Deal.listing_condition.is_not(None),
                Deal.title_snapshot != film_title,
            ),
        )
        .values(title_snapshot=film_title, image_url=None, listing_condition=None)
        .execution_options(synchronize_session=False)
    )
    await db.commit()


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


def deal_alert(find: Find, user_id: uuid.UUID) -> Alert:
    """The push: the listing's own title and condition first, then the film it was filed as.

    Since Batch X1 the title is the listing's, not the film's: of the 60 deal pushes before
    9 Oct, 14 were another product under a film's name, and three of those no title rule
    can tell apart. The usual price says what it is: asking prices, and how many.
    """
    label = FORMAT_LABELS.get(find.format_code, find.format_code)
    why = (
        "It's on the Wanted list."
        if find.wanted
        else "It would be an upgrade on the copy on the shelf."
    )
    year = f" ({find.film.year})" if find.film.year else ""
    return Alert(
        user_id=user_id,
        title=short(find.listing.listing.title, 80),
        body=(
            f"{find.condition}, {pounds(find.listing.total)} with postage on eBay: "
            f"{find.discount_percent}% under the usual {pounds(find.figure.amount)} "
            f"(asking prices, {find.usual.sample_size} listings). "
            f"Filed as {short(find.film.title)}{year} on {label}. {why}"
        ),
        url=find.listing.url,
        dedupe_key=f"{DEAL_KEY_PREFIX}{find.listing.legacy_id}:{user_id}",
    )


#: Answers whether a find can still be bought: ``True``, ``False`` when it has ended or sold
#: out, ``None`` when that could not be asked (no budget left, or eBay failed).
Recheck = Callable[[Find], Awaitable[bool | None]]


async def _already_told(db: AsyncSession, alert: Alert) -> bool:
    found = await db.scalar(
        select(Notification.id).where(Notification.dedupe_key == alert.dedupe_key).limit(1)
    )
    return found is not None


async def end_find(db: AsyncSession, find: Find, *, now: datetime) -> None:
    """Take a find that has ended or sold out off the Deals page now."""
    await db.execute(
        update(Deal)
        .where(
            Deal.retailer_id.is_(None),
            Deal.retailer_name_snapshot == EBAY,
            Deal.url == find.listing.url,
        )
        .values(expires_at_utc=now)
        .execution_options(synchronize_session=False)
    )


def item_rechecker(
    client: WatchClient, run: EbayWatchRun, *, clock: Callable[[], datetime]
) -> Recheck:
    """One item call per find, within the pass's budget."""

    async def still_for_sale(find: Find) -> bool | None:
        if client.search_calls + client.attempts_per_search > run.budget:
            return None
        try:
            payload = await client.get_item_by_legacy_id(find.listing.legacy_id)
        except EbayError as exc:
            logger.warning("ebay_deal_recheck_failed", item=find.listing.legacy_id, error=str(exc))
            return None
        state = item_state(payload) if payload is not None else None
        if state is None or not state.available:
            return False
        return state.ends_at is None or state.ends_at > clock()

    return still_for_sale


async def queue_deal_pushes(
    db: AsyncSession, finds: list[Find], *, now: datetime, recheck: Recheck
) -> int:
    """Tell both people about the best finds, within each one's daily limit.

    Each find is re-checked once, just before its first push: one that has ended or sold out
    is not pushed and leaves the Deals page; one that could not be checked is not pushed and
    stays there. Returns how many finds were pushed to anyone.
    """
    if not finds:
        return 0
    people = list(
        (
            await db.scalars(
                select(Profile.id).where(Profile.deleted_at.is_(None), Profile.is_active.is_(True))
            )
        ).all()
    )
    ordered = sorted(finds, key=lambda find: (not find.wanted, -find.discount_percent))
    pushed: set[str] = set()
    checked: dict[str, bool | None] = {}
    for person in people:
        room = MAX_DEAL_PUSHES_PER_DAY - await _deal_pushes_today(db, person, now=now)
        for find in ordered:
            if room <= 0:
                break
            alert = deal_alert(find, person)
            if await _already_told(db, alert):
                continue
            key = find.listing.legacy_id
            if key not in checked:
                checked[key] = await recheck(find)
                if checked[key] is False:
                    await end_find(db, find, now=now)
            if not checked[key]:
                continue
            if await _queue_alert(db, alert, now=now):
                room -= 1
                pushed.add(key)
    return len(pushed)


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
            run.deals_pushed = await queue_deal_pushes(
                db, ended.finds, now=clock(), recheck=item_rechecker(client, run, clock=clock)
            )
            await clear_ended_finds(db, now=clock())
            if run.deals_pushed:
                told |= set(
                    (
                        await db.scalars(
                            select(Profile.id).where(
                                Profile.deleted_at.is_(None), Profile.is_active.is_(True)
                            )
                        )
                    ).all()
                )
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
