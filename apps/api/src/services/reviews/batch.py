"""The reviews batch — Batch V9, `DECISIONS.md` #228 and #241 within #110 and #202.

**Three phases, in this order, each bounded:**

1. **Search, on Brave.** Each wanted film without a review row for a site gets one search per
   site, up to :data:`SEARCHES_PER_RUN`, within :data:`MONTHLY_REVIEW_SEARCHES` (the cap of
   its own #228 asked for) and the month's shared ceiling (#202). A search that fails leaves
   the want as it was, so the next batch tries again; one that finds nothing says so, and is
   tried again after :data:`SEARCH_AGAIN_AFTER`. Finding sends neither site a request.
2. **Seed, sending nothing.** Each owned film and format whose disc has a spec page gets a
   Blu-ray.com row to read from that page (#241). No search: the page is already known.
3. **Read, from Blu-ray.com.** Rows waiting to be read, up to :data:`FETCHES_PER_RUN`
   requests, through the spec fetcher's own rules: exact release pages only, five seconds
   apart, and a 403 or 429 halts the whole integration until an owner decision (#110). A
   page that is another year's film is not used. A page without a review is followed to the
   edition it links as having one, of the same format, which is one more paced request; a
   page without either has no review of that format.

**AVForums is never read** (#241): its rows are a link and Brave's line, and stay ``found``.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import httpx
import structlog
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.reviews import FilmReview, ReviewRun
from src.models.wanted import WantedItem
from src.services.reviews.bluray_com import OUT_OF, format_of, review_scores, reviewed_editions
from src.services.reviews.finding import (
    ReviewHit,
    avforums_hits,
    avforums_query,
    bluray_com_hits,
    bluray_com_query,
    choose,
    choose_bluray_com,
)
from src.services.specs.backfill import (
    MONTHLY_SEARCH_CEILING,
    Searcher,
    month_start,
    searches_this_month,
)
from src.services.specs.bluray_com import (
    OutOfBounds,
    canonical_release_url,
    extract_year,
    is_release_url,
)
from src.services.specs.runner import (
    MIN_INTERVAL_SECONDS,
    IntegrationHalted,
    PageMoved,
    fetch_page,
    get_state,
)
from src.services.specs.search import BraveError, BraveNotConfigured

logger = structlog.get_logger(__name__)

#: Brave searches one nightly batch may send. Ten wants, two sites each: twenty.
SEARCHES_PER_RUN = 40
#: Review searches in a calendar month, all batches together: the cap of its own (#228).
MONTHLY_REVIEW_SEARCHES = 100
#: Blu-ray.com requests one batch may make, follows included: 150 a night (#241).
FETCHES_PER_RUN = 150
#: A page that will not load after this many batches is given up on.
MAX_ATTEMPTS = 3
#: A search that found nothing is tried again after this, since reviews follow releases.
SEARCH_AGAIN_AFTER = timedelta(days=30)
RUN_STALE_AFTER = timedelta(minutes=30)
MAX_FAILURES_IN_A_ROW = 5
#: A film's year and its page's may differ by one: a festival or UK date (as T7's check).
YEAR_TOLERANCE = 1

SITES = ("bluray_com", "avforums")
NOT_CONFIGURED = "Searching is not set up: BRAVE_SEARCH_API_KEY is missing."

PhaseOutcome = Literal["done", "budget", "failed", "halted", "not_configured"]


@dataclass(frozen=True)
class PhaseEnd:
    outcome: PhaseOutcome
    message: str | None = None


@dataclass(frozen=True)
class Want:
    """A wanted film, as a search needs it."""

    movie_id: uuid.UUID
    title: str
    year: int | None
    format_code: str | None


# ---------------------------------------------------------------------------
# What is due
# ---------------------------------------------------------------------------


def _covers(row: FilmReview, format_code: str | None) -> bool:
    """Whether a row answers a want's search for its site: the same format, or for a want
    with no format, any row the search left."""
    return format_code is None or row.format_code == format_code


async def wants_to_search(db: AsyncSession, *, now: datetime) -> list[tuple[Want, str]]:
    """Each wanted film and site still to search, in the order the wants were added.

    Due when no row answers it, or when the only answer is an old ``none``.
    """
    wants = (
        await db.execute(
            select(WantedItem, Movie)
            .join(Movie, Movie.id == WantedItem.movie_id)
            .where(
                WantedItem.deleted_at.is_(None),
                WantedItem.is_active.is_(True),
                Movie.deleted_at.is_(None),
            )
            .order_by(WantedItem.added_at, WantedItem.id)
        )
    ).all()
    if not wants:
        return []
    rows = (
        (
            await db.execute(
                select(FilmReview).where(FilmReview.movie_id.in_([movie.id for _, movie in wants]))
            )
        )
        .scalars()
        .all()
    )
    due: list[tuple[Want, str]] = []
    for item, movie in wants:
        want = Want(movie.id, movie.title, movie.year, item.preferred_format)
        for site in SITES:
            answers = [
                row
                for row in rows
                if row.movie_id == movie.id and row.site == site and _covers(row, want.format_code)
            ]
            fresh = [
                row
                for row in answers
                if row.status != "none" or row.found_utc > now - SEARCH_AGAIN_AFTER
            ]
            if not fresh:
                due.append((want, site))
    return due


async def review_searches_this_month(db: AsyncSession, *, now: datetime) -> int:
    spent = await db.scalar(
        select(func.coalesce(func.sum(ReviewRun.searches), 0)).where(
            ReviewRun.started_utc >= month_start(now)
        )
    )
    return int(spent or 0)


async def search_budget(db: AsyncSession, *, now: datetime, per_run: int) -> int:
    """Searches this batch may send: its own limit, the cap of its own, and the shared
    ceiling, whichever is least."""
    own = MONTHLY_REVIEW_SEARCHES - await review_searches_this_month(db, now=now)
    shared = MONTHLY_SEARCH_CEILING - await searches_this_month(db, now=now)
    return max(min(per_run, own, shared), 0)


# ---------------------------------------------------------------------------
# Searching
# ---------------------------------------------------------------------------


async def _existing(
    db: AsyncSession, movie_id: uuid.UUID, site: str, format_code: str | None
) -> FilmReview | None:
    return (
        await db.execute(
            select(FilmReview).where(
                FilmReview.movie_id == movie_id,
                FilmReview.site == site,
                func.coalesce(FilmReview.format_code, "") == (format_code or ""),
            )
        )
    ).scalar_one_or_none()


async def record_search(
    db: AsyncSession,
    want: Want,
    site: str,
    hits: list[ReviewHit],
    *,
    query: str,
    now: datetime,
) -> FilmReview:
    """Keep the review Brave found for this want and site, or record that it found none.

    A ``none`` row is keyed on the want's format, so a want for another format searches
    afresh; a kept review is keyed on its own format. An old ``none`` is replaced.
    """
    chosen = (
        choose_bluray_com(hits, want.format_code)
        if site == "bluray_com"
        else choose(hits, want.format_code)
    )
    stale = [
        row
        for row in (
            await db.execute(
                select(FilmReview).where(
                    FilmReview.movie_id == want.movie_id,
                    FilmReview.site == site,
                    FilmReview.status == "none",
                )
            )
        ).scalars()
        if _covers(row, want.format_code)
    ]
    for row in stale:
        await db.delete(row)
    await db.flush()

    if chosen is None:
        row = FilmReview(
            id=uuid.uuid4(),
            movie_id=want.movie_id,
            site=site,
            format_code=want.format_code,
            status="none",
            found_via="brave",
            search_query=query,
            found_utc=now,
            note="Brave found no review of this film on the site.",
        )
        db.add(row)
        await db.flush()
        return row

    existing = await _existing(db, want.movie_id, site, chosen.format_code)
    if existing is not None:
        # Another want, or an owned disc's spec page, already holds this film and format.
        return existing
    row = FilmReview(
        id=uuid.uuid4(),
        movie_id=want.movie_id,
        site=site,
        format_code=chosen.format_code,
        status="found",
        url=chosen.url,
        found_via="brave",
        found_url=chosen.url,
        search_query=query,
        title=chosen.title,
        description=chosen.description or None,
        found_utc=now,
    )
    db.add(row)
    await db.flush()
    return row


async def search_one(
    db: AsyncSession, searcher: Searcher, want: Want, site: str, *, now: datetime
) -> FilmReview:
    """One Brave search for one want on one site. Raises :class:`BraveError` on failure,
    having written nothing, so the want is searched again next time."""
    if site == "bluray_com":
        query = bluray_com_query(want.title, want.year, want.format_code)
        hits = bluray_com_hits(await searcher.search(query), want.title)
    else:
        query = avforums_query(want.title, want.year, want.format_code)
        hits = avforums_hits(await searcher.search(query), want.title)
    return await record_search(db, want, site, hits, query=query, now=now)


async def search_phase(
    db: AsyncSession,
    run: ReviewRun,
    searcher: Searcher,
    due: list[tuple[Want, str]],
    *,
    budget: int,
    clock: Callable[[], datetime],
) -> PhaseEnd:
    """Search for each due want and site, within ``budget`` Brave requests."""
    if not due:
        return PhaseEnd("done")
    if not searcher.configured:
        return PhaseEnd("not_configured", NOT_CONFIGURED)
    run_id = run.id
    for index, (want, site) in enumerate(due):
        if searcher.search_calls + searcher.attempts_per_search > budget:
            return PhaseEnd("budget")
        try:
            row = await search_one(db, searcher, want, site, now=clock())
        except (BraveError, BraveNotConfigured) as exc:
            await db.rollback()
            run = await _reload(db, run_id)
            run.searches = searcher.search_calls
            run.last_error = f"{want.title}: {exc}"[:500]
            run.heartbeat_utc = clock()
            await db.commit()
            # Brave failing once usually means it will fail for the rest: stop, and leave
            # every want after this one as it was.
            return PhaseEnd("failed", run.last_error)
        if row.status == "found":
            run.found += 1
        run.searches = searcher.search_calls
        run.heartbeat_utc = clock()
        await db.commit()
        logger.info(
            "review_searched",
            film=want.title,
            site=site,
            kept=row.url,
            remaining=len(due) - index - 1,
        )
    return PhaseEnd("done")


async def _reload(db: AsyncSession, run_id: uuid.UUID) -> ReviewRun:
    """The run, fetched again by id: after a rollback every loaded object is expired, and
    reading an expired attribute in an async session is an error."""
    reloaded = await db.get(ReviewRun, run_id)
    if reloaded is None:  # pragma: no cover - the run row was committed before any work
        raise ValueError(f"review run {run_id} vanished")
    return reloaded


# ---------------------------------------------------------------------------
# Seeding owned films from their spec pages (#241)
# ---------------------------------------------------------------------------


async def seed_owned(db: AsyncSession, *, now: datetime) -> int:
    """A Blu-ray.com row to read for each owned film and format with a spec page.

    The format is the spec page's own, read from its address. Sends nothing. A search that
    found nothing for the same film and format gives way: the spec page is the disc's own.
    """
    pages = (
        await db.execute(
            select(CollectionItem.movie_id, CollectionItem.specs_source_url)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(
                owned_copy(),
                CollectionItem.specs_source_url.is_not(None),
                Movie.deleted_at.is_(None),
            )
            .order_by(CollectionItem.specs_fetched_at_utc, CollectionItem.id)
        )
    ).all()
    existing = {
        (row.movie_id, row.format_code): row
        for row in (
            await db.execute(select(FilmReview).where(FilmReview.site == "bluray_com"))
        ).scalars()
    }
    seeded = 0
    for movie_id, page in pages:
        if not page or not is_release_url(page):
            continue
        format_code = format_of(page)
        if format_code is None:
            continue
        key = (movie_id, format_code)
        held = existing.get(key)
        if held is not None and held.status != "none":
            continue
        if held is not None:
            await db.delete(held)
            await db.flush()
        url = canonical_release_url(page)
        row = FilmReview(
            id=uuid.uuid4(),
            movie_id=movie_id,
            site="bluray_com",
            format_code=format_code,
            status="found",
            url=url,
            found_via="spec_page",
            found_url=url,
            found_utc=now,
        )
        db.add(row)
        existing[key] = row
        seeded += 1
    if seeded:
        await db.commit()
    return seeded


# ---------------------------------------------------------------------------
# Reading Blu-ray.com's scores
# ---------------------------------------------------------------------------


def _year_problem(page_year: int | None, film_year: int | None) -> str | None:
    if film_year is None:
        return "The film has no year to check the page against"
    if page_year is None:
        return "The page shows no year to check"
    if abs(page_year - film_year) > YEAR_TOLERANCE:
        return f"The page is for a {page_year} film and this one is from {film_year}"
    return None


async def _pause(seconds: float) -> None:
    """The batch's one wait between requests, in one place, so a test can stand in for it."""
    await asyncio.sleep(seconds)


