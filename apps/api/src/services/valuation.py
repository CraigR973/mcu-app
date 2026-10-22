"""Pricing the whole collection at current eBay asking prices — Batch T6, snag 7.

**What a run does.** It finds the films due a price, searches eBay once per film and
format, judges the listings with the film page's own estimator, and stores the answer. It
stops at a share of eBay's daily allowance, and the next run carries on from there.

**The numbers, and why:**

- :data:`DAILY_SHARE`: 750 calls, 15% of the 5,000 a day eBay allows (`DECISIONS.md` #126).
  The first full valuation, 1,454 films and formats, takes two days, as the reconciliation
  proposed, and leaves 85% of each day for the film page's checks, barcode lookups and T8.
  Counted per UTC day: a rolling 24 hours would leave a job that runs at the same time
  every night with nothing, because yesterday's run would still be inside the window.
- :data:`MIN_SAMPLE`: 3 listings. Below that a median is one seller's asking price, so the
  disc is "not priced" instead (#129: "Two listings have a median and it means nothing").
- :data:`REVALUE_AFTER`: 30 days, the monthly refresh. Films that could not be priced are
  retried on the same clock: a rare disc does not become common in a week.
- :data:`RUN_STALE_AFTER`: 30 minutes without a heartbeat means the process running it died.
- :data:`MAX_FAILURES_IN_A_ROW`: 5. An eBay outage should stop a run, not spend it on errors.

**Every total is "at current eBay asking prices"**, which usually run above what discs
actually sell for. Sold prices are closed to apps (#16, #126).

**Each disc is valued as a used copy** (Batch X6, #256 amending #209): the median of its
used listings when there are three or more, otherwise New's median times the used-to-New
factor for its format (``pricing.used_value``). The factor is **measured from the stored
values themselves**: the median ratio over the films with three or more of each, per format
(:func:`used_factors`). Two sources on 11–14 Oct disagreed about it by format (4K 0.60 or
0.71, Blu-ray 0.69 or 0.59, from 19–113 films each), so no constant is trusted for long:
:data:`FALLBACK_FACTOR` stands in only until :data:`MIN_FACTOR_PAIRS` films say otherwise,
and every run ends by re-scaling the New-based values to the factor its own prices give.
A value stored before X6 (no ``used_count``) is due at once and counts nowhere until then.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Literal, Protocol

import structlog
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Subquery

from src.clock import utcnow
from src.database import AsyncSessionLocal
from src.ebay.client import DEFAULT_MAX_RETRIES, EbayClient, EbayError, EbayNotConfigured
from src.ebay.estimate import EbaySearch, estimate_price, search_query
from src.ebay.pricing import (
    ASKING_PRICES,
    MIN_SAMPLE,
    NEW_CONDITION_ID,
    PriceEstimate,
    UsedValue,
    median,
    used_value,
)
from src.matching.engine import searchable_title as search_title
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.valuation import VALUED_FORMATS, DiscValuation, ValuationRun

logger = structlog.get_logger()

#: eBay's default Browse allowance per day (`DECISIONS.md` #126).
DAILY_ALLOWANCE = 5_000
#: The part of each UTC day's allowance valuation runs may spend: 15%.
DAILY_SHARE = 750
REVALUE_AFTER = timedelta(days=30)
RUN_STALE_AFTER = timedelta(minutes=30)
MAX_FAILURES_IN_A_ROW = 5
#: The fewest calls worth starting a run with: one search and its retries. A run stops when
#: its next search might overrun the budget, so it can leave up to two calls unspent, and
#: a run started on those would stop before its first search.
MIN_RUN_BUDGET = DEFAULT_MAX_RETRIES + 1
#: A total is only added up in one currency. Everything eBay GB returns is in pounds.
CURRENCY = "GBP"
#: The used-to-New factor before the stored values can measure one: the lower end of what
#: was measured on 11–14 Oct (0.59–0.71 by format and source), so a value does not overstate.
FALLBACK_FACTOR = Decimal("0.60")
#: Films with three or more used and three or more New listings a format needs before its
#: own factor replaces the fallback.
MIN_FACTOR_PAIRS = 20
#: A used copy is never valued above a new one, whatever a thin market says.
MAX_FACTOR = Decimal("1.00")

StartReason = Literal["started", "running", "budget_spent", "nothing_due"]


class Searcher(EbaySearch, Protocol):
    """An eBay client that also says how many calls it has made. :class:`EbayClient` is one."""

    search_calls: int

    @property
    def attempts_per_search(self) -> int: ...


# ---------------------------------------------------------------------------
# Which films are due a price
# ---------------------------------------------------------------------------


def valued_format(formats: Sequence[str]) -> str | None:
    """The format a disc is valued as: its best physical one, or None for a download.

    A 4K box with a Blu-ray inside sells as a 4K, so it is priced as one.
    """
    return next((code for code in VALUED_FORMATS if code in formats), None)


def _valued_format_sql() -> ColumnElement[str | None]:
    """:func:`valued_format`, in SQL."""
    return case(
        *((CollectionItem.formats.contains([code]), code) for code in VALUED_FORMATS),
        else_=None,
    )


@dataclass(frozen=True)
class DueFilm:
    movie_id: uuid.UUID
    format_code: str
    title: str
    identified: bool
    #: A TV title: "Complete Series" and "Season" listings are the thing itself (Batch X6).
    is_tv: bool = False

    @property
    def search_title(self) -> str:
        return search_title(self.title, identified=self.identified)


def _owned_discs() -> tuple[ColumnElement[str | None], list[ColumnElement[bool]]]:
    """The valued format of each owned disc, and the conditions that make it one."""
    return _valued_format_sql(), [owned_copy(), Movie.deleted_at.is_(None)]


def _due_condition(now: datetime) -> ColumnElement[bool]:
    """Never priced, priced over 30 days ago, priced before the film was last identified,
    or priced before Batch X6.

    The third is Batch T9's. A film priced under its spreadsheet title ("Captain Ameica") was
    searched for under that title; once identified, the search the film page would run is
    different, so the stored value no longer agrees with it (#209's reason for the shared
    estimator). ``last_tmdb_sync_utc`` is written only when a film is identified. The last is
    X6's: a value from before it is a new copy's price, and ``used_count`` is what every value
    since carries.
    """
    return or_(
        DiscValuation.id.is_(None),
        DiscValuation.checked_utc < now - REVALUE_AFTER,
        DiscValuation.checked_utc < Movie.last_tmdb_sync_utc,
        DiscValuation.used_count.is_(None),
    )


def current_value() -> ColumnElement[bool]:
    """A stored value made by Batch X6's rule, so one a reader may show or add up."""
    return DiscValuation.used_count.is_not(None)


