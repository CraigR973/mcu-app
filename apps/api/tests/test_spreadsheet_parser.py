from __future__ import annotations

import io
from pathlib import Path

import openpyxl
import pytest

from src.spreadsheet.models import ImportCandidate
from src.spreadsheet.parser import (
    _build_header_map,
    normalise_formats,
    normalise_title,
    parse_location,
    parse_row,
    parse_xlsx,
)

# ---------------------------------------------------------------------------
# normalise_formats
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Blu-ray", ["blu_ray"]),
        ("BLU-RAY", ["blu_ray"]),
        ("blu ray", ["blu_ray"]),
        ("BD", ["blu_ray"]),
        ("4K UHD", ["4k_uhd"]),
        ("4k uhd", ["4k_uhd"]),
        ("4K", ["4k_uhd"]),
        ("UHD", ["4k_uhd"]),
        ("4K Blu-ray", ["4k_uhd"]),
        ("DVD", ["dvd"]),
        ("dvd", ["dvd"]),
        ("Download", ["download"]),
        ("Digital Download", ["download"]),
        ("digital", ["download"]),
        # combo packs
        ("Blu-ray + DVD + Download", ["blu_ray", "dvd", "download"]),
        ("DVD / Download", ["dvd", "download"]),
        ("Blu-ray, DVD", ["blu_ray", "dvd"]),
        ("4K UHD & Blu-ray", ["4k_uhd", "blu_ray"]),
        ("Blu-ray and Download", ["blu_ray", "download"]),
        # deduplicated
        ("Blu-ray + Blu-ray", ["blu_ray"]),
        # empty / unknown
        ("", []),
        ("VHS", []),
    ],
)
def test_normalise_formats(raw: str, expected: list[str]) -> None:
    assert normalise_formats(raw) == expected


# ---------------------------------------------------------------------------
# parse_location
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, exp_section, exp_shelf",
    [
        ("Front 2nd shelf", "Front", "2nd"),
        ("front 2nd shelf", "Front", "2nd"),
        ("FRONT 2ND SHELF", "Front", "2nd"),
        ("Front 1st", "Front", "1st"),
        ("Back 3rd shelf", "Back", "3rd"),
        ("Back 10th shelf", "Back", "10th"),
        ("Lounge", "Lounge", None),
        ("Garage", "Garage", None),
        ("Digital", "Digital", None),
        # bare number normalised to ordinal
        ("Front 2 shelf", "Front", "2nd"),
        ("Back 1 shelf", "Back", "1st"),
        ("Lounge 4th shelf", "Lounge", "4th"),
        # no location
        ("", None, None),
        ("   ", None, None),
        # unknown section still extracts shelf
        ("Storage 3rd", None, "3rd"),
    ],
)
def test_parse_location(raw: str, exp_section: str | None, exp_shelf: str | None) -> None:
    section, shelf = parse_location(raw)
    assert section == exp_section
    assert shelf == exp_shelf


# ---------------------------------------------------------------------------
# normalise_title
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Already mixed-case — trusted as-is
        ("The Dark Knight", "The Dark Knight"),
        ("Avengers: Infinity War", "Avengers: Infinity War"),
        # ALL CAPS — title-cased with article lowercasing
        ("THE DARK KNIGHT", "The Dark Knight"),
        ("AVENGERS INFINITY WAR", "Avengers Infinity War"),
        ("A MAN FOR ALL SEASONS", "A Man for All Seasons"),
        # Single word
        ("INCEPTION", "Inception"),
        # Empty
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalise_title(raw: str, expected: str) -> None:
    assert normalise_title(raw) == expected


# ---------------------------------------------------------------------------
# parse_row
# ---------------------------------------------------------------------------

HEADER_MAP = _build_header_map(
    ("Title", "Format", "Location", "Category", "Sub Category", "Type")
)


def test_parse_row_basic() -> None:
    row = ("The Dark Knight", "Blu-ray", "Front 2nd shelf", "Film", "Action", "Single")
    result = parse_row(row, HEADER_MAP, row_number=2)
    assert result is not None
    assert result.title == "The Dark Knight"
    assert result.formats == ["blu_ray"]
    assert result.location_raw == "Front 2nd shelf"
    assert result.section == "Front"
    assert result.shelf == "2nd"
    assert result.category == "Film"
    assert result.sub_category == "Action"
    assert result.item_type == "Single"
    assert result.row_number == 2


def test_parse_row_combo_format() -> None:
    row = ("Inception", "4K UHD + Blu-ray", "Front 1st shelf", "Film", "Sci-Fi", "Single")
    result = parse_row(row, HEADER_MAP, row_number=5)
    assert result is not None
    assert result.formats == ["4k_uhd", "blu_ray"]


