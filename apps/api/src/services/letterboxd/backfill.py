"""Every dated diary entry not yet recorded — Batch X5, Craig's decision of 11 Oct (#269).

The September import (S8) wrote a watch only for films in the collection, so 756 dated
viewings were never recorded: 579 of Craig's and 177 of Mark's, about 680 films, most of
them films neither person owns. Since X5 a film only watched has a row of its own, so they
can be.

**Two steps, as T9's identification is.** :func:`plan_backfill` writes nothing: for each
entry it decides one of four things and keeps the reason. :func:`apply_backfill` writes
that exact plan, after checking each entry is still unrecorded and each film still there.

- ``owned``: the entry's title is an owned film's, and no known year says otherwise (the
  matcher's rules, including X5's: a known year more than one apart excludes).
- ``existing``: a film already listed but not owned (a want, or a film only watched), by
  the same title rule; or the TMDB film it identifies as, owned or not.
- ``new``: a film the catalogue lacks; it gets a row, filled in from TMDB.
- ``doubtful``: two owned films answer to the title, or TMDB has no one strong match for it
  (T9's rule: one strong match, and where TMDB holds another film of that title, a year
  agreeing with this one and not the others). **Doubtful entries are not written**; they go
  to Craig as a list.

**Matched with T9's care, not ``MatchingEngine``** (CT46-01): the diary file carries a title
and the film's year and nothing else, so each distinct ``(title, year)`` goes through T9's
:class:`~src.services.identify.matcher.Identifier`, once, with no web search.
"""

from __future__ import annotations

import csv
import json
import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_item import owned_film
from src.models.movie import Movie
from src.models.watch_log import WatchLog
from src.services.identify.matcher import Identifier, Proposal
from src.services.identify.titles import parse_title
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.importer import ImportReport, TmdbDetails, film_for_tmdb_id
from src.services.letterboxd.matcher import build_index, match_entry

log = structlog.get_logger(__name__)

#: The plan file's shape. The live run refuses any other.
PLAN_VERSION = 1
ACTIONS = ("owned", "existing", "new", "doubtful")


@dataclass
class Planned:
    """One diary entry, and what the backfill will do with it."""

    viewing_id: str
    watched_at: str
    title: str
    year: int | None
    rating: str | None
    is_rewatch: bool
    line: int
    action: str
    #: ``owned`` and ``existing``: the row the watch goes on.
    movie_id: str | None = None
    #: ``existing`` and ``new``: the TMDB film the entry is; kept on the watch.
    tmdb_id: int | None = None
    #: What the row or TMDB calls it, for the report.
    film: str | None = None
    #: Why, in the words Craig reads; for ``doubtful``, what to decide.
    reason: str = ""


@dataclass
class BackfillPlan:
    person: str
    user_id: str
    entries: list[Planned] = field(default_factory=list)
    tmdb_calls: int = 0

    def counts(self) -> dict[str, int]:
        found = Counter(entry.action for entry in self.entries)
        return {action: found.get(action, 0) for action in ACTIONS}

    def films_to_add(self) -> int:
        return len({entry.tmdb_id for entry in self.entries if entry.action == "new"})

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": PLAN_VERSION,
                "person": self.person,
                "userId": self.user_id,
                "tmdbCalls": self.tmdb_calls,
                "entries": [asdict(entry) for entry in self.entries],
            },
            indent=1,
        )

    @classmethod
    def from_json(cls, raw: str) -> BackfillPlan:
        data: dict[str, Any] = json.loads(raw)
        if data.get("version") != PLAN_VERSION:
            raise ValueError(f"plan version {data.get('version')!r}, expected {PLAN_VERSION}")
        return cls(
            person=data["person"],
            user_id=data["userId"],
            tmdb_calls=int(data.get("tmdbCalls", 0)),
            entries=[Planned(**entry) for entry in data["entries"]],
        )

    def summary(self) -> str:
        counts = self.counts()
        written = counts["owned"] + counts["existing"] + counts["new"]
        return (
            f"{self.person}: {len(self.entries)} entries not yet recorded\n"
            f"  on an owned film          {counts['owned']}\n"
            f"  on a film already listed  {counts['existing']}\n"
            f"  on a film to add          {counts['new']} ({self.films_to_add()} films)\n"
            f"  doubtful, for Craig       {counts['doubtful']}\n"
            f"  watches to write          {written}"
        )