def owned_valued_discs() -> Subquery:
    """Each owned physical disc and the format it is valued as — the discs the value counts.

    One row per disc, so two copies of a film count twice. Shared by the collection's total
    and Home's most valuable discs (Batch V5), so the two cannot disagree about which discs
    stand behind a price.
    """
    fmt, conditions = _owned_discs()
    return (
        select(CollectionItem.id, CollectionItem.movie_id, fmt.label("format_code"))
        .join(Movie, Movie.id == CollectionItem.movie_id)
        .where(*conditions, fmt.is_not(None))
        .subquery()
    )


def _film_formats() -> Subquery:
    """Each owned film and the format its discs are valued as, once."""
    fmt, conditions = _owned_discs()
    return (
        select(CollectionItem.movie_id.label("movie_id"), fmt.label("format_code"))
        .join(Movie, Movie.id == CollectionItem.movie_id)
        .where(*conditions, fmt.is_not(None))
        .distinct()
        .subquery()
    )


async def due_films(db: AsyncSession, *, now: datetime, limit: int) -> list[DueFilm]:
    """The films and formats due a price, never-priced first, then the oldest."""
    pairs = _film_formats()
    rows = await db.execute(
        select(pairs.c.movie_id, pairs.c.format_code, Movie.title, Movie.tmdb_id, Movie.is_tv)
        .join(Movie, Movie.id == pairs.c.movie_id)
        .outerjoin(
            DiscValuation,
            and_(
                DiscValuation.movie_id == pairs.c.movie_id,
                DiscValuation.format_code == pairs.c.format_code,
            ),
        )
        .where(_due_condition(now))
        .order_by(DiscValuation.checked_utc.asc().nulls_first(), Movie.title, pairs.c.format_code)
        .limit(limit)
    )
    return [
        DueFilm(
            movie_id=movie_id,
            format_code=code,
            title=title,
            identified=tmdb_id is not None,
            is_tv=bool(is_tv),
        )
        for movie_id, code, title, tmdb_id, is_tv in rows
    ]


