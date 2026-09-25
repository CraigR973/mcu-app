"""The live run: applying a dry run's plan — Batch T9.

**It applies exactly what Craig read**, film by film, after checking each film still is what
the dry run saw: live, unidentified, with the same title and a disc on the shelf. A film
that changed, or that Craig has already decided on the Identify films page, is left alone
and counted.

- **identify**: TMDB's full record is fetched and applied, audited, with the old title kept
  as an alias. If the collection has gained the film since the dry run, it waits for Craig
  instead, because a merge is never automatic.
- **ask**: the film waits on the Identify films page with the candidates and the reason.
- **set_aside**: marked as a TV series or not a film, audited, and out of the queue.

Each film commits on its own, so a failure part-way keeps everything before it. The run
records the Brave searches the dry run spent, which is when they count against the month's
ceiling that T7's batches share.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Protocol

import httpx
import structlog
from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import CollectionItem, owned_copy
from src.models.identify import IdentifyLookup, IdentifyRun
from src.models.movie import Movie
from src.services.identification import IdentifyError, MergeNeeded, identify_film, set_aside
from src.services.identify.plan import Item, Plan
from src.tmdb.models import Movie as TmdbMovie

logger = structlog.get_logger(__name__)

RUN_STALE_AFTER = timedelta(minutes=30)
MAX_FAILURES_IN_A_ROW = 5


class FullRecord(Protocol):
    """What applying needs from TMDB: one film's full record."""

    async def get_movie_full(self, movie_id: int) -> TmdbMovie: ...


class RunInProgress(RuntimeError):
    """Another live run holds the claim."""


def candidates_json(item: Item) -> list[dict[str, Any]]:
    """The offered films as the Identify films page stores and shows them."""
    return [asdict(candidate) for candidate in item.candidates]


async def _abandon_stale(db: AsyncSession, now: datetime) -> None:
    await db.execute(
        update(IdentifyRun)
        .where(IdentifyRun.status == "running", IdentifyRun.heartbeat_utc < now - RUN_STALE_AFTER)
        .values(
            status="abandoned",
            finished_utc=now,
            last_error="Nothing heard from it for 30 minutes; its process probably stopped.",
        )
    )
    await db.commit()


async def start_run(
    db: AsyncSession,
    plan: Plan,
    *,
    trigger: str = "job",
    by: uuid.UUID | None = None,
    earlier_searches: int = 0,
) -> IdentifyRun:
    """Claim the one running slot and record the plan's Brave spend, with any spent by
    earlier dry runs that were never applied, so the monthly ceiling sees all of it."""
    now = utcnow()
    await _abandon_stale(db, now)
    run = IdentifyRun(
        id=uuid.uuid4(),
        trigger=trigger,
        status="running",
        started_by=by,
        started_utc=now,
        heartbeat_utc=now,
        planned_utc=datetime.fromisoformat(plan.made_utc),
        searches=plan.brave_searches + max(earlier_searches, 0),
        films=len(plan.items),
        identified=0,
        queued=0,
        set_aside=0,
        unchanged=0,
        failed=0,
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise RunInProgress("Another identification run is in progress.") from exc
    return run


async def _still_as_planned(db: AsyncSession, item: Item) -> tuple[Movie | None, str | None]:
    """The film, if it is still the one the dry run saw; otherwise why not."""
    movie = await db.get(Movie, uuid.UUID(item.movie_id))
    if movie is None or movie.deleted_at is not None:
        return None, "The film is no longer in the collection."
    if movie.tmdb_id is not None:
        return None, "The film was identified after the dry run."
    if movie.title != item.title:
        return None, "The film's title changed after the dry run."
    on_shelf = await db.scalar(
        select(exists().where(CollectionItem.movie_id == movie.id, owned_copy()))
    )
    if not on_shelf:
        return None, "The film has no disc on the shelf any more."
    decided = await db.scalar(
        select(IdentifyLookup).where(
            IdentifyLookup.movie_id == movie.id, IdentifyLookup.decided_by.is_not(None)
        )
    )
    if decided is not None and decided.status in ("skipped", "set_aside"):
        return None, "Craig has already decided this film."
    return movie, None


async def _queue(db: AsyncSession, movie: Movie, item: Item, run: IdentifyRun, note: str) -> None:
    lookup = await db.scalar(select(IdentifyLookup).where(IdentifyLookup.movie_id == movie.id))
    if lookup is None:
        lookup = IdentifyLookup(id=uuid.uuid4(), movie_id=movie.id)
        db.add(lookup)
    lookup.status = "needs_you"
    lookup.set_aside_as = None
    lookup.how = None
    lookup.tmdb_id = None
    lookup.note = note
    lookup.evidence = list(item.evidence)
    lookup.candidates = candidates_json(item)
    lookup.proposed_tmdb_id = item.chosen.tmdb_id if item.chosen else None
    lookup.run_id = run.id


async def apply_item(db: AsyncSession, item: Item, run: IdentifyRun, tmdb: FullRecord) -> str:
    """Apply one film's outcome. Returns what happened: identified, queued, set_aside or
    unchanged. Does not commit."""
    movie, why_not = await _still_as_planned(db, item)
    if movie is None:
        logger.info("identify_left_alone", title=item.title, reason=why_not)
        return "unchanged"

    if item.outcome == "set_aside" and item.set_aside_as:
        await set_aside(db, movie, item.set_aside_as, by=None, note=item.reason, run_id=run.id)
        return "set_aside"

    if item.outcome == "identify" and item.chosen is not None:
        record = await tmdb.get_movie_full(item.chosen.tmdb_id)
        try:
            await identify_film(
                db,
                movie,
                record,
                by=None,
                how="auto",
                evidence=item.evidence,
                allow_merge=False,
                run_id=run.id,
            )
        except MergeNeeded as exc:
            await _queue(
                db,
                movie,
                item,
                run,
                f"{exc} The collection gained this film after the dry run.",
            )
            return "queued"
        return "identified"

    await _queue(db, movie, item, run, item.reason)
    return "queued"


async def apply_plan(
    db: AsyncSession,
    plan: Plan,
    tmdb: FullRecord,
    *,
    run: IdentifyRun,
    clock: Callable[[], datetime] = utcnow,
    progress: Callable[[int, int, Item, str], None] | None = None,
) -> IdentifyRun:
    """Apply every film in the plan, committing each on its own."""
    failures_in_a_row = 0
    for index, item in enumerate(plan.items, start=1):
        try:
            outcome = await apply_item(db, item, run, tmdb)
            if outcome == "identified":
                run.identified += 1
            elif outcome == "queued":
                run.queued += 1
            elif outcome == "set_aside":
                run.set_aside += 1
            else:
                run.unchanged += 1
            run.heartbeat_utc = clock()
            await db.commit()
            failures_in_a_row = 0
        except (httpx.HTTPError, IdentifyError, IntegrityError) as exc:
            await db.rollback()
            failures_in_a_row += 1
            fresh = await db.get(IdentifyRun, run.id)
            if fresh is not None:
                run = fresh
            run.failed += 1
            run.last_error = f"{item.title}: {type(exc).__name__}: {exc}"[:500]
            run.heartbeat_utc = clock()
            await db.commit()
            outcome = "failed"
            logger.warning("identify_apply_failed", title=item.title, error=run.last_error)
            if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                run.status = "stopped"
                run.finished_utc = clock()
                await db.commit()
                return run
        if progress is not None:
            progress(index, len(plan.items), item, outcome)
    run.status = "finished"
    run.finished_utc = clock()
    await db.commit()
    return run
