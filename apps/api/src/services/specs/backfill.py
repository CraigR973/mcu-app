"""The Blu-ray.com backfill — Batch T7, `DECISIONS.md` #202 within #110.

**One batch does two things, in this order:**

1. **Search, on Brave.** Up to :data:`SEARCHES_PER_RUN` Blu-ray and 4K discs without specs
   are searched for, one search each. The matcher (``candidates.py``) either accepts one
   page or leaves the disc for Craig with the candidates and a reason. A disc left for
   Craig whose film has been identified since its search is searched once more, first,
   under the film's own title (Batch T10).
2. **Fetch, from Blu-ray.com.** Up to :data:`FETCHES_PER_RUN` accepted pages are fetched by
   the existing runner's rules: exact release URLs only, five seconds apart, and a 403 or
   429 halts the whole integration until an owner decision. A page the matcher chose must
   show the film's year before its specs are written; a page Craig chose is his call. A
   page that moved to a new address for the same release is followed once and kept at its
   new address; one sent anywhere else goes straight back to Craig (Batch U1).

**Nothing is fetched until a page is accepted**, and nothing here searches Blu-ray.com.

**Spend is capped twice:** per batch, and per calendar month at
:data:`MONTHLY_SEARCH_CEILING`, which covers the whole backfill with room for retries: about
£2 beyond Brave's $5 of monthly credit at most.

**The 10 discs specced on 10 Sep.** Those specs sit on rows the 18 Sep refresh put in the
Trash, and at least two came from US pages (region A). So the old page is added to the
disc's candidates, and its specs are copied across only when the search shows that page is
a UK edition of the right film and format. Otherwise the disc goes the ordinary way.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx
import structlog
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.clock import utcnow
from src.matching.engine import searchable_title
from src.models.collection_item import CollectionItem, owned_copy
from src.models.identify import IdentifyRun
from src.models.movie import Movie
from src.models.reviews import ReviewRun
from src.models.specs_backfill import SpecCandidate, SpecLookup, SpecRun
from src.services.specs.bluray_com import (
    OutOfBounds,
    canonical_release_url,
    extract_year,
    is_release_url,
)
from src.services.specs.candidates import Candidate, Disc, decide, judge, search_query
from src.services.specs.editions import EditionKind, SettledEdition, settled_edition
from src.services.specs.runner import (
    MIN_INTERVAL_SECONDS,
    IntegrationHalted,
    PageMoved,
    apply_specs,
    fetch_page,
    get_state,
)
from src.services.specs.search import BraveError, BraveNotConfigured, SearchHit

logger = structlog.get_logger(__name__)

#: Brave searches one batch may send: about nine nights for the ~1,250 discs.
SEARCHES_PER_RUN = 150
#: Blu-ray.com pages one batch may fetch. Five seconds apart, 150 take about 13 minutes.
FETCHES_PER_RUN = 150
#: Brave searches in a calendar month, all batches together. The backfill is ~1,250.
MONTHLY_SEARCH_CEILING = 1_500
RUN_STALE_AFTER = timedelta(minutes=30)
MAX_FAILURES_IN_A_ROW = 5
#: A page that will not load after this many batches goes back to Craig.
MAX_FETCH_ATTEMPTS = 3
#: A film's year and its disc page's year may differ by one: a festival or UK date.
YEAR_TOLERANCE = 1

#: The discs in scope, as their best physical format. DVDs are out: their pages live
#: under `/dvd/`, which #110's predicate does not allow.
BACKFILL_FORMATS = ("4k_uhd", "blu_ray")

NOT_CONFIGURED = "Searching is not set up: BRAVE_SEARCH_API_KEY is missing."

StartReason = Literal["started", "running", "halted", "nothing_due"]
PhaseOutcome = Literal["done", "budget", "failed", "not_configured", "halted"]


class Searcher(Protocol):
    """What a batch needs from Brave. :class:`~src.services.specs.search.BraveSearch` is one."""

    search_calls: int

    @property
    def configured(self) -> bool: ...

    @property
    def attempts_per_search(self) -> int: ...

    async def search(
        self, query: str, *, count: int = ..., country: str = ...
    ) -> list[SearchHit]: ...


@dataclass(frozen=True)
class PhaseEnd:
    outcome: PhaseOutcome
    message: str | None = None


# ---------------------------------------------------------------------------
# Which discs
# ---------------------------------------------------------------------------


def _format_sql() -> ColumnElement[str | None]:
    return case(
        *((CollectionItem.formats.contains([code]), code) for code in BACKFILL_FORMATS),
        else_=None,
    )


def _in_scope() -> tuple[ColumnElement[str | None], list[ColumnElement[bool]]]:
    """Owned Blu-ray and 4K discs of live films, and the format each is looked up as."""
    fmt = _format_sql()
    return fmt, [owned_copy(), Movie.deleted_at.is_(None), fmt.is_not(None)]


@dataclass(frozen=True)
class DiscRow:
    item_id: uuid.UUID
    movie_id: uuid.UUID
    title: str
    identified: bool
    year: int | None
    format_code: str
    grouping: str | None

    @property
    def disc(self) -> Disc:
        return Disc(
            title=searchable_title(self.title, identified=self.identified),
            year=self.year,
            format_code=self.format_code,
            grouping=self.grouping,
        )


async def discs_to_search(
    db: AsyncSession, *, limit: int, first: set[uuid.UUID] | None = None
) -> list[DiscRow]:
    """Discs without specs that have never been searched for; films in ``first`` first."""
    fmt, conditions = _in_scope()
    searched = select(SpecLookup.id).where(SpecLookup.collection_item_id == CollectionItem.id)
    query = (
        select(
            CollectionItem.id,
            CollectionItem.movie_id,
            Movie.title,
            Movie.tmdb_id,
            Movie.year,
            fmt,
            CollectionItem.sub_category,
        )
        .join(Movie, Movie.id == CollectionItem.movie_id)
        .where(*conditions, CollectionItem.specs_source_url.is_(None), ~searched.exists())
    )
    if first:
        query = query.order_by(case((CollectionItem.movie_id.in_(first), 0), else_=1))
    rows = await db.execute(query.order_by(Movie.title, CollectionItem.id).limit(limit))
    return [
        DiscRow(
            item_id=item_id,
            movie_id=movie_id,
            title=title,
            identified=tmdb_id is not None,
            year=year,
            format_code=code,
            grouping=grouping,
        )
        for item_id, movie_id, title, tmdb_id, year, code, grouping in rows
    ]


#: How the fetch words a page that failed its year check. A disc sent back with one stays
#: with Craig, as the second look leaves it, so searching again cannot accept that page anew.
_YEAR_CHECK_FAILED = (
    "The page is for a ",
    "The page shows no year",
    "The film has no year to check",
)


async def discs_to_search_again(
    db: AsyncSession, *, limit: int
) -> list[tuple[SpecLookup, DiscRow]]:
    """Queued discs whose film was identified after the disc was searched — Batch T10.

    A disc searched under the spreadsheet's title ("Captain Ameica - Civil War") stays stuck:
    the second look judges those results again and never searches. Once the film is
    identified, the words a search would use differ, so the disc is searched once more.

    **Once needs no flag.** Identifying a film writes ``last_tmdb_sync_utc`` and nothing else
    does to a film that already exists, and the new search is later than that. A merge
    rewrites the kept film's too, which is why the words must differ as well: the kept
    film's own discs were searched under its title already. A disc Craig has decided on,
    one with specs, and one whose page failed its year check are left as they are.
    """
    fmt, conditions = _in_scope()
    rows = await db.execute(
        select(
            SpecLookup,
            CollectionItem.id,
            CollectionItem.movie_id,
            Movie.title,
            Movie.year,
            fmt,
            CollectionItem.sub_category,
        )
        .join(CollectionItem, CollectionItem.id == SpecLookup.collection_item_id)
        .join(Movie, Movie.id == CollectionItem.movie_id)
        .where(
            *conditions,
            SpecLookup.status.in_(("needs_you", "no_match")),
            SpecLookup.decided_by.is_(None),
            SpecLookup.searched_utc.is_not(None),
            CollectionItem.specs_source_url.is_(None),
            Movie.tmdb_id.is_not(None),
            Movie.last_tmdb_sync_utc > SpecLookup.searched_utc,
        )
        .order_by(Movie.title, CollectionItem.id)
    )
    found: list[tuple[SpecLookup, DiscRow]] = []
    for lookup, item_id, movie_id, title, year, code, grouping in rows:
        if (lookup.note or "").startswith(_YEAR_CHECK_FAILED):
            continue
        row = DiscRow(
            item_id=item_id,
            movie_id=movie_id,
            title=title,
            identified=True,
            year=year,
            format_code=code,
            grouping=grouping,
        )
        if search_query(row.disc.title, row.format_code) == lookup.search_query:
            continue
        found.append((lookup, row))
        if len(found) >= limit:
            break
    return found


async def trashed_specs(db: AsyncSession) -> dict[tuple[uuid.UUID, str], CollectionItem]:
    """The 10 Sep test's spec rows, now in the Trash, by film and format."""
    fmt = _format_sql()
    rows = await db.execute(
        select(CollectionItem, fmt)
        .where(CollectionItem.deleted_at.is_not(None), CollectionItem.specs_source_url.is_not(None))
        .order_by(CollectionItem.specs_fetched_at_utc.desc())
    )
    found: dict[tuple[uuid.UUID, str], CollectionItem] = {}
    for item, code in rows:
        if code is not None:
            found.setdefault((item.movie_id, code), item)
    return found