async def count_due(db: AsyncSession, *, now: datetime) -> int:
    pairs = _film_formats()
    total = await db.scalar(
        select(func.count())
        .select_from(pairs)
        .join(Movie, Movie.id == pairs.c.movie_id)
        .outerjoin(
            DiscValuation,
            and_(
                DiscValuation.movie_id == pairs.c.movie_id,
                DiscValuation.format_code == pairs.c.format_code,
            ),
        )
        .where(_due_condition(now))
    )
    return int(total or 0)


# ---------------------------------------------------------------------------
# The budget
# ---------------------------------------------------------------------------


def day_start(now: datetime) -> datetime:
    return datetime.combine(now.date(), time.min)


async def budget_left(db: AsyncSession, *, now: datetime) -> int:
    """Calls a run may still make today, UTC, or 0 if too few to start one.

    Runs in progress count what they have spent so far, and a bid trial's calls (Batch V6)
    count like any run's.
    """
    spent = await db.scalar(
        select(func.coalesce(func.sum(ValuationRun.calls), 0)).where(
            ValuationRun.started_utc >= day_start(now)
        )
    )
    left = DAILY_SHARE - int(spent or 0)
    return left if left >= MIN_RUN_BUDGET else 0


# ---------------------------------------------------------------------------
# The used-to-New factor (Batch X6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsedFactor:
    """What a New median is multiplied by to value a used copy, and what it rests on."""

    factor: Decimal
    #: Films with three or more of each kind of listing behind it; 0 for the fallback.
    films: int

    @property
    def measured(self) -> bool:
        return self.films > 0


def factors_from(pairs: dict[str, list[Decimal]]) -> dict[str, UsedFactor]:
    """Each format's factor from its films' used-to-New ratios, or the fallback.

    The median ratio, because a few collector-priced New groups would pull a mean anywhere;
    capped at :data:`MAX_FACTOR`.
    """
    factors: dict[str, UsedFactor] = {}
    for code in VALUED_FORMATS:
        ratios = pairs.get(code, [])
        if len(ratios) < MIN_FACTOR_PAIRS:
            factors[code] = UsedFactor(FALLBACK_FACTOR, 0)
        else:
            factors[code] = UsedFactor(min(median(ratios), MAX_FACTOR), len(ratios))
    return factors


async def used_factors(db: AsyncSession) -> dict[str, UsedFactor]:
    """The factor per format, measured from the stored values that have both groups."""
    rows = await db.execute(
        select(
            DiscValuation.format_code, DiscValuation.used_median, DiscValuation.new_median
        ).where(
            DiscValuation.used_count >= MIN_SAMPLE,
            DiscValuation.new_count >= MIN_SAMPLE,
            DiscValuation.new_median > 0,
        )
    )
    pairs: dict[str, list[Decimal]] = {}
    for code, used, new in rows:
        pairs.setdefault(code, []).append(Decimal(used) / Decimal(new))
    return factors_from(pairs)


async def rescale(db: AsyncSession, factors: dict[str, UsedFactor]) -> int:
    """Bring every New-based value to its format's factor; how many rows moved.

    Run at the end of each run, so the whole collection rests on one factor per format
    rather than on whatever each night's run started with.
    """
    moved = 0
    for code, used in factors.items():
        result = await db.execute(
            update(DiscValuation)
            .where(
                DiscValuation.format_code == code,
                DiscValuation.value_basis == "new_scaled",
                DiscValuation.factor != used.factor,
            )
            .values(price=func.round(DiscValuation.new_median * used.factor, 2), factor=used.factor)
            .returning(DiscValuation.id)
        )
        moved += len(result.all())
    return moved


