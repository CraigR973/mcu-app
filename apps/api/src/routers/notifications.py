"""Notification preferences, devices and the outbox — Batch 11, §6.1 and §6.2.

Everything here is caller-scoped. A device belongs to the person who registered it and a
notification to the person it is about, so there is no admin view of somebody else's
devices — with two profiles, one of them the owner's, that would be a surveillance feature
rather than an administrative one. The two admin-only routes are the *jobs*: seeding sale
seasons and running the reminder pass, both of which act on the whole app.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, cast
from urllib.parse import urlsplit

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.auth import AdminUser, CurrentUser
from src.clock import utc_today, utcnow
from src.config import settings
from src.models.notification import (
    Notification,
    NotificationCategory,
    NotificationStatus,
    PushSubscription,
)
from src.routers.movies import Database
from src.schemas.notifications import (
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
    NotificationResponse,
    NotificationStatusName,
    PushDeviceStatusRequest,
    PushDeviceStatusResponse,
    PushSubscriptionCreateRequest,
    PushSubscriptionListResponse,
    PushSubscriptionResponse,
    ReminderRunResponse,
    TestNotificationResponse,
    VapidKeyResponse,
)
from src.services import webpush
from src.services.notifications import (
    REVOKED_REFUSED,
    REVOKED_REMOVED,
    active_subscriptions,
    deliver_pending,
    deliver_to_subscriptions,
    get_or_create_preferences,
    notification_payload,
)
from src.services.push_transport import push_sender as push_sender
from src.services.push_transport import set_push_sender as set_push_sender
from src.services.reminders import run_reminders
from src.services.sale_seasons import seed_year

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["notifications"])


def _push_service(endpoint: str) -> str:
    """Which push service minted this endpoint — "fcm.googleapis.com" and so on.

    Shown instead of the endpoint itself, which is a bearer capability.
    """
    return urlsplit(endpoint).netloc or "unknown"


def _subscription_response(subscription: PushSubscription) -> PushSubscriptionResponse:
    return PushSubscriptionResponse(
        id=subscription.id,
        deviceLabel=subscription.device_label,
        # Enough to tell two rows apart, far too little to push with.
        endpointPreview=f"…{subscription.endpoint[-12:]}",
        pushService=_push_service(subscription.endpoint),
        userAgent=subscription.user_agent,
        createdAt=subscription.created_at,
        lastUsedAt=subscription.last_used_at_utc,
        failureCount=subscription.failure_count,
    )


def _status_name(value: str) -> NotificationStatusName:
    """Narrow the ``status`` column to the wire literal.

    The column is a plain ``String`` with a CHECK behind it, so the database guarantees
    the set of values and the typechecker cannot see that. Narrowing here — once, with a
    real failure if the two ever diverge — beats an ``ignore`` at each call site, which
    gotcha 21 would turn into a red gate the moment CI's mypy disagrees with this one.
    """
    if value not in ("queued", "sent", "suppressed", "failed"):  # pragma: no cover - CHECK
        raise ValueError(f"unknown notification status: {value!r}")
    return cast(NotificationStatusName, value)


def _notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        category=notification.category,
        status=_status_name(notification.status),
        title=notification.title,
        body=notification.body,
        url=notification.url,
        createdAt=notification.created_at_utc,
        deliverAfter=notification.deliver_after_utc,
        deferredReason=notification.deferred_reason,
        suppressedReason=notification.suppressed_reason,
        sentAt=notification.sent_at_utc,
        deliveredCount=notification.delivered_count,
    )


@router.get("/notifications/vapid-key", response_model=VapidKeyResponse)
async def vapid_key(_user: CurrentUser) -> VapidKeyResponse:
    """The public key a browser needs to subscribe.

    **Derived from the private key rather than read from its own variable.** Two variables
    can disagree; a derived one cannot. If Railway holds only the private half, this still
    answers correctly — and if it holds neither, ``configured: false`` lets the UI say
    "push is not set up on the server" instead of failing at ``subscribe()`` with a
    ``DOMException`` nobody can act on.
    """
    if settings.vapid_private_key:
        try:
            private_key = webpush.load_vapid_private_key(settings.vapid_private_key)
        except ValueError:
            logger.error("vapid_private_key_unreadable")
            return VapidKeyResponse(configured=False)
        derived = webpush.b64url_encode(webpush.vapid_public_key_bytes(private_key))
        if settings.vapid_public_key and settings.vapid_public_key.strip() != derived:
            # Worth shouting about: the pair does not match, so every subscription taken
            # with the configured public key would encrypt to a key we cannot sign for.
            logger.error("vapid_key_pair_mismatch")
        return VapidKeyResponse(publicKey=derived, configured=True)

    if settings.vapid_public_key:
        # A public key with no private half can mint subscriptions that can never be
        # pushed to. Refuse rather than collect them.
        logger.error("vapid_public_key_without_private_key")
    return VapidKeyResponse(configured=False)


@router.get("/notifications/subscriptions", response_model=PushSubscriptionListResponse)
async def list_subscriptions(user: CurrentUser, db: Database) -> PushSubscriptionListResponse:
    """This person's registered devices — §6.2's per-device records."""
    subscriptions = await active_subscriptions(db, user.id)
    stopped = None
    if not subscriptions:
        # Batch X3: their last device went because the push service refused it.
        stopped = await db.scalar(
            select(func.max(PushSubscription.revoked_at_utc)).where(
                PushSubscription.user_id == user.id,
                PushSubscription.revoked_reason == REVOKED_REFUSED,
            )
        )
    return PushSubscriptionListResponse(
        items=[_subscription_response(subscription) for subscription in subscriptions],
        total=len(subscriptions),
        stoppedAt=stopped,
    )


@router.post("/notifications/subscriptions/status", response_model=PushDeviceStatusResponse)
async def device_status(
    payload: PushDeviceStatusRequest, user: CurrentUser, db: Database
) -> PushDeviceStatusResponse:
    """Batch X3 (DS44-02): what the server holds for this browser's subscription.

    The page asks on every open and when the worker reports a subscription change, and
    registers the phone again when the answer is ``unknown`` or ``refused``. Before X3 the
    page read only the browser's own subscription, so Settings said "Notifications are on
    for this device" above "No devices are registered yet", and nothing ever re-registered.
    A device of another person's reads ``unknown``: registering reassigns it, as it always has.
    """
    device = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint, PushSubscription.user_id == user.id
        )
    )
    if device is None:
        return PushDeviceStatusResponse(state="unknown")
    if device.revoked_at_utc is None:
        return PushDeviceStatusResponse(state="live")
    state: Literal["refused", "removed"] = (
        "refused" if device.revoked_reason == REVOKED_REFUSED else "removed"
    )
    return PushDeviceStatusResponse(state=state, revokedAt=device.revoked_at_utc)


@router.post(
    "/notifications/subscriptions",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_subscription(
    payload: PushSubscriptionCreateRequest,
    user: CurrentUser,
    db: Database,
    user_agent: Annotated[str | None, Query(alias="userAgent")] = None,
) -> PushSubscriptionResponse:
    """Register this browser, or refresh the registration it already has.

    **Upsert on the endpoint, not insert.** A push service hands back the same endpoint
    when a browser re-subscribes, so a plain insert would give one device two rows and
    every future push two copies. The conflict target is the unique index migration 020
    creates for exactly this.

    An endpoint that moves between people — the same browser, a different login — is
    reassigned rather than refused: the device is whoever is signed into it now.
    """
    now = utcnow()
    result = await db.execute(
        pg_insert(PushSubscription)
        .values(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            device_label=payload.deviceLabel,
            user_agent=user_agent,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[PushSubscription.endpoint],
            set_={
                "user_id": user.id,
                "p256dh": payload.keys.p256dh,
                "auth": payload.keys.auth,
                "device_label": payload.deviceLabel,
                "user_agent": user_agent,
                # A device coming back is a working device, whatever it did before: a
                # refused one revives here (Batch X3), as a removed one always did.
                "failure_count": 0,
                "revoked_at_utc": None,
                "revoked_reason": None,
            },
        )
        .returning(PushSubscription)
    )
    subscription = result.scalar_one()
    await db.commit()
    await db.refresh(subscription)
    return _subscription_response(subscription)


@router.delete(
    "/notifications/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_subscription(subscription_id: str, user: CurrentUser, db: Database) -> None:
    """Unregister one device — §6.2's "removing one doesn't silence the other".

    Scoped to the caller, so one person cannot unsubscribe the other's phone. Revoked
    rather than deleted, so the row can still explain a push that stopped arriving.
    """
    subscription = (
        await db.execute(
            select(PushSubscription).where(
                PushSubscription.id == subscription_id,
                PushSubscription.user_id == user.id,
                PushSubscription.revoked_at_utc.is_(None),
            )
        )
    ).scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    subscription.revoked_at_utc = utcnow()
    subscription.revoked_reason = REVOKED_REMOVED
    await db.commit()


@router.post(
    "/notifications/subscriptions/{subscription_id}/test",
    response_model=TestNotificationResponse,
)
async def send_test_notification(
    subscription_id: str, user: CurrentUser, db: Database
) -> TestNotificationResponse:
    """§6.2's test-notification button, aimed at **one** device.

    Aiming it at one device rather than all of them is what makes the criterion testable:
    "both receive pushes" and "removing one doesn't silence the other" are questions about
    individual devices, and a button that sprays every device cannot answer either.

    The test bypasses quiet hours and digest mode deliberately — pressing a button and
    being told the push will arrive at nine tomorrow is not a test of anything — but it
    does **not** bypass the category toggles, because there is no category to switch off.
    """
    subscription = (
        await db.execute(
            select(PushSubscription).where(
                PushSubscription.id == subscription_id,
                PushSubscription.user_id == user.id,
                PushSubscription.revoked_at_utc.is_(None),
            )
        )
    ).scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    now = utcnow()
    notification = Notification(
        user_id=user.id,
        category=NotificationCategory.movie_night.value,
        status=NotificationStatus.queued.value,
        title="Test notification",
        body=(
            f"Push is working on {subscription.device_label or 'this device'}. "
            "Sent from your notification settings."
        ),
        url="/settings/notifications",
        created_at_utc=now,
    )
    db.add(notification)
    await db.flush()

    async with push_sender() as sender:
        fan_out = await deliver_to_subscriptions(
            db,
            subscriptions=[subscription],
            payload=notification_payload([notification]),
            sender=sender,
            now=now,
        )

    if fan_out.delivered:
        notification.status = NotificationStatus.sent.value
        notification.sent_at_utc = now
        notification.delivered_count = fan_out.delivered
    else:
        notification.status = NotificationStatus.failed.value

    await db.commit()
    return TestNotificationResponse(
        notificationId=notification.id,
        delivered=fan_out.delivered,
        devicesTried=1,
        subscriptionsRemoved=len(fan_out.removed),
        status=_status_name(notification.status),
        suppressedReason=notification.suppressed_reason,
    )


@router.get("/notifications/preferences", response_model=NotificationPreferenceResponse)
async def read_preferences(user: CurrentUser, db: Database) -> NotificationPreferenceResponse:
    """§6.1's toggles, created with everything on if this is the first read."""
    preference = await get_or_create_preferences(db, user.id)
    await db.commit()
    return NotificationPreferenceResponse(
        dealsEnabled=preference.deals_enabled,
        saleEventsEnabled=preference.sale_events_enabled,
        releasesEnabled=preference.releases_enabled,
        loansEnabled=preference.loans_enabled,
        movieNightEnabled=preference.movie_night_enabled,
        digestMode=preference.digest_mode,
        digestHourLocal=preference.digest_hour_local,
        quietHoursStart=preference.quiet_hours_start,
        quietHoursEnd=preference.quiet_hours_end,
        quietHoursTimezone=preference.quiet_hours_timezone,
    )