def same_page(first: str, second: str) -> bool:
    """One release page, however the address was written: `www.` and the slash vary."""

    def key(url: str) -> tuple[str, str]:
        parts = urlsplit(url)
        return (parts.hostname or "").lower().removeprefix("www."), parts.path.rstrip("/")

    return key(first) == key(second)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


def month_start(now: datetime) -> datetime:
    return datetime.combine(now.date().replace(day=1), time.min)


async def searches_this_month(db: AsyncSession, *, now: datetime) -> int:
    """Brave searches billed this calendar month, by these batches, by Batch T9's
    identification runs and by V9's review searches, which all share the ceiling."""
    spent = await db.scalar(
        select(func.coalesce(func.sum(SpecRun.searches), 0)).where(
            SpecRun.started_utc >= month_start(now)
        )
    )
    identifying = await db.scalar(
        select(func.coalesce(func.sum(IdentifyRun.searches), 0)).where(
            IdentifyRun.started_utc >= month_start(now)
        )
    )
    reviewing = await db.scalar(
        select(func.coalesce(func.sum(ReviewRun.searches), 0)).where(
            ReviewRun.started_utc >= month_start(now)
        )
    )
    return int(spent or 0) + int(identifying or 0) + int(reviewing or 0)


async def accepted_waiting(db: AsyncSession) -> int:
    count = await db.scalar(
        select(func.count()).select_from(SpecLookup).where(SpecLookup.status == "accepted")
    )
    return int(count or 0)


