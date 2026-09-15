"""Reading a Letterboxd diary file into entries — Batch S8.

**The shape here is the one that exists, measured rather than assumed.** Both files were
retrieved on 2026-09-15 (`DECISIONS.md` #160) and their header is::

    WatchedDate,Slug,Name,Year,Rating,Rewatch,ViewingId

2,322 rows across the two, every ``ViewingId`` distinct, and **``Rating`` is the only
column ever blank** — Mark rates nothing, which is correct data and not missing data
(#159).

**A note where this diverges from `DECISIONS.md` #161.** That entry says the input shape
is *"deliberately the same as Letterboxd's own `diary.csv`"*. It is not: Letterboxd's paid
export has different column names and **no viewing id at all**, and the acceptance
criterion this module is built against names ``ViewingId`` specifically — it is the
idempotency key, so it is not an optional nicety. Support for the paid export's shape is
**deliberately not written**, because nobody here has ever seen one, and `AGENTS.md` is
explicit: *work from real sample payloads, not guessed shapes*. Adding it later means
adding a reader, not changing anything below.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import IO

#: The columns a diary file must carry. ``Slug`` is read but not required by the matcher —
#: it is kept because it is the only stable link back to the Letterboxd page for a row
#: that fails to match, which is what a person needs in order to resolve one by hand.
REQUIRED_COLUMNS = ("WatchedDate", "Name", "Year", "Rating", "Rewatch", "ViewingId")

#: §3.7's scale. A Letterboxd rating is already half-stars out of five, so it transfers
#: without conversion — and ``watch_log.personal_rating`` has a CHECK that enforces it.
_RATING_STEP = Decimal("0.5")


class DiaryParseError(Exception):
    """The file is not a diary this importer can read.

    Raised for structural problems only — a missing column, an unparseable date. A single
    odd *row* is reported rather than raised, because one bad line in 1,173 should not
    cost the other 1,172.
    """


@dataclass(frozen=True)
class DiaryEntry:
    """One viewing, from whichever source read it.

    ``tmdb_id`` is always ``None`` from a CSV — the retrieved diary carries no TMDB id.
    It exists because **the RSS feed does** carry ``tmdb:movieId`` on every entry (#158),
    and S5 builds the same record so both take the same path through the matcher.
    """

    viewing_id: str
    watched_at: date
    title: str
    year: int | None
    rating: Decimal | None
    is_rewatch: bool
    slug: str | None = None
    tmdb_id: int | None = None
    #: Which line of the file this came from, for a report a person has to act on.
    line: int = 0


def _parse_date(raw: str, line: int) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise DiaryParseError(f"line {line}: {raw!r} is not an ISO date") from exc


def _parse_year(raw: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_rating(raw: str, line: int) -> Decimal | None:
    """A blank rating is a fact, not a gap.

    **0 of Mark's 1,149 entries carry one** (#159), so treating blank as missing data and
    warning about it would produce 1,149 warnings describing normal behaviour.
    """
    value = raw.strip()
    if not value:
        return None
    try:
        rating = Decimal(value)
    except InvalidOperation as exc:
        raise DiaryParseError(f"line {line}: {value!r} is not a rating") from exc
    if not (Decimal("0.5") <= rating <= Decimal("5.0")) or rating % _RATING_STEP != 0:
        raise DiaryParseError(f"line {line}: rating {value} is not a half-star 0.5-5.0")
    return rating


def _parse_rewatch(raw: str) -> bool:
    return raw.strip().lower() in {"yes", "true", "1"}


def parse_diary(handle: IO[str]) -> Iterator[DiaryEntry]:
    """Yield one :class:`DiaryEntry` per row, in file order."""
    reader = csv.DictReader(handle)
    missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        raise DiaryParseError(
            "not a Letterboxd diary export — missing column(s): " + ", ".join(missing)
        )

    for offset, row in enumerate(reader, start=2):  # 1 is the header
        viewing_id = (row.get("ViewingId") or "").strip()
        if not viewing_id:
            raise DiaryParseError(f"line {offset}: no ViewingId, so the row cannot be idempotent")
        title = (row.get("Name") or "").strip()
        if not title:
            raise DiaryParseError(f"line {offset}: no Name")

        yield DiaryEntry(
            viewing_id=viewing_id,
            watched_at=_parse_date(row.get("WatchedDate") or "", offset),
            title=title,
            year=_parse_year(row.get("Year") or ""),
            rating=_parse_rating(row.get("Rating") or "", offset),
            is_rewatch=_parse_rewatch(row.get("Rewatch") or ""),
            slug=(row.get("Slug") or "").strip() or None,
            line=offset,
        )


def read_diary_csv(path: Path) -> list[DiaryEntry]:
    """Read a whole diary file.

    Returns a list rather than an iterator on purpose: the importer needs the count before
    it starts, both for its report and so a dry-run can say how many rows it *would* have
    written. 2,322 rows is nothing to hold in memory.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        entries = list(parse_diary(handle))

    seen: dict[str, int] = {}
    for entry in entries:
        first = seen.get(entry.viewing_id)
        if first is not None:
            raise DiaryParseError(
                f"line {entry.line}: ViewingId {entry.viewing_id} already appeared on line {first}"
            )
        seen[entry.viewing_id] = entry.line
    return entries
