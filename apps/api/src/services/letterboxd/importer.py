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

**Batch 40 separated identification from the already-imported skip** after step 1 of
`OWNER-ACTIONS.md` 1i ran without ``--identify`` on 2026-09-15 and left the flag
unreachable — every entry short-circuited on its viewing id before the match, so
``--identify`` reported success and identified nothing. The counts above are still the
first-run counts; on the live database that same pass now identifies the films and writes
**zero** watches (`DECISIONS.md` #197).

**66% of watches are of films they own** — the same 66% both the 100-entry RSS sample and
#160's coarser pass predicted, which is the check that the matcher behaves the same on
2,322 rows as on 100.

**Since Batch X5 (#269) two things changed.** A feed entry for a film not in the catalogue
is no longer dropped: the film gets a row of its own, with no copies, kept out of everything
that counts the collection (``owned_film``), and the watch goes on it. And this import no
longer identifies anything: its ``MatchingEngine`` step put three diary films on the wrong
owned rows (CT46-01). Identifying an owned film is T9's job (``identify_films``); a watch of
an unidentified owned film still lands on it by title, and :attr:`ImportReport.identifiable`
counts them for that job.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import httpx
import structlog
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.watch_log import WatchLog
from src.services.identification import apply_identification
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.matcher import Ambiguity, CollectionIndex, build_index, match_entry
from src.tmdb.models import Movie as TmdbMovie

log = structlog.get_logger(__name__)


class TmdbDetails(Protocol):
    """What filling in a new film's details needs. :class:`~src.tmdb.TMDBClient` is one."""

    async def get_movie_full(self, movie_id: int, language: str = ...) -> TmdbMovie: ...


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
    #: Batch X5: watches of films the feed named and the catalogue lacks, written on a film
    #: row of their own.
    matched_not_owned: int = 0
    not_in_collection: int = 0
    ambiguous: list[Ambiguity] = field(default_factory=list)
    #: Distinct owned films found carrying no ``tmdb_id``, counted **whether or not their
    #: watches were already imported**: work for identification (T9), which this import no
    #: longer does (X5).
    identifiable: dict[uuid.UUID, str] = field(default_factory=dict)
    #: Batch X5: films given a row of their own, ``tmdb_id`` to title.
    films_added: dict[int, str] = field(default_factory=dict)
    #: Of those, how many TMDB filled in (poster, cast, overview). The rest have the feed's
    #: title and year until a Sync now from the app fills them.
    films_filled: int = 0
    #: Feed films whose TMDB id belongs to a film in the Trash: left alone, said here.
    in_trash: list[str] = field(default_factory=list)
    written: int = 0

    @property
    def would_write(self) -> int:
        """Rows a real run would insert — matched, and not already present."""
        return self.matched_identified + self.matched_unidentified + self.matched_not_owned

    def summary(self) -> str:
        mode = "DRY RUN — nothing written" if self.dry_run else f"WROTE {self.written} watches"
        return (
            f"{mode}\n"
            f"  entries read           {self.entries}\n"
            f"  already imported       {self.already_imported}\n"
            f"  matched, identified    {self.matched_identified}\n"
            f"  matched, unidentified  {self.matched_unidentified}\n"
            f"  films not owned        {self.matched_not_owned} watches, "
            f"{len(self.films_added)} films\n"
            f"  ambiguous (offered)    {len(self.ambiguous)}\n"
            f"  not in the collection  {self.not_in_collection}\n"
            f"  films to identify      {len(self.identifiable)}"
        )


async def _existing_viewing_ids(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    rows = await db.scalars(
        select(WatchLog.letterboxd_viewing_id).where(
            WatchLog.user_id == user_id,
            WatchLog.letterboxd_viewing_id.is_not(None),
        )
    )
    return {value for value in rows if value is not None}


async def film_for_tmdb_id(
    db: AsyncSession,
    *,
    tmdb_id: int,
    title: str,
    year: int | None,
    index: CollectionIndex,
    tmdb: TmdbDetails | None,
    report: ImportReport,
) -> Movie | None:
    """The row for a film the catalogue lacks, made now: no copies, just the film — X5.

    Filled in from TMDB when a client is given (the app's Sync now; the backfill); the
    08:00 job has no TMDB token, so its rows carry the feed's title and year until then.
    ``None`` when a film in the Trash holds the id: ``movies.tmdb_id`` is unique, and a
    trashed film is a decision this import does not reverse.
    """
    trashed = await db.scalar(
        select(Movie.id).where(Movie.tmdb_id == tmdb_id, Movie.deleted_at.is_not(None))
    )
    if trashed is not None:
        report.in_trash.append(f"{title} ({year or '?'})")
        return None
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=year,
        media_type="film",
    )
    db.add(movie)
    await db.flush()
    index.by_tmdb_id[tmdb_id] = movie
    report.films_added[tmdb_id] = title
    if tmdb is not None:
        try:
            details = await tmdb.get_movie_full(tmdb_id)
        except (httpx.HTTPError, RuntimeError) as exc:
            # A 429 on the last try is TMDBRefused, a RuntimeError. The row keeps the feed's
            # title and year, and a later Sync now fills it in (`fill_bare_films`).
            log.warning("watched_film_details_failed", tmdb_id=tmdb_id, error=str(exc))
        else:
            movie = await apply_identification(db, movie, details)
            index.by_tmdb_id[tmdb_id] = movie
            report.films_filled += 1
    return movie


#: Films a Sync now fills in, at most: one TMDB call each, inside a request.
FILL_PER_SYNC = 20


async def fill_bare_films(
    db: AsyncSession, tmdb: TmdbDetails, *, limit: int = FILL_PER_SYNC
) -> int:
    """Fill in films only watched that still carry just the feed's title and year — X5.

    The 08:00 job adds such rows without a TMDB token; the app's Sync now, which has one,
    fills up to ``limit`` of them each time. A row is bare when it has a TMDB id, has never
    been filled (``last_tmdb_sync_utc``), and no disc of any kind points at it. Does not
    commit.
    """
    bare = list(
        await db.scalars(
            select(Movie)
            .where(
                Movie.deleted_at.is_(None),
                Movie.tmdb_id.is_not(None),
                Movie.last_tmdb_sync_utc.is_(None),
                ~exists(select(CollectionItem.id).where(CollectionItem.movie_id == Movie.id)),
            )
            .order_by(Movie.created_at)
            .limit(limit)
        )
    )
    filled = 0
    for movie in bare:
        assert movie.tmdb_id is not None
        try:
            details = await tmdb.get_movie_full(movie.tmdb_id)
        except (httpx.HTTPError, RuntimeError) as exc:
            log.warning("watched_film_details_failed", tmdb_id=movie.tmdb_id, error=str(exc))
            break
        await apply_identification(db, movie, details)
        filled += 1
    return filled


async def run_import(
    db: AsyncSession,
    profile: Profile,
    entries: list[DiaryEntry],
    *,
    dry_run: bool = True,
    tmdb: TmdbDetails | None = None,
    now: datetime | None = None,
) -> ImportReport:
    """Import one person's diary entries, from a file or the feed.

    **``dry_run`` defaults to ``True``.** A file import writes hundreds of rows on a live
    database; a signature whose default writes is one that eventually writes because
    somebody forgot an argument.

    **Idempotent on ``letterboxd_viewing_id``.** Every entry already present for this
    person writes no watch row, so a second run of the same file writes zero — and so an
    RSS sync (S5) cannot re-import a viewing this file already wrote, because the feed's
    ``guid`` wraps the same id.

    **A film the feed names and the catalogue lacks gets a row of its own** (X5), filled in
    from ``tmdb`` when one is given. A dry run creates nothing and says how many it would.
    """
    del now  # watched_at comes from the file; nothing here needs the clock
    report = ImportReport(dry_run=dry_run, entries=len(entries))

    movies = list(await db.scalars(select(Movie).where(Movie.deleted_at.is_(None))))
    index = build_index(movies)
    seen = await _existing_viewing_ids(db, profile.id)

    for entry in entries:
        already = entry.viewing_id in seen
        if already:
            report.already_imported += 1

        outcome = match_entry(entry, index)
        if outcome.ambiguity is not None:
            # **Offered, never guessed.** 28 entries across 15 distinct titles, measured
            # on the real diaries — the collection genuinely holds two `Dunkirk`s, two
            # `Titanic`s, two `Lion King`s and three `Mummy`s, and nothing in the diary
            # row says which. Each needs a person to choose.
            report.ambiguous.append(outcome.ambiguity)
            continue

        movie = outcome.movie
        if movie is None:
            if entry.tmdb_id is None:
                report.not_in_collection += 1
                continue
            if already:
                continue
            report.matched_not_owned += 1
            if dry_run:
                report.films_added.setdefault(entry.tmdb_id, entry.title)
                continue
            movie = await film_for_tmdb_id(
                db,
                tmdb_id=entry.tmdb_id,
                title=entry.title,
                year=entry.year,
                index=index,
                tmdb=tmdb,
                report=report,
            )
            if movie is None:
                continue
        elif movie.tmdb_id is None:
            report.identifiable[movie.id] = movie.title
            if not already:
                report.matched_unidentified += 1
        elif movie.tmdb_id in report.films_added:
            # A second watch of a film this run gave a row: counted as the dry run counts it.
            if not already:
                report.matched_not_owned += 1
        elif not already:
            report.matched_identified += 1

        if already or dry_run:
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
                tmdb_id=entry.tmdb_id,
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
        films_added=len(report.films_added),
    )
    return report
