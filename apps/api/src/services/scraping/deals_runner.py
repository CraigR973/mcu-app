"""Running a deals scrape and writing what survives it — Batch 22, Phase 5.9.

Three things happen per retailer, in this order, and the order is the point:

1. **Fetch and extract**, through Batch 19's `fetcher` — so the SSRF guard, the rate
   limiting and the honest user agent all apply unchanged. A deals page is still somebody
   else's website.
2. **Judge**, per page and then per card (`deals.check_page_shape`, `judge_cards`).
   A page that fails its population check has **every** card discarded, not just the bad
   ones: if the `was` selector is reading a banner, each individual discount is wrong in
   exactly the way that looks right. On a page that passes, a card at a single price is
   counted as not discounted and a card that fails a check as rejected (Batch 22b).
3. **Match and write**, skipping anything already owned.

**"Skip already-owned" is format-aware, and the criterion does not say so.** §5.9 says
*"skip already-owned"*, which read literally would hide the 4K of a film you own on DVD —
and that is the single most useful deal there is. So a deal is skipped when the format on
offer is **not better than** what is already owned, using the same `FORMAT_RANK` the
`best_format_owned` trigger enforces. An upgrade is never already-owned.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import FORMAT_RANK, CollectionItem, owned_copy
from src.models.deal import Deal
from src.models.movie import Movie
from src.models.wanted import Retailer
from src.services.scraping.deals import (
    DealCandidate,
    check_page_shape,
    deal_format,
    extract_deals,
    judge_cards,
)
from src.services.scraping.extract import TITLE_NOISE, YEAR_PATTERN, _normalise
from src.services.scraping.fetcher import FetchError, UnsafeUrlError, fetch_page

logger = structlog.get_logger()


@dataclass
class RetailerDealsOutcome:
    """What one retailer's sale page produced."""

    retailer: str
    ok: bool
    found: int = 0
    kept: int = 0
    skipped_owned: int = 0
    rejected: int = 0
    matched: int = 0
    #: Batch 22b. Cards on the sale page at a single price: listed, not discounted, and
    #: not a failure (`deals.judge_cards`).
    not_discounted: int = 0
    #: Why the page as a whole was refused, when it was. A page-level failure discards
    #: every card, so this is the difference between "a quiet sale" and "broken".
    page_reasons: list[str] = field(default_factory=list)
    #: Why the first few rejected cards were rejected, so a page that passed but kept
    #: little says why.
    rejected_reasons: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class DealsRunSummary:
    """The whole run, per `batch-verify`'s "report by acceptance criterion"."""

    started_at_utc: datetime
    outcomes: list[RetailerDealsOutcome] = field(default_factory=list)

    @property
    def written(self) -> int:
        return sum(outcome.kept for outcome in self.outcomes)

    @property
    def retailers_with_deals(self) -> int:
        """§5.9's "≥ 3 retailers", computed rather than asserted."""
        return sum(1 for outcome in self.outcomes if outcome.kept > 0)

    @property
    def skipped_owned(self) -> int:
        """§5.9's "skip already-owned", as a number somebody can check."""
        return sum(outcome.skipped_owned for outcome in self.outcomes)


def _rank(codes: list[str]) -> int | None:
    ranks = [FORMAT_RANK.index(code) for code in codes if code in FORMAT_RANK]
    return min(ranks) if ranks else None


async def already_owned(db: AsyncSession, movie_id: uuid.UUID, format_code: str | None) -> bool:
    """Whether this deal is for something already on the shelf.

    **An upgrade is not already-owned.** Reading §5.9's "skip already-owned" literally
    would hide the 4K of a film owned on DVD, which is the most interesting deal the feed
    could carry. So the comparison is on `FORMAT_RANK`: a deal is skipped only when the
    format on offer is no better than the best already owned.

    A deal whose format could not be read is skipped when *anything* is owned — an
    unknown format cannot be shown to be an upgrade, and the feed is better short than
    wrong.
    """
    owned_formats = (
        (
            await db.execute(
                select(CollectionItem.formats).where(
                    CollectionItem.movie_id == movie_id, owned_copy()
                )
            )
        )
        .scalars()
        .all()
    )
    if not owned_formats:
        return False

    best_owned = _rank([code for formats in owned_formats for code in formats])
    if best_owned is None:
        return True
    if format_code is None or format_code not in FORMAT_RANK:
        return True
    return FORMAT_RANK.index(format_code) >= best_owned


