"""Re-checking the old paths' identifications — Batch X9 (CT46-01). These run in CI.

**What this proves:** the re-check reads only copies the import or the diary identified,
not films T9 or a person has identified since (unless that was undone); it asks T9 once per
sheet title and grouping and sorts every answer into a verdict; the review's French
Connection and Good Fellas rows, through T9's real identifier, are flagged; the report says
of each of the 30 known wrong copies whether it appears, was corrected already, or was missed;
and applying the plan raises a doubt per copy, strongest first, leaving a copy that changed
since the dry run and one Craig kept before.

**What it does not:** the live TMDB, or the spreadsheet. Craig's run at the Mac is that.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.clock import utcnow
from src.models.identify import IdentifyDoubt
from src.services.identification import identify_film, undo_identification
from src.services.identify.matcher import Candidate, Identifier, Proposal
from src.services.identify.recheck import (
    DOUBT_CLASSES,
    KNOWN_WRONG,
    KnownCopy,
    OldCopy,
    RecheckPlan,
    SheetRow,
    judge,
    old_path_copies,
    raise_one,
    recheck,
    render_report,
    to_raise,
)
from tests.test_identify_films import _disc, _film, _person, _record, _tmdb_ids
from tests.test_import_collection import _NamesakeTmdb

NOW = datetime(2026, 10, 16, 21, 0)


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


def _copy(tmdb_id: int = 10711, row: int | None = 550, **fields: Any) -> OldCopy:
    values: dict[str, Any] = {
        "item_id": str(uuid.uuid4()),
        "movie_id": str(uuid.uuid4()),
        "film_title": "French Connection II",
        "film_year": 1975,
        "tmdb_id": tmdb_id,
        "sheet_row": row,
        "grouping": None,
    }
    values.update(fields)
    return OldCopy(**values)


def _candidate(tmdb_id: int, title: str, year: int, votes: int = 100) -> Candidate:
    return Candidate(
        tmdb_id=tmdb_id, title=title, original_title=title, year=year, vote_count=votes
    )


# ---------------------------------------------------------------------------
# Reading the copies the old paths decided
# ---------------------------------------------------------------------------


async def test_only_copies_the_old_paths_decided_are_re_checked(db: AsyncSession) -> None:
    imported_id, t9_id, undone_id = _tmdb_ids()
    imported = await _film(db, "French Connection II", tmdb_id=imported_id, year=1975)
    imported_disc = await _disc(db, imported, "blu_ray", import_source_row=550)
    by_t9 = await _film(db, "Peeping Tom")
    await _disc(db, by_t9, "dvd", import_source_row=1200)
    craig = await _person(db)
    await identify_film(db, by_t9, _record(t9_id, "Peeping Tom", 1960), by=None, how="auto")
    undone = await _film(db, "Holiday")
    undone_disc = await _disc(db, undone, "dvd", import_source_row=713)
    done = await identify_film(
        db, undone, _record(undone_id, "Holiday", 1938), by=craig.id, how="picked"
    )
    await undo_identification(db, done.audit.id, by=craig.id)
    # An undo leaves the row unidentified; give it an identification no one audited, as the
    # diary import's were.
    undone.tmdb_id = undone_id
    await db.flush()

    found = {copy.item_id: copy for copy in await old_path_copies(db)}

    assert str(imported_disc.id) in found and str(undone_disc.id) in found
    assert all(copy.movie_id != str(by_t9.id) for copy in found.values())
    copy = found[str(imported_disc.id)]
    assert (copy.tmdb_id, copy.sheet_row, copy.film_year) == (imported_id, 550, 1975)


# ---------------------------------------------------------------------------
# Judging T9's answer
# ---------------------------------------------------------------------------


def test_every_answer_gets_a_verdict() -> None:
    sheet = SheetRow("French Connection", None)
    copy = _copy()
    real = _candidate(1051, "The French Connection", 1971, 2400)
    sequel = _candidate(10711, "French Connection II", 1975, 486)

    agrees = judge(copy, sheet, Proposal("identify", chosen=sequel, candidates=[sequel]))
    different = judge(copy, sheet, Proposal("identify", chosen=real, candidates=[real]))
    series = judge(copy, sheet, Proposal("set_aside", set_aside_as="tv", reason="A series."))
    not_film = judge(copy, sheet, Proposal("set_aside", set_aside_as="not_film"))
    unsure = judge(copy, sheet, Proposal("ask", chosen=sequel, candidates=[sequel, real]))
    not_offered = judge(copy, sheet, Proposal("ask", candidates=[real]))
    nothing = judge(copy, sheet, Proposal("ask", reason="TMDB could not be reached."))

    assert [c.verdict for c in (agrees, different, series, not_film)] == [
        "agrees",
        "different",
        "series",
        "not_film",
    ]
    assert [c.verdict for c in (unsure, not_offered, nothing)] == [
        "unsure",
        "not_offered",
        "nothing",
    ]
    assert different.note == (
        "T9 identifies the sheet's “French Connection” as The French Connection (1971), "
        "not French Connection II (1975)."
    )
    assert different.proposed_tmdb_id == 1051
    assert [c["tmdb_id"] for c in different.candidates] == [1051]
    assert unsure.proposed_tmdb_id is None
    assert series.evidence == ["A series."]


async def test_the_reviews_namesake_rows_are_flagged_by_t9s_real_identifier() -> None:
    """French Connection on the sequel and Good Fellas on a 0-vote namesake (CT46-01)."""
    sheet = {550: SheetRow("French Connection", None), 614: SheetRow("Good Fellas", None)}
    copies = [
        _copy(10711, 550),
        _copy(626867, 614, film_title="Good Fellas", film_year=2016),
        _copy(10711, None),
    ]

    plan = await recheck(copies, sheet, Identifier(_NamesakeTmdb()), now=NOW)  # type: ignore[arg-type]

    verdicts = {item.sheet_row: (item.verdict, item.proposed_tmdb_id) for item in plan.items}
    assert verdicts[550] == ("different", 1051)
    # T9 will not choose between the namesake and GoodFellas: it asks, and the doubt asks.
    assert verdicts[614][0] == "unsure"
    assert plan.without_row == 1


async def test_one_sheet_title_is_asked_about_once() -> None:
    calls: list[str] = []

    class Counting(Identifier):
        async def identify(self, parsed: Any, *, held: Any = None) -> Proposal:
            calls.append(parsed.main)
            return Proposal("ask")

    sheet = {1: SheetRow("Dunkirk", "War"), 2: SheetRow("Dunkirk", "War")}
    copies = [_copy(1, 1, grouping="War"), _copy(2, 2, grouping=" war ")]
    await recheck(copies, sheet, Counting(_NamesakeTmdb()), now=NOW)  # type: ignore[arg-type]

    assert len(calls) == 1


async def test_a_row_from_another_version_of_the_sheet_is_not_re_checked() -> None:
    """Copies are keyed by spreadsheet line since the 18 Sep refresh: a row whose grouping is
    not the copy's is another row, so its title says nothing about the copy."""
    sheet = {728: SheetRow("Comedy Classics Box", "Comedy")}
    copy = _copy(259577, 728, film_title="House on the River", grouping="Fritz Lang")
    known = {728: KnownCopy(728, copy.item_id, 259577, None, "House on the River")}

    plan = await recheck([copy], sheet, Identifier(_NamesakeTmdb()), now=NOW, known=known)  # type: ignore[arg-type]

    assert (plan.items, plan.mismatched) == ([], [728])
    status = {check.row: check.status for check in plan.known}
    assert status[728] == "Not re-checked: the sheet's row has another grouping than the copy."
    assert "1 a row with another grouping" in render_report(plan, app_url="https://mcu.example")