async def abandon_stale_runs(db: AsyncSession, *, now: datetime) -> None:
    await db.execute(
        update(SpecRun)
        .where(SpecRun.status == "running", SpecRun.heartbeat_utc < now - RUN_STALE_AFTER)
        .values(
            status="abandoned",
            finished_utc=now,
            last_error="Nothing heard from it for 30 minutes; its process probably restarted.",
        )
    )
    await db.commit()


async def running_run(db: AsyncSession) -> SpecRun | None:
    result = await db.execute(select(SpecRun).where(SpecRun.status == "running"))
    return result.scalar_one_or_none()


async def latest_run(db: AsyncSession) -> SpecRun | None:
    result = await db.execute(select(SpecRun).order_by(SpecRun.started_utc.desc()).limit(1))
    return result.scalar_one_or_none()


@dataclass(frozen=True)
class StartOutcome:
    reason: StartReason
    run: SpecRun | None


async def start_run(
    db: AsyncSession,
    *,
    trigger: Literal["job", "admin"],
    search_configured: bool,
    started_by: uuid.UUID | None = None,
    now: datetime | None = None,
) -> StartOutcome:
    """Claim the right to run a batch, if there is work and the integration is not halted.

    The claim is the insert of a ``running`` row, and the partial unique index lets only
    one exist, as for valuation runs. Without a Brave key there is still work when Craig
    has chosen pages that are waiting to be fetched.
    """
    now = now or utcnow()
    await abandon_stale_runs(db, now=now)
    if (await get_state(db)).halted:
        return StartOutcome("halted", None)
    if await running_run(db) is not None:
        return StartOutcome("running", None)
    to_search = search_configured and (
        bool(await discs_to_search(db, limit=1)) or bool(await discs_to_search_again(db, limit=1))
    )
    if not to_search and await accepted_waiting(db) == 0:
        return StartOutcome("nothing_due", None)

    monthly_left = MONTHLY_SEARCH_CEILING - await searches_this_month(db, now=now)
    run = SpecRun(
        id=uuid.uuid4(),
        trigger=trigger,
        status="running",
        started_by=started_by,
        started_utc=now,
        heartbeat_utc=now,
        search_budget=max(min(SEARCHES_PER_RUN, monthly_left), 0),
        searches=0,
        searched=0,
        accepted=0,
        queued=0,
        no_match=0,
        restored=0,
        searched_again=0,
        settled_again=0,
        fetch_budget=FETCHES_PER_RUN,
        fetched=0,
        applied=0,
        sent_back=0,
        fetch_failed=0,
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return StartOutcome("running", None)
    return StartOutcome("started", run)


# ---------------------------------------------------------------------------
# Searching
# ---------------------------------------------------------------------------


def _restore_from(old: CollectionItem, item: CollectionItem) -> None:
    """Copy the 10 Sep test's specs and their provenance onto the live disc."""
    item.video_specs = old.video_specs
    item.audio_specs = old.audio_specs
    item.special_features = old.special_features
    item.region_code = old.region_code
    item.release_label = old.release_label
    item.specs_source_url = old.specs_source_url
    item.specs_fetched_at_utc = old.specs_fetched_at_utc


def _candidate_row(lookup_id: uuid.UUID, candidate: Candidate) -> SpecCandidate:
    release = candidate.release
    return SpecCandidate(
        id=uuid.uuid4(),
        lookup_id=lookup_id,
        url=candidate.url,
        title=candidate.title,
        snippet=candidate.snippet or None,
        rank=candidate.rank,
        country=release.country,
        format_label=release.format_label,
        edition=" · ".join(release.editions) or None,
        matches=candidate.matches,
        origin="search",
    )


async def record_search(
    db: AsyncSession,
    run: SpecRun,
    row: DiscRow,
    query: str,
    hits: list[SearchHit],
    old: CollectionItem | None,
    now: datetime,
) -> SpecLookup:
    """Judge the hits, store the candidates, and settle where the disc stands."""
    disc = row.disc
    candidates = judge(hits, disc)
    verdict = decide(candidates, disc)
    lookup = SpecLookup(
        id=uuid.uuid4(),
        collection_item_id=row.item_id,
        status=verdict.decision,
        search_query=query,
        searched_utc=now,
        run_id=run.id,
        note=verdict.note,
        attempts=0,
    )
    if verdict.decision == "accepted":
        lookup.accepted_url = verdict.url
        lookup.how = "auto"
        lookup.decided_utc = now
    db.add(lookup)
    await db.flush()
    for candidate in candidates:
        db.add(_candidate_row(lookup.id, candidate))
    run.searched += 1

    old_url = old.specs_source_url if old is not None else None
    if old is not None and old_url:
        confirmed = any(c.matches and same_page(c.url, old_url) for c in candidates)
        item = await db.get(CollectionItem, row.item_id)
        if confirmed and item is not None and not item.specs_source_url:
            _restore_from(old, item)
            lookup.status = "done"
            lookup.accepted_url = canonical_release_url(old_url)
            lookup.how = "restored"
            lookup.decided_utc = now
            lookup.fetched_utc = now
            lookup.note = "Specs from the 10 Sep test, whose page is this film's UK edition."
            run.restored += 1
            return lookup
        if is_release_url(old_url) and not any(same_page(c.url, old_url) for c in candidates):
            db.add(
                SpecCandidate(
                    id=uuid.uuid4(),
                    lookup_id=lookup.id,
                    url=canonical_release_url(old_url),
                    title="The page the 10 Sep test used; its edition was not confirmed",
                    rank=len(candidates),
                    matches=False,
                    origin="restored",
                )
            )
        lookup.note = (
            f"{verdict.note} The 10 Sep test used a page the search did not confirm as this "
            "film's UK edition, so its specs were not copied."
        )

    _count_outcome(run, lookup)
    return lookup


def _count_outcome(run: SpecRun, lookup: SpecLookup) -> None:
    if lookup.status == "accepted":
        run.accepted += 1
    elif lookup.status == "no_match":
        run.no_match += 1
    else:
        run.queued += 1


async def record_search_again(
    db: AsyncSession,
    run: SpecRun,
    lookup: SpecLookup,
    row: DiscRow,
    query: str,
    hits: list[SearchHit],
    now: datetime,
) -> SpecLookup:
    """Judge a queued disc's second search and settle it as a first search would — T10.

    The first search's candidates came from the old title, so they are replaced. A page the
    10 Sep test used stays offered, and is not offered twice.
    """
    candidates = judge(hits, row.disc)
    verdict = decide(candidates, row.disc)
    await db.execute(
        delete(SpecCandidate).where(
            SpecCandidate.lookup_id == lookup.id, SpecCandidate.origin == "search"
        )
    )
    kept = (
        await db.scalars(select(SpecCandidate.url).where(SpecCandidate.lookup_id == lookup.id))
    ).all()
    for candidate in candidates:
        if not any(same_page(candidate.url, url) for url in kept):
            db.add(_candidate_row(lookup.id, candidate))

    lookup.status = verdict.decision
    lookup.search_query = query
    lookup.searched_utc = now
    lookup.run_id = run.id
    lookup.note = verdict.note
    if verdict.decision == "accepted":
        lookup.accepted_url = verdict.url
        lookup.how = "auto"
        lookup.decided_utc = now
        run.settled_again += 1
    else:
        lookup.accepted_url = None
        lookup.how = None
    run.searched += 1
    run.searched_again += 1
    _count_outcome(run, lookup)
    return lookup


async def search_phase(
    db: AsyncSession, run: SpecRun, searcher: Searcher, *, clock: Callable[[], datetime]
) -> PhaseEnd:
    """Search for discs until the budget or the list runs out.

    Discs whose film was identified since their search go first (Batch T10): there are few,
    and each is a disc Craig would otherwise have to settle by hand.
    """
    if not searcher.configured:
        return PhaseEnd("not_configured", NOT_CONFIGURED)
    trashed = await trashed_specs(db)
    # One more than the budget could reach, to know whether the budget cut the list.
    reach = run.search_budget + 1
    again = await discs_to_search_again(db, limit=reach)
    fresh = await discs_to_search(
        db, limit=max(reach - len(again), 0), first={movie_id for movie_id, _ in trashed}
    )
    work: list[tuple[SpecLookup | None, DiscRow]] = [*again, *((None, row) for row in fresh)]
    cut_short = len(work) > run.search_budget
    work = work[: run.search_budget]
    failures_in_a_row = 0
    for lookup, row in work:
        if searcher.search_calls + searcher.attempts_per_search > run.search_budget:
            return PhaseEnd("budget")
        query = search_query(row.disc.title, row.format_code)
        try:
            hits = await searcher.search(query)
        except BraveNotConfigured:
            return PhaseEnd("not_configured", NOT_CONFIGURED)
        except BraveError as exc:
            failures_in_a_row += 1
            run.searches = searcher.search_calls
            run.last_error = f"{row.disc.title} ({row.format_code}): {exc}"
            await db.commit()
            if exc.status_code in (401, 403, 429) or failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                return PhaseEnd("failed", run.last_error)
            continue
        failures_in_a_row = 0
        if lookup is None:
            await record_search(
                db, run, row, query, hits, trashed.get((row.movie_id, row.format_code)), clock()
            )
        else:
            await record_search_again(db, run, lookup, row, query, hits, clock())
        run.searches = searcher.search_calls
        run.heartbeat_utc = clock()
        await db.commit()
    return PhaseEnd("budget" if cut_short else "done")


async def redecide_queue(db: AsyncSession, run: SpecRun, *, clock: Callable[[], datetime]) -> int:
    """Look again at discs the matcher left for Craig, with the matcher as it is now.

    No new searches: the stored results are judged again. Only the matcher's own reasons are
    reconsidered (several UK editions, no UK page matched, and, once identification has given
    the film one, no year). A disc Craig has acted on, or one whose page failed its year
    check, stays where it is, so a rejected page is never chosen again by this.
    """
    fmt, conditions = _in_scope()
    rows = (
        await db.execute(
            select(SpecLookup, CollectionItem, Movie, fmt)
            .join(CollectionItem, CollectionItem.id == SpecLookup.collection_item_id)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(
                SpecLookup.status == "needs_you",
                SpecLookup.decided_by.is_(None),
                CollectionItem.specs_source_url.is_(None),
                *conditions,
            )
        )
    ).all()
    settled = 0
    for lookup, item, movie, code in rows:
        note = lookup.note or ""
        # Batch T9: a film identified since its disc was searched has a year now, and often
        # a corrected title, so the matcher's "no year" reason is worth another look too.
        undated_then = note.startswith("This film has no year") and movie.year is not None
        if not (note.startswith("No UK page") or "UK editions match" in note or undated_then):
            continue
        stored = list(
            (
                await db.scalars(
                    select(SpecCandidate)
                    .where(SpecCandidate.lookup_id == lookup.id, SpecCandidate.origin == "search")
                    .order_by(SpecCandidate.rank)
                )
            ).all()
        )
        row = DiscRow(
            item_id=item.id,
            movie_id=movie.id,
            title=movie.title,
            identified=movie.tmdb_id is not None,
            year=movie.year,
            format_code=code,
            grouping=item.sub_category,
        )
        judged = judge([SearchHit(c.url, c.title, c.snippet or "") for c in stored], row.disc)
        verdicts = {candidate.url: candidate.matches for candidate in judged}
        for candidate in stored:
            candidate.matches = verdicts.get(candidate.url, candidate.matches)
        verdict = decide(judged, row.disc)
        if verdict.decision == "accepted":
            lookup.status = "accepted"
            lookup.accepted_url = verdict.url
            lookup.how = "auto"
            lookup.decided_utc = clock()
            lookup.note = "Matched on a second look at the same search results."
            settled += 1
    run.accepted += settled
    await db.commit()
    return settled


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _send_back(lookup: SpecLookup, note: str) -> None:
    """Return a disc to Craig's queue, with the reason. Its page is no longer chosen."""
    lookup.status = "needs_you"
    lookup.accepted_url = None
    lookup.how = None
    lookup.note = note


async def fetch_phase(
    db: AsyncSession,
    run: SpecRun,
    client: httpx.AsyncClient,
    *,
    clock: Callable[[], datetime],
    pause: float = MIN_INTERVAL_SECONDS,
) -> PhaseEnd:
    """Fetch accepted pages under #110's rules."""
    lookups = list(
        (
            await db.execute(
                select(SpecLookup)
                .where(SpecLookup.status == "accepted")
                .order_by(SpecLookup.decided_utc.asc().nulls_last(), SpecLookup.id)
                .limit(run.fetch_budget + 1)
            )
        ).scalars()
    )
    over_budget = len(lookups) > run.fetch_budget
    lookups = lookups[: run.fetch_budget]
    failures_in_a_row = 0
    requested = False
    for lookup in lookups:
        item = await db.get(CollectionItem, lookup.collection_item_id)
        url = lookup.accepted_url
        if item is None or item.deleted_at is not None or url is None:
            _send_back(lookup, "The disc is no longer in the collection.")
            lookup.status = "skipped"
            await db.commit()
            continue
        if item.specs_source_url:
            lookup.status = "done"
            lookup.note = "This disc already had specs."
            await db.commit()
            continue
        if not is_release_url(url):
            _send_back(lookup, "That address is not a Blu-ray.com release page.")
            await db.commit()
            continue
        if requested and pause:
            await asyncio.sleep(pause)
        requested = True

        try:
            page = await fetch_page(client, url, db, pause=pause)
        except IntegrationHalted as exc:
            run.last_error = f"The Blu-ray.com integration is halted: {exc}"
            await db.commit()
            return PhaseEnd("halted", run.last_error)
        except OutOfBounds:
            _send_back(lookup, "That address is not a Blu-ray.com release page.")
            await db.commit()
            continue
        except PageMoved as exc:
            # Batch U1: a page sent anywhere but its own new address goes straight back to
            # Craig, rather than after three batches. It still counts towards stopping the
            # batch, so a site sending every page elsewhere costs five discs, not 150.
            _send_back(lookup, f"{exc.reason} Pick the right page, or skip.")
            lookup.last_error = exc.reason[:500]
            run.sent_back += 1
            failures_in_a_row += 1
            run.heartbeat_utc = clock()
            await db.commit()
            if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                message = f"Blu-ray.com failed {failures_in_a_row} times in a row."
                return PhaseEnd("failed", message)
            continue
        except httpx.HTTPError as exc:
            lookup.attempts += 1
            lookup.last_error = str(exc)[:500] or type(exc).__name__
            run.fetch_failed += 1
            failures_in_a_row += 1
            if lookup.attempts >= MAX_FETCH_ATTEMPTS:
                _send_back(lookup, f"The page would not load after {lookup.attempts} tries.")
            await db.commit()
            if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                message = f"Blu-ray.com failed {failures_in_a_row} times in a row."
                return PhaseEnd("failed", message)
            continue

        failures_in_a_row = 0
        run.fetched += 1
        now = clock()
        if page.url != url:
            # Batch U1: the page moved to a new address for the same release. That address
            # is the disc's page from now on, and its specs' source.
            url = canonical_release_url(page.url)
            lookup.accepted_url = url
        if lookup.how == "auto":
            movie = await db.get(Movie, item.movie_id)
            film_year = movie.year if movie is not None else None
            page_year = extract_year(page.html)
            reason: str | None = None
            if film_year is None:
                reason = "The film has no year to check the page against"
            elif page_year is None:
                reason = "The page shows no year to check"
            elif abs(page_year - film_year) > YEAR_TOLERANCE:
                reason = f"The page is for a {page_year} film and this one is from {film_year}"
            if reason is not None:
                _send_back(lookup, f"{reason}, so its specs were not used. Pick the right page.")
                run.sent_back += 1
                run.heartbeat_utc = now
                await db.commit()
                continue

        if await apply_specs(db, item, page.html, url=url, now=now):
            lookup.status = "done"
            lookup.fetched_utc = now
            lookup.last_error = None
            run.applied += 1
            # Batch U2: the page names the disc's edition only when it is certainly the copy.
            await fill_edition(db, lookup, item)
        else:
            _send_back(lookup, "That page had no specs to read. Pick another, or skip.")
            run.sent_back += 1
        run.heartbeat_utc = now
        await db.commit()
    return PhaseEnd("budget" if over_budget else "done")


# ---------------------------------------------------------------------------
# Editions — Batch U2, `DECISIONS.md` #220
# ---------------------------------------------------------------------------


def _looked_up_as(item: CollectionItem) -> str | None:
    """The format a disc is looked up as, as :func:`_format_sql` says: 4K before Blu-ray."""
    return next((code for code in BACKFILL_FORMATS if code in (item.formats or [])), None)


async def fill_edition(
    db: AsyncSession, lookup: SpecLookup, item: CollectionItem
) -> SettledEdition | None:
    """Write a disc's edition from its settled page, when that page is certainly the copy and
    names one. Never over an edition already there, typed or filled."""
    code = _looked_up_as(item)
    movie = await db.get(Movie, item.movie_id)
    if item.edition is not None or code is None or movie is None:
        return None
    row = DiscRow(
        item_id=item.id,
        movie_id=movie.id,
        title=movie.title,
        identified=movie.tmdb_id is not None,
        year=movie.year,
        format_code=code,
        grouping=item.sub_category,
    )
    found = await settled_edition(db, lookup, row.disc)
    if found is None or found.edition is None:
        return None
    item.edition = found.edition
    logger.info("edition_filled", item_id=str(item.id), kind=found.kind, edition=found.edition)
    return found


@dataclass(frozen=True)
class EditionFound:
    """A settled disc with no edition whose page is certainly the copy."""

    item_id: uuid.UUID
    title: str
    format_code: str
    kind: EditionKind
    #: ``None`` when the page is a plain release, or its name is not known.
    edition: str | None


async def editions_to_fill(db: AsyncSession) -> list[EditionFound]:
    """Every settled disc without an edition whose page is certainly the copy. Reads only.

    Batch U2's one-off backfill, for the discs settled before editions existed; each batch
    since fills its own as it settles them.
    """
    fmt, conditions = _in_scope()
    rows = (
        await db.execute(
            select(SpecLookup, CollectionItem, Movie, fmt)
            .join(CollectionItem, CollectionItem.id == SpecLookup.collection_item_id)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(SpecLookup.status == "done", CollectionItem.edition.is_(None), *conditions)
            .order_by(Movie.title, CollectionItem.id)
        )
    ).all()
    found: list[EditionFound] = []
    for lookup, item, movie, code in rows:
        row = DiscRow(
            item_id=item.id,
            movie_id=movie.id,
            title=movie.title,
            identified=movie.tmdb_id is not None,
            year=movie.year,
            format_code=code,
            grouping=item.sub_category,
        )
        settled = await settled_edition(db, lookup, row.disc)
        if settled is not None:
            found.append(EditionFound(item.id, movie.title, code, settled.kind, settled.edition))
    return found


async def fill_editions(db: AsyncSession, found: list[EditionFound]) -> int:
    """Write the editions :func:`editions_to_fill` found, into blanks only."""
    written = 0
    for entry in found:
        if entry.edition is None:
            continue
        item = await db.get(CollectionItem, entry.item_id)
        if item is not None and item.edition is None:
            item.edition = entry.edition
            written += 1
    await db.commit()
    return written


async def work_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    *,
    searcher: Searcher,
    client: httpx.AsyncClient,
    clock: Callable[[], datetime] = utcnow,
    pause: float = MIN_INTERVAL_SECONDS,
) -> SpecRun:
    """Search, then fetch, then record how the batch ended."""
    run = await db.get(SpecRun, run_id)
    if run is None or run.status != "running":
        raise ValueError(f"spec run {run_id} is not running")
    try:
        await redecide_queue(db, run, clock=clock)
        searching = await search_phase(db, run, searcher, clock=clock)
        fetching = await fetch_phase(db, run, client, clock=clock, pause=pause)

        run.searches = searcher.search_calls
        if fetching.outcome == "halted":
            run.status = "halted"
        elif "failed" in (searching.outcome, fetching.outcome):
            run.status = "stopped"
            run.last_error = fetching.message or searching.message
        elif "budget" in (searching.outcome, fetching.outcome):
            run.status = "budget_spent"
        else:
            run.status = "finished"
        if searching.outcome == "not_configured":
            run.last_error = NOT_CONFIGURED
        run.finished_utc = clock()
        run.heartbeat_utc = run.finished_utc
        await db.commit()
    except Exception as exc:
        await db.rollback()
        stopped = await db.get(SpecRun, run_id)
        if stopped is not None and stopped.status == "running":
            stopped.status = "stopped"
            stopped.finished_utc = clock()
            stopped.searches = searcher.search_calls
            stopped.last_error = f"{type(exc).__name__}: {exc}"
            await db.commit()
        raise

    logger.info(
        "spec_run_finished",
        status=run.status,
        searches=run.searches,
        accepted=run.accepted,
        queued=run.queued,
        restored=run.restored,
        fetched=run.fetched,
        applied=run.applied,
    )
    return run


