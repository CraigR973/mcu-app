"""A preference change cancels/excludes pending films permanently, before any send claim."""

import copy
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cinema_digest import CinemaDigestAppearance, CinemaDigestDay, CinemaDigestDelivery
from src.models.notification import Notification, NotificationPreference
from src.services.cinema_digest.evaluate import words


async def apply_pending(db: AsyncSession, user_id: uuid.UUID, pref: NotificationPreference) -> None:
    claims = (
        await db.scalars(
            select(CinemaDigestDelivery).where(CinemaDigestDelivery.user_id == user_id)
        )
    ).all()
    claimed = {value for claim in claims for value in claim.notification_ids}
    rows = [
        row
        for row in (
            await db.scalars(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.category == "cinemas",
                    Notification.status == "queued",
                )
            )
        ).all()
        if str(row.id) not in claimed
    ]
    if not pref.cinemas_enabled:
        for row in rows:
            row.status, row.suppressed_reason = "suppressed", "category_disabled"
        return
    if not pref.cinemas_older_only or not rows:
        return
    by_id = {str(row.id): row for row in rows}
    for day in (await db.scalars(select(CinemaDigestDay))).all():
        report = copy.deepcopy(day.report)
        entry = report.get("recipients", {}).get(str(user_id))
        if not entry or entry["notificationId"] not in by_id:
            continue
        original = list(entry["appearanceIds"])
        items = list(
            (
                await db.scalars(
                    select(CinemaDigestAppearance).where(
                        CinemaDigestAppearance.id.in_([uuid.UUID(value) for value in original])
                    )
                )
            ).all()
        )
        older = [item for item in items if "Rerun" in item.run_labels]
        entry.setdefault("originalAppearanceIds", original)
        entry["appearanceIds"] = [str(item.id) for item in older]
        entry["olderOnly"] = True
        day.report = report
        row = by_id[entry["notificationId"]]
        if older:
            row.title, row.body = words(older, True)
            row.url = "/movie-night/cinema?view=new-this-week&run=olderFilm"
        else:
            row.status, row.suppressed_reason = "suppressed", "cinema_filter_empty"