async def value_of(
    db: AsyncSession, estimate: PriceEstimate, format_code: str | None
) -> UsedValue | None:
    """A live check's value as a used copy, on the factor the stored values give.

    The film page's "What is it worth?", the upgrade prompt and the listing link use this, so
    each shows the number a valuation run would store for the same listings.
    """
    if format_code not in VALUED_FORMATS:
        return None
    factors = await used_factors(db)
    return used_value(estimate, format_code, factor=factors[format_code].factor)


# ---------------------------------------------------------------------------
# A price, or not
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Valuation:
    status: Literal["priced", "not_priced"]
    price: Decimal | None
    #: Listings behind the price; for a film not priced, the larger of its two groups.
    sample_size: int
    #: "Used" or "New": which group the price came from.
    condition_label: str | None
    #: ``"used"`` or ``"new_scaled"`` when priced (``pricing.UsedValue.basis``).
    value_basis: str | None = None
    factor: Decimal | None = None
    low: Decimal | None = None
    high: Decimal | None = None
    #: Both groups, priced or not: what the factor is measured from.
    used_median: Decimal | None = None
    used_count: int = 0
    new_median: Decimal | None = None
    new_count: int = 0


def valuation_from(estimate: PriceEstimate, format_code: str, *, factor: Decimal) -> Valuation:
    """A disc's value as a used copy, if enough listings stand behind it — Batch X6.

    ``pricing.used_value`` decides, so a stored value is the number the film page's check
    shows as "As a used copy". Too few used and too few New listings is "not priced", never
    a guess from what there is.
    """
    pooled = estimate.used_pooled.get((format_code, "standard"))
    new = estimate.headline(format_code=format_code, condition_id=NEW_CONDITION_ID)
    used_count = pooled.count if pooled else 0
    new_count = new.sample_size if new else 0
    groups = Valuation(
        "not_priced",
        None,
        max(used_count, new_count),
        None,
        used_median=pooled.median if pooled else None,
        used_count=used_count,
        new_median=new.median if new else None,
        new_count=new_count,
    )
    value = used_value(estimate, format_code, factor=factor)
    if value is None or value.currency != CURRENCY:
        return groups
    return replace(
        groups,
        status="priced",
        price=value.price,
        sample_size=value.sample_size,
        condition_label="Used" if value.basis == "used" else "New",
        value_basis=value.basis,
        factor=value.factor,
        low=value.low,
        high=value.high,
    )


async def _store(
    db: AsyncSession,
    film: DueFilm,
    estimate: PriceEstimate,
    valuation: Valuation,
    *,
    run_id: uuid.UUID,
    checked: datetime,
) -> None:
    values = {
        "status": valuation.status,
        "price": valuation.price,
        "currency": CURRENCY,
        "sample_size": valuation.sample_size,
        "condition_label": valuation.condition_label,
        "value_basis": valuation.value_basis,
        "factor": valuation.factor,
        "low": valuation.low,
        "high": valuation.high,
        "used_median": valuation.used_median,
        "used_count": valuation.used_count,
        "new_median": valuation.new_median,
        "new_count": valuation.new_count,
        "matched": estimate.matched,
        "considered": estimate.considered,
        "basis": ASKING_PRICES,
        "search_query": search_query(film.search_title, film.format_code),
        "checked_utc": checked,
        "run_id": run_id,
    }
    await db.execute(
        insert(DiscValuation)
        .values(id=uuid.uuid4(), movie_id=film.movie_id, format_code=film.format_code, **values)
        .on_conflict_do_update(constraint="uq_disc_valuations_movie_format", set_=values)
    )


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StartOutcome:
    reason: StartReason
    run: ValuationRun | None
    due: int
    budget_left: int


