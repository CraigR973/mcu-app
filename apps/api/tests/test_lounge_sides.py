"""Mark's request of 14 Oct: the Lounge cabinet's left and right sides, and migration 055.

He chose the Lounge from the Section picker, typed "Right Hand Side" in the Location box, and
saved; the copy came back as plain "Lounge". #266's rule (13 Oct) dropped any text naming a
different place from the pickers, and text naming no place at all counted as different. Two
copies lost their side that way: Nope and Us, both 4K.

So the Lounge's sides become its shelves, a picker like Front's and Back's; text naming no
place is kept as a detail of the one the pickers chose; and 055 fills in the side for the
copies whose text already said it. The rules are pure and run anywhere; the migration's
round trip runs against Postgres in CI.
"""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncConnection

from src.models.collection_item import (
    LOUNGE,
    LOUNGE_SIDES,
    SECTIONS,
    location_text,
    shelf_label,
    shelf_noun,
)
from src.routers.collection import _resolve_location
from src.routers.movies import _shelf_facets, location_label
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


migration_055 = _load_migration("055")


@dataclass
class _Form:
    """What the copy form, or a move, sends: the three place fields."""

    location: str | None = None
    section: str | None = None
    shelf: str | None = None


# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------


def test_the_lounge_is_a_section_with_two_sides() -> None:
    assert LOUNGE in SECTIONS
    assert LOUNGE_SIDES == ("Left", "Right")
    assert shelf_noun(LOUNGE) == "side"
    assert shelf_noun("Front") == "shelf"
    assert shelf_label(LOUNGE, "Left") == "Left hand side"
    assert shelf_label("Front", "2nd") == "2nd shelf"


def test_a_side_is_spelled_as_the_imported_lounge_copies_spell_it() -> None:
    """162 imported copies read "Lounge Cabinet - Right/Left Hand Side"."""
    assert location_text(LOUNGE, "Right") == "Lounge Cabinet - Right Hand Side"
    assert location_text(LOUNGE, None) == "Lounge"
    assert location_text("Back", "3rd") == "Back 3rd shelf"
    assert location_text("Garage", None) == "Garage"


def test_the_film_page_label_names_the_side() -> None:
    assert location_label(LOUNGE, "Left") == "Lounge Left"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Lounge Cabinet - Right Hand Side", (LOUNGE, "Right")),
        ("Lounge Cabinet - Left Hand Side", (LOUNGE, "Left")),
        # Two live copies carry their download's path too.
        ("Lounge Cabinet - Left Hand Side & E:\\Movies", (LOUNGE, "Left")),
        ("lounge right", (LOUNGE, "Right")),
        # Both sides, or neither, name no side.
        ("Lounge, left or right", (LOUNGE, None)),
        ("Lounge", (LOUNGE, None)),
        # A shelf typed in the Lounge still reads as one, as before.
        ("Lounge 4th shelf", (LOUNGE, "4th")),
        # Sides are read only inside the Lounge: this is a cabinet in the fish room.
        ("Left Hand Side Small Cabinet Fish Room", ("Fish Room Cabinet", None)),
        # And text that is not a place names no side, whatever it says.
        ("Right Hand Side", (None, None)),
    ],
)
def test_the_parser_reads_a_lounge_side(raw: str, expected: tuple[str | None, ...]) -> None:
    assert parse_location(raw) == expected


# ---------------------------------------------------------------------------
# What a save stores
# ---------------------------------------------------------------------------


def test_the_side_picker_files_the_disc_and_writes_its_text() -> None:
    assert _resolve_location(_Form(section=LOUNGE, shelf="Right")) == (
        "Lounge Cabinet - Right Hand Side",
        LOUNGE,
        "Right",
    )


def test_marks_typed_side_is_kept_and_read_from_an_app_without_the_picker() -> None:
    """The save that lost Nope's side, sent by a phone still on the app before this fix."""
    assert _resolve_location(_Form(location="Right Hand Side", section=LOUNGE)) == (
        "Lounge - Right Hand Side",
        LOUNGE,
        "Right",
    )


def test_detail_typed_in_a_section_without_shelves_is_kept_after_it() -> None:
    assert _resolve_location(_Form(location="top row", section="Garage")) == (
        "Garage - top row",
        "Garage",
        None,
    )


def test_a_detail_already_saved_is_kept_as_written_on_the_next_save() -> None:
    saved = _Form(location="Garage - top row", section="Garage")
    assert _resolve_location(saved) == ("Garage - top row", "Garage", None)


def test_an_imported_lounge_copy_re_saved_keeps_its_text() -> None:
    """Every one of the 164, once 055 has given it its side."""
    copy = _Form(
        location="Lounge Cabinet - Left Hand Side & E:\\Movies", section=LOUNGE, shelf="Left"
    )
    assert _resolve_location(copy) == (copy.location, LOUNGE, "Left")


def test_a_new_side_replaces_text_naming_the_old_one() -> None:
    """#266's rule, for sides: the picker moved the disc, the text did not follow."""
    moved = _Form(location="Lounge Cabinet - Right Hand Side", section=LOUNGE, shelf="Left")
    assert _resolve_location(moved) == ("Lounge Cabinet - Left Hand Side", LOUNGE, "Left")


