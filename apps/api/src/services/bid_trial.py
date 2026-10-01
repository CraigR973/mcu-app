"""A trial of pricing from live bids — Batch V6, snag 2's first step (#228: "trial first").

**What it does.** Craig taps "Try bid prices" on Home. The trial takes up to 100 priced films
and formats, a third each from 4K, Blu-ray and DVD as far as each has them, searches eBay
once for each with Buy It Now and auctions together, and reports by format what bids would
say against asking prices. **It saves no prices**: ``disc_valuations`` is never written.
Craig's pick of a blend or bids only follows the report (V7).

**Why it is a valuation run.** Its calls come out of the same 750-a-day share (#209), and it
must not overlap a run spending that share. So it claims a ``valuation_runs`` row with
trigger ``trial``, and the share, the one-at-a-time claim and the 30-minute abandonment are
the runs' own rather than a second ledger that could disagree with them. Its report is kept
on that row (:class:`~src.schemas.bid_trial.BidTrialReport`) for a later session to read.

**The rules**, from the snag (`docs/owner-snags-2026-09-30.md` §2):

- An auction counts only with at least one bid, and passes the matcher a Buy It Now listing
  passes: the right film and format, a UK seller, a standard edition.
- A film has a bid price when three or more auctions count (``MIN_SAMPLE``, #129): their
  median, in any condition. Bids are thin, and splitting them by condition as the asking
  price is split would leave almost none.
- Its asking price comes from the same search by the valuation's own rule
  (:func:`~src.services.valuation.valuation_from`), so both halves are from the same minute.
  The stored price is reported beside it.
- **Blend**: a film's bid price when it has one, its asking price otherwise. **Bids only**: a
  bid price or nothing. Every total says how many discs stand behind it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from statistics import median as plain_median
from typing import Any, Literal, Protocol

import structlog
from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.database import AsyncSessionLocal
from src.ebay.bids import (
    AUCTION,
    BUY_IT_NOW_AND_AUCTIONS,
    auction_from_summary,
    buying_options,
    offers_buy_it_now,
)
from src.ebay.client import EbayClient, EbayError, EbayNotConfigured
from src.ebay.estimate import UK, search_query
from src.ebay.matching import listing_from_summary, match
from src.ebay.pricing import median, summarise
from src.matching.engine import searchable_title as search_title
from src.models.movie import Movie
from src.models.valuation import VALUED_FORMATS, DiscValuation, ValuationRun
from src.schemas.bid_trial import (
    BidTrialReport,
    TrialAsking,
    TrialBids,
    TrialBlendTotal,
    TrialFilm,
    TrialResults,
    TrialStoredPrice,
    TrialSummary,
    TrialTotal,
)
from src.services.valuation import (
    CURRENCY,
    MAX_FAILURES_IN_A_ROW,
    MIN_SAMPLE,
    abandon_stale_runs,
    budget_left,
    owned_valued_discs,
    running_run,
    valuation_from,
)

logger = structlog.get_logger()

#: Films and formats a trial searches, at most: about 100 of the day's 750 calls.
SAMPLE_SIZE = 100
#: An auction ending within this is near its final price; the report counts them.
ENDING_SOON = timedelta(hours=24)

TrialStartReason = Literal["started", "running", "budget_spent", "nothing_to_sample"]

_PENNY = Decimal("0.01")


class BidSearcher(Protocol):
    """What the trial needs from a client: a search that takes a ``filter``, and its count.

    :class:`~src.ebay.client.EbayClient` is one.
    """

    search_calls: int

    @property
    def marketplace_id(self) -> str: ...

    @property
    def attempts_per_search(self) -> int: ...

    async def search(
        self,
        query: str,
        *,
        limit: int = ...,
        category_ids: str | None = None,
        filter: str | None = None,  # noqa: A002 - Browse's own parameter name
    ) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# The sample
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SampledFilm:
    movie_id: uuid.UUID
    format_code: str
    title: str
    identified: bool
    copies: int
    stored_price: Decimal
    stored_sample: int

    @property
    def search_title(self) -> str:
        return search_title(self.title, identified=self.identified)


def quotas(available: Mapping[str, int], size: int) -> dict[str, int]:
    """A third of the sample each for 4K, Blu-ray and DVD; what one cannot fill, the others take.

    Even shares rather than the collection's own mix, because the report is by format and a
    format with five films in it says nothing. One place at a time to the format with the
    fewest so far, the first on a tie: 34, 33 and 33 for a sample of 100.
    """
    shares = dict.fromkeys(VALUED_FORMATS, 0)
    for _ in range(size):
        open_formats = [code for code in VALUED_FORMATS if shares[code] < available.get(code, 0)]
        if not open_formats:
            break
        shares[min(open_formats, key=lambda code: shares[code])] += 1
    return shares


def _priced_films() -> Select[Any]:
    """Each owned film and format with a stored price, its copies and that price."""
    discs = owned_valued_discs()
    return (
        select(
            DiscValuation.movie_id,
            DiscValuation.format_code,
            Movie.title,
            Movie.tmdb_id,
            DiscValuation.price,
            DiscValuation.sample_size,
            func.count(discs.c.id).label("copies"),
        )
        .join(
            discs,
            and_(
                discs.c.movie_id == DiscValuation.movie_id,
                discs.c.format_code == DiscValuation.format_code,
            ),
        )
        .join(Movie, Movie.id == DiscValuation.movie_id)
        .where(DiscValuation.status == "priced")
        .group_by(DiscValuation.id, Movie.id)
    )


async def available_films(db: AsyncSession) -> dict[str, int]:
    """Priced, owned films and formats, counted by format."""
    films = _priced_films().subquery()
    rows = await db.execute(select(films.c.format_code, func.count()).group_by(films.c.format_code))
    return {code: int(count) for code, count in rows}


async def sample_films(db: AsyncSession, *, size: int = SAMPLE_SIZE) -> list[SampledFilm]:
    """Up to ``size`` priced films and formats, at random within each format's share."""
    shares = quotas(await available_films(db), size)
    sample: list[SampledFilm] = []
    for code in VALUED_FORMATS:
        if shares[code] == 0:
            continue
        rows = await db.execute(
            _priced_films()
            .where(DiscValuation.format_code == code)
            .order_by(func.random())
            .limit(shares[code])
        )
        sample.extend(
            SampledFilm(
                movie_id=movie_id,
                format_code=format_code,
                title=title,
                identified=tmdb_id is not None,
                copies=int(copies),
                stored_price=price,
                stored_sample=sample_size,
            )
            for movie_id, format_code, title, tmdb_id, price, sample_size, copies in rows
        )
    return sample


