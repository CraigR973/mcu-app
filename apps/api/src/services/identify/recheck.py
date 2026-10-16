"""Re-checking the films the old paths identified — Batch X9 (CT46-01).

**30 copies were confidently the wrong film on 12 Oct**, 27 matched by the 8 Sep import's
engine and 3 by the diary import, and nothing marked them. The old engine kept a leading
article, scored an exact namesake above the real film, floored any containing title at 0.9
and read one results page. T9's identifier identified 156 films with none of those faults.

This asks T9's identifier again about every copy the old paths decided, from the copy's own
spreadsheet row (its title and the grouping it sits under), with free TMDB calls and no
Brave, and compares the answer with the film the copy is catalogued as:

- ``agrees``: T9 identifies the catalogued film.
- ``different``: T9 identifies another film.
- ``series``: T9 reads the row as a TV series.
- ``not_offered``: T9 cannot decide, and the catalogued film is not even among its candidates.
- ``unsure``: T9 cannot decide between films that include the catalogued one.
- ``not_film``: T9 reads the row as not a film.
- ``nothing``: TMDB finds nothing for the row, or could not be reached. No evidence either way.

**The dry run writes nothing.** It reads the collection in a read-only transaction that is
over before TMDB is asked anything, and saves a plan and a report. **Applying the plan, at
Craig's word, raises a doubt** (``services/identify/doubts``) for every copy in the classes
he names, the strongest first, so each waits on Identify films with its evidence. It never
re-identifies a film: Craig settles each doubt with a tap. The report checks the review's 30
known wrong copies (``docs/reviews/BATCH_43-48_EVIDENCE.md``, section 2) one by one.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from sqlalchemy import String, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.services.identification import MOVIES_TABLE
from src.services.identify.doubts import raise_doubt
from src.services.identify.matcher import Identifier, Proposal
from src.services.identify.plan import Offered
from src.services.identify.titles import parse_title
from src.tmdb.client import TMDBRefused

logger = structlog.get_logger(__name__)

RECHECK_VERSION = 1

#: Strongest first: the order the doubts are raised in, so Identify lists them that way.
DOUBT_CLASSES = ("different", "series", "not_offered", "unsure", "not_film")
CLASSES = ("agrees", *DOUBT_CLASSES, "nothing")

#: The review's 30 wrong copies: the spreadsheet row, the sheet title, and the TMDB film it
#: was catalogued as on 12 Oct (``docs/reviews/BATCH_43-48_EVIDENCE.md``, section 2; the
#: diary rows, 713, 878 and 934, give the film's TMDB id after its year).
KNOWN_WRONG: tuple[tuple[int, str, int | None], ...] = (
    (115, "Arsenic & Old Lace", 609337),
    (138, "Bad Neighbours", 1372178),
    (141, "Band of Brothers", 484744),
    (231, "Bridge on the River Kwai", 930421),
    (313, "Cloak & Dagger", 48677),
    (366, "Dangerous", 763788),
    (550, "French Connection", 10711),
    (592, "Ghostbusters 2", 571906),
    (614, "Good Fellas", 626867),
    (617, "Good the bad & the ugly", 1000945),
    (635, "Great Wall", 216472),
    (656, "Halfway House", 1250593),
    (670, "Harder They Fall", 280183),
    (713, "Holiday", 1581),
    (714, "Holy Grail, The", 600613),
    (728, "House on the River", 259577),
    (738, "Hunchback of Notre Dame", 119406),
    (878, "King Kong [1976]", 254),
    (925, "Left Right & Centre", 1003963),
    (934, "Life", 395992),
    (1147, "Night of the Hunter", 243714),
    (1254, "Planet Earth II", 596683),
    (1335, "Rome", 1550418),
    (1473, "Spiderman", 1536316),
    (1560, "Tale of Two Cities", 942168),
    (1620, "Tinker Tailor Soldier Spy (TV)", 49517),
    (1696, "Vacation from Marriage [Perfect Strangers]", 513801),
    (1780, "Wonders of the Solar System", 164531),
    (1789, "X-Men 2", 758075),
    (1831, "11.22.63", 1144348),
)


@dataclass(frozen=True)
class OldCopy:
    """A copy whose film an old path identified, as the collection holds it now."""

    item_id: str
    movie_id: str
    film_title: str
    film_year: int | None
    tmdb_id: int
    sheet_row: int | None
    grouping: str | None


@dataclass(frozen=True)
class SheetRow:
    title: str
    grouping: str | None


@dataclass
class Checked:
    """One copy re-checked: what T9 says of its sheet row, against the catalogued film."""

    item_id: str
    movie_id: str
    film_title: str
    film_year: int | None
    tmdb_id: int
    sheet_row: int | None
    sheet_title: str
    grouping: str | None
    verdict: str
    note: str
    evidence: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    proposed_tmdb_id: int | None = None


@dataclass
class KnownCheck:
    row: int
    sheet_title: str
    wrong_tmdb_id: int | None
    status: str


@dataclass
class RecheckPlan:
    version: int
    made_utc: str
    copies: int
    tmdb_calls: int
    items: list[Checked]
    known: list[KnownCheck] = field(default_factory=list)
    #: Copies with no spreadsheet row to read, which were not re-checked.
    without_row: int = 0

    def count(self, verdict: str) -> int:
        return sum(1 for item in self.items if item.verdict == verdict)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> RecheckPlan:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("version") != RECHECK_VERSION:
            raise ValueError(f"{path} is not a version {RECHECK_VERSION} re-check plan.")
        return cls(
            version=raw["version"],
            made_utc=raw["made_utc"],
            copies=raw["copies"],
            tmdb_calls=raw["tmdb_calls"],
            items=[Checked(**item) for item in raw["items"]],
            known=[KnownCheck(**known) for known in raw.get("known", [])],
            without_row=raw.get("without_row", 0),
        )


# ---------------------------------------------------------------------------
# Reading the collection
# ---------------------------------------------------------------------------


def _decided_since() -> Any:
    """An identification of the film by T9 or by a person that stands (is not undone)."""
    undo = aliased(AdminAction)
    return exists().where(
        AdminAction.target_table == MOVIES_TABLE,
        AdminAction.target_id == Movie.id.cast(String),
        AdminAction.changes["kind"].astext == "identify",
        ~exists().where(
            undo.target_table == MOVIES_TABLE,
            undo.changes["undoes"].astext == AdminAction.id.cast(String),
        ),
    )


async def old_path_copies(db: AsyncSession) -> list[OldCopy]:
    """Owned copies of films identified as films by the import or the diary, which neither T9
    nor a person has identified since."""
    rows = await db.execute(
        select(
            CollectionItem.id,
            Movie.id,
            Movie.title,
            Movie.year,
            Movie.tmdb_id,
            CollectionItem.import_source_row,
            CollectionItem.sub_category,
        )
        .join(Movie, Movie.id == CollectionItem.movie_id)
        .where(
            owned_copy(),
            Movie.deleted_at.is_(None),
            Movie.tmdb_id.is_not(None),
            ~_decided_since(),
        )
        .order_by(Movie.title, CollectionItem.id)
    )
    return [
        OldCopy(str(item_id), str(movie_id), title, year, int(tmdb_id), row, grouping)
        for item_id, movie_id, title, year, tmdb_id, row, grouping in rows
    ]


@dataclass(frozen=True)
class KnownCopy:
    """A known wrong copy as the collection holds it now."""

    row: int
    item_id: str
    tmdb_id: int | None
    tmdb_tv_id: int | None
    title: str


async def known_copies(db: AsyncSession) -> dict[int, KnownCopy]:
    rows = await db.execute(
        select(
            CollectionItem.import_source_row,
            CollectionItem.id,
            Movie.tmdb_id,
            Movie.tmdb_tv_id,
            Movie.title,
        )
        .join(Movie, Movie.id == CollectionItem.movie_id)
        .where(
            CollectionItem.import_source_row.in_([row for row, _, _ in KNOWN_WRONG]),
            CollectionItem.deleted_at.is_(None),
        )
    )
    return {
        int(row): KnownCopy(int(row), str(item_id), tmdb_id, tmdb_tv_id, title)
        for row, item_id, tmdb_id, tmdb_tv_id, title in rows
    }


# ---------------------------------------------------------------------------
# Asking T9 again
# ---------------------------------------------------------------------------


def _offered(proposal: Proposal) -> list[dict[str, Any]]:
    return [
        asdict(Offered.of(candidate, proposal.notes.get(candidate.tmdb_id, [])))
        for candidate in proposal.candidates
    ]


def _film(title: str, year: int | None) -> str:
    return f"{title} ({year})" if year else title


def judge(copy: OldCopy, sheet: SheetRow, proposal: Proposal) -> Checked:
    """Compare T9's answer for the copy's sheet row with the film it is catalogued as."""
    catalogued = _film(copy.film_title, copy.film_year)
    offered = _offered(proposal)
    ids = [candidate.tmdb_id for candidate in proposal.candidates]
    verdict, note, proposed = "nothing", "", None
    if proposal.outcome == "identify" and proposal.chosen is not None:
        chosen = proposal.chosen
        if chosen.tmdb_id == copy.tmdb_id:
            verdict = "agrees"
            note = f"T9 identifies the sheet's “{sheet.title}” as {catalogued} too."
        else:
            verdict, proposed = "different", chosen.tmdb_id
            note = (
                f"T9 identifies the sheet's “{sheet.title}” as {_film(chosen.title, chosen.year)}"
                f", not {catalogued}."
            )
            if chosen.tmdb_id not in ids:
                offered.insert(
                    0, asdict(Offered.of(chosen, proposal.notes.get(chosen.tmdb_id, [])))
                )
    elif proposal.outcome == "set_aside":
        verdict = "series" if proposal.set_aside_as == "tv" else "not_film"
        what = "a TV series" if verdict == "series" else "not a film"
        note = f"T9 reads the sheet's “{sheet.title}” as {what}, not {catalogued}."
    elif proposal.candidates:
        if copy.tmdb_id in ids:
            verdict = "unsure"
            note = (
                f"T9 cannot tell which film the sheet's “{sheet.title}” is, and {catalogued} "
                "is only one of the films it could be."
            )
        else:
            verdict = "not_offered"
            note = (
                f"T9 cannot tell which film the sheet's “{sheet.title}” is, and {catalogued} "
                "is not among the films it could be."
            )
        if proposal.chosen is not None and proposal.chosen.tmdb_id != copy.tmdb_id:
            proposed = proposal.chosen.tmdb_id
    else:
        note = f"TMDB finds nothing for the sheet's “{sheet.title}”."
    evidence = [line for line in [proposal.reason, *proposal.evidence] if line]
    return Checked(
        item_id=copy.item_id,
        movie_id=copy.movie_id,
        film_title=copy.film_title,
        film_year=copy.film_year,
        tmdb_id=copy.tmdb_id,
        sheet_row=copy.sheet_row,
        sheet_title=sheet.title,
        grouping=sheet.grouping,
        verdict=verdict,
        note=note,
        evidence=evidence,
        candidates=offered,
        proposed_tmdb_id=proposed,
    )


async def recheck(
    copies: Iterable[OldCopy],
    sheet: dict[int, SheetRow],
    identifier: Identifier,
    *,
    now: datetime,
    known: dict[int, KnownCopy] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> RecheckPlan:
    """The plan for copies already read from the collection. Touches no database."""
    every = list(copies)
    todo = [copy for copy in every if copy.sheet_row is not None and copy.sheet_row in sheet]
    without_row = len(every) - len(todo)
    answers: dict[tuple[str, str | None], Proposal] = {}
    items: list[Checked] = []
    for index, copy in enumerate(todo, start=1):
        row = sheet[copy.sheet_row or 0]
        key = (row.title, row.grouping)
        if key not in answers:
            try:
                answers[key] = await identifier.identify(parse_title(row.title, row.grouping))
            except (httpx.HTTPError, TMDBRefused) as exc:
                logger.warning("recheck_lookup_failed", title=row.title, error=type(exc).__name__)
                answers[key] = Proposal(
                    "ask", reason=f"TMDB could not be reached ({type(exc).__name__})."
                )
        items.append(judge(copy, row, answers[key]))
        if progress is not None:
            progress(index, len(todo))
    plan = RecheckPlan(
        version=RECHECK_VERSION,
        made_utc=now.isoformat(timespec="seconds"),
        copies=len(items),
        tmdb_calls=identifier.counters.tmdb_calls,
        items=items,
        without_row=without_row,
    )
    plan.known = check_known(plan, known or {})
    return plan


def check_known(plan: RecheckPlan, known: dict[int, KnownCopy]) -> list[KnownCheck]:
    """Whether each of the review's 30 wrong copies appears, or why it does not."""
    by_row = {item.sheet_row: item for item in plan.items if item.sheet_row is not None}
    found: list[KnownCheck] = []
    for row, title, wrong in KNOWN_WRONG:
        copy = known.get(row)
        item = by_row.get(row)
        if copy is None:
            status = "No live copy from this row: it was sold, binned or never imported."
        elif copy.tmdb_tv_id is not None:
            status = f"Already corrected: identified as the series “{copy.title}”."
        elif copy.tmdb_id != wrong:
            now = f"“{copy.title}”" if copy.tmdb_id else "unidentified"
            status = f"Already corrected: the copy is now {now}."
        elif item is None:
            status = "Not re-checked: the film was identified again by T9 or a person since."
        elif item.verdict in DOUBT_CLASSES:
            status = f"Appears: {item.verdict}. {item.note}"
        else:
            status = f"MISSED ({item.verdict}): {item.note}"
        found.append(KnownCheck(row, title, wrong, status))
    return found