# ---------------------------------------------------------------------------
# The review's 30, and the report
# ---------------------------------------------------------------------------


async def test_each_known_wrong_copy_is_accounted_for() -> None:
    sheet = {550: SheetRow("French Connection", None), 614: SheetRow("Good Fellas", None)}
    copies = [_copy(10711, 550), _copy(626867, 614, film_title="Good Fellas", film_year=2016)]
    known = {
        550: KnownCopy(550, "a", 10711, None, "French Connection II"),
        614: KnownCopy(614, "b", 626867, None, "Good Fellas"),
        141: KnownCopy(141, "c", None, 4613, "Band of Brothers"),
        878: KnownCopy(878, "d", 10730, None, "King Kong"),
        1335: KnownCopy(1335, "e", 1550418, None, "Rome"),
    }

    plan = await recheck(copies, sheet, Identifier(_NamesakeTmdb()), now=NOW, known=known)  # type: ignore[arg-type]

    status = {check.row: check.status for check in plan.known}
    assert len(status) == len(KNOWN_WRONG) == 30
    assert status[550].startswith("Appears: different.")
    assert status[614].startswith("Appears: unsure.")
    assert status[141] == "Already corrected: identified as the series “Band of Brothers”."
    assert status[878] == "Already corrected: the copy is now “King Kong”."
    assert status[1335] == (
        "Not re-checked: the film was identified again by T9 or a person since."
    )
    assert status[115] == "No live copy from this row: it was sold, binned or never imported."
    report = render_report(plan, app_url="https://mcu.example/")
    assert "| 550 | French Connection | 10711 | Appears: different." in report
    assert "/movies/" in report and "## different (1)" in report


