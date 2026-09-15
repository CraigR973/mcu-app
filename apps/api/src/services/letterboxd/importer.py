"""Writing a diary into `watch_log` — Batch S8, snag 10b.

**What one run of this does to the live database**, measured by running *this* matcher over
both real diaries against live Neon on 2026-09-15 — 2,322 entries against 1,854 films:

==============================================  ==========  ==========
                                                  measured   #160 said
==============================================  ==========  ==========
Links straight to an owned film                        969         950
Owned but unidentified → identify **and** link         586         580
Ambiguous — offered, never guessed                  **28**       **6**
Not in the collection                                  739         786
**Watches written**                             **~1,555**      ~1,530
**Distinct films identified**                      **397**         396
==============================================  ==========  ==========

**The ambiguity count is the one real disagreement, and this matcher is the stricter of
the two** (`DECISIONS.md` #174). #160's analysis did not collapse parenthetical
disambiguators or rotate trailing articles, so `'Mummy, The (Brendan Fraser)'`,
`'Mummy, The (Original)'` and `'Mummy, The (Tom Cruise)'` looked like three unrelated
titles and a diary entry for *The Mummy* matched **none** of them — counted as "not in the
collection" rather than as a question. That is the whole of the 47-row difference in the
last row: **22 silent misses became 22 explicit questions**, and 25 more watches found a
home.

Every one of the 15 distinct ambiguities is genuine. The collection really does hold two
*Dunkirk*s, two *Titanic*s, two *Lion King*s and three *Mummy*s.

Two things follow from these numbers, and both shape the code below.

**It overwrites ~397 existing `movies` rows.** That is why the live run is the owner's and
why :func:`run_import` defaults to ``dry_run=True``: a default that writes is a default
that eventually writes by accident.

**66% of watches are of films they own** — the same 66% both the 100-entry RSS sample and
#160's coarser pass predicted, which is the check that the matcher behaves the same on
2,322 rows as on 100.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.matching import MatchingEngine
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.watch_log import WatchLog
from src.services.identification import apply_identification
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.matcher import Ambiguity, build_index, match_entry

log = structlog.get_logger(__name__)


@dataclass
class ImportReport:
    """Every count a person needs before deciding to run this for real.

    Reported identically by a dry run and a real one, so the dry run is a genuine
    rehearsal rather than a different code path that happens to print numbers.
    """

    dry_run: bool
    entries: int = 0
    #: Already present by ``letterboxd_viewing_id``. **On a second run this is everything**
    #: — the criterion that makes re-running safe.
    already_imported: int = 0
    matched_identified: int = 0
    matched_unidentified: int = 0
    not_in_collection: int = 0
    ambiguous: list[Ambiguity] = field(default_factory=list)
    #: ``(title, tmdb_id)`` for each film this run filled in. Reported per film, as the
    #: criterion asks, rather than as a single total.
    identified: list[tuple[str, int]] = field(default_factory=list)
    identification_failures: list[str] = field(default_factory=list)
    written: int = 0

    @property
    def would_write(self) -> int:
        """Rows a real run would insert — matched, and not already present."""
        return self.matched_identified + self.matched_unidentified

    def summary(self) -> str:
        mode = "DRY RUN — nothing written" if self.dry_run else f"WROTE {self.written} watches"
        return (
            f"{mode}\n"
            f"  entries read           {self.entries}\n"
            f"  already imported       {self.already_imported}\n"
            f"  matched, identified    {self.matched_identified}\n"
            f"  matched, unidentified  {self.matched_unidentified}\n"
            f"  ambiguous (offered)    {len(self.ambiguous)}\n"
            f"  not in the collection  {self.not_in_collection}\n"
            f"  films identified       {len(self.identified)}"
        )


async def _existing_viewing_ids(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    rows = await db.scalars(
        select(WatchLog.letterboxd_viewing_id).where(
            WatchLog.user_id == user_id,
            WatchLog.letterboxd_viewing_id.is_not(None),
        )
    )
    return {value for value in rows if value is not None}


async def _resolve_tmdb_id(
    entry: DiaryEntry, engine: MatchingEngine, report: ImportReport
) -> int | None:
    """Work out which TMDB film a diary entry is, when the entry does not say.

    **The RSS feed says; a CSV never does.** `tmdb:movieId` is on 100 of 100 feed entries
    (`DECISIONS.md` #158) and on none of the 2,322 retrieved rows, so a file import has to
    search — which means the same care Batch 4's collection import needed.

    **A guess is refused, not lowered.** `MatchingEngine` already reports `ambiguous` when
    the leading candidate ties with films that are not plausibly the same film, and a tie
    there is broken by TMDB *popularity* rather than by anything in the diary row
    (`DECISIONS.md` #31). Identification rewrites title, year, poster, runtime and cast on
    a row that already exists, so being wrong is expensive and silent.
    """
    if entry.tmdb_id is not None:
        return entry.tmdb_id

    query = entry.title if entry.year is None else f"{entry.title} ({entry.year})"
    try:
        result = await engine.match(query)
    except httpx.HTTPError as exc:
        report.identification_failures.append(f"{entry.title}: TMDB search failed — {exc}")
        return None

    if result.ambiguous or not result.matched or not result.candidates:
        report.identification_failures.append(
            f"{entry.title} ({entry.year or '?'}): no confident TMDB match — left unidentified"
        )
        return None
    return result.candidates[0].tmdb_id


async def _identify(
    db: AsyncSession,
    movie: Movie,
    entry: DiaryEntry,
    engine: MatchingEngine,
    report: ImportReport,
) -> Movie:
    """Fill in a film the April import never resolved — `tmdb_id`, year, poster, runtime
    and cast — and report it by name.

    Reuses `services/identification.py`, which is the same code
    `POST /movies/{id}/identify` runs, so an imported identification and a hand-made one
    cannot drift apart. **It may return a *different* row than it was given**: if the
    collection already holds this TMDB id the two are merged, because `movies.tmdb_id` is
    unique and two rows would split one film's discs and watches between them.
    """
    tmdb_id = await _resolve_tmdb_id(entry, engine, report)
    if tmdb_id is None:
        return movie
    try:
        tmdb_movie = await engine.tmdb.get_movie_full(tmdb_id)
    except httpx.HTTPError as exc:
        report.identification_failures.append(f"{entry.title}: TMDB {tmdb_id} — {exc}")
        return movie
    target = await apply_identification(db, movie, tmdb_movie)
    if target.tmdb_id is not None:
        report.identified.append((target.title, target.tmdb_id))
    return target


async def run_import(
    db: AsyncSession,
    profile: Profile,
    entries: list[DiaryEntry],
    *,
    dry_run: bool = True,
    engine: MatchingEngine | None = None,
    now: datetime | None = None,
) -> ImportReport:
    """Import one person's diary.

    **``dry_run`` defaults to ``True``.** This writes ~1,530 rows and overwrites 396
    existing ``movies`` rows on a live database; a signature whose default writes is one
    that eventually writes because somebody forgot an argument.

    **Idempotent on ``letterboxd_viewing_id``.** Every entry already present for this
    person is skipped, so a second run of the same file writes zero rows — and so an RSS
    sync (S5) cannot re-import a viewing this file already wrote, because the feed's
    ``guid`` wraps the same id.
    """
    del now  # watched_at comes from the file; nothing here needs the clock
    report = ImportReport(dry_run=dry_run, entries=len(entries))

    movies = list(await db.scalars(select(Movie).where(Movie.deleted_at.is_(None))))
    index = build_index(movies)
    seen = await _existing_viewing_ids(db, profile.id)

    for entry in entries:
        if entry.viewing_id in seen:
            report.already_imported += 1
            continue

        outcome = match_entry(entry, index)
        if outcome.ambiguity is not None:
            # **Offered, never guessed.** 28 entries across 15 distinct titles, measured
            # on the real diaries — the collection genuinely holds two `Dunkirk`s, two
            # `Titanic`s, two `Lion King`s and three `Mummy`s, and nothing in the diary
            # row says which. Each needs a person to choose.
            report.ambiguous.append(outcome.ambiguity)
            continue
        if outcome.movie is None:
            report.not_in_collection += 1
            continue

        movie = outcome.movie
        if outcome.identifies:
            report.matched_unidentified += 1
            # **Identification is opt-in even on a real run.** Writing watches is additive
            # and reversible; this rewrites rows that already exist and merges two into
            # one where the collection holds both. Different-sized decisions, different
            # flags — see `scripts/import_watch_history.py`.
            if not dry_run and engine is not None:
                movie = await _identify(db, movie, entry, engine, report)
        else:
            report.matched_identified += 1

        if dry_run:
            continue

        db.add(
            WatchLog(
                id=uuid.uuid4(),
                movie_id=movie.id,
                user_id=profile.id,
                watched_at=entry.watched_at,
                is_rewatch=entry.is_rewatch,
                personal_rating=entry.rating,
                letterboxd_viewing_id=entry.viewing_id,
            )
        )
        # Guarding against a repeated id *within one file* as well as across runs. The two
        # retrieved diaries have none, but a file assembled by hand could.
        seen.add(entry.viewing_id)
        report.written += 1

    if not dry_run:
        await db.commit()

    log.info(
        "letterboxd_import",
        dry_run=dry_run,
        entries=report.entries,
        written=report.written,
        already=report.already_imported,
        ambiguous=len(report.ambiguous),
        identified=len(report.identified),
    )
    return report