def _planned(entry: DiaryEntry, action: str, **found: Any) -> Planned:
    return Planned(
        viewing_id=entry.viewing_id,
        watched_at=entry.watched_at.isoformat(),
        title=entry.title,
        year=entry.year,
        rating=str(entry.rating) if entry.rating is not None else None,
        is_rewatch=entry.is_rewatch,
        line=entry.line,
        action=action,
        **found,
    )


def _label(title: str, year: int | None) -> str:
    return f"{title} ({year})" if year is not None else title


def _doubt(proposal: Proposal) -> str:
    offered = ", ".join(
        f"{_label(candidate.title, candidate.year)} [tmdb {candidate.tmdb_id}]"
        for candidate in proposal.candidates[:3]
    )
    reason = proposal.reason or "TMDB has no one strong match"
    return f"{reason}{'; offered: ' + offered if offered else ''}"


async def plan_backfill(
    db: AsyncSession,
    person: tuple[uuid.UUID, str],
    entries: Sequence[DiaryEntry],
    identifier: Identifier,
    *,
    on_film: Callable[[int], None] | None = None,
) -> BackfillPlan:
    """Decide every unrecorded entry. Reads the database and TMDB; writes nothing.

    ``on_film`` is told each time another distinct film has been put to TMDB, for progress.

    ``person`` is the profile's id and name only, so the read-only role, which cannot read
    a PIN hash, can run it.
    """
    user_id, name = person
    plan = BackfillPlan(person=name, user_id=str(user_id))
    index = build_index(list(await db.scalars(select(Movie).where(Movie.deleted_at.is_(None)))))
    owned = set(await db.scalars(select(Movie.id).where(Movie.deleted_at.is_(None), owned_film())))
    recorded = set(
        await db.scalars(
            select(WatchLog.letterboxd_viewing_id).where(
                WatchLog.user_id == user_id, WatchLog.letterboxd_viewing_id.is_not(None)
            )
        )
    )
    # Everything is read; hand the connection back before minutes of TMDB searches. T9's
    # second dry run lost its plan when Neon dropped a connection held through them.
    # Nothing was written, so ending the read transaction this way changes nothing; it
    # keeps what was loaded usable, where a rollback would expire it.
    await db.commit()
    proposals: dict[tuple[str, int | None], Proposal] = {}
    for entry in entries:
        if entry.viewing_id in recorded:
            continue
        outcome = match_entry(entry, index)
        if outcome.ambiguity is not None:
            options = ", ".join(_label(m.title, m.year) for m in outcome.ambiguity.candidates)
            plan.entries.append(
                _planned(entry, "doubtful", reason=f"the collection holds several: {options}")
            )
            continue
        if outcome.movie is not None:
            movie = outcome.movie
            plan.entries.append(
                # No TMDB id on the watch: a title match is not an identification.
                _planned(
                    entry,
                    "owned" if movie.id in owned else "existing",
                    movie_id=str(movie.id),
                    film=_label(movie.title, movie.year),
                    reason="its title, and no known year against it",
                )
            )
            continue
        key = (entry.title.casefold(), entry.year)
        if key not in proposals:
            raw = entry.title if entry.year is None else f"{entry.title} ({entry.year})"
            try:
                proposals[key] = await identifier.identify(parse_title(raw))
            except httpx.HTTPError as exc:
                proposals[key] = Proposal("ask", reason=f"TMDB did not answer: {exc}")
            if on_film is not None:
                on_film(len(proposals))
        proposal = proposals[key]
        chosen = proposal.chosen
        if proposal.outcome != "identify" or chosen is None:
            plan.entries.append(_planned(entry, "doubtful", reason=_doubt(proposal)))
            continue
        listed = index.by_tmdb_id.get(chosen.tmdb_id)
        plan.entries.append(
            _planned(
                entry,
                "existing" if listed is not None else "new",
                movie_id=str(listed.id) if listed is not None else None,
                tmdb_id=chosen.tmdb_id,
                film=_label(chosen.title, chosen.year),
                reason="; ".join(proposal.evidence) or "one strong match on TMDB",
            )
        )
    plan.tmdb_calls = identifier.counters.tmdb_calls
    return plan


