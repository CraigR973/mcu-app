"""Claim durably before transport: an uncertain cinema send is never replayed (#348)."""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from src.clock import utcnow
from src.models.cinema import CinemaFilm, CinemaScreening
from src.models.cinema_digest import (
    CinemaDigestAppearance,
    CinemaDigestDay,
    CinemaDigestDelivery,
    CinemaDigestFilm,
)
from src.models.notification import DEFERRED_QUIET_HOURS, Notification
from src.models.profile import Profile
from src.services.cinema_digest.evaluate import london_day, tmdb_id, words
from src.services.notifications import (
    DeliverySummary,
    PushSender,
    _quiet_hours_end_after,
    active_subscriptions,
    deliver_to_subscriptions,
    get_or_create_preferences,
    quiet_hours_cover,
)

log = structlog.get_logger(__name__)


def payload(items: list[CinemaDigestAppearance], older: bool, tag: str) -> dict[str, Any]:
    title, body = words(items, older, bounded=True)
    result = {
        "title": title,
        "body": body,
        "url": "/movie-night/cinema?view=new-this-week" + ("&run=olderFilm" if older else ""),
        "category": "cinemas",
        "tag": tag,
    }
    # Keep run labels and a valid UTF-8/JSON payload even for long multibyte titles.
    shown = min(3, len(items))
    while len(json.dumps(result, ensure_ascii=False).encode()) > 3000 and shown > 1:
        shown -= 1
        _, lines = words(items[:shown], older, bounded=True)
        result["body"] = lines + f"\nAnd {len(items) - shown} more. Open New this week."
    return result


async def _claim(
    engine: AsyncEngine, user_id: uuid.UUID, now: datetime
) -> CinemaDigestDelivery | None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db, db.begin():
        person = await db.scalar(
            select(Profile)
            .where(Profile.id == user_id, Profile.is_active.is_(True))
            .with_for_update()
        )
        if person is None:
            return None
        history = list(
            (
                await db.scalars(
                    select(CinemaDigestDelivery).where(CinemaDigestDelivery.user_id == user_id)
                )
            ).all()
        )
        consumed = {value for claim in history for value in claim.notification_ids}
        rows = list(
            (
                await db.scalars(
                    select(Notification)
                    .where(
                        Notification.user_id == user_id,
                        Notification.category == "cinemas",
                        Notification.status == "queued",
                        (Notification.deliver_after_utc.is_(None))
                        | (Notification.deliver_after_utc <= now),
                    )
                    .order_by(Notification.created_at_utc)
                    .with_for_update()
                )
            ).all()
        )
        # A claimant can crash before it changes outbox status. Its durable claim still wins.
        for claim in history:
            if claim.outcome == "claimed" and claim.claimed_at_utc < now - timedelta(minutes=30):
                claim.outcome = "unknown"
                claim.finished_at_utc = now
                for row in rows:
                    if str(row.id) in claim.notification_ids:
                        row.status, row.suppressed_reason = "failed", "cinema_delivery_unknown"
        rows = [row for row in rows if str(row.id) not in consumed]
        if not rows or any(c.local_date == london_day(now) for c in history):
            return None
        pref = await get_or_create_preferences(db, user_id)
        if not pref.cinemas_enabled:
            for row in rows:
                row.status, row.suppressed_reason = "suppressed", "category_disabled"
            return None
        if quiet_hours_cover(pref, now):
            # These rows have already passed their original digest target. Restarting
            # the digest clock at each late quiet check can starve daily 08:00 delivery.
            target = _quiet_hours_end_after(pref, now)
            for row in rows:
                row.deliver_after_utc = target
                row.deferred_reason = DEFERRED_QUIET_HOURS
            return None
        days = (
            await db.scalars(
                select(CinemaDigestDay).where(
                    CinemaDigestDay.evaluated_at_utc >= now - timedelta(days=8)
                )
            )
        ).all()
        ids_by_notification: dict[str, list[str]] = {}
        for day in days:
            entry = day.report.get("recipients", {}).get(str(user_id))
            if entry:
                ids_by_notification[entry["notificationId"]] = entry["appearanceIds"]
        ids = {value for row in rows for value in ids_by_notification.get(str(row.id), [])}
        appearances = list(
            (
                await db.scalars(
                    select(CinemaDigestAppearance).where(
                        CinemaDigestAppearance.id.in_([uuid.UUID(value) for value in ids]),
                        CinemaDigestAppearance.recognised_utc > now - timedelta(days=7),
                    )
                )
            ).all()
        )
        remaining = {
            identity
            for showing, film in (
                await db.execute(
                    select(CinemaScreening, CinemaFilm)
                    .join(CinemaFilm, CinemaFilm.id == CinemaScreening.film_id)
                    .where(
                        CinemaScreening.starts_utc > now,
                        CinemaScreening.deleted_at.is_(None),
                        CinemaFilm.deleted_at.is_(None),
                        CinemaScreening.confirmation == "confirmed",
                        CinemaScreening.source_expired.is_(False),
                    )
                )
            ).all()
            if (identity := tmdb_id(film)) is not None
            and (not pref.cinemas_older_only or showing.release_category == "olderFilm")
        }
        states = {
            f.id: f.tmdb_id
            for f in (
                await db.scalars(
                    select(CinemaDigestFilm).where(
                        CinemaDigestFilm.id.in_([a.film_id for a in appearances])
                    )
                )
            ).all()
        }
        eligible = sorted(
            [
                a
                for a in appearances
                if states.get(a.film_id) in remaining
                and (not pref.cinemas_older_only or "Rerun" in a.run_labels)
            ],
            key=lambda a: (a.title.casefold(), str(a.id)),
        )
        eligible_ids = {str(a.id) for a in eligible}
        usable = []
        for row in rows:
            if eligible_ids.intersection(ids_by_notification.get(str(row.id), [])):
                usable.append(row)
            else:
                row.status, row.suppressed_reason = (
                    "suppressed",
                    "cinema_filter_empty"
                    if pref.cinemas_older_only and appearances
                    else "cinema_digest_expired",
                )
        if not usable:
            return None
        devices = await active_subscriptions(db, user_id)
        if not devices:
            for row in usable:
                row.status, row.suppressed_reason = "suppressed", "no_subscriptions"
            return None
        claim = CinemaDigestDelivery(
            id=uuid.uuid4(),
            user_id=user_id,
            local_date=london_day(now),
            claimed_at_utc=now,
            outcome="claimed",
            delivered_count=0,
            notification_ids=[str(row.id) for row in usable],
            appearance_ids=sorted(eligible_ids),
            device_ids=[str(device.id) for device in devices],
            payload=payload(
                eligible, pref.cinemas_older_only, f"cinemas:{user_id}:{london_day(now)}"
            ),
        )
        db.add(claim)
        # The last row represents a coalesced delivery; originals remain readable as history.
        for row in usable[:-1]:
            row.status, row.suppressed_reason = "suppressed", "cinema_digest_coalesced"
        await db.flush()
        return claim