def narrowing_word(title: str) -> str | None:
    """The word :func:`match_to_film` narrows its SQL on: the longest that could be in a
    film's title.

    **Not simply the longest word** (Batch 22b). A shop's own words are often the longest
    in a listing, and no film's title contains them: on Zavvi's captured page "Spectre - 4K
    Ultra HD (Includes 2D Blu-ray)" narrowed on *includes* and "The Deer Hunter - 40th
    Anniversary Edition" on *anniversary*, so neither found its film, an owned copy was not
    skipped and the deal had no poster. The words the price scraper already treats as a
    shop's (`TITLE_NOISE`) and bare years are passed over. Ties go alphabetically, so the
    choice does not depend on set order.
    """
    words = _normalise(title)
    if not words:
        return None
    telling = {word for word in words if word not in TITLE_NOISE and not YEAR_PATTERN.match(word)}
    return max(sorted(telling or words), key=len)


async def match_to_film(db: AsyncSession, title: str) -> Movie | None:
    """The catalogued film a deal's title names, or ``None``.

    Deliberately conservative: it matches against films **already in the catalogue** by
    significant-word overlap, and requires every significant word of the film's title to
    appear in the deal's. That direction matters — "Jaws" is contained in "Jaws 2", so
    matching the other way round would file a Jaws 2 deal under Jaws.

    A deal that matches nothing is **kept with a null `movie_id`**, not dropped. An
    unmatched deal is the evidence that the matcher needs work; dropping it would make a
    broken matcher look like a quiet sale page, which is the failure this whole batch is
    written against.
    """
    words = _normalise(title)
    narrow = narrowing_word(title)
    if not words or narrow is None:
        return None

    # Candidate films share at least one significant word. Narrowing in SQL first keeps
    # this from loading 1,843 rows per card.
    candidates = (
        (
            await db.execute(
                select(Movie)
                .where(Movie.deleted_at.is_(None), Movie.title.ilike(f"%{narrow}%"))
                .limit(50)
            )
        )
        .scalars()
        .all()
    )

    best: Movie | None = None
    best_size = 0
    for movie in candidates:
        film_words = _normalise(movie.title)
        if film_words and film_words <= words and len(film_words) > best_size:
            best, best_size = movie, len(film_words)
    return best