async def continue_run_in_background(run_id: uuid.UUID) -> None:
    """The Disc specs page's batch, after the response has gone. Its own session and clients."""
    from src.database import AsyncSessionLocal
    from src.services.specs.search import BraveSearch

    try:
        async with AsyncSessionLocal() as db, BraveSearch() as brave, httpx.AsyncClient() as client:
            await work_run(db, run_id, searcher=brave, client=client)
    except Exception:  # noqa: BLE001 - the run records its own failure; nothing is waiting
        logger.warning("spec_run_failed", run_id=str(run_id), exc_info=True)


# ---------------------------------------------------------------------------
# Coverage and the queue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Coverage:
    discs: int
    with_specs: int
    accepted: int
    needs_you: int
    no_match: int
    skipped: int
    not_searched: int


async def coverage(db: AsyncSession) -> Coverage:
    """Where the ~1,250 Blu-ray and 4K discs stand."""
    _fmt, conditions = _in_scope()
    has_specs = CollectionItem.specs_source_url.is_not(None)
    without = ~has_specs

    def waiting(status: str) -> ColumnElement[int]:
        return func.count(CollectionItem.id).filter(without, SpecLookup.status == status)

    row = (
        await db.execute(
            select(
                func.count(CollectionItem.id),
                func.count(CollectionItem.id).filter(has_specs),
                waiting("accepted"),
                waiting("needs_you"),
                waiting("no_match"),
                waiting("skipped"),
                func.count(CollectionItem.id).filter(without, SpecLookup.id.is_(None)),
            )
            .select_from(CollectionItem)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .outerjoin(SpecLookup, SpecLookup.collection_item_id == CollectionItem.id)
            .where(*conditions)
        )
    ).one()
    discs, with_specs, accepted, needs_you, no_match, skipped, not_searched = (int(v) for v in row)
    return Coverage(discs, with_specs, accepted, needs_you, no_match, skipped, not_searched)