# ---------------------------------------------------------------------------
# Applying, at Craig's word
# ---------------------------------------------------------------------------


async def raise_one(db: AsyncSession, item: Checked) -> str:
    """Raise the doubt for one re-checked copy, if it is still as the dry run saw it.

    Returns ``raised``, ``kept_before`` (Craig kept this film before), or ``changed``.
    Commits.
    """
    copy = await db.get(CollectionItem, uuid.UUID(item.item_id))
    movie = await db.get(Movie, uuid.UUID(item.movie_id))
    if (
        copy is None
        or copy.deleted_at is not None
        or str(copy.movie_id) != item.movie_id
        or movie is None
        or movie.tmdb_id != item.tmdb_id
    ):
        return "changed"
    sheet = f"Spreadsheet row {item.sheet_row}: “{item.sheet_title}”" + (
        f", under {item.grouping}." if item.grouping else "."
    )
    doubt = await raise_doubt(
        db,
        movie,
        source="recheck",
        note=item.note,
        evidence=[sheet, *item.evidence],
        collection_item_id=copy.id,
        candidates=item.candidates,
        proposed_tmdb_id=item.proposed_tmdb_id,
        search_hint=item.sheet_title,
    )
    await db.commit()
    return "raised" if doubt is not None else "kept_before"


