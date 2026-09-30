"""Batch V4 — "Craig's house" as a section, and migration 042 that allows it.

The name is the first in the vocabulary with an apostrophe. Migration 007 built the CHECK by
pasting each name inside quotes, which would end the SQL string after ``Craig``; 042
escapes it. These tests hold the clause, the constraint Postgres ends up with, and the
downgrade's order (clear the section, then narrow the CHECK) against a real row — the part
CI's empty-schema round trip cannot prove (`STATUS.md` gotchas 15 and 18).
"""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from src.models.collection_item import CRAIGS_HOUSE, SECTIONS, SHELVED_SECTIONS
from src.spreadsheet.parser import parse_location


def _load_migration(revision_prefix: str) -> ModuleType:
    """Load a migration by its file name, which is not an importable module name."""
    versions_dir = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    (path,) = versions_dir.glob(f"{revision_prefix}_*.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration_007 = _load_migration("007")
migration_042 = _load_migration("042")


# ---------------------------------------------------------------------------
# The vocabulary and the parser
# ---------------------------------------------------------------------------


def test_craigs_house_is_a_section_with_no_shelves() -> None:
    assert CRAIGS_HOUSE == "Craig's house"
    assert CRAIGS_HOUSE in SECTIONS
    assert CRAIGS_HOUSE not in SHELVED_SECTIONS
    # The migration spells the vocabulary out at its own revision; today's model agrees.
    assert tuple(SECTIONS) == migration_042._SECTIONS_V3


@pytest.mark.parametrize(
    "typed",
    ["Craig's house", "Craigs house", "craigs house", "CRAIG'S HOUSE", "Craig’s house"],
)
def test_typing_craigs_house_lands_there(typed: str) -> None:
    # The curly apostrophe is what an iPhone types by default.
    assert parse_location(typed) == ("Craig's house", None)


def test_a_house_that_is_not_craigs_is_not_filed_there() -> None:
    assert parse_location("Craig house") == (None, None)
    assert parse_location("Mark's house") == (None, None)


# ---------------------------------------------------------------------------
# Migration 042's SQL
# ---------------------------------------------------------------------------


def test_the_check_escapes_the_apostrophe() -> None:
    clause = migration_042._check_clause(migration_042._SECTIONS_V3)
    assert "'Craig''s house'" in clause
    assert clause.startswith("section IS NULL OR section IN (")
    for name in migration_042._SECTIONS_V2:
        assert f"'{name}'" in clause


def test_the_way_007_built_it_would_have_broken_on_the_apostrophe() -> None:
    # Why 042 has its own quoting: 007's pasting leaves a bare quote mid-string.
    clause = migration_007._check_clause((CRAIGS_HOUSE,))
    assert "'Craig's house'" in clause
    assert "'Craig''s house'" not in clause


class _RecordingOp:
    """Stands in for ``alembic.op`` and writes down what a migration asks it to do."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def execute(self, statement: Any) -> None:
        self.calls.append(("execute", str(statement)))

    def drop_constraint(self, name: str, table: str, type_: str) -> None:
        self.calls.append(("drop_constraint", (name, table, type_)))

    def create_check_constraint(self, name: str, table: str, condition: str) -> None:
        self.calls.append(("create_check_constraint", (name, table, condition)))


def _recorded(step: Callable[[], None], monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    recorder = _RecordingOp()
    monkeypatch.setattr(migration_042, "op", recorder)
    step()
    return recorder.calls


def test_the_upgrade_writes_no_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _recorded(migration_042.upgrade, monkeypatch)
    assert [name for name, _ in calls] == ["drop_constraint", "create_check_constraint"]
    assert "'Craig''s house'" in calls[1][1][2]


def test_the_downgrade_clears_the_section_before_narrowing_and_leaves_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _recorded(migration_042.downgrade, monkeypatch)
    assert [name for name, _ in calls] == ["execute", "drop_constraint", "create_check_constraint"]
    update = calls[0][1]
    assert update.startswith("UPDATE collection_items SET section = NULL WHERE section = :name")
    assert "location" not in update
    assert "Craig" not in calls[2][1][2]


# ---------------------------------------------------------------------------
# Against Postgres, inside the test's rolled-back transaction
# ---------------------------------------------------------------------------


async def test_the_live_check_holds_the_escaped_name(db_conn: AsyncConnection) -> None:
    definition = (
        await db_conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_collection_items_section'"
            )
        )
    ).scalar_one()
    assert "'Craig''s house'" in definition


async def _a_disc(db_conn: AsyncConnection, *, section: str | None, location: str) -> uuid.UUID:
    movie_id, item_id = uuid.uuid4(), uuid.uuid4()
    await db_conn.execute(
        text("INSERT INTO movies (id, title) VALUES (:id, 'Round Trip')"), {"id": movie_id}
    )
    await db_conn.execute(
        text(
            "INSERT INTO collection_items (id, movie_id, location, section) "
            "VALUES (:id, :movie, :location, :section)"
        ),
        {"id": item_id, "movie": movie_id, "location": location, "section": section},
    )
    return item_id


async def test_a_disc_can_be_in_craigs_house_and_nowhere_unlisted(
    db_conn: AsyncConnection,
) -> None:
    item = await _a_disc(db_conn, section=CRAIGS_HOUSE, location="Craigs house")
    stored = (
        await db_conn.execute(
            text("SELECT section FROM collection_items WHERE id = :id"), {"id": item}
        )
    ).scalar_one()
    assert stored == "Craig's house"

    savepoint = await db_conn.begin_nested()
    with pytest.raises(IntegrityError):
        await db_conn.execute(
            text("UPDATE collection_items SET section = 'Mark''s house' WHERE id = :id"),
            {"id": item},
        )
    await savepoint.rollback()


def _run(step: Callable[[], None]) -> Callable[[Connection], None]:
    def run(sync_conn: Connection) -> None:
        with Operations.context(MigrationContext.configure(sync_conn)):
            step()

    return run


async def test_the_downgrade_and_upgrade_round_trip_with_a_disc_there(
    db_conn: AsyncConnection,
) -> None:
    """The one round trip CI cannot make: its migration job runs on an empty schema."""
    item = await _a_disc(db_conn, section=CRAIGS_HOUSE, location="Craigs house, spare room")

    await db_conn.run_sync(_run(migration_042.downgrade))

    section, location = (
        await db_conn.execute(
            text("SELECT section, location FROM collection_items WHERE id = :id"), {"id": item}
        )
    ).one()
    assert section is None
    assert location == "Craigs house, spare room"

    # Narrowed: the name is refused again until the upgrade.
    savepoint = await db_conn.begin_nested()
    with pytest.raises(IntegrityError):
        await db_conn.execute(
            text("UPDATE collection_items SET section = :name WHERE id = :id"),
            {"name": CRAIGS_HOUSE, "id": item},
        )
    await savepoint.rollback()

    await db_conn.run_sync(_run(migration_042.upgrade))
    await db_conn.execute(
        text("UPDATE collection_items SET section = :name WHERE id = :id"),
        {"name": CRAIGS_HOUSE, "id": item},
    )