# ---------------------------------------------------------------------------
# One search, judged
# ---------------------------------------------------------------------------


def _money(amount: Decimal) -> str:
    return str(amount.quantize(_PENNY, rounding=ROUND_HALF_UP))


def _stored(film: SampledFilm) -> TrialStoredPrice:
    return TrialStoredPrice(price=_money(film.stored_price), sampleSize=film.stored_sample)


def judge_search(
    payload: Mapping[str, Any], *, film: SampledFilm, marketplace_id: str, now: datetime
) -> TrialFilm:
    """What one Buy It Now and auctions search says about one film and format."""
    summaries = [entry for entry in payload.get("itemSummaries") or [] if isinstance(entry, dict)]
    total = payload.get("total")
    buy_it_now = [entry for entry in summaries if offers_buy_it_now(entry)]

    # The asking price, exactly as a valuation run would take it from these listings.
    judged = []
    unusable = 0
    for entry in buy_it_now:
        listing = listing_from_summary(entry)
        if listing is None:
            unusable += 1
            continue
        verdict = match(
            listing, film_title=film.search_title, format_code=film.format_code, country=UK
        )
        judged.append((listing, verdict))
    estimate = summarise(
        judged,
        film_title=film.search_title,
        format_code=film.format_code,
        marketplace_id=marketplace_id,
        unusable=unusable,
    )
    asking = valuation_from(estimate, film.format_code)

    # The auctions: counted only with a bid, and only past the same matcher.
    counted: list[Decimal] = []
    without_bids = rejected = ending_soon = auctions_only = 0
    for entry in summaries:
        options = buying_options(entry)
        if AUCTION not in options:
            continue
        if not offers_buy_it_now(entry):
            auctions_only += 1
        auction = auction_from_summary(entry)
        if auction is None:
            rejected += 1
            continue
        verdict = match(
            auction.listing,
            film_title=film.search_title,
            format_code=film.format_code,
            country=UK,
        )
        if not verdict.ok or verdict.edition != "standard" or auction.listing.currency != CURRENCY:
            rejected += 1
            continue
        if auction.bid_count < 1:
            without_bids += 1
            continue
        counted.append(auction.listing.price)
        if auction.ends_utc is not None and auction.ends_utc <= now + ENDING_SOON:
            ending_soon += 1

    return TrialFilm(
        movieId=film.movie_id,
        title=film.title,
        formatCode=film.format_code,
        copies=film.copies,
        stored=_stored(film),
        results=TrialResults(
            total=total if isinstance(total, int) and not isinstance(total, bool) else None,
            returned=len(summaries),
            buyItNow=len(buy_it_now),
            auctionOnly=auctions_only,
        ),
        asking=TrialAsking(
            price=_money(asking.price) if asking.price is not None else None,
            sampleSize=asking.sample_size,
        ),
        bids=TrialBids(
            counted=len(counted),
            withoutBids=without_bids,
            rejected=rejected,
            price=_money(median(counted)) if len(counted) >= MIN_SAMPLE else None,
            endingSoon=ending_soon,
        ),
    )