@dataclass
class _Reading:
    """One row's read, which may take two requests."""

    requests: int = 0


async def _get(
    db: AsyncSession,
    client: httpx.AsyncClient,
    url: str,
    reading: _Reading,
    *,
    pause: float,
) -> tuple[str, str]:
    """One paced request through the spec fetcher. Returns the page's address and HTML."""
    if pause:
        # Before every request, the first included: the spec batch may have fetched a page
        # a moment ago in the same job, and #110's spacing is between any two requests.
        await _pause(pause)
    reading.requests += 1
    page = await fetch_page(client, url, db, pause=pause)
    return canonical_release_url(page.url), page.html


async def read_one(
    db: AsyncSession,
    row: FilmReview,
    client: httpx.AsyncClient,
    reading: _Reading,
    *,
    film_year: int | None,
    now: datetime,
    pause: float,
    may_follow: bool,
) -> None:
    """Read one row's review, following the page's link to the reviewed edition if needed.

    Raises :class:`IntegrationHalted`, :class:`PageMoved` and :class:`httpx.HTTPError` for
    the caller to record.
    """
    assert row.url is not None
    url, html = await _get(db, client, row.url, reading, pause=pause)
    row.checked_utc = now
    problem = _year_problem(extract_year(html), film_year)
    if problem:
        row.status = "mismatch"
        row.note = f"{problem}, so its review was not used."
        return

    scores = review_scores(html)
    if scores is None:
        edition = next(
            (
                found
                for found in reviewed_editions(html)
                if found.format_code == row.format_code
                and (
                    found.year is None
                    or film_year is None
                    or abs(found.year - film_year) <= YEAR_TOLERANCE
                )
            ),
            None,
        )
        if edition is None:
            row.status = "no_review"
            row.note = "Blu-ray.com has no review of this film on this format."
            return
        if not may_follow:
            # Out of requests for tonight: read the reviewed edition's page next time.
            row.found_url = row.found_url or row.url
            row.url = edition.url
            row.note = "The review is on another edition's page, to be read next time."
            return
        url, html = await _get(db, client, edition.url, reading, pause=pause)
        problem = _year_problem(extract_year(html), film_year)
        scores = review_scores(html)
        if problem or scores is None:
            row.status = "mismatch" if problem else "no_review"
            row.note = (
                f"{problem}, so its review was not used."
                if problem
                else "The edition Blu-ray.com links as reviewed shows no review."
            )
            return

    row.found_url = row.found_url or row.url
    row.url = url
    row.status = "scored"
    row.scores = [{"heading": heading, "score": float(score)} for heading, score in scores.scores]
    row.overall = scores.overall
    row.out_of = OUT_OF
    row.scores_read_utc = now
    row.note = None