def test_a_plan_reads_back_as_it_was_saved(tmp_path: Path) -> None:
    item = judge(_copy(), SheetRow("French Connection", None), Proposal("ask"))
    plan = RecheckPlan(1, "2026-10-16T21:00:00", 1, 4, [item], without_row=2)

    plan.save(tmp_path / "plan.json")
    again = RecheckPlan.load(tmp_path / "plan.json")

    assert again == plan
    (tmp_path / "old.json").write_text('{"version": 0}', encoding="utf-8")
    with pytest.raises(ValueError, match="not a version 1"):
        RecheckPlan.load(tmp_path / "old.json")


# ---------------------------------------------------------------------------
# Applying, at Craig's word
# ---------------------------------------------------------------------------


async def test_applying_raises_a_doubt_per_copy_strongest_first(db: AsyncSession) -> None:
    sequel_id, namesake_id, other_id = _tmdb_ids()
    sequel = await _film(db, "French Connection II", tmdb_id=sequel_id, year=1975)
    wrong = await _disc(db, sequel, "blu_ray", import_source_row=550, sub_category="Crime")
    namesake = await _film(db, "Good Fellas", tmdb_id=namesake_id, year=2016)
    unsure_disc = await _disc(db, namesake, "blu_ray", import_source_row=614)
    moved_on = await _film(db, "Dangerous", tmdb_id=other_id, year=2021)
    moved_disc = await _disc(db, moved_on, "download", import_source_row=366)
    await db.commit()

    def checked(film: Any, disc: Any, verdict: str, title: str) -> Any:
        copy = _copy(
            film.tmdb_id,
            disc.import_source_row,
            item_id=str(disc.id),
            movie_id=str(film.id),
            film_title=film.title,
            film_year=film.year,
        )
        item = judge(copy, SheetRow(title, disc.sub_category), Proposal("ask"))
        item.verdict, item.note = verdict, f"{title}: {verdict}."
        return item

    plan = RecheckPlan(
        1,
        "2026-10-16T21:00:00",
        3,
        0,
        [
            checked(namesake, unsure_disc, "unsure", "Good Fellas"),
            checked(sequel, wrong, "different", "French Connection"),
            checked(moved_on, moved_disc, "different", "Dangerous"),
        ],
    )
    moved_on.tmdb_id = other_id + 7
    await db.commit()

    order = [item.sheet_title for item in to_raise(plan, DOUBT_CLASSES)]
    results = [await raise_one(db, item) for item in to_raise(plan, DOUBT_CLASSES)]

    assert order == ["French Connection", "Dangerous", "Good Fellas"]
    assert results == ["raised", "changed", "raised"]
    doubt = await db.scalar(
        select(IdentifyDoubt).where(IdentifyDoubt.collection_item_id == wrong.id)
    )
    assert doubt is not None
    assert (doubt.source, doubt.status, doubt.search_hint) == (
        "recheck",
        "open",
        "French Connection",
    )
    assert doubt.evidence[0] == "Spreadsheet row 550: “French Connection”, under Crime."
    assert [item.sheet_title for item in to_raise(plan, ["unsure"])] == ["Good Fellas"]

    doubt.status, doubt.decided_utc = "kept", utcnow()
    await db.commit()
    assert await raise_one(db, plan.items[1]) == "kept_before"
