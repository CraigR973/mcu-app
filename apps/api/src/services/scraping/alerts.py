"""Price-drop alerts — §5.6.

**§5.6 describes a Postgres trigger and that cannot work.** *"Postgres trigger after
price_check insert: if price ≤ max_price and not notified, queue push"* — a trigger runs
inside the writing transaction and cannot make an HTTP request to a push service. The most
it could do is write a queue row, and Batch 11 already built that queue: the `notifications`
outbox. So the detection lives here, in the scrape path, and writes a `deals` notification
that the ordinary delivery pass sends. The `price_checks.notification_sent` column §3.6
designed for the trigger is still the flag; this is simply the code that sets it.

**An alert fires on the way down, not on every night the price stays low.** "Price ≤
max_price" is true for as long as the disc is cheap, so alerting on the condition would
send the same message every night until the owner either bought it or turned the category
off. What is worth telling someone is the *transition*: the most recent previous check for
the same want at the same shop was above the threshold (or there wasn't one). The alert
re-arms by itself when the price goes back up, which is exactly when a second alert would
be news again.

**A substituted format or edition still alerts, and says so.** `DECISIONS.md` #105 and #106
mean a want for 4K is a want for 4K, and Batch 19 already records when it priced something
else instead. Suppressing the alert would hide a real find; sending it silently would let
"Deep Red is £15" mean the Blu-ray when the want was the 4K. So it is sent with the
substitution named in the body — the same rule `ScrapeOutcome` states for its own fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.movie import Movie
from src.models.notification import NotificationCategory
from src.models.price_check import PriceCheck
from src.models.profile import Profile
from src.models.wanted import WantedItem
from src.services.ebay_watch.refs import Yardstick
from src.services.ebay_watch.usual import shop_usual
from src.services.format_names import format_label
from src.services.notifications import queue_notification

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AlertCandidate:
    """One newly written price check, with what the scrape knew about it."""

    check: PriceCheck
    wanted: WantedItem
    #: Set when the wanted format was not on the shelf and another was priced instead.
    substituted_format: str | None = None
    #: ``False`` when a specific edition was wanted and a different one was priced.
    edition_matched: bool | None = None


def _money(amount: Decimal, currency: str) -> str:
    """A price as money. Never converted — see `DECISIONS.md` #79."""
    symbol = {"GBP": "£", "USD": "$", "EUR": "€"}.get(currency.upper())
    return f"{symbol}{amount:.2f}" if symbol else f"{amount:.2f} {currency}"


async def _previously_alerted_below_threshold(
    db: AsyncSession, candidate: AlertCandidate, threshold: Decimal
) -> bool:
    """Was the last check for this want at this shop already a notified drop?

    The question that turns "the price is low" into "the price has *just become* low".
    Scoped to the retailer as well as the want, so a drop at Zavvi is not silenced by an
    earlier drop at Arrow — they are different offers on different pages.
    """
    previous = (
        await db.execute(
            select(PriceCheck)
            .where(
                PriceCheck.wanted_id == candidate.check.wanted_id,
                PriceCheck.retailer_id == candidate.check.retailer_id,
                PriceCheck.id != candidate.check.id,
                PriceCheck.checked_at <= candidate.check.checked_at,
            )
            .order_by(PriceCheck.checked_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if previous is None:
        return False
    return previous.notification_sent and previous.price <= threshold


def _body(candidate: AlertCandidate, title: str, usual: Yardstick | None = None) -> str:
    """What the notification says, including any substitution."""
    price = _money(candidate.check.price, candidate.check.currency)
    parts = [f"{price} at {candidate.check.retailer_name_snapshot}."]

    if candidate.substituted_format:
        # Never silent: the alert compares against whatever was priced, so the reader has
        # to be able to see that it was not the format they asked for.
        parts.append(
            f"This is the {format_label(candidate.substituted_format)}, not the format you wanted."
        )
    if candidate.edition_matched is False:
        parts.append(
            f"It is a different edition from the {candidate.wanted.preferred_edition!r} "
            "you asked for."
        )
    if usual is not None:
        # A drop with no limit set says what it was measured against.
        parts.append(
            f"Under the usual {_money(usual.median, candidate.check.currency)} on eBay "
            f"(asking prices, {usual.sample_size} listings)."
        )
    if candidate.check.title_snapshot and candidate.check.title_snapshot != title:
        parts.append(f"Listed as {candidate.check.title_snapshot!r}.")
    return " ".join(parts)


async def queue_price_drop_alerts(
    db: AsyncSession, candidates: list[AlertCandidate], *, now: datetime | None = None
) -> int:
    """Notify about every candidate that has just fallen to or below its threshold.

    Returns how many notifications were written. Both people hear about it: §3.5's wanted
    list is one shared list rather than two private ones, and §6.1's `deals` toggle is
    what lets either of them opt out.
    """
    if not candidates:
        return 0

    people = list(
        (
            await db.execute(
                select(Profile).where(Profile.deleted_at.is_(None), Profile.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    if not people:  # pragma: no cover - the app always has two profiles
        return 0

    queued = 0
    stamp = now or utcnow()
    for candidate in candidates:
        threshold = candidate.wanted.max_price
        usual: Yardstick | None = None
        if threshold is None:
            # No limit set (Batch X11, MK47-05): 9 of the 10 wants had none, so no shop alert
            # could fire. The film's usual stands in, like for like, and only when one is
            # stored: see :func:`shop_usual`.
            if candidate.check.currency != "GBP":
                continue
            usual = await shop_usual(
                db,
                movie_id=candidate.wanted.movie_id,
                title=candidate.check.title_snapshot,
                url=candidate.check.url,
                now=stamp,
            )
            if usual is None or candidate.check.price >= usual.median:
                continue
            threshold = usual.median
        elif candidate.check.price > threshold:
            continue
        if await _previously_alerted_below_threshold(db, candidate, threshold):
            # Still cheap, already said so. Re-arms when it goes back above.
            candidate.check.notification_sent = True
            continue

        movie = await db.get(Movie, candidate.wanted.movie_id)
        title = movie.title if movie is not None else "A wanted film"
        price = _money(candidate.check.price, candidate.check.currency)

        for person in people:
            written = await queue_notification(
                db,
                user_id=person.id,
                category=NotificationCategory.deals,
                title=f"{title} is {price}",
                body=_body(candidate, title, usual),
                url="/wanted",
                # The check's own id: one alert per person per drop, and a re-run that
                # updates the same row cannot produce a second.
                dedupe_key=f"price-drop:{candidate.check.id}:{person.id}",
                now=now,
            )
            if written is not None:
                queued += 1

        candidate.check.notification_sent = True
        logger.info(
            "price_drop_alert",
            title=title,
            price=str(candidate.check.price),
            retailer=candidate.check.retailer_name_snapshot,
            threshold=str(threshold),
            basis="usual" if usual is not None else "limit",
        )

    return queued