def to_raise(plan: RecheckPlan, verdicts: Iterable[str]) -> list[Checked]:
    """The copies to raise doubts for, in the classes named, strongest first."""
    wanted = [verdict for verdict in DOUBT_CLASSES if verdict in set(verdicts)]
    return [item for verdict in wanted for item in plan.items if item.verdict == verdict]


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def render_report(plan: RecheckPlan, *, app_url: str) -> str:
    counts = Counter(item.verdict for item in plan.items)
    lines = [
        "# Re-check of the old paths' identifications (Batch X9)",
        "",
        f"Made {plan.made_utc} UTC: {plan.copies} copies re-checked, {plan.tmdb_calls} TMDB "
        f"calls, no Brave. {plan.without_row} copies had no spreadsheet row and were not "
        "re-checked.",
        "",
        "| Verdict | Copies |",
        "|---|---|",
        *[f"| {verdict} | {counts.get(verdict, 0)} |" for verdict in CLASSES],
        "",
        "## The review's 30 known wrong copies",
        "",
        "| Row | Sheet title | Catalogued as | Now |",
        "|---|---|---|---|",
        *[
            f"| {known.row} | {known.sheet_title} | {known.wrong_tmdb_id} | {known.status} |"
            for known in plan.known
        ],
    ]
    for verdict in DOUBT_CLASSES:
        rows = [item for item in plan.items if item.verdict == verdict]
        if not rows:
            continue
        lines += ["", f"## {verdict} ({len(rows)})", ""]
        for item in rows:
            link = f"{app_url.rstrip('/')}/movies/{item.movie_id}"
            lines.append(
                f"- [{_film(item.film_title, item.film_year)}]({link}), row "
                f"{item.sheet_row}: {item.note}"
            )
    return "\n".join(lines) + "\n"