@dataclass(frozen=True)
class QueueEntry:
    lookup: SpecLookup
    item: CollectionItem
    movie: Movie
    format_code: str
    candidates: list[SpecCandidate]


async def queue(db: AsyncSession, *, limit: int) -> tuple[list[QueueEntry], int]:
    """Discs waiting for Craig, the ones with candidates first."""
    fmt, conditions = _in_scope()
    waiting = SpecLookup.status.in_(("needs_you", "no_match"))
    base = (
        select(SpecLookup, CollectionItem, Movie, fmt)
        .join(CollectionItem, CollectionItem.id == SpecLookup.collection_item_id)
        .join(Movie, Movie.id == CollectionItem.movie_id)
        .where(waiting, *conditions, CollectionItem.specs_source_url.is_(None))
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(
                case((SpecLookup.status == "needs_you", 0), else_=1), Movie.title, SpecLookup.id
            ).limit(limit)
        )
    ).all()
    ids = [row[0].id for row in rows]
    by_lookup: dict[uuid.UUID, list[SpecCandidate]] = {lookup_id: [] for lookup_id in ids}
    if ids:
        found = await db.scalars(
            select(SpecCandidate)
            .where(SpecCandidate.lookup_id.in_(ids))
            .order_by(SpecCandidate.matches.desc(), SpecCandidate.rank)
        )
        for candidate in found:
            by_lookup[candidate.lookup_id].append(candidate)
    entries = [
        QueueEntry(lookup, item, movie, code, by_lookup[lookup.id])
        for lookup, item, movie, code in rows
    ]
    return entries, int(total or 0)