def failed_film(film: SampledFilm, error: str) -> TrialFilm:
    """A film eBay did not answer for: in the report, left out of every figure."""
    return TrialFilm(
        movieId=film.movie_id,
        title=film.title,
        formatCode=film.format_code,
        copies=film.copies,
        stored=_stored(film),
        results=None,
        asking=None,
        bids=None,
        error=error,
    )


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def _total(priced: Sequence[tuple[Decimal, int]]) -> TrialTotal:
    return TrialTotal(
        total=_money(sum((price * copies for price, copies in priced), Decimal(0))),
        discs=sum(copies for _, copies in priced),
    )


def summarise_trial(films: Sequence[TrialFilm], format_code: str | None) -> TrialSummary:
    """The report's figures for one format, or for every format when ``format_code`` is None.

    Only films eBay answered for count, so each basis is totalled over the same films.
    """
    searched = [
        (film, film.results, film.asking, film.bids)
        for film in films
        if (format_code is None or film.formatCode == format_code)
        and film.results is not None
        and film.asking is not None
        and film.bids is not None
    ]
    with_bids = [entry for entry in searched if entry[3].price is not None]
    ratios = [
        Decimal(bids.price) / Decimal(asking.price)
        for _, _, asking, bids in with_bids
        if bids.price is not None and asking.price is not None and Decimal(asking.price) > 0
    ]
    cut = [
        entry
        for entry in searched
        if entry[1].total is not None and entry[1].total > entry[1].returned
    ]

    stored = [(Decimal(film.stored.price), film.copies) for film, _, _, _ in searched]
    asking_priced = [
        (Decimal(asking.price), film.copies)
        for film, _, asking, _ in searched
        if asking.price is not None
    ]
    bids_priced = [
        (Decimal(bids.price), film.copies)
        for film, _, _, bids in searched
        if bids.price is not None
    ]
    blend: list[tuple[Decimal, int]] = []
    from_bids = from_asking = 0
    for film, _, asking, bids in searched:
        if bids.price is not None:
            blend.append((Decimal(bids.price), film.copies))
            from_bids += film.copies
        elif asking.price is not None:
            blend.append((Decimal(asking.price), film.copies))
            from_asking += film.copies
    blend_total = _total(blend)

    return TrialSummary(
        formatCode=format_code,
        films=len(searched),
        withBids=len(with_bids),
        withBidsEndingSoon=sum(1 for *_, bids in searched if bids.endingSoon >= MIN_SAMPLE),
        auctionsCounted=sum(bids.counted for *_, bids in with_bids),
        endingSoon=sum(bids.endingSoon for *_, bids in with_bids),
        compared=len(ratios),
        bidToAskingPercent=(
            int((Decimal(plain_median(ratios)) * 100).quantize(Decimal(1), ROUND_HALF_UP))
            if ratios
            else None
        ),
        cut=len(cut),
        auctionOnlyPlaces=sum(results.auctionOnly for _, results, _, _ in cut),
        askingSample=sum(asking.sampleSize for _, _, asking, _ in searched),
        storedSample=sum(film.stored.sampleSize for film, _, _, _ in searched),
        askingLost=sum(1 for _, _, asking, _ in searched if asking.price is None),
        stored=_total(stored),
        asking=_total(asking_priced),
        bids=_total(bids_priced),
        blend=TrialBlendTotal(
            total=blend_total.total,
            discs=blend_total.discs,
            fromBids=from_bids,
            fromAsking=from_asking,
        ),
    )


def build_report(sampled: int, films: Sequence[TrialFilm]) -> BidTrialReport:
    return BidTrialReport(
        sampled=sampled,
        films=list(films),
        formats=[summarise_trial(films, code) for code in VALUED_FORMATS],
        overall=summarise_trial(films, None),
    )


