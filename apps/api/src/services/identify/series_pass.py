"""Identify the TV series still to identify, automatically where TMDB leaves no doubt — Batch Y3.

Craig, 15 Oct: rather than Mark choosing each of the 46 series one by one, a pass proposes a
TMDB series for every title "Still to identify" (:func:`waiting.still_to_identify`, the same
list Mark sees), and identifies only the ones it is sure of. It works as T9's identify run does:

1. **The dry run reads, and writes nothing.** For each title it searches TMDB's series index
   with the title as a series is sold under ("Broadchurch", not "Broadchurch Series 1 - 3",
   :func:`titles.parse_title`'s ``tv_title``) and proposes:

   - **identify**, when exactly one series has that title (:func:`titles.compare`,
     ``same_title``), or one has at least :data:`DOMINANT_RATIO` times the votes of every other
     of that title and at least :data:`MIN_VOTES`; a year in the title must agree with its
     first-air year, within a year;
   - **ask**, otherwise: several series of that title and none dominant, or none at all (it
     may be a film after all). Mark chooses those from their pages.

   It saves the plan and a report for Craig.
2. **The live run applies that exact plan**, after Craig has read the report. It re-checks each
   title first (still live, still unidentified, same title), fetches the series, and identifies
   it through :func:`identification.identify_film` — audited with ``how="auto"``, its evidence
   kept, undone from the Identify films page like any other. **It never merges:** a series
   another title already holds is left for Mark, named in the result.
"""

from __future__ import annotations

import html
import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from src.models.collection_item import CollectionItem, owned_copy
from src.models.identify import IdentifyLookup
from src.models.movie import Movie
from src.services.identification import IdentifyError, MergeNeeded, identify_film
from src.services.identify.titles import compare, parse_title
from src.services.identify.waiting import still_to_identify
from src.tmdb.models import TvSearchResult, TvSearchResults, TvShow

PLAN_VERSION = 1
#: One series of a title must be this much better known than every other of that title.
DOMINANT_RATIO = 5
#: And known at all.
MIN_VOTES = 50
#: The other series the report shows beside a proposal, so Craig can see what was passed over.
OFFERED = 4


class SeriesTmdb(Protocol):
    async def search_tv(self, query: str) -> TvSearchResults: ...

    async def get_tv_full(self, tv_id: int) -> TvShow: ...


@dataclass(frozen=True)
class Waiting:
    """A title still to identify, as the dry run read it."""

    movie_id: uuid.UUID
    title: str
    set_aside_as: str | None = None
    grouping: str | None = None


@dataclass
class Proposal:
    movie_id: str
    title: str
    query: str
    outcome: str  #: "identify" or "ask"
    reason: str
    tmdb_tv_id: int | None = None
    series: str | None = None
    series_year: int | None = None
    votes: int = 0
    set_aside_as: str | None = None
    offered: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SeriesPlan:
    made_utc: str
    proposals: list[Proposal]
    failed: list[str] = field(default_factory=list)
    version: int = PLAN_VERSION

    def count(self, outcome: str) -> int:
        return sum(1 for p in self.proposals if p.outcome == outcome)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SeriesPlan:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("version") != PLAN_VERSION:
            raise ValueError(
                f"A plan of version {raw.get('version')}; this run reads {PLAN_VERSION}."
            )
        return cls(
            made_utc=raw["made_utc"],
            proposals=[Proposal(**item) for item in raw["proposals"]],
            failed=list(raw.get("failed", [])),
        )


# ---------------------------------------------------------------------------
# Reading the titles still to identify
# ---------------------------------------------------------------------------


def waiting_query() -> Select[Any]:
    on_shelf = exists().where(CollectionItem.movie_id == Movie.id, owned_copy())
    grouping = (
        select(CollectionItem.sub_category)
        .where(
            CollectionItem.movie_id == Movie.id,
            owned_copy(),
            CollectionItem.sub_category.is_not(None),
        )
        .order_by(CollectionItem.sub_category)
        .limit(1)
        .scalar_subquery()
    )
    set_aside = (
        select(IdentifyLookup.set_aside_as)
        .where(IdentifyLookup.movie_id == Movie.id, IdentifyLookup.status == "set_aside")
        .scalar_subquery()
    )
    return (
        select(Movie.id, Movie.title, set_aside, grouping)
        .where(Movie.deleted_at.is_(None), still_to_identify(), on_shelf)
        .order_by(Movie.title, Movie.id)
    )