async def read_phase(
    db: AsyncSession,
    run: ReviewRun,
    client: httpx.AsyncClient,
    *,
    budget: int,
    clock: Callable[[], datetime],
    pause: float = MIN_INTERVAL_SECONDS,
) -> PhaseEnd:
    """Read waiting Blu-ray.com rows, wanted films' first, within ``budget`` requests."""
    if (await get_state(db)).halted:
        return PhaseEnd("halted", "The Blu-ray.com integration is halted (DECISIONS.md #110).")
    rows = list(
        (
            await db.execute(
                select(FilmReview)
                .where(FilmReview.site == "bluray_com", FilmReview.status == "found")
                .order_by(
                    (FilmReview.found_via == "brave").desc(),
                    FilmReview.found_utc,
                    FilmReview.id,
                )
            )
        ).scalars()
    )
    failures_in_a_row = 0
    for row in rows:
        left = budget - run.fetched
        if left <= 0:
            return PhaseEnd("budget")
        movie = await db.get(Movie, row.movie_id)
        reading = _Reading()
        try:
            await read_one(
                db,
                row,
                client,
                reading,
                film_year=movie.year if movie is not None else None,
                now=clock(),
                pause=pause,
                may_follow=left >= 2,
            )
        except IntegrationHalted as exc:
            run.fetched += reading.requests
            run.last_error = f"The Blu-ray.com integration is halted: {exc}"
            await db.commit()
            return PhaseEnd("halted", run.last_error)
        except (OutOfBounds, PageMoved) as exc:
            run.fetched += reading.requests
            row.status = "failed"
            row.note = (exc.reason if isinstance(exc, PageMoved) else str(exc))[:500]
            failures_in_a_row += 1
        except httpx.HTTPError as exc:
            run.fetched += reading.requests
            row.attempts += 1
            row.checked_utc = clock()
            row.note = (str(exc) or type(exc).__name__)[:500]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = "failed"
            failures_in_a_row += 1
        else:
            run.fetched += reading.requests
            failures_in_a_row = 0
            if row.status == "scored":
                run.scored += 1
            elif row.status == "no_review":
                run.no_review += 1
        run.heartbeat_utc = clock()
        await db.commit()
        if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
            return PhaseEnd("failed", f"Blu-ray.com failed {failures_in_a_row} times in a row.")
    return PhaseEnd("done")


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


