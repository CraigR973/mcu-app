"""Keeping the watch history current — Batch S5, snag 10a.

**This module owns none of the hard parts.** The feed reader turns XML into
:class:`~.diary.DiaryEntry`; S8's matcher decides which film each one is; S8's importer
writes the rows and refuses the ambiguous ones. All that is left is: fetch, hand over,
record what happened.

That is the whole reason S8 runs before S5 (`DECISIONS.md` #161). **There is no second
matching implementation here**, which is the criterion — building it twice is the waste
the ordering exists to avoid.

**Recording the run is not bookkeeping.** The feed returns 50 entries and no more: Mark
cycles his in about eight weeks, so a sync that quietly stops running loses history
without failing. `letterboxd_syncs` is how "when did this last run" becomes answerable.

**Since Batch X5 it also runs weekly by itself** (:func:`sync_due`, inside the 08:00
reminders job, ``trigger = cron``), and a feed entry for a film not in the catalogue gives
the film a row of its own rather than being dropped (#269).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.letterboxd_sync import LetterboxdSync
from src.models.profile import Profile
from src.services.letterboxd.diary import DiaryParseError
from src.services.letterboxd.feed import FEED_ENTRY_CAP, fetch_feed
from src.services.letterboxd.importer import TmdbDetails, run_import

log = structlog.get_logger(__name__)


class SyncNotConfigured(Exception):
    """This person has not told the app their Letterboxd username."""


@dataclass(frozen=True)
class SyncResult:
    run: LetterboxdSync
    #: Ambiguities this run declined to guess, described for a person to settle.
    ambiguities: list[str]
    #: True when the feed came back full. **Not an error — a warning about cadence.** 50
    #: is Letterboxd's cap, so a full feed means entries may have fallen off the end since
    #: the last sync, and the interval is too long rather than the sync being wrong.
    feed_was_full: bool


async def last_sync(db: AsyncSession, user_id: uuid.UUID) -> LetterboxdSync | None:
    """The most recent run for this person, finished or not.

    The result is bound to a typed name rather than returned straight from ``scalar``:
    CI's mypy resolves that call as ``Any`` and ``warn_no_any_return`` makes the implicit
    version a red gate, while this machine's does not notice (`STATUS.md` gotcha 21).
    """
    run: LetterboxdSync | None = await db.scalar(
        select(LetterboxdSync)
        .where(LetterboxdSync.user_id == user_id)
        .order_by(desc(LetterboxdSync.started_at_utc))
        .limit(1)
    )
    return run


async def sync_watch_history(
    db: AsyncSession,
    profile: Profile,
    *,
    trigger: str = "manual",
    client: httpx.AsyncClient | None = None,
    tmdb: TmdbDetails | None = None,
) -> SyncResult:
    """Fetch this person's diary feed and write whatever is new.

    **Writes by default**, unlike S8's importer — and the asymmetry is deliberate. A file
    import is a 1,555-row operation against history going back to 2013; a sync is at most
    50 recent entries, of which a healthy run writes a handful. The dangerous default is
    the one attached to the dangerous operation.

    **Identification is not attempted here**, even though every feed entry carries a TMDB
    id. A sync that rewrote `movies` rows on a schedule would make an operation the owner
    was asked to authorise in S8 happen quietly and repeatedly instead. **A film the feed
    names and the catalogue lacks gets a new row** (X5), which rewrites nothing; ``tmdb``
    fills its details in when given (the app's Sync now; the 08:00 job has no token).
    """
    if not profile.letterboxd_username:
        raise SyncNotConfigured(f"{profile.display_name} has no Letterboxd username set")

    run = LetterboxdSync(
        id=uuid.uuid4(),
        user_id=profile.id,
        started_at_utc=utcnow(),
        trigger=trigger,
    )
    db.add(run)
    await db.flush()

    try:
        entries = await fetch_feed(profile.letterboxd_username, client=client)
    except (httpx.HTTPError, DiaryParseError) as exc:
        # The row stays, with the reason on it. A sync that failed and left no trace is
        # indistinguishable from one that never ran — which is the thing the 50-entry cap
        # makes expensive.
        run.finished_at_utc = utcnow()
        run.error = f"{type(exc).__name__}: {exc}"
        await db.commit()
        log.warning("letterboxd_sync_failed", user=str(profile.id), error=run.error)
        return SyncResult(run=run, ambiguities=[], feed_was_full=False)

    report = await run_import(db, profile, entries, dry_run=False, tmdb=tmdb)

    run.finished_at_utc = utcnow()
    run.entries = report.entries
    run.written = report.written
    run.already_imported = report.already_imported
    run.ambiguous = len(report.ambiguous)
    run.not_in_collection = report.not_in_collection
    await db.commit()

    log.info(
        "letterboxd_sync",
        user=str(profile.id),
        trigger=trigger,
        entries=run.entries,
        written=run.written,
        already=run.already_imported,
    )
    return SyncResult(
        run=run,
        ambiguities=[item.describe() for item in report.ambiguous],
        feed_was_full=len(entries) >= FEED_ENTRY_CAP,
    )


#: How often the 08:00 job syncs each person (X5): weekly, so a 50-entry feed never runs out
#: between syncs even at Mark's pace of about eight weeks per 50. Six and a half days, so a
#: daily job whose start drifts by minutes still syncs on the seventh day, not the eighth.
SYNC_EVERY = timedelta(days=6, hours=12)


async def sync_due(
    db: AsyncSession, *, now: datetime, client: httpx.AsyncClient | None = None
) -> list[SyncResult]:
    """Sync everyone with a username whose last sync, by any trigger, is a week old.

    A failure is recorded on that person's run row, and never stops the other person's
    sync or the job around it (`run_reminders.py`).

    **Nothing ORM-backed is read after a rollback** (AG1, CR49-01). A rollback expires every
    row the session holds, and under async SQLAlchemy reading an expired attribute raises
    ``MissingGreenlet``: the handler used to read ``person.id`` after its rollback, which
    masked the first error, skipped the next person and stopped the 08:00 job. So each
    person's id and name are taken as plain values before any of them is synced, the
    profile is read afresh for its own sync, and a failure is written on a run row of its
    own and committed, so the person is not left due for the same crash every morning.
    """
    people = [
        (row.id, row.display_name)
        for row in (
            await db.execute(
                select(Profile.id, Profile.display_name)
                .where(Profile.letterboxd_username.is_not(None), Profile.letterboxd_username != "")
                .order_by(Profile.display_name)
            )
        ).all()
    ]
    results: list[SyncResult] = []
    for person_id, name in people:
        last = await last_sync(db, person_id)
        if last is not None and last.started_at_utc > now - SYNC_EVERY:
            continue
        started = utcnow()
        try:
            person = await db.get(Profile, person_id, populate_existing=True)
            if person is None:
                continue
            result = await sync_watch_history(db, person, trigger="cron", client=client)
            # Committed; detached so a later person's rollback cannot expire it before the
            # job prints it.
            db.expunge(result.run)
            results.append(result)
        except Exception as exc:  # noqa: BLE001 - one person's failure must not stop the job
            error = f"{type(exc).__name__}: {exc}"[:500]
            await db.rollback()
            log.warning("letterboxd_weekly_sync_failed", user=str(person_id), exc_info=True)
            failed = await _record_failure(db, person_id, started=started, error=error)
            if failed is not None:
                results.append(SyncResult(run=failed, ambiguities=[], feed_was_full=False))
            else:
                log.warning("letterboxd_weekly_sync_unrecorded", user=str(person_id), name=name)
    return results


async def _record_failure(
    db: AsyncSession, person_id: uuid.UUID, *, started: datetime, error: str
) -> LetterboxdSync | None:
    """Write a failed run on a committed row of its own, or ``None`` if even that fails.

    The rollback erased the row the sync had only flushed, so without this a failed person
    leaves no trace and stays due, and the same crash repeats every morning.
    """
    run = LetterboxdSync(
        id=uuid.uuid4(),
        user_id=person_id,
        started_at_utc=started,
        finished_at_utc=utcnow(),
        trigger="cron",
        error=error,
    )
    try:
        db.add(run)
        await db.commit()
        db.expunge(run)
    except Exception:  # noqa: BLE001 - the job carries on; the log line is the trace
        await db.rollback()
        return None
    return run
