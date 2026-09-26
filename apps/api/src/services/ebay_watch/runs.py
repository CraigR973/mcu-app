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
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.ebay.client import DEFAULT_MAX_RETRIES, EbayError, EbayNotConfigured
from src.models.ebay_watch import EbayWatchRun
from src.models.notification import Notification, NotificationCategory
from src.models.profile import Profile
from src.services.ebay_watch.client import WatchClient
from src.services.ebay_watch.scan import FIRST_LOOK_BACK, Find, scan
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


async def scanned_up_to(db: AsyncSession) -> datetime | None:
    """Where the last pass that read listings got to."""
    return await db.scalar(
        select(func.max(EbayWatchRun.newest_listing_utc)).where(
            EbayWatchRun.newest_listing_utc.is_not(None)
        )
    )


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
    label = FORMAT_LABELS.get(find.format_code, find.format_code)
    why = (
        "It's on the Wanted list."
        if find.wanted
        else "It would be an upgrade on the copy on the shelf."
    )
    return Alert(
        user_id=user_id,
        title=f"{short(find.film.title)} on {label}: {pounds(find.listing.total)}",
        body=(
            f"Listed on eBay just now at {pounds(find.listing.total)} with postage, "
            f"{find.discount_percent}% under its usual {pounds(find.usual.median)}. {why}"
        ),
        url=find.listing.url,
        dedupe_key=f"{DEAL_KEY_PREFIX}{find.listing.legacy_id}:{user_id}",
    )


async def queue_deal_pushes(db: AsyncSession, finds: list[Find], *, now: datetime) -> int:
    """Tell both people about the best finds, within each one's daily limit.

    Returns how many finds were pushed to anyone.
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
    for person in people:
        room = MAX_DEAL_PUSHES_PER_DAY - await _deal_pushes_today(db, person, now=now)
        for find in ordered:
            if room <= 0:
                break
            if await _queue_alert(db, deal_alert(find, person), now=now):
                room -= 1
                pushed.add(find.listing.legacy_id)
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
            since = await scanned_up_to(db) or (run.started_utc - FIRST_LOOK_BACK)
            ended = await scan(db, client, run, since=since, clock=clock)
            run.deals_pushed = await queue_deal_pushes(db, ended.finds, now=clock())
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
