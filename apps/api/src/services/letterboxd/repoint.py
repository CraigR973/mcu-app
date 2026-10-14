"""The 15 watches of one film that sit on another of the same name — Batch X5 (CT46-02).

The September import matched by title with the year as a tie-break only (#158), so a logged
*The Heat* (2013) went on Michael Mann's *Heat* (1995), *Cape Fear* (1962) on the 1991 film,
and 13 more (`docs/reviews/BATCH_43-48_EVIDENCE.md`, section 3). X5's year rule stops it
happening again; this moves the 15 that happened, to the films they were of.

**Exactly the review's 15**, by the film each sits on and the year it was logged with. Of the
30 watches whose film's year differs from the diary's, 14 are of the right film on a disc
identified as the wrong one (CT46-01): the film is what is wrong there, and X9 fixes it, so
moving those watches would move them away from the disc they were of. The last, *Force of
Evil*, is two years out and probably the same film.

**Two steps, as the backfill.** :func:`plan_repoint` reads the watches, finds each one's diary
entry in the two files on the Mac (by viewing id), and identifies the film it was of with T9's
care; it writes nothing. :func:`apply_repoint` moves each planned watch, at Craig's word,
after checking it still sits where the plan found it.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.movie import Movie
from src.models.watch_log import WatchLog
from src.services.identify.matcher import Identifier
from src.services.identify.titles import parse_title
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.importer import ImportReport, TmdbDetails, film_for_tmdb_id
from src.services.letterboxd.matcher import build_index

PLAN_VERSION = 1

#: The review's 15, as (the TMDB id of the film each sits on, the year it was logged with).
#: Section 3 of the evidence names them; this is that table.
MISATTRIBUTED: tuple[tuple[int, int], ...] = (
    (12092, 2010),  # Alice in Wonderland, logged 2010, on the 1951 film
    (18174, 2015),  # An Inspector Calls, logged 2015, on the 1954 film
    (4886, 1974),  # And Then There Were None, logged 1974, on the 1945 film
    (1598, 1962),  # Cape Fear, logged 1962, on the 1991 film
    (7340, 2013),  # Carrie, logged 2013, on the 1976 film
    (20051, 2016),  # Dad's Army, logged 2016, on the 1971 film
    (124905, 1998),  # Godzilla, logged 1998, on the 2014 film
    (11571, 2008),  # Journey to the Center of the Earth, logged 2008, on the 1959 film
    (35852, 2025),  # Obsession, logged 2025, on the 1949 film
    (748230, 1979),  # Salem's Lot, logged 1979, on the 2024 film
    (260, 1959),  # The 39 Steps, logged 1959, on the 1935 film
    (10649, 1951),  # The Enforcer, logged 1951, on the 1976 film
    (949, 2013),  # The Heat, logged 2013, on Heat (1995)
    (1091, 2011),  # The Thing, logged 2011, on the 1982 film
    (74, 1953),  # The War of the Worlds, logged 1953, on the 2005 film
)


@dataclass
class Move:
    watch_id: str
    viewing_id: str
    watched_at: str
    logged: str
    from_movie_id: str
    from_film: str
    #: ``move`` (to ``to_movie_id``, or a new row for ``to_tmdb_id``) or ``doubtful``.
    action: str
    to_tmdb_id: int | None = None
    to_movie_id: str | None = None
    to_film: str | None = None
    reason: str = ""


@dataclass
class RepointPlan:
    moves: list[Move] = field(default_factory=list)
    #: Of the 15, how many no watch matched (already moved, or deleted since the review).
    not_found: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": PLAN_VERSION,
                "moves": [asdict(move) for move in self.moves],
                "notFound": self.not_found,
            },
            indent=1,
        )

    @classmethod
    def from_json(cls, raw: str) -> RepointPlan:
        data: dict[str, Any] = json.loads(raw)
        if data.get("version") != PLAN_VERSION:
            raise ValueError(f"plan version {data.get('version')!r}, expected {PLAN_VERSION}")
        return cls(moves=[Move(**move) for move in data["moves"]], not_found=data["notFound"])

    def summary(self) -> str:
        moving = [move for move in self.moves if move.action == "move"]
        lines = [f"{len(moving)} watches to move; {len(self.moves) - len(moving)} doubtful"]
        for move in self.moves:
            target = move.to_film or "?"
            if move.action == "move" and move.to_movie_id is None:
                target += " (a new film row)"
            verb = "→" if move.action == "move" else "? doubtful:"
            lines.append(
                f"  {move.watched_at} {move.logged}: {move.from_film} {verb} "
                f"{target if move.action == 'move' else move.reason}"
            )
        lines.extend(f"  not found: {item}" for item in self.not_found)
        return "\n".join(lines)


def _label(title: str, year: int | None) -> str:
    return f"{title} ({year})" if year is not None else title


async def plan_repoint(
    db: AsyncSession, diaries: Mapping[str, DiaryEntry], identifier: Identifier
) -> RepointPlan:
    """Find the 15 and the film each was of. ``diaries``: every diary entry, by viewing id."""
    plan = RepointPlan()
    index = build_index(list(await db.scalars(select(Movie).where(Movie.deleted_at.is_(None)))))
    films = {tmdb_id: index.by_tmdb_id.get(tmdb_id) for tmdb_id, _ in MISATTRIBUTED}
    on_them = list(
        await db.scalars(
            select(WatchLog).where(
                WatchLog.movie_id.in_([film.id for film in films.values() if film is not None]),
                WatchLog.deleted_at.is_(None),
                WatchLog.letterboxd_viewing_id.is_not(None),
            )
        )
    )
    # Everything is read; hand the connection back before the TMDB searches (as the backfill).
    # Nothing was written, so ending the read transaction this way changes nothing; it
    # keeps what was loaded usable, where a rollback would expire it.
    await db.commit()
    for tmdb_id, logged_year in MISATTRIBUTED:
        on = films[tmdb_id]
        if on is None:
            plan.not_found.append(f"no film carries TMDB {tmdb_id}")
            continue
        watches = [watch for watch in on_them if watch.movie_id == on.id]
        found = [
            (watch, diaries[str(watch.letterboxd_viewing_id)])
            for watch in watches
            if str(watch.letterboxd_viewing_id) in diaries
            and diaries[str(watch.letterboxd_viewing_id)].year == logged_year
        ]
        if not found:
            plan.not_found.append(f"{_label(on.title, on.year)}, logged {logged_year}")
            continue
        for watch, entry in found:
            move = Move(
                watch_id=str(watch.id),
                viewing_id=str(watch.letterboxd_viewing_id),
                watched_at=watch.watched_at.isoformat(),
                logged=_label(entry.title, entry.year),
                from_movie_id=str(on.id),
                from_film=_label(on.title, on.year),
                action="doubtful",
            )
            try:
                proposal = await identifier.identify(parse_title(f"{entry.title} ({entry.year})"))
            except httpx.HTTPError as exc:
                move.reason = f"TMDB did not answer: {exc}"
                plan.moves.append(move)
                continue
            chosen = proposal.chosen
            if proposal.outcome != "identify" or chosen is None or chosen.tmdb_id == tmdb_id:
                move.reason = proposal.reason or "TMDB has no one strong match"
                plan.moves.append(move)
                continue
            listed = index.by_tmdb_id.get(chosen.tmdb_id)
            move.action = "move"
            move.to_tmdb_id = chosen.tmdb_id
            move.to_movie_id = str(listed.id) if listed is not None else None
            move.to_film = _label(chosen.title, chosen.year)
            move.reason = "; ".join(proposal.evidence) or "one strong match on TMDB"
            plan.moves.append(move)
    return plan


@dataclass
class RepointResult:
    moved: int = 0
    films_added: int = 0
    skipped: list[str] = field(default_factory=list)


async def apply_repoint(
    db: AsyncSession, plan: RepointPlan, tmdb: TmdbDetails | None
) -> RepointResult:
    """Move each planned watch, if it still sits on the film the plan found it on. Commits."""
    result = RepointResult()
    index = build_index(list(await db.scalars(select(Movie).where(Movie.deleted_at.is_(None)))))
    report = ImportReport(dry_run=False)
    for move in plan.moves:
        if move.action != "move" or move.to_tmdb_id is None:
            continue
        watch = await db.get(WatchLog, uuid.UUID(move.watch_id))
        if watch is None or watch.deleted_at is not None:
            result.skipped.append(f"{move.logged}: the watch is gone")
            continue
        if str(watch.movie_id) != move.from_movie_id:
            result.skipped.append(f"{move.logged}: it has moved since the plan")
            continue
        target = index.by_tmdb_id.get(move.to_tmdb_id)
        if target is None:
            year = int(move.logged.rsplit("(", 1)[-1].rstrip(")"))
            target = await film_for_tmdb_id(
                db,
                tmdb_id=move.to_tmdb_id,
                title=move.logged.rsplit(" (", 1)[0],
                year=year,
                index=index,
                tmdb=tmdb,
                report=report,
            )
        if target is None:
            result.skipped.append(f"{move.logged}: a film in the Trash holds its TMDB id")
            continue
        watch.movie_id = target.id
        watch.tmdb_id = move.to_tmdb_id
        result.moved += 1
    result.films_added = len(report.films_added)
    await db.commit()
    return result