async def scrape_retailer_deals(
    db: AsyncSession,
    retailer: Retailer,
    *,
    dry_run: bool = False,
) -> RetailerDealsOutcome:
    """One retailer's sale page, end to end."""
    outcome = RetailerDealsOutcome(retailer=retailer.name, ok=False)

    if not retailer.deals_url:
        outcome.error = "no deals URL configured"
        return outcome

    try:
        page = await fetch_page(retailer.deals_url)
    except (FetchError, UnsafeUrlError) as exc:
        outcome.error = str(exc)
        return outcome

    candidates = extract_deals(
        page.html, dict(retailer.scraper_config or {}), page_url=page.final_url
    )
    outcome.found = len(candidates)

    page_verdict = check_page_shape(candidates)
    if not page_verdict.ok:
        # Every card is discarded, not just the failing ones. If the `was` selector is
        # reading a banner, each discount is wrong in precisely the way that looks right.
        outcome.page_reasons = page_verdict.reasons
        outcome.error = "; ".join(page_verdict.reasons)
        logger.warning(
            "deals_page_shape_failed", retailer=retailer.name, reasons=page_verdict.reasons
        )
        return outcome

    # A hostname, as the price runner passes it. Batch 22 passed the whole base URL, which
    # failed every one of Second Sight's and 101 Films' own listings (`extract._host_of`).
    judged = judge_cards(
        candidates,
        expected_currency=retailer.currency,
        retailer_host=urlparse(retailer.base_url).hostname,
    )
    outcome.not_discounted = judged.not_discounted
    outcome.rejected = judged.rejected
    outcome.rejected_reasons = judged.rejected_reasons

    now = utcnow()
    for candidate in judged.deals:
        format_code = deal_format(candidate)
        movie = await match_to_film(db, candidate.title or "")
        if movie is not None:
            outcome.matched += 1
            if await already_owned(db, movie.id, format_code):
                outcome.skipped_owned += 1
                continue

        if not dry_run:
            await _upsert(db, retailer, candidate, movie, format_code, now)
        outcome.kept += 1

    outcome.ok = True
    logger.info(
        "deals_scraped",
        retailer=retailer.name,
        found=outcome.found,
        kept=outcome.kept,
        skipped_owned=outcome.skipped_owned,
        not_discounted=outcome.not_discounted,
        rejected=outcome.rejected,
    )
    return outcome


async def _upsert(
    db: AsyncSession,
    retailer: Retailer,
    candidate: DealCandidate,
    movie: Movie | None,
    format_code: str | None,
    now: datetime,
) -> None:
    """Insert a deal, or refresh the one already recorded for this URL.

    **Refreshing rather than replacing keeps two things a delete-and-reinsert loses**:
    `first_seen_at_utc`, which is how long something has been on offer, and
    `dismissed_at_utc`, which is §5.10's *"dismissed items don't reappear"* surviving
    tonight's scrape re-finding the same deal.
    """
    existing = await db.scalar(
        select(Deal).where(Deal.retailer_id == retailer.id, Deal.url == candidate.url)
    )
    if existing is not None:
        existing.price = candidate.price  # type: ignore[assignment]
        existing.was_price = candidate.was_price
        existing.discount_percent = candidate.discount_percent
        existing.title_snapshot = candidate.title or existing.title_snapshot
        existing.image_url = candidate.image_url or existing.image_url
        existing.format_code = format_code
        existing.last_seen_at_utc = now
        if movie is not None:
            existing.movie_id = movie.id
            existing.tmdb_id = movie.tmdb_id
        return

    db.add(
        Deal(
            id=uuid.uuid4(),
            retailer_id=retailer.id,
            retailer_name_snapshot=retailer.name,
            movie_id=movie.id if movie else None,
            tmdb_id=movie.tmdb_id if movie else None,
            title_snapshot=candidate.title or "(untitled)",
            url=candidate.url or "",
            image_url=candidate.image_url,
            format_code=format_code,
            price=candidate.price,
            was_price=candidate.was_price,
            currency=candidate.currency or retailer.currency,
            discount_percent=candidate.discount_percent,
            first_seen_at_utc=now,
            last_seen_at_utc=now,
        )
    )


async def run_deals_scrape(db: AsyncSession, *, dry_run: bool = False) -> DealsRunSummary:
    """Every enabled retailer that has a sale page.

    **A retailer with no `deals_url` is reported, not skipped silently.** Four of the five
    enabled shops had none when this batch was written, and §5.9's acceptance needs three
    retailers producing rows — so "nothing configured" has to read differently from
    "nothing on sale".
    """
    summary = DealsRunSummary(started_at_utc=utcnow())
    retailers = (
        (
            await db.execute(
                select(Retailer)
                .where(Retailer.deleted_at.is_(None), Retailer.enabled.is_(True))
                .order_by(Retailer.name)
            )
        )
        .scalars()
        .all()
    )

    for retailer in retailers:
        summary.outcomes.append(await scrape_retailer_deals(db, retailer, dry_run=dry_run))

    if not dry_run:
        await db.commit()
    return summary