def test_a_lounge_copy_without_its_side_would_lose_its_text() -> None:
    """Why 055 has to land with the parser: unfilled, the next edit wipes the side."""
    unfilled = _Form(location="Lounge Cabinet - Right Hand Side", section=LOUNGE)
    assert _resolve_location(unfilled) == ("Lounge", LOUNGE, None)


def test_the_12_angry_men_rule_still_holds_for_shelves() -> None:
    moved = _Form(location="Front 3rd shelf", section="Front", shelf="4th")
    assert _resolve_location(moved) == ("Front 4th shelf", "Front", "4th")


def test_typed_text_alone_is_still_filed_by_the_parser() -> None:
    typed = _Form(location="Lounge Cabinet - Left Hand Side")
    assert _resolve_location(typed) == (typed.location, LOUNGE, "Left")


# ---------------------------------------------------------------------------
# What the pickers offer
# ---------------------------------------------------------------------------


def test_the_lounge_offers_both_sides_even_while_one_is_empty() -> None:
    offered = _shelf_facets(LOUNGE, [("Right", 96, 90), (None, 2, 2)])
    assert [(entry.shelf, entry.label, entry.itemCount) for entry in offered] == [
        ("Left", "Left hand side", 0),
        ("Right", "Right hand side", 96),
    ]


def test_front_offers_the_shelves_its_discs_are_on_in_order() -> None:
    offered = _shelf_facets("Front", [("3rd", 5, 5), ("1st", 2, 2), (None, 1, 1)])
    assert [(entry.shelf, entry.label) for entry in offered] == [
        ("1st", "1st shelf"),
        ("3rd", "3rd shelf"),
    ]


def test_a_section_without_shelves_offers_none() -> None:
    assert _shelf_facets("Garage", [(None, 35, 35)]) == []


# ---------------------------------------------------------------------------
# Migration 055, against Postgres inside the test's rolled-back transaction
# ---------------------------------------------------------------------------


def _run(step: Callable[[], None]) -> Callable[[Connection], None]:
    def run(sync_conn: Connection) -> None:
        with Operations.context(MigrationContext.configure(sync_conn)):
            step()

    return run


async def _a_lounge_disc(
    db_conn: AsyncConnection, location: str, *, shelf: str | None = None, deleted: bool = False
) -> uuid.UUID:
    movie_id, item_id = uuid.uuid4(), uuid.uuid4()
    await db_conn.execute(
        text("INSERT INTO movies (id, title) VALUES (:id, 'Lounge Film')"), {"id": movie_id}
    )
    await db_conn.execute(
        text(
            "INSERT INTO collection_items (id, movie_id, location, section, shelf, deleted_at) "
            "VALUES (:id, :movie, :location, 'Lounge', :shelf, :deleted_at)"
        ),
        {
            "id": item_id,
            "movie": movie_id,
            "location": location,
            "shelf": shelf,
            "deleted_at": datetime(2026, 1, 1) if deleted else None,
        },
    )
    return item_id


async def _place(db_conn: AsyncConnection, item: uuid.UUID) -> tuple[str | None, str | None]:
    row = (
        await db_conn.execute(
            text("SELECT shelf, location FROM collection_items WHERE id = :id"), {"id": item}
        )
    ).one()
    return row[0], row[1]


async def test_055_fills_each_side_from_the_text_and_its_downgrade_clears_them(
    db_conn: AsyncConnection,
) -> None:
    # CI's database is at head, so the sides are cleared first: the state before 055.
    await db_conn.run_sync(_run(migration_055.downgrade))
    right = await _a_lounge_disc(db_conn, "Lounge Cabinet - Right Hand Side")
    left = await _a_lounge_disc(db_conn, "Lounge Cabinet - Left Hand Side & E:\\Movies")
    trashed = await _a_lounge_disc(db_conn, "Lounge Cabinet - Right Hand Side", deleted=True)
    bare = await _a_lounge_disc(db_conn, "Lounge")
    both = await _a_lounge_disc(db_conn, "Lounge, left or right")
    # "Brightly" holds "right" but not as a word.
    brightly = await _a_lounge_disc(db_conn, "Lounge, brightly lit")
    # A side already set is never overwritten.
    picked = await _a_lounge_disc(db_conn, "Lounge Cabinet - Right Hand Side", shelf="Left")

    await db_conn.run_sync(_run(migration_055.upgrade))

    assert await _place(db_conn, right) == ("Right", "Lounge Cabinet - Right Hand Side")
    assert await _place(db_conn, left) == ("Left", "Lounge Cabinet - Left Hand Side & E:\\Movies")
    assert (await _place(db_conn, trashed))[0] == "Right"
    assert (await _place(db_conn, bare))[0] is None
    assert (await _place(db_conn, both))[0] is None
    assert (await _place(db_conn, brightly))[0] is None
    assert (await _place(db_conn, picked))[0] == "Left"

    await db_conn.run_sync(_run(migration_055.downgrade))

    assert await _place(db_conn, right) == (None, "Lounge Cabinet - Right Hand Side")
    assert (await _place(db_conn, picked))[0] is None

    # Back to head, as the rest of the suite expects.
    await db_conn.run_sync(_run(migration_055.upgrade))
