"""Price targets: setting them, and checking them on the schedule — Batch T8a.

Two kinds, both on the app's own eBay access (`DECISIONS.md` #216):

- **A listing**, by its web address. Checked with one ``get_item_by_legacy_id`` call. A
  Buy It Now price counts with its postage, because that is what is paid. An auction's
  current bid counts on its own, and the alert offers the target as a **maximum bid**: the
  app cannot bid (eBay's bidding API is Limited Release, #203), but eBay's own proxy bidding
  will, up to that amount, once the person sets it. Met once, then left alone until the
  target changes.
- **A saved search**: a film on a format, meaning any UK Buy It Now listing of it. Checked
  with one search, judged by the film page's matcher. Auctions are left out: an opening bid
  of 99p a week before the end is not a price anyone pays. It stays watching, so the next
  cheap listing is news too, and each listing is told once.

**The alert goes to the person who set the target** and nobody else, in the ``deals``
category, so the setting that silences deal pushes silences these too.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ebay.client import EbayError
from src.ebay.estimate import search_query
from src.ebay.matching import CONDITION_LABELS, match
from src.matching.engine import searchable_title
from src.models.ebay_watch import EbayTarget, EbayWatchRun
from src.models.movie import Movie
from src.services.ebay_watch.client import WatchClient
from src.services.ebay_watch.links import NOT_A_LISTING, legacy_item_id
from src.services.ebay_watch.listings import ItemState, ScanListing, item_state, scan_listing

logger = structlog.get_logger(__name__)

FORMAT_LABELS = {"4k_uhd": "4K", "blu_ray": "Blu-ray", "dvd": "DVD"}

#: Consecutive eBay failures before a pass stops checking targets.
MAX_FAILURES_IN_A_ROW = 5


class TargetError(ValueError):
    """The target cannot be set, with the reason in the words the page shows."""


@dataclass(frozen=True)
class Alert:
    """One push to one person."""

    user_id: uuid.UUID
    title: str
    body: str
    url: str
    dedupe_key: str


PENNY = Decimal("0.01")


def pounds(amount: Decimal) -> str:
    return f"£{amount:.2f}"


def short(title: str, limit: int = 60) -> str:
    """A title short enough for a push, which a phone cuts off anyway."""
    return title if len(title) <= limit else f"{title[: limit - 1].rstrip()}…"


def _key(target: EbayTarget, item_id: str) -> str:
    """One push per target, per listing, per target price: a new target may tell again."""
    return f"ebay-target:{target.id}:{item_id}:{target.target_price}"


# ---------------------------------------------------------------------------
# Setting
# ---------------------------------------------------------------------------


def _record(target: EbayTarget, state: ItemState, now: datetime) -> None:
    target.title = state.title
    target.url = state.url
    target.image_url = state.image_url or target.image_url
    target.is_auction = state.is_auction_only
    target.current_price = state.buy_now if state.buy_now is not None else state.current_bid
    target.current_postage = state.postage
    target.current_item_id = state.legacy_id
    target.current_url = state.url
    target.ends_at_utc = state.ends_at
    target.last_checked_utc = now
    target.last_error = None


def _met(target: EbayTarget, state: ItemState) -> tuple[str, Decimal] | None:
    """``("buy", total)`` or ``("bid", bid)`` when the listing is at or under the target."""
    if state.buy_now is not None and state.total(state.buy_now) <= target.target_price:
        return "buy", state.total(state.buy_now)
    if state.current_bid is not None and state.current_bid <= target.target_price:
        return "bid", state.current_bid
    return None


def _ended(state: ItemState | None, now: datetime) -> bool:
    return (
        state is None or not state.available or (state.ends_at is not None and state.ends_at <= now)
    )


async def create_listing_target(
    db: AsyncSession,
    client: WatchClient,
    *,
    owner_id: uuid.UUID,
    address: str,
    target_price: Decimal,
    now: datetime,
) -> EbayTarget:
    """A target on one listing. Costs one eBay call, to read the listing as it is now.

    A listing already at or under the target is saved as met, without a push: the person
    is looking at it, and a push would only repeat what the page says.
    """
    legacy = legacy_item_id(address)
    if legacy is None:
        raise TargetError(NOT_A_LISTING)
    existing = await db.scalar(
        select(EbayTarget.id).where(
            EbayTarget.owner_id == owner_id,
            EbayTarget.kind == "listing",
            EbayTarget.legacy_item_id == legacy,
            EbayTarget.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise TargetError("You already have a price alert on this listing. Change its target.")
    payload = await client.get_item_by_legacy_id(legacy)
    state = item_state(payload) if payload is not None else None
    if state is None:
        raise TargetError("eBay has no listing with that number. It may have ended.")
    if state.currency != "GBP":
        raise TargetError("That listing is not priced in pounds, so it cannot be compared.")
    target = EbayTarget(
        id=uuid.uuid4(),
        owner_id=owner_id,
        kind="listing",
        legacy_item_id=legacy,
        target_price=target_price.quantize(PENNY),
        currency="GBP",
        title=state.title,
        status="watching",
        created_at_utc=now,
    )
    _record(target, state, now)
    if _ended(state, now):
        target.status = "ended"
    elif _met(target, state) is not None:
        target.status = "met"
        target.met_at_utc = now
    db.add(target)
    await db.flush()
    return target


async def create_search_target(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    movie: Movie,
    format_code: str,
    target_price: Decimal,
    now: datetime,
) -> EbayTarget:
    """A target on a film and format. Costs nothing now; the next pass searches for it."""
    if format_code not in FORMAT_LABELS:
        raise TargetError("Choose 4K, Blu-ray or DVD.")
    if movie.tmdb_id is None:
        raise TargetError("Identify this film first, so eBay is searched under its real title.")
    existing = await db.scalar(
        select(EbayTarget.id).where(
            EbayTarget.owner_id == owner_id,
            EbayTarget.kind == "search",
            EbayTarget.movie_id == movie.id,
            EbayTarget.format_code == format_code,
            EbayTarget.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise TargetError(
            f"You already have a price alert on the {FORMAT_LABELS[format_code]} of this film."
        )
    target = EbayTarget(
        id=uuid.uuid4(),
        owner_id=owner_id,
        kind="search",
        movie_id=movie.id,
        format_code=format_code,
        target_price=target_price.quantize(PENNY),
        currency="GBP",
        title=movie.title,
        status="watching",
        created_at_utc=now,
    )
    db.add(target)
    await db.flush()
    return target


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------


async def check_listing(client: WatchClient, target: EbayTarget, *, now: datetime) -> Alert | None:
    """Read the listing; say so if it is at or under the target."""
    if target.ends_at_utc is not None and target.ends_at_utc <= now:
        target.status = "ended"
        target.last_checked_utc = now
        return None
    payload = await client.get_item_by_legacy_id(target.legacy_item_id or "")
    state = item_state(payload) if payload is not None else None
    if state is None or _ended(state, now):
        target.status = "ended"
        target.last_checked_utc = now
        return None
    _record(target, state, now)
    met = _met(target, state)
    if met is None:
        return None
    how, amount = met
    target.status = "met"
    target.met_at_utc = now
    goal = pounds(target.target_price)
    if how == "buy":
        body = (
            f"Buy It Now at {pounds(amount)} with postage, at or under your {goal}. "
            "Tap to open the listing."
        )
        title = f"{short(state.title)}: {pounds(amount)}"
    else:
        postage = f" (plus {pounds(state.postage)} postage)" if state.postage else ""
        ends = f" It ends {state.ends_at:%a %d %b at %H:%M} UTC." if state.ends_at else ""
        body = (
            f"Bidding is at {pounds(amount)}{postage}, under your {goal}. Set {goal} as "
            f"your maximum bid on eBay, and eBay's own bidding goes up to it for you.{ends}"
        )
        title = f"{short(state.title)}: bidding at {pounds(amount)}"
    return Alert(target.owner_id, title, body, state.url, _key(target, state.legacy_id))


async def check_search(
    client: WatchClient, target: EbayTarget, movie: Movie, *, now: datetime
) -> Alert | None:
    """Search for the film on the format; say so if the cheapest copy is at or under."""
    format_code = target.format_code or ""
    title = searchable_title(movie.title, identified=movie.tmdb_id is not None)
    raw = await client.search(search_query(title, format_code))
    cheapest: ScanListing | None = None
    for summary in raw.get("itemSummaries") or []:
        found = scan_listing(summary)
        if found is None or not found.buy_now:
            continue
        verdict = match(found.listing, film_title=title, format_code=format_code, country="GB")
        if not verdict.ok:
            continue
        if cheapest is None or found.total < cheapest.total:
            cheapest = found
    target.last_checked_utc = now
    target.last_error = None
    if cheapest is None:
        target.current_price = None
        target.current_postage = None
        target.current_item_id = None
        target.current_url = None
        return None
    target.current_price = cheapest.listing.price
    target.current_postage = cheapest.postage
    target.current_item_id = cheapest.legacy_id
    target.current_url = cheapest.url
    if cheapest.total > target.target_price:
        return None
    label = FORMAT_LABELS.get(format_code, format_code)
    condition = CONDITION_LABELS.get(cheapest.listing.condition_id, "Condition not stated")
    return Alert(
        target.owner_id,
        f"{short(movie.title)} on {label}: {pounds(cheapest.total)}",
        f"{condition}, Buy It Now at {pounds(cheapest.total)} with postage, at or under your "
        f"{pounds(target.target_price)}. Tap to open the listing.",
        cheapest.url,
        _key(target, cheapest.legacy_id),
    )


async def check_targets(
    db: AsyncSession,
    client: WatchClient,
    run: EbayWatchRun,
    *,
    clock: Callable[[], datetime],
) -> tuple[list[Alert], str | None]:
    """Check every watching target, oldest-checked first, within the run's budget.

    Returns the alerts and, if the pass stopped early, why: ``budget`` or ``failed``.
    Each target is committed as it is checked.
    """
    targets = list(
        (
            await db.scalars(
                select(EbayTarget)
                .where(EbayTarget.deleted_at.is_(None), EbayTarget.status == "watching")
                .order_by(EbayTarget.last_checked_utc.asc().nulls_first(), EbayTarget.id)
            )
        ).all()
    )
    alerts: list[Alert] = []
    failures_in_a_row = 0
    for target in targets:
        if client.search_calls + client.attempts_per_search > run.budget:
            return alerts, "budget"
        now = clock()
        try:
            if target.kind == "listing":
                alert = await check_listing(client, target, now=now)
            else:
                movie = await db.get(Movie, target.movie_id) if target.movie_id else None
                if movie is None or movie.deleted_at is not None:
                    target.status = "ended"
                    target.last_checked_utc = now
                    alert = None
                else:
                    alert = await check_search(client, target, movie, now=now)
        except EbayError as exc:
            failures_in_a_row += 1
            target.last_error = str(exc)[:300]
            run.last_error = f"{short(target.title, 40)}: {exc}"
            logger.warning("ebay_target_check_failed", target=str(target.id), error=str(exc))
            run.calls = client.search_calls
            await db.commit()
            if exc.status_code == 429 or failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                return alerts, "failed"
            continue
        failures_in_a_row = 0
        run.targets_checked += 1
        if alert is not None:
            alerts.append(alert)
        run.calls = client.search_calls
        run.heartbeat_utc = now
        await db.commit()
    return alerts, None