async def deliver(
    engine: AsyncEngine,
    sender: PushSender,
    *,
    now: datetime | None = None,
    user_id: object | None = None,
) -> DeliverySummary:
    now = now or utcnow()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    summary = DeliverySummary()
    async with factory() as db:
        query = (
            select(Notification.user_id)
            .where(Notification.category == "cinemas", Notification.status == "queued")
            .distinct()
        )
        if user_id is not None:
            query = query.where(Notification.user_id == user_id)
        users = list((await db.scalars(query)).all())
    for owner in users:
        claim = await _claim(engine, owner, now)
        if claim is None:
            continue
        summary.considered += 1
        # The claim transaction above has committed. Sending cannot roll it back.
        try:
            async with factory() as db, db.begin():
                devices = [
                    s
                    for s in await active_subscriptions(db, owner)
                    if str(s.id) in claim.device_ids
                ]
                result = await deliver_to_subscriptions(
                    db,
                    subscriptions=devices,
                    payload=json.dumps(claim.payload, ensure_ascii=False).encode(),
                    sender=sender,
                    now=now,
                )
                stored = await db.get(CinemaDigestDelivery, claim.id)
                assert stored is not None
                stored.outcome = "sent" if result.delivered else "failed"
                stored.finished_at_utc, stored.delivered_count = now, result.delivered
                for row in (
                    await db.scalars(
                        select(Notification).where(
                            Notification.id.in_(
                                [uuid.UUID(value) for value in claim.notification_ids]
                            )
                        )
                    )
                ).all():
                    if row.suppressed_reason == "cinema_digest_coalesced":
                        continue
                    row.status = "sent" if result.delivered else "failed"
                    row.sent_at_utc = now if result.delivered else None
                    row.delivered_count = result.delivered
                summary.sent += int(bool(result.delivered))
                summary.failed += int(not result.delivered)
                summary.pushes_delivered += result.delivered
                summary.subscriptions_removed += len(result.removed)
        except Exception:
            # Durable claim remains consumed even if transport or the result commit failed.
            log.warning("cinema_digest_delivery_uncertain", claim=str(claim.id), exc_info=True)
            async with factory() as db, db.begin():
                stored = await db.get(CinemaDigestDelivery, claim.id)
                assert stored is not None
                stored.outcome, stored.finished_at_utc = "unknown", now
                for row in (
                    await db.scalars(
                        select(Notification).where(
                            Notification.id.in_(
                                [uuid.UUID(value) for value in claim.notification_ids]
                            ),
                            Notification.status == "queued",
                        )
                    )
                ).all():
                    row.status, row.suppressed_reason = "failed", "cinema_delivery_unknown"
            summary.failed += 1
    return summary