async def abandon_stale_runs(db: AsyncSession, *, now: datetime) -> None:
    await db.execute(
        update(ReviewRun)
        .where(ReviewRun.status == "running", ReviewRun.heartbeat_utc < now - RUN_STALE_AFTER)
        .values(
            status="abandoned",
            finished_utc=now,
            last_error="Nothing heard from it for 30 minutes; its process probably restarted.",
        )
    )
    await db.commit()


async def start_run(
    db: AsyncSession, *, trigger: Literal["job", "want_added"], now: datetime | None = None
) -> ReviewRun | None:
    """Claim a run. ``None`` when another nightly batch is running."""
    now = now or utcnow()
    await abandon_stale_runs(db, now=now)
    run = ReviewRun(
        id=uuid.uuid4(),
        trigger=trigger,
        status="running",
        started_utc=now,
        heartbeat_utc=now,
        searches=0,
        found=0,
        fetched=0,
        scored=0,
        no_review=0,
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None
    return run


def _status(*ends: PhaseEnd) -> str:
    outcomes = {end.outcome for end in ends}
    if "halted" in outcomes:
        return "halted"
    if "failed" in outcomes:
        return "stopped"
    return "finished"


async def work_run(
    db: AsyncSession,
    run: ReviewRun,
    *,
    searcher: Searcher,
    client: httpx.AsyncClient,
    clock: Callable[[], datetime] = utcnow,
    pause: float = MIN_INTERVAL_SECONDS,
    searches_per_run: int = SEARCHES_PER_RUN,
    fetches_per_run: int = FETCHES_PER_RUN,
) -> ReviewRun:
    """The nightly batch: search, seed, read; then record how it ended."""
    run_id = run.id
    try:
        now = clock()
        due = await wants_to_search(db, now=now)
        budget = await search_budget(db, now=now, per_run=searches_per_run)
        searching = await search_phase(db, run, searcher, due, budget=budget, clock=clock)
        run = await _reload(db, run_id)
        await seed_owned(db, now=clock())
        run = await _reload(db, run_id)
        reading = await read_phase(
            db, run, client, budget=fetches_per_run, clock=clock, pause=pause
        )

        run.searches = searcher.search_calls
        run.status = _status(searching, reading)
        if run.status != "finished":
            run.last_error = reading.message or searching.message or run.last_error
        elif searching.outcome == "not_configured":
            run.last_error = NOT_CONFIGURED
        run.finished_utc = clock()
        run.heartbeat_utc = run.finished_utc
        await db.commit()
    except Exception as exc:
        await db.rollback()
        stopped = await db.get(ReviewRun, run_id)
        if stopped is not None and stopped.status == "running":
            stopped.status = "stopped"
            stopped.finished_utc = clock()
            stopped.searches = searcher.search_calls
            stopped.last_error = f"{type(exc).__name__}: {exc}"[:500]
            await db.commit()
        raise
    logger.info(
        "review_run_finished",
        status=run.status,
        searches=run.searches,
        found=run.found,
        fetched=run.fetched,
        scored=run.scored,
        no_review=run.no_review,
    )
    return run


async def search_for_want(
    db: AsyncSession,
    movie_id: uuid.UUID,
    *,
    searcher: Searcher,
    clock: Callable[[], datetime] = utcnow,
) -> ReviewRun | None:
    """A film just added to Wanted: search both sites for its review now, within the caps.

    No page is read here; the nightly batch reads Blu-ray.com's, five seconds apart with the
    spec batch, so no two processes ever ask Blu-ray.com at once.
    """
    now = clock()
    due = [
        (want, site)
        for want, site in await wants_to_search(db, now=now)
        if want.movie_id == movie_id
    ]
    if not due or not searcher.configured:
        return None
    budget = await search_budget(db, now=now, per_run=len(due) * searcher.attempts_per_search)
    run = await start_run(db, trigger="want_added", now=now)
    if run is None:  # pragma: no cover - only the nightly batch is held to one at a time
        return None
    run_id = run.id
    searching = await search_phase(db, run, searcher, due, budget=budget, clock=clock)
    run = await _reload(db, run_id)
    run.searches = searcher.search_calls
    run.status = "stopped" if searching.outcome == "failed" else "finished"
    run.last_error = searching.message if searching.outcome != "done" else None
    run.finished_utc = clock()
    run.heartbeat_utc = run.finished_utc
    await db.commit()
    return run


async def search_for_want_in_background(movie_id: uuid.UUID) -> None:
    """After the response to adding a want has gone. Its own session and Brave client."""
    from src.database import AsyncSessionLocal
    from src.services.specs.search import BraveSearch

    try:
        async with AsyncSessionLocal() as db, BraveSearch() as brave:
            await search_for_want(db, movie_id, searcher=brave)
    except Exception:  # noqa: BLE001 - nothing is waiting; the nightly batch tries again
        logger.warning("review_search_failed", movie_id=str(movie_id), exc_info=True)