async def read_waiting(db: AsyncSession) -> list[Waiting]:
    rows = (await db.execute(waiting_query())).all()
    return [Waiting(movie_id, title, aside, grouping) for movie_id, title, aside, grouping in rows]


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


def _named(query: str, show: TvSearchResult) -> bool:
    names = [show.name, *([show.original_name] if show.original_name else [])]
    return any(compare(query, name).same_title for name in names)


def _offer(show: TvSearchResult) -> dict[str, Any]:
    return {"tmdb_tv_id": show.id, "name": show.name, "year": show.year, "votes": show.vote_count}


def series_query(item: Waiting) -> tuple[str, int | None]:
    """The title as a series is sold under, and any year the title gives."""
    parsed = parse_title(item.title, item.grouping)
    return parsed.tv_title or parsed.main or item.title, parsed.year


def propose(item: Waiting, found: TvSearchResults) -> Proposal:
    query, year = series_query(item)
    base = Proposal(
        movie_id=str(item.movie_id),
        title=item.title,
        query=query,
        outcome="ask",
        reason="",
        set_aside_as=item.set_aside_as,
    )
    same = [show for show in found.results if _named(query, show)]
    if year is not None:
        dated = [s for s in same if s.year is None or abs(s.year - year) <= 1]
        if same and not dated:
            base.reason = f"TMDB's series called '{query}' did not start in or near {year}."
            base.offered = [_offer(s) for s in same[:OFFERED]]
            return base
        same = dated
    if not same:
        base.reason = f"TMDB's series index has nothing called '{query}'; it may be a film."
        base.offered = [_offer(s) for s in found.results[:OFFERED]]
        return base
    ranked = sorted(same, key=lambda s: (s.vote_count, s.popularity), reverse=True)
    best, rest = ranked[0], ranked[1:]
    if rest and not (
        best.vote_count >= MIN_VOTES
        and all(best.vote_count >= DOMINANT_RATIO * max(other.vote_count, 1) for other in rest)
    ):
        base.reason = f"TMDB has {len(ranked)} series called '{query}', none far better known."
        base.offered = [_offer(s) for s in ranked[:OFFERED]]
        return base
    base.outcome = "identify"
    base.tmdb_tv_id = best.id
    base.series = best.name
    base.series_year = best.year
    base.votes = best.vote_count
    base.reason = (
        f"TMDB has one series called '{best.name}'."
        if not rest
        else f"'{best.name}' ({best.year or '?'}) has {best.vote_count:,} votes; the other "
        f"{len(rest)} of that name have {max(s.vote_count for s in rest):,} at most."
    )
    base.offered = [_offer(s) for s in rest[:OFFERED]]
    return base


async def dry_run(
    waiting: Sequence[Waiting],
    tmdb: SeriesTmdb,
    *,
    now: datetime,
    progress: Callable[[int, int], None] | None = None,
) -> SeriesPlan:
    plan = SeriesPlan(made_utc=now.isoformat(), proposals=[])
    for index, item in enumerate(waiting, start=1):
        query, _year = series_query(item)
        try:
            found = await tmdb.search_tv(query)
        except (httpx.HTTPError, RuntimeError):
            # TMDB's client raises these once its retries are spent; one title is noted.
            plan.failed.append(item.title)
        else:
            plan.proposals.append(propose(item, found))
        if progress is not None:
            progress(index, len(waiting))
    return plan


# ---------------------------------------------------------------------------
# The live run
# ---------------------------------------------------------------------------


@dataclass
class Outcome:
    title: str
    result: str  #: "identified", "unchanged", "waits" or "failed"
    note: str = ""


