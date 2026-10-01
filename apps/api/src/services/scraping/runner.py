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
from src.services.scraping.alerts import AlertCandidate
from src.services.scraping.extract import (
    DEFAULT_FORMAT_SEARCH_TERM,
    DISC_FORMATS,
    FORMAT_SEARCH_TERMS,
    ScrapeCandidate,
    check_shape,
    edition_matches,
    edition_words,
    extract,
    primary_format,
)
from src.services.scraping.fetcher import (
    FetchError,
    RefusedError,
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
    #: False only when a wanted **edition** was not on the shelf and a different one was
    #: priced instead; None when the want named no edition. Same reasoning as
    #: `substituted_format`: a `max_price` alert compares against whatever was priced.
    edition_matched: bool | None = None
    #: Set only when the wanted format was not on the shelf and a different one was priced
    #: instead. A fallback is allowed, but it is never silent: `max_price` alerts compare
    #: against whatever was priced, so the reader has to be able to see it was a substitute.
    substituted_format: str | None = None
    #: True when nothing was attempted — a want these shops cannot serve at all. Neither a
    #: success nor a failure, and specifically **not** counted towards auto-disable: three
    #: digital wants would otherwise switch off every retailer in the app.
    skipped: bool = False
    #: True when the shop **was** asked, answered with real listings, and none of them is
    #: this film. Also not a failure, for the same reason `skipped` is not: a boutique
    #: label that does not carry a blockbuster has not broken. Distinct from `skipped`
    #: because the question was put and answered — it just came back "no".
    not_stocked: bool = False
    #: True when the shop answered with **no listings at all** — an empty results page.
    #:
    #: **Deliberately neither a failure nor a claim** (`DECISIONS.md` #125). Zero cards is
    #: what "we do not stock that" looks like *and* what a broken selector looks like, and
    #: nothing in the response distinguishes them. Counting it as a failure auto-disabled
    #: shops that simply carry different films; counting it as `not_stocked` would let a
    #: parser that stopped matching read as a healthy "nothing found" forever, which is
    #: exactly how #122 hid for a day. So it is recorded, reported, and excluded from the
    #: auto-disable arithmetic — and a retailer answering this way for *every* want in a
    #: run is flagged, because that is what a broken selector looks like.
    no_results: bool = False
    #: True when the shop **refused** the request, answering ``429`` (Batch 20b). Not a
    #: failure for auto-disable either: a refusal says nothing about whether the scraper
    #: works, and on 30 Sep and 1 Oct it was about to switch off shops that were not
    #: broken. Still recorded with what the shop sent back, so a run says who refused.
    refused: bool = False
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
    #: The rows this run actually wrote, paired with the want they were found for and what
    #: the scrape had to substitute. Batch 20 turns these into §5.6's price-drop alerts —
    #: collected here rather than re-queried afterwards, because "checks written today" is
    #: not the same set as "checks this run wrote" once a second run exists.
    written_checks: list[AlertCandidate] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.ok)

    @property
    def failed(self) -> int:
        return sum(
            1
            for outcome in self.outcomes
            if not outcome.ok
            and not outcome.skipped
            and not outcome.not_stocked
            and not outcome.no_results
        )

    @property
    def not_stocked(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.not_stocked)

    @property
    def no_results(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.no_results)

    @property
    def skipped(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.skipped)

    @property
    def refused(self) -> int:
        """Counted within ``failed`` too: a refused request still brought no price back."""
        return sum(1 for outcome in self.outcomes if outcome.refused)


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
    preferred_edition: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[ScrapeCandidate | None, ScrapeOutcome]:
    """Fetch and extract one film's price at one shop. **Makes a live request.**

    Retries once on a transport failure. Does **not** retry a shape failure: a page that
    parsed into something implausible will parse the same way again, and asking a shop
    twice for the same wrong answer is just rudeness.
    """
    outcome = ScrapeOutcome(retailer=retailer.name, wanted_title=title, ok=False)

    if preferred_format is not None and preferred_format not in DISC_FORMATS:
        # A digital want. These are disc shops, so there is nothing to look for — and
        # nothing the shop did wrong, which is why it is skipped rather than failed.
        outcome.skipped = True
        outcome.error = f"{retailer.name} sells discs; this want is for a digital copy"
        return None, outcome

    if not retailer.scraper_config:
        outcome.error = "no selectors configured"
        return None, outcome

    url = search_url_for(retailer, title, preferred_format)
    if url is None:
        outcome.error = "no search URL template configured"
        return None, outcome

    last_error: FetchError | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            page = await fetch_page(url, client=client)
            break
        except UnsafeUrlError as exc:
            # Never retried: the URL is not going to become safe.
            outcome.error = f"refused: {exc}"
            return None, outcome
        except FetchError as exc:
            last_error = exc
            if isinstance(exc, RefusedError):
                # One line per refused request, with its time: the evidence 20b's second
                # half waits for (after how many requests, and what the shop asked for).
                logger.warning(
                    "scrape_refused",
                    retailer=retailer.name,
                    wanted=title,
                    attempt=attempt + 1,
                    status=exc.status,
                    retry_after=exc.retry_after,
                    evidence=exc.evidence,
                )
            if attempt + 1 < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_PAUSE_SECONDS)
    else:
        outcome.error = str(last_error) if last_error else "could not be fetched"
        # Judged by the last answer: a shop that refused once and then timed out has a
        # problem a person should see, and that one still counts.
        outcome.refused = isinstance(last_error, RefusedError)
        return None, outcome

    candidate = extract(
        page.html,
        retailer.scraper_config,
        expected_title=title,
        preferred_format=preferred_format,
        preferred_edition=preferred_edition,
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
        preferred_edition=preferred_edition,
    )
    outcome.price = candidate.price
    outcome.currency = candidate.currency or retailer.currency
    outcome.url = candidate.url or page.final_url
    outcome.reasons = verdict.reasons
    outcome.ok = verdict.ok
    # The page parsed into real listings and none of them names this film. That is the
    # shop answering, not the scraper breaking, so `run_scrape` must not count it. Read
    # from the card counts rather than from the rejection message, because the first card
    # is often priceless and `check_shape` then stops before it reaches its title rules.
    if not verdict.ok and candidate.titled_cards > 0 and candidate.matching_cards == 0:
        outcome.not_stocked = True
        outcome.error = f"{retailer.name} does not stock {title}"
    elif not verdict.ok and candidate.titled_cards == 0:
        # The page parsed into **no listings at all**. Measured on 2026-09-10: Arrow's
        # "Sorry We Couldn't Find Any Results" and 101 Films' "0 results found" both land
        # here, and both were being counted as scraper failures — 8 of one run's 11.
        # `not_stocked` cannot claim this, because a selector that has stopped matching
        # produces exactly the same nothing (`DECISIONS.md` #125).
        outcome.no_results = True
        outcome.error = f"{retailer.name} returned no listings for {title}"
    if verdict.ok and preferred_format in DISC_FORMATS:
        priced = primary_format(candidate.title, candidate.url)
        if priced != preferred_format:
            outcome.substituted_format = priced
    if verdict.ok and edition_words(preferred_edition):
        outcome.edition_matched = edition_matches(candidate.title, candidate.url, preferred_edition)
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


