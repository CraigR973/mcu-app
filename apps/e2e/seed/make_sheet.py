"""The import fixture: a small sheet in the shape of the real catalogue's columns.

usage: make_sheet.py <out.xlsx> [rows.json [first data row]]
The titles come from the fake TMDB's catalogue, so every row can settle.
"""

import json
import sys
from pathlib import Path

from openpyxl import Workbook

from outside_world.catalogue import NAMED

#: (title, format as the sheet writes it, location as the sheet writes it)
ROWS = [
    ("The Lighthouse Keeper (1994)", "4K", "Front 1st shelf"),
    ("Night Train to Lisbon Docks", "Blu-ray", "Front 2nd shelf"),
    ("Copper Canyon", "DVD", "Back 1st shelf"),
    ("Paper Moons Over Leeds", "Blu-ray", "Back 2nd shelf"),
    ("The Quiet Engine", "4K", "Lounge"),
    ("Harbour Lights", "Blu-ray", "Garage"),
    ("A Winter Of Wolves", "4K", "Front 3rd shelf"),
    ("Glass Orchard", "DVD", "Back 3rd shelf"),
]


def main(out: Path, rows_file: Path | None = None, first_row: int = 2) -> None:
    """With ``rows_file`` (a JSON list of [title, format, location]) the sheet holds those rows."""
    assert len(ROWS) <= len(NAMED)
    rows = [tuple(row) for row in json.loads(rows_file.read_text())] if rows_file else ROWS
    book = Workbook()
    sheet = book.active
    sheet.append(["Title", "Format", "Location", "Category", "Sub Category", "Type"])
    # The importer keys an item on its sheet row, so a second sheet must start further down
    # than the first, as a real one does: the blank rows before it are skipped.
    for _ in range(first_row - 2):
        sheet.append([None, None, None, None, None, None])
    for title, fmt, location in rows:
        sheet.append([title, fmt, location, "Film", "", "Disc"])
    # A blank row, as the real sheet has trailing ones: the parser must drop it.
    sheet.append([None, None, None, None, None, None])
    book.save(out)


if __name__ == "__main__":
    main(
        Path(sys.argv[1]),
        Path(sys.argv[2]) if len(sys.argv) > 2 else None,
        int(sys.argv[3]) if len(sys.argv) > 3 else 2,
    )