@dataclass
class BackfillResult:
    written: int = 0
    films_added: int = 0
    films_filled: int = 0
    #: Recorded since the plan was made (a sync, or a second apply): skipped.
    already: int = 0
    #: The planned film is gone (deleted or merged) or in the Trash: skipped, listed.
    skipped: list[str] = field(default_factory=list)


async def apply_backfill(
    db: AsyncSession, plan: BackfillPlan, tmdb: TmdbDetails | None
) -> BackfillResult:
    """Write the plan's watches, exactly; doubtful entries are not touched. Commits."""
    result = BackfillResult()
    user_id = uuid.UUID(plan.user_id)
    recorded = set(
        await db.scalars(
            select(WatchLog.letterboxd_viewing_id).where(
                WatchLog.user_id == user_id, WatchLog.letterboxd_viewing_id.is_not(None)
            )
        )
    )
    index = build_index(list(await db.scalars(select(Movie).where(Movie.deleted_at.is_(None)))))
    report = ImportReport(dry_run=False)
    for entry in plan.entries:
        if entry.action == "doubtful":
            continue
        if entry.viewing_id in recorded:
            result.already += 1
            continue
        movie: Movie | None
        if entry.action == "new":
            assert entry.tmdb_id is not None
            movie = index.by_tmdb_id.get(entry.tmdb_id)
            if movie is None:
                # The diary's title and year until TMDB fills the row in.
                movie = await film_for_tmdb_id(
                    db,
                    tmdb_id=entry.tmdb_id,
                    title=entry.title,
                    year=entry.year,
                    index=index,
                    tmdb=tmdb,
                    report=report,
                )
        else:
            movie = await db.get(Movie, uuid.UUID(str(entry.movie_id)))
            if movie is not None and movie.deleted_at is not None:
                movie = None
        if movie is None:
            result.skipped.append(f"{_label(entry.title, entry.year)}: its film is gone")
            continue
        db.add(
            WatchLog(
                id=uuid.uuid4(),
                movie_id=movie.id,
                user_id=user_id,
                watched_at=date.fromisoformat(entry.watched_at),
                is_rewatch=entry.is_rewatch,
                personal_rating=Decimal(entry.rating) if entry.rating is not None else None,
                letterboxd_viewing_id=entry.viewing_id,
                tmdb_id=entry.tmdb_id,
            )
        )
        recorded.add(entry.viewing_id)
        result.written += 1
    result.films_added = len(report.films_added)
    result.films_filled = report.films_filled
    result.skipped.extend(f"{name}: a film in the Trash holds it" for name in report.in_trash)
    await db.commit()
    log.info(
        "letterboxd_backfill",
        person=plan.person,
        written=result.written,
        films_added=result.films_added,
        already=result.already,
        skipped=len(result.skipped),
    )
    return result


def write_doubtful(plan: BackfillPlan, path: Path) -> int:
    """The doubtful entries, as a CSV Craig can read and answer. Returns how many."""
    doubtful = [entry for entry in plan.entries if entry.action == "doubtful"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["watched", "title", "year", "why it is doubtful"])
        for entry in doubtful:
            writer.writerow([entry.watched_at, entry.title, entry.year or "", entry.reason])
    return len(doubtful)