def _record_no_results(retailer: Retailer, count: int) -> None:
    """Every want came back empty. Say so; do not count it as a failure.

    `consecutive_failures` is deliberately **left alone** rather than reset: a shop that
    answered nothing has neither failed nor succeeded, and zeroing the counter here would
    let a genuinely broken shop launder its failures by returning one empty page.
    """
    retailer.last_scrape_status = "no_results"
    retailer.last_scrape_error = (
        f"{count} want(s) returned an empty results page. The shop may not carry them, or "
        "the selectors may have stopped matching — nothing in the response tells them apart."
    )[:2000]
    retailer.last_scraped_at = utcnow()
    logger.info("retailer_no_results", retailer=retailer.name, wants=count)


def _record_refused(retailer: Retailer, refused: list[ScrapeOutcome]) -> None:
    """The shop refused every request it did not answer with a "no". Say so; do not count it.

    **Batch 20b.** `blocked` is the status Batch 16 declared for this and nothing used.
    `consecutive_failures` is **left alone**, as `_record_no_results` leaves it: a refusal
    is neither a failure nor a success, and the scraper behind it is untested either way.
    """
    retailer.last_scrape_status = "blocked"
    retailer.last_scrape_error = (
        f"{len(refused)} request(s) refused. The last: {refused[-1].error}"
    )[:2000]
    retailer.last_scraped_at = utcnow()
    logger.warning("retailer_refused", retailer=retailer.name, wants=len(refused))


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
                preferred_edition=wanted.preferred_edition,
                client=client,
            )
            result.outcomes.append(outcome)

            if candidate is not None and candidate.price is not None:
                any_success = True
                if not dry_run:
                    row = await _write_check(db, retailer, wanted, candidate, outcome)
                    if row is not None:
                        result.written += 1
                        result.written_checks.append(
                            AlertCandidate(
                                check=row,
                                wanted=wanted,
                                substituted_format=outcome.substituted_format,
                                edition_matched=outcome.edition_matched,
                            )
                        )

            if polite_pause:
                await asyncio.sleep(polite_pause)

        if not dry_run:
            mine = [o for o in result.outcomes if o.retailer == retailer.name]
            attempted = [
                o
                for o in mine
                if not o.skipped and not o.not_stocked and not o.no_results and not o.refused
            ]
            refused = [o for o in mine if o.refused]
            empty = [o for o in mine if o.no_results]
            if any_success:
                _record_success(retailer)
            elif attempted:
                message = "; ".join(o.error or "; ".join(o.reasons) for o in attempted)[:2000]
                if await _record_failure(db, retailer, message or "no usable result"):
                    result.disabled.append(retailer.name)
            elif refused:
                # **Never a failure** (Batch 20b). Before it, three refused nights would
                # have switched off shops whose scrapers were fine.
                _record_refused(retailer, refused)
            elif empty:
                # **Flagged, never disabled** (`DECISIONS.md` #125). Every want this shop
                # was asked came back with an empty page and nothing came back priced.
                # That is what a boutique label stocking none of these films looks like —
                # and equally what a selector that has stopped matching looks like. Saying
                # so is honest; switching the shop off over it is the bug this replaced,
                # and calling it "not stocked" is the one it must not become.
                _record_no_results(retailer, len(empty))
            # Nothing attempted: every want was one this shop could not be asked, or was
            # asked and honestly has not got. A shop that was never asked has not failed,
            # and neither has one that answered "no" — three digital wants, or three films
            # a boutique label does not carry, would otherwise switch off the whole app.

    if not dry_run:
        await db.commit()
    return result


async def _write_check(
    db: AsyncSession,
    retailer: Retailer,
    wanted: WantedItem,
    candidate: ScrapeCandidate,
    outcome: ScrapeOutcome,
) -> PriceCheck | None:
    """Persist one price check and return the row, or ``None`` if nothing was written.

    Returns the row rather than a bool so Batch 20 can decide whether it is a price drop
    without re-reading the table — see :class:`ScrapeRunResult.written_checks`.

    A second run on the same day updates the row rather than failing: `uq_price_checks_
    listing_day` exists so an afternoon re-run does not double-count, and hitting it is a
    normal outcome rather than an error.
    """
    if candidate.price is None:  # pragma: no cover - callers check
        return None
    url = candidate.url or ""
    if not url.lower().startswith(("http://", "https://")):
        return None

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
        return existing

    try:
        # Keep a same-day race inside a savepoint. Rolling back the whole session here
        # would also discard valid rows written earlier in this multi-retailer run.
        async with db.begin_nested():
            row = PriceCheck(
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
            db.add(row)
            await db.flush()
    except IntegrityError:
        # Lost a race with a concurrent run against the same listing. The row that won
        # says the same thing, so there is nothing to correct or count as a new write.
        outcome.reasons.append("already recorded today")
        return None
    return row
