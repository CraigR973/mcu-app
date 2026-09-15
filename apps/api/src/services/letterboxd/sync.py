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
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx
import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.letterboxd_sync import LetterboxdSync
from src.models.profile import Profile
from src.services.letterboxd.diary import DiaryParseError
from src.services.letterboxd.feed import FEED_ENTRY_CAP, fetch_feed
from src.services.letterboxd.importer import run_import

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
) -> SyncResult:
    """Fetch this person's diary feed and write whatever is new.

    **Writes by default**, unlike S8's importer — and the asymmetry is deliberate. A file
    import is a 1,555-row operation against history going back to 2013; a sync is at most
    50 recent entries, of which a healthy run writes a handful. The dangerous default is
    the one attached to the dangerous operation.

    **Identification is not attempted here**, even though every feed entry carries a TMDB
    id. A sync that rewrote `movies` rows on a schedule would make an operation the owner
    was asked to authorise in S8 happen quietly and repeatedly instead.
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

    report = await run_import(db, profile, entries, dry_run=False)

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