# ---------------------------------------------------------------------------
# A trial
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrialStart:
    reason: TrialStartReason
    run: ValuationRun | None
    sampled: int
    budget_left: int


async def latest_trial(db: AsyncSession) -> ValuationRun | None:
    result = await db.execute(
        select(ValuationRun)
        .where(ValuationRun.trigger == "trial")
        .order_by(ValuationRun.started_utc.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def start_trial(
    db: AsyncSession, *, started_by: uuid.UUID | None, now: datetime | None = None
) -> TrialStart:
    """Claim the right to run, as a valuation run claims it: one at a time, within the share."""
    now = now or utcnow()
    await abandon_stale_runs(db, now=now)
    sampled = sum(quotas(await available_films(db), SAMPLE_SIZE).values())
    left = await budget_left(db, now=now)
    if await running_run(db) is not None:
        return TrialStart("running", None, sampled, left)
    if sampled == 0:
        return TrialStart("nothing_to_sample", None, sampled, left)
    if left == 0:
        return TrialStart("budget_spent", None, sampled, left)

    run = ValuationRun(
        id=uuid.uuid4(),
        trigger="trial",
        status="running",
        started_by=started_by,
        started_utc=now,
        heartbeat_utc=now,
        budget=left,
        calls=0,
        priced=0,
        not_priced=0,
        failed=0,
        report=build_report(sampled, []).model_dump(mode="json"),
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return TrialStart("running", None, sampled, left)
    return TrialStart("started", run, sampled, left)


async def work_trial(
    db: AsyncSession,
    client: BidSearcher,
    run_id: uuid.UUID,
    *,
    clock: Callable[[], datetime] = utcnow,
) -> ValuationRun:
    """Search each sampled film once, judge it, and write the report after every film."""
    run = await db.get(ValuationRun, run_id)
    if run is None or run.status != "running" or run.trigger != "trial":
        raise ValueError(f"bid trial {run_id} is not running")

    try:
        films = await sample_films(db)
        results: list[TrialFilm] = []
        outcome: str | None = None
        failures_in_a_row = 0
        for film in films:
            if client.search_calls + client.attempts_per_search > run.budget:
                outcome = "budget_spent"
                break
            try:
                payload = await client.search(
                    search_query(film.search_title, film.format_code),
                    filter=BUY_IT_NOW_AND_AUCTIONS,
                )
            except EbayNotConfigured:
                run.last_error = "eBay is not configured in this deployment."
                outcome = "stopped"
                break
            except EbayError as exc:
                run.failed += 1
                failures_in_a_row += 1
                run.last_error = f"{film.search_title} ({film.format_code}): {exc}"
                results.append(failed_film(film, str(exc)))
                logger.warning(
                    "bid_trial_search_failed", film=film.search_title, status=exc.status_code
                )
                if exc.status_code == 429 or failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                    outcome = "stopped"
                    break
            else:
                failures_in_a_row = 0
                result = judge_search(
                    payload, film=film, marketplace_id=client.marketplace_id, now=clock()
                )
                results.append(result)
                if result.bids is not None and result.bids.price is not None:
                    run.priced += 1
                else:
                    run.not_priced += 1
            run.calls = client.search_calls
            run.heartbeat_utc = clock()
            run.report = build_report(len(films), results).model_dump(mode="json")
            await db.commit()

        finished = clock()
        run.calls = client.search_calls
        run.remaining = len(films) - len(results)
        run.status = outcome or "finished"
        run.finished_utc = finished
        run.heartbeat_utc = finished
        run.report = build_report(len(films), results).model_dump(mode="json")
        await db.commit()
    except Exception as exc:
        await db.rollback()
        stopped = await db.get(ValuationRun, run_id)
        if stopped is not None and stopped.status == "running":
            stopped.status = "stopped"
            stopped.finished_utc = clock()
            stopped.calls = client.search_calls
            stopped.last_error = f"{type(exc).__name__}: {exc}"
            await db.commit()
        raise

    logger.info(
        "bid_trial_finished",
        status=run.status,
        calls=run.calls,
        with_bids=run.priced,
        without=run.not_priced,
        failed=run.failed,
    )
    return run


async def continue_trial_in_background(run_id: uuid.UUID) -> None:
    """The Home button's trial, after the response has gone. Its own session and client."""
    try:
        async with AsyncSessionLocal() as db, EbayClient() as client:
            await work_trial(db, client, run_id)
    except Exception:  # noqa: BLE001 - the trial records its own failure; nothing is waiting
        logger.warning("bid_trial_failed", run_id=str(run_id), exc_info=True)