def test_parse_row_missing_title_returns_none() -> None:
    row = ("", "Blu-ray", "Front 2nd shelf", "Film", "Action", "Single")
    assert parse_row(row, HEADER_MAP, row_number=3) is None


def test_parse_row_none_title_returns_none() -> None:
    row = (None, "Blu-ray", "Front 2nd shelf", "Film", "Action", "Single")
    assert parse_row(row, HEADER_MAP, row_number=4) is None


def test_parse_row_empty_optional_fields() -> None:
    row = ("Jaws", "DVD", "", None, None, None)
    result = parse_row(row, HEADER_MAP, row_number=6)
    assert result is not None
    assert result.section is None
    assert result.shelf is None
    assert result.category is None
    assert result.sub_category is None
    assert result.item_type is None


def test_parse_row_preserves_raw_location() -> None:
    row = ("Alien", "Blu-ray", "Back 3rd shelf", "Film", "Sci-Fi", "Single")
    result = parse_row(row, HEADER_MAP, row_number=7)
    assert result is not None
    assert result.location_raw == "Back 3rd shelf"


# ---------------------------------------------------------------------------
# parse_xlsx — integration test via in-memory workbook
# ---------------------------------------------------------------------------

SAMPLE_ROWS: list[tuple[str | None, ...]] = [
    ("Title", "Format", "Location", "Category", "Sub Category", "Type"),
    ("The Dark Knight", "Blu-ray", "Front 2nd shelf", "Film", "Action", "Single"),
    ("Inception", "4K UHD", "Front 1st shelf", "Film", "Sci-Fi", "Single"),
    ("Jaws", "DVD", "Back 3rd shelf", "Film", "Thriller", "Single"),
    ("The Godfather", "Blu-ray + DVD", "Lounge", "Film", "Drama", "Single"),
    (
        "Blade Runner 2049",
        "4K UHD + Blu-ray + Download",
        "Front 1st shelf",
        "Film",
        "Sci-Fi",
        "Single",
    ),
    # Empty row — should be skipped
    (None, None, None, None, None, None),
    ("Alien", "Blu-ray", "Back 1st shelf", "Film", "Sci-Fi", "Single"),
]


def _make_xlsx_bytes(rows: list[tuple[str | None, ...]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx(tmp_path: Path) -> Path:
    data = _make_xlsx_bytes(SAMPLE_ROWS)
    p = tmp_path / "collection.xlsx"
    p.write_bytes(data)
    return p


def test_parse_xlsx_row_count(sample_xlsx: Path) -> None:
    results = parse_xlsx(sample_xlsx)
    # 7 data rows, 1 blank → 6 candidates
    assert len(results) == 6


def test_parse_xlsx_first_row(sample_xlsx: Path) -> None:
    results = parse_xlsx(sample_xlsx)
    first = results[0]
    assert first.title == "The Dark Knight"
    assert first.formats == ["blu_ray"]
    assert first.section == "Front"
    assert first.shelf == "2nd"
    assert first.row_number == 2


def test_parse_xlsx_combo_formats(sample_xlsx: Path) -> None:
    results = parse_xlsx(sample_xlsx)
    blade = next(r for r in results if "Blade Runner" in r.title)
    assert blade.formats == ["4k_uhd", "blu_ray", "download"]


def test_parse_xlsx_lounge_no_shelf(sample_xlsx: Path) -> None:
    results = parse_xlsx(sample_xlsx)
    godfather = next(r for r in results if "Godfather" in r.title)
    assert godfather.section == "Lounge"
    assert godfather.shelf is None


def test_parse_xlsx_no_title_column_raises(tmp_path: Path) -> None:
    bad_rows: list[tuple[str, ...]] = [
        ("Film", "Format", "Location"),
        ("The Dark Knight", "Blu-ray", "Front 2nd shelf"),
    ]
    p = tmp_path / "bad.xlsx"
    p.write_bytes(_make_xlsx_bytes(bad_rows))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no 'Title' column"):
        parse_xlsx(p)


def test_parse_xlsx_empty_workbook(tmp_path: Path) -> None:
    p = tmp_path / "empty.xlsx"
    p.write_bytes(_make_xlsx_bytes([]))
    assert parse_xlsx(p) == []


def test_parse_xlsx_returns_import_candidates(sample_xlsx: Path) -> None:
    results = parse_xlsx(sample_xlsx)
    for item in results:
        assert isinstance(item, ImportCandidate)


def test_parse_xlsx_row_numbers_are_sequential(sample_xlsx: Path) -> None:
    results = parse_xlsx(sample_xlsx)
    # Row 2 is first data row (row 1 is header); blank row is skipped
    row_nums = [r.row_number for r in results]
    assert row_nums == [2, 3, 4, 5, 6, 8]