class QueueError(ValueError):
    """The disc cannot take that decision."""


async def _waiting_lookup(db: AsyncSession, lookup_id: uuid.UUID) -> SpecLookup:
    lookup = await db.get(SpecLookup, lookup_id)
    if lookup is None:
        raise LookupError("No such disc in the queue.")
    if lookup.status not in ("needs_you", "no_match"):
        raise QueueError("This disc is no longer waiting for a decision.")
    return lookup


async def accept_page(
    db: AsyncSession, lookup_id: uuid.UUID, url: str, *, by: uuid.UUID, now: datetime | None = None
) -> SpecLookup:
    """Craig's choice: one of the candidates, or a link he pasted. The next batch fetches it."""
    if not is_release_url(url):
        raise QueueError(
            "That is not a Blu-ray.com release page. Paste an address like "
            "https://www.blu-ray.com/movies/Heat-Blu-ray/12345/."
        )
    lookup = await _waiting_lookup(db, lookup_id)
    page = canonical_release_url(url)
    offered = await db.scalar(
        select(func.count())
        .select_from(SpecCandidate)
        .where(SpecCandidate.lookup_id == lookup.id, SpecCandidate.url == page)
    )
    lookup.status = "accepted"
    lookup.accepted_url = page
    lookup.how = "confirmed" if offered else "pasted"
    lookup.decided_by = by
    lookup.decided_utc = now or utcnow()
    lookup.attempts = 0
    lookup.last_error = None
    lookup.note = "Chosen by hand. The next batch fetches it."
    await db.commit()
    return lookup


async def skip_disc(
    db: AsyncSession, lookup_id: uuid.UUID, *, by: uuid.UUID, now: datetime | None = None
) -> SpecLookup:
    """Craig's other choice: no specs for this disc."""
    lookup = await _waiting_lookup(db, lookup_id)
    lookup.status = "skipped"
    lookup.decided_by = by
    lookup.decided_utc = now or utcnow()
    lookup.note = "Skipped by hand."
    await db.commit()
    return lookup
