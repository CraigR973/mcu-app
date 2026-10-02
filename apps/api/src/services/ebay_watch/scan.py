"""The deal scan: new UK 4K and Blu-ray listings well under their usual price — Batch T8a.

**It reads eBay's newest listings rather than searching film by film.** On 26 Sep about 200
new UK Blu-ray and 4K Buy It Now listings appeared every two or three hours, so reading
them all costs a few calls a pass. Searching the 1,300-odd films that could be bought
better, one by one, would cost that many a pass and still see each film only now and then.

A pass reads the newest listings back to where the last pass stopped (at most
:data:`MAX_PAGES` pages; in a flood the older ones are skipped for good). Each one that is
a film on the Wanted list, or an upgrade on what is owned (`deals_runner.already_owned`'s
rule: a better format than the best on the shelf), is compared with that film's usual
price on that format (:mod:`refs`), averaged since Batch V8 with the shops' recent prices
for it where the nightly check has any (:mod:`usual`). **A deal is one that costs,
postage included, no more than :data:`DEAL_RATIO` of that usual price.** Deals go on the
Deals page, as "eBay", for :data:`DEAL_LIFETIME`, since nothing checks later whether
one has sold.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ebay.client import EbayError
from src.models.deal import Deal
from src.models.ebay_watch import EbayWatchRun
from src.services.ebay_watch.catalogue import CatalogueFilm, load_catalogue
from src.services.ebay_watch.client import WatchClient
from src.services.ebay_watch.listings import ScanListing, scan_listing
from src.services.ebay_watch.refs import Yardstick, fetch_ref, stored_ref, yardstick
from src.services.ebay_watch.usual import ShopPrice, UsualPrice, shop_prices

logger = structlog.get_logger(__name__)

#: The Deals page's name for these, and the rows' ``retailer_name_snapshot``.
EBAY = "eBay"

#: Blu-ray and 4K, however the seller spells it. The category filter keeps it to discs.
SCAN_QUERY = "(blu-ray,bluray,4k,uhd)"
#: eBay UK's "DVDs & Blu-rays", the category the estimator's matcher also requires.
SCAN_CATEGORY = "617"
#: Sellers in the UK, and listings that can be bought outright: a new auction's opening bid
#: is not a price.
SCAN_FILTER = "itemLocationCountry:GB,buyingOptions:{FIXED_PRICE}"
PAGE_SIZE = 200
#: Pages a pass reads at most: 2,000 listings, far more than two hours brings.
MAX_PAGES = 10
#: How far back the very first pass looks.
FIRST_LOOK_BACK = timedelta(hours=3)
#: A deal costs no more than this share of the usual price: 30% or more under it.
DEAL_RATIO = Decimal("0.70")
#: How long a deal stays on the Deals page.
DEAL_LIFETIME = timedelta(days=3)


@dataclass(frozen=True)
class Candidate:
    film: CatalogueFilm
    format_code: str
    listing: ScanListing
    wanted: bool


@dataclass(frozen=True)
class Find:
    """A deal, and what the push about it says."""

    film: CatalogueFilm
    format_code: str
    listing: ScanListing
    #: eBay's figure for the film and format.
    usual: Yardstick
    wanted: bool
    discount_percent: int
    #: The shops' recent prices averaged into it (Batch V8); none for most finds.
    shops: tuple[ShopPrice, ...] = ()

    @property
    def figure(self) -> UsualPrice:
        """The usual price the find was judged against, and where it comes from."""
        return UsualPrice(self.usual, self.shops)


@dataclass
class ScanEnd:
    finds: list[Find]
    #: ``budget`` or ``failed`` when the pass stopped early.
    stopped: str | None = None


def _discount(usual: Decimal, price: Decimal) -> int:
    share = (usual - price) / usual * 100
    return int(share.to_integral_value(rounding=ROUND_HALF_UP))


def is_deal(total: Decimal, usual: Decimal) -> bool:
    return total <= (usual * DEAL_RATIO).quantize(Decimal("0.01"))


async def read_new_listings(
    client: WatchClient,
    run: EbayWatchRun,
    *,
    since: datetime,
) -> tuple[list[ScanListing], str | None]:
    """The listings created after ``since``, newest first; and why it stopped, if early.

    Pages are sorted newest first, so the pass stops at the first page whose last listing
    is not newer than ``since``. A promoted listing can sit at the top of a page out of
    order, which is why the last listing decides and not the first.
    """
    found: dict[str, ScanListing] = {}
    # The next pass starts where this one got to, and never earlier than it started.
    newest = max(run.newest_listing_utc or since, since)
    stopped: str | None = None
    for page in range(MAX_PAGES):
        if client.search_calls + client.attempts_per_search > run.budget:
            stopped = "budget"
            break
        raw = await client.search(
            SCAN_QUERY,
            category_ids=SCAN_CATEGORY,
            sort="newlyListed",
            filter=SCAN_FILTER,
            limit=PAGE_SIZE,
            offset=page * PAGE_SIZE,
        )
        run.pages += 1
        summaries = [item for item in raw.get("itemSummaries") or [] if isinstance(item, dict)]
        for summary in summaries:
            listing = scan_listing(summary)
            if listing is None or listing.listed_at is None:
                continue
            newest = max(newest, listing.listed_at)
            if listing.listed_at > since:
                found.setdefault(listing.legacy_id, listing)
        last = scan_listing(summaries[-1]) if summaries else None
        if (
            len(summaries) < PAGE_SIZE
            or last is None
            or (last.listed_at is not None and last.listed_at <= since)
        ):
            break
    run.newest_listing_utc = newest
    return list(found.values()), stopped


async def _record_deal(db: AsyncSession, find: Find, *, now: datetime) -> None:
    """Put the deal on the Deals page, or refresh the one already there for this listing."""
    listing = find.listing
    existing = await db.scalar(
        select(Deal).where(
            Deal.retailer_id.is_(None),
            Deal.retailer_name_snapshot == EBAY,
            Deal.url == listing.url,
        )
    )
    if existing is not None:
        existing.price = listing.total
        existing.was_price = find.figure.amount
        existing.usual_sources = find.figure.sources()
        existing.discount_percent = find.discount_percent
        existing.last_seen_at_utc = now
        existing.expires_at_utc = now + DEAL_LIFETIME
        return
    db.add(
        Deal(
            id=uuid.uuid4(),
            retailer_id=None,
            retailer_name_snapshot=EBAY,
            movie_id=find.film.movie_id,
            tmdb_id=find.film.tmdb_id,
            title_snapshot=listing.listing.title,
            url=listing.url,
            image_url=listing.image_url,
            format_code=find.format_code,
            price=listing.total,
            was_price=find.figure.amount,
            usual_sources=find.figure.sources(),
            currency="GBP",
            discount_percent=find.discount_percent,
            first_seen_at_utc=now,
            last_seen_at_utc=now,
            expires_at_utc=now + DEAL_LIFETIME,
        )
    )


async def scan(
    db: AsyncSession,
    client: WatchClient,
    run: EbayWatchRun,
    *,
    since: datetime,
    clock: Callable[[], datetime],
) -> ScanEnd:
    """Read the new listings, find the deals, and put them on the Deals page."""
    catalogue = await load_catalogue(db)
    listings, stopped = await read_new_listings(client, run, since=since)
    run.listings_seen = len(listings)
    run.calls = client.search_calls
    await db.commit()

    candidates: list[Candidate] = []
    for listing in listings:
        named = catalogue.named_in(listing.listing)
        if named is None:
            continue
        film, format_code = named
        wanted = film.wants(format_code)
        if wanted or film.upgraded_by(format_code):
            candidates.append(Candidate(film, format_code, listing, wanted))
    run.candidates = len(candidates)
    # The Wanted list first: if the budget runs out, it runs out on upgrades.
    candidates.sort(key=lambda candidate: (not candidate.wanted, candidate.listing.total))

    finds: list[Find] = []
    failures_in_a_row = 0
    for candidate in candidates:
        now = clock()
        ref = await stored_ref(
            db, movie_id=candidate.film.movie_id, format_code=candidate.format_code, now=now
        )
        if ref is None:
            if client.search_calls + client.attempts_per_search > run.budget:
                stopped = stopped or "budget"
                break
            try:
                ref = await fetch_ref(
                    db,
                    client,
                    movie_id=candidate.film.movie_id,
                    title=candidate.film.title,
                    format_code=candidate.format_code,
                    now=now,
                )
            except EbayError as exc:
                failures_in_a_row += 1
                run.last_error = f"{candidate.film.title}: {exc}"
                logger.warning("ebay_usual_price_failed", film=candidate.film.title, error=str(exc))
                if exc.status_code == 429 or failures_in_a_row >= 5:
                    stopped = "failed"
                    break
                continue
            failures_in_a_row = 0
            run.refs_fetched += 1
        usual = yardstick(ref, candidate.listing.listing.condition_id)
        if usual is not None:
            shops = await shop_prices(
                db,
                movie_id=candidate.film.movie_id,
                format_code=candidate.format_code,
                now=now,
            )
            figure = UsualPrice(usual, shops)
            if is_deal(candidate.listing.total, figure.amount):
                find = Find(
                    film=candidate.film,
                    format_code=candidate.format_code,
                    listing=candidate.listing,
                    usual=usual,
                    wanted=candidate.wanted,
                    discount_percent=_discount(figure.amount, candidate.listing.total),
                    shops=shops,
                )
                await _record_deal(db, find, now=now)
                finds.append(find)
                run.deals_found += 1
        run.calls = client.search_calls
        run.heartbeat_utc = now
        await db.commit()
    return ScanEnd(finds=finds, stopped=stopped)
