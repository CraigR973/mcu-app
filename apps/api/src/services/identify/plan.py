"""The dry run: what identification proposes for every unmatched film — Batch T9.

**It writes nothing.** It reads the collection, asks TMDB and at most a budgeted number of
Brave searches, and returns a :class:`Plan`: for every unidentified film with a live disc,
identify (with the evidence), ask Craig (with the candidates and why), or set aside (a TV
series or not a film). The plan is saved as JSON beside a report Craig reads.

**The live run applies that exact plan** (``apply.py``), after checking each film has not
changed since. So what Craig approved is what happens, and the Brave searches the dry run
spent are not spent again.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.watch_log import WatchLog
from src.services.identify.matcher import Candidate, Identifier, Proposal
from src.services.identify.titles import parse_title

logger = structlog.get_logger(__name__)

FORMAT_NAMES = {"4k_uhd": "4K", "blu_ray": "Blu-ray", "dvd": "DVD", "download": "Download"}

#: The plan file's shape. The live run refuses any other.
PLAN_VERSION = 1


@dataclass
class Disc:
    format_code: str | None
    grouping: str | None
    location: str | None

    def label(self) -> str:
        parts = [FORMAT_NAMES.get(self.format_code or "", self.format_code or "No format")]
        if self.grouping:
            parts.append(self.grouping)
        if self.location:
            parts.append(self.location)
        return " · ".join(parts)


@dataclass
class Film:
    """An unidentified film with a live disc, as the plan found it."""

    movie_id: str
    title: str
    discs: list[Disc]
    watches: int

    @property
    def grouping(self) -> str | None:
        return next((d.grouping for d in self.discs if d.grouping), None)


@dataclass
class Offered:
    """A TMDB film offered for one of ours, with what speaks for it."""

    tmdb_id: int
    title: str
    year: int | None
    poster_path: str | None
    overview: str
    votes: int
    origin: str
    notes: list[str] = field(default_factory=list)

    @classmethod
    def of(cls, candidate: Candidate, notes: list[str]) -> Offered:
        return cls(
            tmdb_id=candidate.tmdb_id,
            title=candidate.title,
            year=candidate.year,
            poster_path=candidate.poster_path,
            overview=(candidate.overview or "")[:600],
            votes=candidate.vote_count,
            origin=candidate.origin,
            notes=notes,
        )


@dataclass
class MergeTarget:
    movie_id: str
    title: str
    year: int | None


@dataclass
class Item:
    """What the plan proposes for one film."""

    movie_id: str
    title: str
    discs: list[Disc]
    watches: int
    outcome: str  #: "identify", "ask" or "set_aside"
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    chosen: Offered | None = None
    candidates: list[Offered] = field(default_factory=list)
    set_aside_as: str | None = None
    merge_into: MergeTarget | None = None
    brave_query: str | None = None


@dataclass
class Plan:
    version: int
    made_utc: str
    films: int
    tmdb_calls: int
    brave_searches: int
    brave_budget: int
    items: list[Item]

    def count(self, outcome: str) -> int:
        return sum(1 for item in self.items if item.outcome == outcome)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, ensure_ascii=False)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Plan:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        if data.get("version") != PLAN_VERSION:
            raise ValueError(
                f"This plan is version {data.get('version')}; expected {PLAN_VERSION}."
            )
        return cls(
            version=data["version"],
            made_utc=data["made_utc"],
            films=data["films"],
            tmdb_calls=data["tmdb_calls"],
            brave_searches=data["brave_searches"],
            brave_budget=data["brave_budget"],
            items=[_item(raw) for raw in data["items"]],
        )


def _offered(raw: dict[str, Any] | None) -> Offered | None:
    return Offered(**raw) if raw else None


def _item(raw: dict[str, Any]) -> Item:
    merge = raw.get("merge_into")
    return Item(
        movie_id=raw["movie_id"],
        title=raw["title"],
        discs=[Disc(**disc) for disc in raw["discs"]],
        watches=raw["watches"],
        outcome=raw["outcome"],
        reason=raw.get("reason", ""),
        evidence=list(raw.get("evidence", [])),
        chosen=_offered(raw.get("chosen")),
        candidates=[Offered(**c) for c in raw.get("candidates", [])],
        set_aside_as=raw.get("set_aside_as"),
        merge_into=MergeTarget(**merge) if merge else None,
        brave_query=raw.get("brave_query"),
    )


# ---------------------------------------------------------------------------
# Reading the collection
# ---------------------------------------------------------------------------


async def unidentified_films(db: AsyncSession) -> list[Film]:
    """Every live film TMDB has not matched that has a disc on the shelf, by title."""
    rows = (
        await db.execute(
            select(
                Movie.id,
                Movie.title,
                CollectionItem.formats,
                CollectionItem.sub_category,
                CollectionItem.location,
            )
            .join(CollectionItem, CollectionItem.movie_id == Movie.id)
            .where(Movie.tmdb_id.is_(None), Movie.deleted_at.is_(None), owned_copy())
            .order_by(Movie.title, Movie.id, CollectionItem.id)
        )
    ).all()
    films: dict[uuid.UUID, Film] = {}
    for movie_id, title, formats, grouping, location in rows:
        film = films.setdefault(movie_id, Film(str(movie_id), title, [], 0))
        best = next((code for code in FORMAT_NAMES if code in (formats or [])), None)
        film.discs.append(Disc(best, grouping, location))
    if films:
        watched = await db.execute(
            select(WatchLog.movie_id, func.count())
            .where(WatchLog.movie_id.in_(list(films)))
            .group_by(WatchLog.movie_id)
        )
        for movie_id, count in watched:
            films[movie_id].watches = int(count)
    return list(films.values())


async def held_films(db: AsyncSession) -> dict[int, MergeTarget]:
    """The collection's identified films, by TMDB id: what an identification would merge into."""
    rows = await db.execute(
        select(Movie.tmdb_id, Movie.id, Movie.title, Movie.year).where(
            Movie.tmdb_id.is_not(None), Movie.deleted_at.is_(None)
        )
    )
    return {
        int(tmdb_id): MergeTarget(str(movie_id), title, year)
        for tmdb_id, movie_id, title, year in rows
    }