async def abandon_stale_runs(db: AsyncSession, *, now: datetime) -> int:
    """Close runs whose process stopped answering, so the next one may start."""
    result = await db.execute(
        update(ValuationRun)
        .where(
            ValuationRun.status == "running",
            ValuationRun.heartbeat_utc < now - RUN_STALE_AFTER,
        )
        .values(
            status="abandoned",
            finished_utc=now,
            last_error="Nothing heard from it for 30 minutes; its process probably restarted.",
        )
        .returning(ValuationRun.id)
    )
    abandoned = len(result.all())
    await db.commit()
    return abandoned


async def running_run(db: AsyncSession) -> ValuationRun | None:
    result = await db.execute(select(ValuationRun).where(ValuationRun.status == "running"))
    return result.scalar_one_or_none()


async def start_run(
    db: AsyncSession,
    *,
    trigger: Literal["job", "admin"],
    started_by: uuid.UUID | None = None,
    now: datetime | None = None,
) -> StartOutcome:
    """Claim the right to run, if there is work, budget, and nobody else running.

    The claim is the insert of a ``running`` row. The partial unique index lets only one
    exist, so a scheduled run and the Home button starting together cannot both win.
    """
    now = now or utcnow()
    await abandon_stale_runs(db, now=now)
    due = await count_due(db, now=now)
    left = await budget_left(db, now=now)
    if await running_run(db) is not None:
        return StartOutcome("running", None, due, left)
    if due == 0:
        return StartOutcome("nothing_due", None, due, left)
    if left == 0:
        return StartOutcome("budget_spent", None, due, left)

    run = ValuationRun(
        id=uuid.uuid4(),
        trigger=trigger,
        status="running",
        started_by=started_by,
        started_utc=now,
        heartbeat_utc=now,
        budget=left,
        calls=0,
        priced=0,
        not_priced=0,
        failed=0,
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return StartOutcome("running", None, due, left)
    return StartOutcome("started", run, due, left)


async def work_run(
    db: AsyncSession,
    client: Searcher,
    run_id: uuid.UUID,
    *,
    clock: Callable[[], datetime] = utcnow,
) -> ValuationRun:
    """Price due films until they run out, the budget does, or eBay stops answering.

    Each film is committed as it is priced, with the run's counts and heartbeat, so a run
    that dies keeps everything it did and the next one starts where it stopped.
    """
    run = await db.get(ValuationRun, run_id)
    if run is None or run.status != "running":
        raise ValueError(f"valuation run {run_id} is not running")

    try:
        factors = await used_factors(db)
        # One more than the budget could reach, to know whether the budget cut the list.
        films = await due_films(db, now=run.started_utc, limit=run.budget + 1)
        cut_short = len(films) > run.budget
        films = films[: run.budget]
        outcome: str | None = None
        failures_in_a_row = 0
        for film in films:
            if client.search_calls + client.attempts_per_search > run.budget:
                outcome = "budget_spent"
                break
            try:
                estimate = await estimate_price(
                    client,
                    film_title=film.search_title,
                    format_code=film.format_code,
                    is_series=film.is_tv,
                )
            except EbayNotConfigured:
                run.last_error = "eBay is not configured in this deployment."
                outcome = "stopped"
                break
            except EbayError as exc:
                run.failed += 1
                failures_in_a_row += 1
                run.last_error = f"{film.search_title} ({film.format_code}): {exc}"
                logger.warning(
                    "valuation_search_failed", film=film.search_title, status=exc.status_code
                )
                if exc.status_code == 429 or failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                    outcome = "stopped"
                    break
            else:
                failures_in_a_row = 0
                valuation = valuation_from(
                    estimate, film.format_code, factor=factors[film.format_code].factor
                )
                await _store(db, film, estimate, valuation, run_id=run.id, checked=clock())
                if valuation.status == "priced":
                    run.priced += 1
                else:
                    run.not_priced += 1
            run.calls = client.search_calls
            run.heartbeat_utc = clock()
            await db.commit()

        # The night's prices measure the factor again; every New-based value moves to it.
        factors = await used_factors(db)
        rescaled = await rescale(db, factors)
        finished = clock()
        run.calls = client.search_calls
        run.remaining = await count_due(db, now=finished)
        if outcome is None:
            # Without a cut, everything due when the run started was tried. Anything left is
            # a film eBay failed on, or one that fell due since; both go first next time.
            outcome = "budget_spent" if cut_short else "finished"
        run.status = outcome
        run.finished_utc = finished
        run.heartbeat_utc = finished
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
        "valuation_run_finished",
        status=run.status,
        calls=run.calls,
        priced=run.priced,
        not_priced=run.not_priced,
        failed=run.failed,
        remaining=run.remaining,
        rescaled=rescaled,
        factors={code: (str(used.factor), used.films) for code, used in factors.items()},
    )
    return run


