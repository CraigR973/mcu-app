"""When a notification is delivered, to whom, and whether at all — §6.1's behaviour.

:mod:`src.services.webpush` knows how to put bytes on the wire. This module decides
whether those bytes should exist: it reads the person's preferences, writes the outbox row
and later delivers it.

**Everything goes through the outbox, including a test push.** That is what makes §6.1's
two acceptance clauses observable rather than asserted — "disabling deals stops deal
pushes" leaves a ``suppressed`` row naming the category, and "quiet hours suppress evening
alerts" leaves a ``queued`` row whose ``deliver_after_utc`` is the following morning. Both
are readable in the app and in a test without a push service in the loop.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.config import settings
from src.models.notification import (
    DEFERRED_DIGEST,
    DEFERRED_QUIET_HOURS,
    SUPPRESSED_CATEGORY_DISABLED,
    SUPPRESSED_NO_SUBSCRIPTIONS,
    Notification,
    NotificationCategory,
    NotificationPreference,
    NotificationStatus,
    PushSubscription,
)
from src.services import webpush

logger = structlog.get_logger(__name__)

#: Why a device was revoked (Batch X3): the person removed it, or the push service refused it.
REVOKED_REMOVED = "removed"
REVOKED_REFUSED = "refused"

#: Which preference column gates which category. A mapping rather than
#: ``getattr(prefs, f"{category}_enabled")`` so a renamed column fails the typechecker
#: instead of quietly returning ``True`` for a category nobody can switch off any more.
#: ``attention`` (Batch X2) is absent on purpose: it has no toggle.
_CATEGORY_COLUMNS: dict[NotificationCategory, str] = {
    NotificationCategory.deals: "deals_enabled",
    NotificationCategory.sale_events: "sale_events_enabled",
    NotificationCategory.releases: "releases_enabled",
    NotificationCategory.loans: "loans_enabled",
    NotificationCategory.movie_night: "movie_night_enabled",
    NotificationCategory.collection_additions: "collection_additions_enabled",
}

#: How long a push service should hold an undelivered message. Four hours: long enough for
#: a phone that is off overnight to still get a morning digest, short enough that a
#: "prices dropped" note does not arrive two days stale.
PUSH_TTL_SECONDS = 4 * 60 * 60

#: Consecutive transient failures before a subscription stops being tried. Not a delete —
#: only a ``404``/``410`` proves a subscription is dead (`DECISIONS.md` #43's reasoning
#: about a 5xx being the *unknown* case, and gotcha 23).
MAX_SUBSCRIPTION_FAILURES = 10


class DeliveryOutcome(StrEnum):
    """What a push service said about one message to one subscription."""

    delivered = "delivered"
    #: ``404``/``410`` — the subscription is gone for good and the row goes with it.
    gone = "gone"
    #: Anything else. The subscription might be fine; see gotcha 23.
    failed = "failed"


@dataclass(frozen=True)
class DeliveryResult:
    outcome: DeliveryOutcome
    status_code: int | None = None
    detail: str | None = None


class PushSender(Protocol):
    """The one thing this module needs from the outside world.

    A protocol so tests substitute a recorder and CI never reaches a push service. The
    stub is not a shortcut: `DECISIONS.md` #111's scraper run is the standing reminder
    that a *live* run proves something a stub cannot, which is why §6.2's acceptance is
    deferred to the owner rather than claimed here.
    """

    async def send(self, subscription: PushSubscription, payload: bytes) -> DeliveryResult: ...


class HttpPushSender:
    """Sends over HTTPS to whichever push service minted the endpoint."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def send(self, subscription: PushSubscription, payload: bytes) -> DeliveryResult:
        if not settings.vapid_private_key or not settings.vapid_subject:
            return DeliveryResult(DeliveryOutcome.failed, detail="VAPID is not configured")

        try:
            private_key = webpush.load_vapid_private_key(settings.vapid_private_key)
            body = webpush.encrypt(
                payload,
                ua_public=webpush.b64url_decode(subscription.p256dh),
                auth_secret=webpush.b64url_decode(subscription.auth),
            )
            authorization = webpush.vapid_authorization(
                endpoint=subscription.endpoint,
                private_key=private_key,
                subject=settings.vapid_subject,
                issued_at=int(utcnow().timestamp()),
            )
        except (ValueError, TypeError) as exc:
            # A malformed subscription or key never becomes deliverable by retrying.
            return DeliveryResult(DeliveryOutcome.failed, detail=str(exc))

        try:
            response = await self._client.post(
                subscription.endpoint,
                content=body,
                headers={
                    "Authorization": authorization,
                    "Content-Encoding": "aes128gcm",
                    "Content-Type": "application/octet-stream",
                    "TTL": str(PUSH_TTL_SECONDS),
                    "Urgency": "normal",
                },
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            return DeliveryResult(DeliveryOutcome.failed, detail=str(exc))

        if response.status_code in (404, 410):
            return DeliveryResult(DeliveryOutcome.gone, response.status_code)
        if 200 <= response.status_code < 300:
            return DeliveryResult(DeliveryOutcome.delivered, response.status_code)
        return DeliveryResult(
            DeliveryOutcome.failed, response.status_code, response.text[:200] or None
        )


async def get_or_create_preferences(db: AsyncSession, user_id: object) -> NotificationPreference:
    """This person's preferences, defaulting every category on.

    Created on first read rather than seeded by migration, because a row per profile
    seeded now would go missing for any profile added later — and there is no code path
    that adds one, so the bug would surface as "Mark's toggles do nothing".
    """
    existing = (
        await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    # Two different senders may initialise the same recipient concurrently.
    await db.execute(
        pg_insert(NotificationPreference)
        .values(id=uuid.uuid4(), user_id=user_id)
        .on_conflict_do_nothing(index_elements=[NotificationPreference.user_id])
    )
    return (
        await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
    ).scalar_one()


def _zone(preference: NotificationPreference) -> ZoneInfo:
    """The person's timezone, falling back rather than failing a delivery pass.

    An unknown IANA name should not be able to stop every notification in the app. It is
    reachable only by writing the column by hand — the API validates on the way in.
    """
    try:
        return ZoneInfo(preference.quiet_hours_timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        # `TypeError` is the unflushed-row case: a `default=` is applied when the INSERT
        # is built, so a constructed row still reads `None` here. Falling back rather
        # than raising means one unreadable value cannot stop a whole delivery pass.
        logger.warning("unknown_quiet_hours_timezone", timezone=preference.quiet_hours_timezone)
        return ZoneInfo("Europe/London")


def _to_local(instant_utc: datetime, zone: ZoneInfo) -> datetime:
    """A naive-UTC column value as an aware local time."""
    return instant_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone)


def _to_naive_utc(local: datetime) -> datetime:
    """An aware local time back into the naive UTC every column here holds."""
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _local_at(day: date, at: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, at, tzinfo=zone)


def quiet_hours_cover(preference: NotificationPreference, instant_utc: datetime) -> bool:
    """Is ``instant_utc`` inside this person's quiet hours?

    Handles the window that wraps midnight, which is the only kind anybody sets: 22:00 to
    07:00 is two intervals in a day and one interval in a night.
    """
    start, end = preference.quiet_hours_start, preference.quiet_hours_end
    if start is None or end is None or start == end:
        return False
    local = _to_local(instant_utc, _zone(preference)).time()
    if start < end:
        return start <= local < end
    return local >= start or local < end


def _quiet_hours_end_after(preference: NotificationPreference, instant_utc: datetime) -> datetime:
    """The next moment quiet hours are over — where a held notification goes."""
    zone = _zone(preference)
    local = _to_local(instant_utc, zone)
    end = preference.quiet_hours_end
    assert end is not None  # guarded by quiet_hours_cover, and by the migration's CHECK
    candidate = _local_at(local.date(), end, zone)
    if candidate <= local:
        candidate = _local_at(local.date() + timedelta(days=1), end, zone)
    return _to_naive_utc(candidate)


def _next_digest_after(preference: NotificationPreference, instant_utc: datetime) -> datetime:
    """The next local digest hour strictly after ``instant_utc``."""
    zone = _zone(preference)
    local = _to_local(instant_utc, zone)
    at = time(hour=preference.digest_hour_local)
    candidate = _local_at(local.date(), at, zone)
    if candidate <= local:
        candidate = _local_at(local.date() + timedelta(days=1), at, zone)
    return _to_naive_utc(candidate)


def scheduled_delivery(
    preference: NotificationPreference, now_utc: datetime
) -> tuple[datetime | None, str | None]:
    """When a notification raised at ``now_utc`` should actually go out.

    ``(None, None)`` means immediately. The two rules compose in this order — digest first,
    then quiet hours — because a digest hour that happens to sit inside quiet hours must
    still wait for the quiet hours to end, not the other way round.
    """
    target = now_utc
    reason: str | None = None

    if preference.digest_mode:
        target = _next_digest_after(preference, now_utc)
        reason = DEFERRED_DIGEST

    if quiet_hours_cover(preference, target):
        target = _quiet_hours_end_after(preference, target)
        reason = DEFERRED_QUIET_HOURS

    if target <= now_utc:
        return None, None
    return target, reason


async def queue_notification(
    db: AsyncSession,
    *,
    user_id: object,
    category: NotificationCategory,
    title: str,
    body: str,
    url: str | None = None,
    dedupe_key: str | None = None,
    now: datetime | None = None,
) -> Notification | None:
    """Write one notification to the outbox, applying §6.1's preferences.

    Returns ``None`` only when ``dedupe_key`` names a notification that already exists —
    a suppressed one is still a row, and still returned, because "why did I not get that"
    deserves an answer.
    """
    now = now or utcnow()
    preference = await get_or_create_preferences(db, user_id)

    notification = Notification(
        # **Assigned here, not left to the column default.** A `default=` is applied when
        # the ORM builds the INSERT, so a constructed-but-unflushed row still reads `None`
        # — and the deduplicated path below inserts these values by hand, which would put
        # a NULL in the primary key. The same trap as the preference defaults above.
        id=uuid.uuid4(),
        user_id=user_id,
        category=category.value,
        title=title,
        body=body,
        url=url,
        dedupe_key=dedupe_key,
        created_at_utc=now,
    )

    column = _CATEGORY_COLUMNS.get(category)
    if column is not None and not getattr(preference, column):
        notification.status = NotificationStatus.suppressed.value
        notification.suppressed_reason = SUPPRESSED_CATEGORY_DISABLED
    else:
        notification.status = NotificationStatus.queued.value
        deliver_after, reason = scheduled_delivery(preference, now)
        notification.deliver_after_utc = deliver_after
        notification.deferred_reason = reason

    if dedupe_key is not None:
        # ON CONFLICT DO NOTHING rather than a read-then-write: two reminder passes racing
        # would both see no row and both insert. The partial unique index is the arbiter.
        result = await db.execute(
            pg_insert(Notification)
            .values(
                id=notification.id,
                user_id=notification.user_id,
                category=notification.category,
                status=notification.status,
                title=notification.title,
                body=notification.body,
                url=notification.url,
                dedupe_key=notification.dedupe_key,
                deliver_after_utc=notification.deliver_after_utc,
                deferred_reason=notification.deferred_reason,
                suppressed_reason=notification.suppressed_reason,
                created_at_utc=notification.created_at_utc,
            )
            .on_conflict_do_nothing(
                index_elements=[Notification.dedupe_key],
                # **The predicate is required, not decorative.** `ix_notifications_dedupe_key`
                # is a *partial* unique index, and Postgres will not infer a partial index as
                # the ON CONFLICT arbiter unless the predicate is repeated here — it fails with
                # "no unique or exclusion constraint matching the ON CONFLICT specification"
                # instead. The index is partial so that several notifications without a dedupe
                # key (a test push) can coexist.
                index_where=Notification.dedupe_key.is_not(None),
            )
            .returning(Notification.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        return (
            await db.execute(select(Notification).where(Notification.id == notification.id))
        ).scalar_one()

    db.add(notification)
    await db.flush()
    return notification


def notification_payload(notifications: list[Notification]) -> bytes:
    """The JSON the service worker reads out of the encrypted push.

    One notification renders as itself; several render as §6.1's digest — one push saying
    how many, with the individual titles in the body. Delivering a digest as N pushes
    would defeat the entire point of the setting.
    """
    if len(notifications) == 1:
        one = notifications[0]
        return json.dumps(
            {
                "title": one.title,
                "body": one.body,
                "url": one.url,
                "category": one.category,
                "tag": str(one.id),
            }
        ).encode("utf-8")

    lines = [f"• {item.title}" for item in notifications[:5]]
    if len(notifications) > 5:
        lines.append(f"…and {len(notifications) - 5} more")
    return json.dumps(
        {
            "title": f"{len(notifications)} updates from your collection",
            "body": "\n".join(lines),
            "url": "/notifications",
            "category": "digest",
            "tag": "mcu-digest",
        }
    ).encode("utf-8")


async def active_subscriptions(db: AsyncSession, user_id: object) -> list[PushSubscription]:
    """This person's live devices, newest first."""
    return list(
        (
            await db.execute(
                select(PushSubscription)
                .where(
                    PushSubscription.user_id == user_id,
                    PushSubscription.revoked_at_utc.is_(None),
                    PushSubscription.failure_count < MAX_SUBSCRIPTION_FAILURES,
                )
                .order_by(PushSubscription.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@dataclass
class DeliverySummary:
    """What one delivery pass did. Read back by the admin endpoint and by the tests."""

    considered: int = 0
    sent: int = 0
    suppressed: int = 0
    failed: int = 0
    pushes_delivered: int = 0
    subscriptions_removed: int = 0


@dataclass
class FanOutResult:
    """One payload's fate across one person's devices."""

    delivered: int = 0
    #: Subscriptions the push service reported gone. Revoked as refused (Batch X3), and
    #: dropped from any further sends in this pass.
    removed: list[PushSubscription] = field(default_factory=list)


async def deliver_to_subscriptions(
    db: AsyncSession,
    *,
    subscriptions: list[PushSubscription],
    payload: bytes,
    sender: PushSender,
    now: datetime,
) -> FanOutResult:
    """Push ``payload`` to every one of ``subscriptions``.

    **A dead subscription is revoked as refused, a failing one is only counted.** Since
    Batch X3 a 404 or 410 keeps the row (`revoked_at_utc`, ``revoked_reason="refused"``), so
    Settings can say when the phone stopped and the app can register it again; before X3
    the row was deleted with an info log, and two phones went silent with nobody told.
    §6.2's "removing one doesn't silence the other" depends on this loop treating each
    device independently — one endpoint answering ``410`` must not stop the other from
    being tried, which is why the result of each send is handled inside the loop rather
    than aborting it.
    """
    result = FanOutResult()
    for subscription in subscriptions:
        outcome = await sender.send(subscription, payload)
        if outcome.outcome is DeliveryOutcome.delivered:
            result.delivered += 1
            subscription.failure_count = 0
            subscription.last_used_at_utc = now
        elif outcome.outcome is DeliveryOutcome.gone:
            subscription.revoked_at_utc = now
            subscription.revoked_reason = REVOKED_REFUSED
            result.removed.append(subscription)
            logger.warning("push_subscription_refused", status_code=outcome.status_code)
        else:
            subscription.failure_count += 1
            logger.warning(
                "push_delivery_failed",
                status_code=outcome.status_code,
                detail=outcome.detail,
                failure_count=subscription.failure_count,
            )
    return result


async def deliver_pending(
    db: AsyncSession,
    *,
    sender: PushSender,
    now: datetime | None = None,
    user_id: object | None = None,
) -> DeliverySummary:
    """Send every queued notification that is due, grouped per person.

    Grouping is what makes digest mode one push rather than several, and it is done here
    rather than at queue time so that a person switching the setting off does not strand
    already-queued rows in a digest that will never be assembled.
    """
    now = now or utcnow()
    summary = DeliverySummary()

    query = select(Notification).where(
        Notification.status == NotificationStatus.queued.value,
        (Notification.deliver_after_utc.is_(None)) | (Notification.deliver_after_utc <= now),
    )
    if user_id is not None:
        query = query.where(Notification.user_id == user_id)

    due = list(
        (
            await db.execute(
                query.order_by(Notification.created_at_utc.asc()).with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    summary.considered = len(due)
    if not due:
        return summary

    by_user: dict[object, list[Notification]] = {}
    for notification in due:
        by_user.setdefault(notification.user_id, []).append(notification)

    for owner_id, items in by_user.items():
        subscriptions = await active_subscriptions(db, owner_id)
        if not subscriptions:
            for notification in items:
                notification.status = NotificationStatus.suppressed.value
                notification.suppressed_reason = SUPPRESSED_NO_SUBSCRIPTIONS
                summary.suppressed += 1
            continue

        preference = await get_or_create_preferences(db, owner_id)
        groups = [items] if preference.digest_mode else [[item] for item in items]

        for group in groups:
            if not subscriptions:
                # Every device went `410` earlier in this same pass. "Nobody to tell" is a
                # different fact from "the send failed", and reads very differently later.
                for notification in group:
                    notification.status = NotificationStatus.suppressed.value
                    notification.suppressed_reason = SUPPRESSED_NO_SUBSCRIPTIONS
                    summary.suppressed += 1
                continue

            fan_out = await deliver_to_subscriptions(
                db,
                subscriptions=subscriptions,
                payload=notification_payload(group),
                sender=sender,
                now=now,
            )
            # Drop the gone ones before the next group, so a deleted row is never handed
            # to the sender a second time in the same pass.
            if fan_out.removed:
                removed_ids = {subscription.id for subscription in fan_out.removed}
                subscriptions = [
                    subscription
                    for subscription in subscriptions
                    if subscription.id not in removed_ids
                ]
                summary.subscriptions_removed += len(fan_out.removed)
            delivered = fan_out.delivered
            summary.pushes_delivered += delivered

            for notification in group:
                if delivered:
                    notification.status = NotificationStatus.sent.value
                    notification.sent_at_utc = now
                    notification.delivered_count = delivered
                    summary.sent += 1
                else:
                    notification.status = NotificationStatus.failed.value
                    summary.failed += 1

    await db.flush()
    return summary
