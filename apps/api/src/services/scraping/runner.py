"""Running the scrapers — retry, auto-disable, and what gets written — Batch 19, §5.3.

**Nothing here makes a live request unless a caller asks it to.** §5.3's acceptance is that
"each built-in scraper runs against the **live** retailer", which `group-start.md` names as
a hard stop: *"a batch whose acceptance requires live third-party requests ... stops before
those runs. The owner performs them."* So this module is the machinery, its tests drive it
against fixtures, and the live run is a command the owner invokes.

Three behaviours §5.3 asks for, and what each is actually for:

**Retry.** A shop that times out once is usually up. Two attempts with a pause, not more —
a scraper that retries hard against a retailer is how an IP gets blocked, which turns a
transient failure into a permanent one.

**Auto-disable after 3 consecutive failures.** The counter resets on any success, so a shop
that fails on Monday and works on Tuesday is never disabled. Three *in a row* means
something changed and a person needs to look.

**A shape assertion, not a success counter.** See ``extract.check_shape``. A result that
parses but does not look like a price is treated as a **failure**, not as data — because
the alternative is a plausible wrong number in the alerts, which is this batch's whole risk.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field, replace
from decimal import Decimal
from urllib.parse import quote, urljoin, urlparse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.movie import Movie
from src.models.price_check import PriceCheck
from src.models.wanted import Retailer, WantedItem
from src.services.scraping.extract import (
    DEFAULT_FORMAT_SEARCH_TERM,
    FORMAT_SEARCH_TERMS,
    ScrapeCandidate,
    check_shape,
    extract,
)
from src.services.scraping.fetcher import (
    FetchError,
    UnsafeUrlError,
    fetch_page,
)

logger = structlog.get_logger()

#: One retry. See the module docstring — retrying hard is how an IP gets blocked.
MAX_ATTEMPTS = 2
RETRY_PAUSE_SECONDS = 2.0

#: §5.3's "auto-disable after 3 fails".
FAILURE_LIMIT = 3

#: A courtesy pause between requests to the same shop. Not a rate limiter — a manners
#: setting, and the difference between a tool a retailer tolerates and one it blocks.
POLITE_PAUSE_SECONDS = 1.0


@dataclass
class ScrapeOutcome:
    retailer: str
    wanted_title: str
    ok: bool
    price: Decimal | None = None
    #: The currency the price was *read in*, never converted (`DECISIONS.md` #79). Carried
    #: so a report can render a price as money rather than as a bare number.
    currency: str | None = None
    url: str | None = None
    #: Why a result was rejected. The important field — a scraper that has started
    #: matching the wrong node reports here rather than silently writing a number.
    reasons: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ScrapeRunResult:
    outcomes: list[ScrapeOutcome] = field(default_factory=list)
    written: int = 0
    disabled: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.ok)

    @property
    def failed(self) -> int:
        return sum(1 for outcome in self.outcomes if not outcome.ok)


def apply_search_template(template: str, title: str, preferred_format: str | None = None) -> str:
    """Fill a search template's placeholders. **The only place that knows what they mean.**

    Both the scheduled run and §5.4's test tool go through here. They used not to: the test
    tool built its URL in the browser and replaced ``{query}`` alone, so the day a
    ``{format}`` placeholder was added it sent Zavvi the literal string ``{format}`` — which
    matched *The Sheriff of Fractured Jaw (Dual **Format** Edition)* and reported it as the
    price of *Jaws*. A tool whose job is to prove a scraper works has to build its request
    the same way the scraper does (`DECISIONS.md` #99).
    """
    filled = template.replace("{query}", quote(title))
    if "{format}" in filled:
        term = FORMAT_SEARCH_TERMS.get(preferred_format or "", DEFAULT_FORMAT_SEARCH_TERM)
        filled = filled.replace("{format}", quote(term))
    return filled


def search_url_for(
    retailer: Retailer, title: str, preferred_format: str | None = None
) -> str | None:
    """Where to look for a film at this shop.

    ``{query}`` in §3.16's ``search_url_template``, percent-encoded. A retailer without a
    template cannot be searched — which is a configuration gap, reported as one, not an
    error.

    A template may also carry **``{format}``**, replaced with how this shop writes the
    wanted item's preferred format. THG's search redirects a bare film title to a franchise
    landing page — twelve T-shirts, towels and statues, no discs — and returns a disc grid
    only when the query names a format, so for those shops the format is what finds the
    film at all. `DEFAULT_FORMAT_SEARCH_TERM` covers a want with no format set.
    """
    template = retailer.search_url_template
    if not template or "{query}" not in template:
        return None
    return apply_search_template(template, title, preferred_format)


async def scrape_one(
    retailer: Retailer,
    title: str,
    *,
    preferred_format: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[ScrapeCandidate | None, ScrapeOutcome]:
    """Fetch and extract one film's price at one shop. **Makes a live request.**

    Retries once on a transport failure. Does **not** retry a shape failure: a page that
    parsed into something implausible will parse the same way again, and asking a shop
    twice for the same wrong answer is just rudeness.
    """
    outcome = ScrapeOutcome(retailer=retailer.name, wanted_title=title, ok=False)

    if not retailer.scraper_config:
        outcome.error = "no selectors configured"
        return None, outcome

    url = search_url_for(retailer, title, preferred_format)
    if url is None:
        outcome.error = "no search URL template configured"
        return None, outcome

    last_error: str | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            page = await fetch_page(url, client=client)
            break
        except UnsafeUrlError as exc:
            # Never retried: the URL is not going to become safe.
            outcome.error = f"refused: {exc}"
            return None, outcome
        except FetchError as exc:
            last_error = str(exc)
            if attempt + 1 < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_PAUSE_SECONDS)
    else:
        outcome.error = last_error or "could not be fetched"
        return None, outcome

    candidate = extract(
        page.html,
        retailer.scraper_config,
        expected_title=title,
        preferred_format=preferred_format,
    )
    # Retailer pages overwhelmingly use relative product links. Persisting one as-is made
    # `_write_check` silently return without a row, even though `written` was incremented.
    # Resolve it against the final page after redirects so the stored link is usable and
    # the same-site shape guard can judge its real host.
    if candidate.url:
        candidate = replace(candidate, url=urljoin(page.final_url, candidate.url))
    verdict = check_shape(
        candidate,
        expected_title=title,
        expected_currency=retailer.currency,
        retailer_host=urlparse(retailer.base_url).hostname,
    )
    outcome.price = candidate.price
    outcome.currency = candidate.currency or retailer.currency
    outcome.url = candidate.url or page.final_url
    outcome.reasons = verdict.reasons
    outcome.ok = verdict.ok
    return (candidate if verdict.ok else None), outcome


async def _record_failure(db: AsyncSession, retailer: Retailer, message: str) -> bool:
    """Count a failure and disable after three in a row. Returns True if it disabled."""
    retailer.consecutive_failures += 1
    retailer.last_scrape_status = "error"
    retailer.last_scrape_error = message[:2000]
    retailer.last_scraped_at = utcnow()
    if retailer.consecutive_failures >= FAILURE_LIMIT and retailer.enabled:
        retailer.enabled = False
        logger.warning(
            "retailer_auto_disabled",
            retailer=retailer.name,
            failures=retailer.consecutive_failures,
        )
        return True
    return False


def _record_success(retailer: Retailer) -> None:
    # Reset, not decrement: three failures *in a row* is the signal. A shop that fails on
    # Monday and works on Tuesday has not accumulated anything.
    retailer.consecutive_failures = 0
    retailer.last_scrape_status = "success"
    retailer.last_scrape_error = None
    retailer.last_scraped_at = utcnow()


async def run_scrape(
    db: AsyncSession,
    *,
    client: httpx.AsyncClient | None = None,
    dry_run: bool = False,
    polite_pause: float = POLITE_PAUSE_SECONDS,
) -> ScrapeRunResult:
    """Every enabled retailer × every active wanted item. **Makes live requests.**

    Not called by any scheduled job — §5.5 is Batch 20 and a cron is a hosting change this
    project keeps explicit (`DECISIONS.md` #60). This is what a schedule, or an owner
    running the acceptance for §5.3, would call.
    """
    result = ScrapeRunResult()

    retailers = list(
        (
            await db.execute(
                select(Retailer).where(Retailer.deleted_at.is_(None), Retailer.enabled.is_(True))
            )
        )
        .scalars()
        .all()
    )
    wanted_rows = (
        await db.execute(
            select(WantedItem, Movie)
            .join(Movie, Movie.id == WantedItem.movie_id)
            .where(WantedItem.deleted_at.is_(None), WantedItem.is_active.is_(True))
        )
    ).all()

    for retailer in retailers:
        any_success = False
        for wanted, movie in wanted_rows:
            candidate, outcome = await scrape_one(
                retailer,
                movie.title,
                preferred_format=wanted.preferred_format,
                client=client,
            )
            result.outcomes.append(outcome)

            if candidate is not None and candidate.price is not None:
                any_success = True
                if not dry_run and await _write_check(db, retailer, wanted, candidate, outcome):
                    result.written += 1

            if polite_pause:
                await asyncio.sleep(polite_pause)

        if not dry_run:
            if any_success:
                _record_success(retailer)
            else:
                message = "; ".join(
                    o.error or "; ".join(o.reasons)
                    for o in result.outcomes
                    if o.retailer == retailer.name
                )[:2000]
                if await _record_failure(db, retailer, message or "no usable result"):
                    result.disabled.append(retailer.name)

    if not dry_run:
        await db.commit()
    return result


async def _write_check(
    db: AsyncSession,
    retailer: Retailer,
    wanted: WantedItem,
    candidate: ScrapeCandidate,
    outcome: ScrapeOutcome,
) -> bool:
    """Persist one price check and report whether a row was inserted or updated.

    A second run on the same day updates the row rather than failing: `uq_price_checks_
    listing_day` exists so an afternoon re-run does not double-count, and hitting it is a
    normal outcome rather than an error.
    """
    if candidate.price is None:  # pragma: no cover - callers check
        return False
    url = candidate.url or ""
    if not url.lower().startswith(("http://", "https://")):
        return False

    existing = (
        await db.execute(
            select(PriceCheck).where(
                PriceCheck.url == url,
                PriceCheck.checked_at
                >= utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.price = candidate.price
        existing.title_snapshot = candidate.title
        return True

    try:
        # Keep a same-day race inside a savepoint. Rolling back the whole session here
        # would also discard valid rows written earlier in this multi-retailer run.
        async with db.begin_nested():
            db.add(
                PriceCheck(
                    id=uuid.uuid4(),
                    wanted_id=wanted.id,
                    retailer_id=retailer.id,
                    # §3.6's own column: the check stays readable after deletion.
                    retailer_name_snapshot=retailer.name,
                    price=candidate.price,
                    currency=candidate.currency or retailer.currency,
                    title_snapshot=candidate.title,
                    url=url,
                    checked_at=utcnow(),
                )
            )
            await db.flush()
    except IntegrityError:
        # Lost a race with a concurrent run against the same listing. The row that won
        # says the same thing, so there is nothing to correct or count as a new write.
        outcome.reasons.append("already recorded today")
        return False
    return True