async def table_exists(db: AsyncSession, name: str) -> bool:
    """The dry run runs before the batch's migration is applied, by design: it is what Craig
    reads before anything merges. So it asks before reading a table the migration adds."""
    found = await db.scalar(text("SELECT to_regclass(:name) IS NOT NULL"), {"name": name})
    return bool(found)


# ---------------------------------------------------------------------------
# Making the plan
# ---------------------------------------------------------------------------


def _item_for(film: Film, proposal: Proposal) -> Item:
    item = Item(
        movie_id=film.movie_id,
        title=film.title,
        discs=film.discs,
        watches=film.watches,
        outcome=proposal.outcome,
        reason=proposal.reason,
        evidence=list(proposal.evidence),
        set_aside_as=proposal.set_aside_as,
        brave_query=proposal.brave_query,
    )
    if proposal.chosen is not None:
        item.chosen = Offered.of(proposal.chosen, proposal.notes.get(proposal.chosen.tmdb_id, []))
    item.candidates = [
        Offered.of(candidate, proposal.notes.get(candidate.tmdb_id, []))
        for candidate in proposal.candidates
    ]
    if proposal.merge_into is not None:
        movie_id, title, year = proposal.merge_into
        item.merge_into = MergeTarget(movie_id, title, year)
    return item


async def make_plan(
    db: AsyncSession,
    identifier: Identifier,
    *,
    now: datetime,
    only: set[str] | None = None,
    progress: Callable[[int, int, Item], None] | None = None,
) -> Plan:
    """Propose an outcome for every unidentified film with a live disc. Writes nothing."""
    films = await unidentified_films(db)
    held = await held_films(db)
    return await propose(films, held, identifier, now=now, only=only, progress=progress)


async def propose(
    films: list[Film],
    held: dict[int, MergeTarget],
    identifier: Identifier,
    *,
    now: datetime,
    only: set[str] | None = None,
    progress: Callable[[int, int, Item], None] | None = None,
) -> Plan:
    """The plan for films already read from the collection. Touches no database.

    Separate from reading, so the dry run holds no connection through half an hour of TMDB
    and Brave calls: the second 25 Sep dry run held one, Neon closed it, and the finished plan
    was lost on the rollback.
    """
    if only:
        films = [film for film in films if film.movie_id in only or film.title in only]
    # A film this plan identifies is one a later film would merge into.
    planned: dict[int, MergeTarget] = {}

    def holder(tmdb_id: int) -> tuple[str, str, int | None] | None:
        target = held.get(tmdb_id) or planned.get(tmdb_id)
        return (target.movie_id, target.title, target.year) if target else None

    items: list[Item] = []
    for index, film in enumerate(films, start=1):
        parsed = parse_title(film.title, film.grouping)
        try:
            proposal = await identifier.identify(parsed, held=holder)
        except httpx.HTTPError as exc:
            logger.warning("identify_lookup_failed", title=film.title, error=type(exc).__name__)
            proposal = Proposal(
                "ask",
                reason=f"TMDB could not be reached ({type(exc).__name__}). Search again.",
            )
        item = _item_for(film, proposal)
        if item.outcome == "identify" and item.chosen is not None:
            planned[item.chosen.tmdb_id] = MergeTarget(
                film.movie_id, item.chosen.title, item.chosen.year
            )
        items.append(item)
        if progress is not None:
            progress(index, len(films), item)

    return Plan(
        version=PLAN_VERSION,
        made_utc=now.isoformat(timespec="seconds"),
        films=len(items),
        tmdb_calls=identifier.counters.tmdb_calls,
        brave_searches=identifier.counters.brave_searches,
        brave_budget=identifier.brave_budget,
        items=items,
    )