async def continue_run_in_background(run_id: uuid.UUID) -> None:
    """The Home button's run, after the response has gone. Its own session and client."""
    try:
        async with AsyncSessionLocal() as db, EbayClient() as client:
            await work_run(db, client, run_id)
    except Exception:  # noqa: BLE001 - the run records its own failure; nothing is waiting
        logger.warning("valuation_run_failed", run_id=str(run_id), exc_info=True)


# ---------------------------------------------------------------------------
# What it adds up to
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CollectionValue:
    total: Decimal | None
    discs: int
    priced: int
    sales_backed: int
    not_priced: int
    checked_from: datetime | None
    checked_to: datetime | None
    due: int
    budget_left: int
    latest_run: ValuationRun | None

    @property
    def unchecked(self) -> int:
        return self.discs - self.priced - self.not_priced


async def collection_value(db: AsyncSession, *, now: datetime | None = None) -> CollectionValue:
    """Every owned physical disc, at its film and format's stored value as a used copy.

    Counted per disc, so two copies of one film count twice: they are two discs. A run whose
    process died is closed here too, or the page would show it pricing for ever, with the
    button that could replace it hidden. A value from before Batch X6 is a new copy's price,
    so its disc counts as not checked yet until a run values it again.
    """
    now = now or utcnow()
    await abandon_stale_runs(db, now=now)
    discs = owned_valued_discs()
    sales_backed = and_(
        DiscValuation.sales_count >= MIN_SAMPLE, DiscValuation.sales_price.is_not(None)
    )
    priced = or_(DiscValuation.status == "priced", sales_backed)
    effective_price = case((sales_backed, DiscValuation.sales_price), else_=DiscValuation.price)
    effective_checked = case(
        (sales_backed, DiscValuation.sales_checked_utc), else_=DiscValuation.checked_utc
    )
    row = (
        await db.execute(
            select(
                func.count(discs.c.id),
                func.count(DiscValuation.id).filter(priced),
                func.count(DiscValuation.id).filter(
                    and_(DiscValuation.status == "not_priced", ~sales_backed)
                ),
                func.count(DiscValuation.id).filter(sales_backed),
                func.sum(effective_price).filter(priced),
                func.min(effective_checked),
                func.max(effective_checked),
            )
            .select_from(discs)
            .outerjoin(
                DiscValuation,
                and_(
                    DiscValuation.movie_id == discs.c.movie_id,
                    DiscValuation.format_code == discs.c.format_code,
                    current_value(),
                ),
            )
        )
    ).one()
    total_discs, priced_discs, not_priced_discs, sales_backed_discs, total, first, last = row
    # A bid trial (Batch V6) prices nothing, so it is not "the last run" of the value.
    latest = (
        await db.execute(
            select(ValuationRun)
            .where(ValuationRun.trigger != "trial")
            .order_by(ValuationRun.started_utc.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return CollectionValue(
        total=total,
        discs=int(total_discs),
        priced=int(priced_discs),
        sales_backed=int(sales_backed_discs),
        not_priced=int(not_priced_discs),
        checked_from=first,
        checked_to=last,
        due=await count_due(db, now=now),
        budget_left=await budget_left(db, now=now),
        latest_run=latest,
    )


async def valuations_for_movie(db: AsyncSession, movie_id: uuid.UUID) -> dict[str, DiscValuation]:
    """A film's stored values by format, for its page; none from before Batch X6."""
    rows = await db.scalars(
        select(DiscValuation).where(DiscValuation.movie_id == movie_id, current_value())
    )
    return {row.format_code: row for row in rows}