async def apply_one(db: AsyncSession, tmdb: SeriesTmdb, proposal: Proposal) -> Outcome:
    """Identify one planned title as its series, if it is still as the dry run saw it. Commits
    on success, rolls back otherwise."""
    if proposal.outcome != "identify" or proposal.tmdb_tv_id is None:
        return Outcome(proposal.title, "unchanged", "Not proposed for identifying.")
    movie = await db.get(Movie, uuid.UUID(proposal.movie_id))
    if movie is None or movie.deleted_at is not None:
        return Outcome(proposal.title, "unchanged", "It is no longer in the collection.")
    if movie.tmdb_id is not None or movie.tmdb_tv_id is not None:
        return Outcome(proposal.title, "unchanged", "It was identified after the dry run.")
    if movie.title != proposal.title:
        return Outcome(proposal.title, "unchanged", "Its title changed after the dry run.")
    try:
        show = await tmdb.get_tv_full(proposal.tmdb_tv_id)
    except (httpx.HTTPError, RuntimeError) as exc:
        return Outcome(proposal.title, "failed", f"TMDB did not answer: {type(exc).__name__}.")
    try:
        await identify_film(
            db,
            movie,
            show,
            by=None,
            how="auto",
            evidence=[proposal.reason, "Proposed by the series pass and applied as planned."],
            allow_merge=False,
        )
    except MergeNeeded as exc:
        # Read before the rollback, which expires the row it names.
        holder = exc.existing.title
        await db.rollback()
        return Outcome(proposal.title, "waits", f"'{holder}' already holds the series.")
    except IdentifyError as exc:
        message = str(exc)
        await db.rollback()
        return Outcome(proposal.title, "failed", message)
    await db.commit()
    return Outcome(proposal.title, "identified", show.name)


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

_STYLE = """
body{font:15px/1.5 system-ui,sans-serif;margin:24px;color:#1c1917;background:#fafaf9}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
p.lede{color:#57534e;margin:0 0 16px;max-width:60rem}
table{border-collapse:collapse;width:100%;background:#fff}
th,td{border-bottom:1px solid #e7e5e4;padding:8px 10px;text-align:left;vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#78716c}
a{color:#9f1239}small{color:#78716c}
"""


def _series_link(tv_id: int, label: str) -> str:
    return f"<a href='https://www.themoviedb.org/tv/{tv_id}'>{html.escape(label)}</a>"


def _offered(items: list[dict[str, Any]]) -> str:
    return "<br>".join(
        f"<small>{_series_link(int(o['tmdb_tv_id']), str(o['name']))} "
        f"{o.get('year') or '?'} · {int(o.get('votes') or 0):,} votes</small>"
        for o in items
    )


def render_report(plan: SeriesPlan, *, app_url: str) -> str:
    base = app_url.rstrip("/")

    def film(p: Proposal) -> str:
        aside = " <small>(set aside as TV)</small>" if p.set_aside_as == "tv" else ""
        return f"<a href='{base}/movies/{p.movie_id}'>{html.escape(p.title)}</a>{aside}"

    sure = [p for p in plan.proposals if p.outcome == "identify"]
    ask = [p for p in plan.proposals if p.outcome == "ask"]
    sure_rows = "".join(
        f"<tr><td>{film(p)}</td><td>{_series_link(p.tmdb_tv_id or 0, p.series or '')} "
        f"{p.series_year or '?'}<br><small>{p.votes:,} votes</small></td>"
        f"<td>{html.escape(p.reason)}</td><td>{_offered(p.offered)}</td></tr>"
        for p in sure
    )
    ask_rows = "".join(
        f"<tr><td>{film(p)}</td><td>{html.escape(p.reason)}</td><td>{_offered(p.offered)}</td></tr>"
        for p in ask
    )
    failed = (
        f"<p>TMDB did not answer for {len(plan.failed)}: {html.escape(', '.join(plan.failed))}."
        " A second dry run tries them again.</p>"
        if plan.failed
        else ""
    )
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Series to identify</title><style>{_STYLE}</style>"
        "<h1>Series to identify</h1>"
        f"<p class='lede'>{len(plan.proposals)} titles still to identify, read {plan.made_utc[:16]}"
        " UTC. Nothing has been changed. The live run identifies the first list exactly as shown,"
        " each undoable from <b>Identify films</b>; the second is left for Mark to choose from"
        " each page.</p>"
        f"{failed}<h2>Will be identified ({len(sure)})</h2>"
        + (
            "<table><thead><tr><th>Title</th><th>TMDB's series</th><th>Why</th>"
            f"<th>Also of that name</th></tr></thead><tbody>{sure_rows}</tbody></table>"
            if sure
            else "<p>None.</p>"
        )
        + f"<h2>Left for Mark ({len(ask)})</h2>"
        + (
            "<table><thead><tr><th>Title</th><th>Why</th><th>TMDB offered</th></tr></thead>"
            f"<tbody>{ask_rows}</tbody></table>"
            if ask
            else "<p>None.</p>"
        )
    )