@router.put("/notifications/preferences", response_model=NotificationPreferenceResponse)
async def update_preferences(
    payload: NotificationPreferenceUpdateRequest, user: CurrentUser, db: Database
) -> NotificationPreferenceResponse:
    """Change some of §6.1's toggles. Absent fields are left alone."""
    preference = await get_or_create_preferences(db, user.id)

    for field_name, column in (
        ("dealsEnabled", "deals_enabled"),
        ("saleEventsEnabled", "sale_events_enabled"),
        ("releasesEnabled", "releases_enabled"),
        ("loansEnabled", "loans_enabled"),
        ("movieNightEnabled", "movie_night_enabled"),
        ("digestMode", "digest_mode"),
        ("digestHourLocal", "digest_hour_local"),
        ("quietHoursTimezone", "quiet_hours_timezone"),
    ):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(preference, column, value)

    if payload.clearQuietHours:
        preference.quiet_hours_start = None
        preference.quiet_hours_end = None
    elif payload.quietHoursStart is not None and payload.quietHoursEnd is not None:
        preference.quiet_hours_start = payload.quietHoursStart
        preference.quiet_hours_end = payload.quietHoursEnd

    await db.commit()
    await db.refresh(preference)
    return NotificationPreferenceResponse(
        dealsEnabled=preference.deals_enabled,
        saleEventsEnabled=preference.sale_events_enabled,
        releasesEnabled=preference.releases_enabled,
        loansEnabled=preference.loans_enabled,
        movieNightEnabled=preference.movie_night_enabled,
        digestMode=preference.digest_mode,
        digestHourLocal=preference.digest_hour_local,
        quietHoursStart=preference.quiet_hours_start,
        quietHoursEnd=preference.quiet_hours_end,
        quietHoursTimezone=preference.quiet_hours_timezone,
    )


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    user: CurrentUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> NotificationListResponse:
    """The caller's outbox, newest first.

    This is the page that answers "why did I not get that": a suppressed row names the
    category that was off, and a queued one shows the morning it is waiting for.
    """
    rows = list(
        (
            await db.execute(
                select(Notification)
                .where(Notification.user_id == user.id)
                .order_by(Notification.created_at_utc.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    total = (
        await db.execute(
            select(func.count()).select_from(Notification).where(Notification.user_id == user.id)
        )
    ).scalar_one()
    queued = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.status == NotificationStatus.queued.value,
            )
        )
    ).scalar_one()
    return NotificationListResponse(
        items=[_notification_response(row) for row in rows],
        total=total,
        queuedCount=queued,
    )


@router.post("/notifications/run-reminders", response_model=ReminderRunResponse)
async def run_reminder_pass(
    _user: AdminUser,
    db: Database,
    as_of: Annotated[date | None, Query(alias="asOf")] = None,
    deliver: Annotated[bool, Query()] = True,
) -> ReminderRunResponse:
    """Run every reminder sender, then deliver whatever is due.

    ``asOf`` is what makes §5.11's acceptance testable — *"test date set 2 weeks before a
    seeded event triggers a reminder"* — and it is also how a missed day is caught up.
    It cannot be pushed into the future beyond today, because reminding somebody about a
    sale that has not been announced is not a feature.

    **This endpoint is the whole scheduler.** There is no in-process timer: `DECISIONS.md`
    #60 already settled that an in-process scheduler is worse than nothing here, because
    a second container silently doubles every reminder. A Railway cron calling this is the
    hosting step Batch 20 stops for.
    """
    today = utc_today()
    if as_of is not None and as_of > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="asOf cannot be in the future",
        )

    summary = await run_reminders(db, as_of=as_of)
    delivered = 0
    if deliver:
        async with push_sender() as sender:
            delivery = await deliver_pending(db, sender=sender)
            delivered = delivery.sent
    await db.commit()

    return ReminderRunResponse(
        asOf=summary.as_of,
        seasonsSeeded=summary.seasons_seeded,
        saleEvents=summary.sale_events,
        releases=summary.releases,
        overdueLoans=summary.overdue_loans,
        queued=summary.queued,
        delivered=delivered,
    )


@router.post("/notifications/seed-sale-seasons", response_model=ReminderRunResponse)
async def seed_sale_seasons(
    _user: AdminUser,
    db: Database,
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
) -> ReminderRunResponse:
    """§5.11's seeded data, for one year. Idempotent — re-running adds nothing."""
    target = year or utc_today().year
    created = await seed_year(db, target)
    await db.commit()
    return ReminderRunResponse(
        asOf=date(target, 1, 1),
        seasonsSeeded=len(created),
        saleEvents=0,
        releases=0,
        overdueLoans=0,
        queued=0,
        delivered=0,
    )


@router.post("/notifications/deliver", response_model=ReminderRunResponse)
async def deliver_now(_user: AdminUser, db: Database) -> ReminderRunResponse:
    """Push everything queued and due, without running the reminder senders."""
    async with push_sender() as sender:
        summary = await deliver_pending(db, sender=sender)
    await db.commit()
    return ReminderRunResponse(
        asOf=utc_today(),
        seasonsSeeded=0,
        saleEvents=0,
        releases=0,
        overdueLoans=0,
        queued=summary.considered,
        delivered=summary.sent,
    )
