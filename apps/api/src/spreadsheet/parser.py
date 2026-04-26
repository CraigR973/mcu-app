from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import openpyxl

from .models import ImportCandidate

# ---------------------------------------------------------------------------
# Format normalisation
# ---------------------------------------------------------------------------

# Order matters: check 4K before Blu-ray (some cells say "4K Blu-ray")
_FORMAT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"4k[\s\-]?uhd|4k[\s\-]?blu|uhd|4k", re.IGNORECASE), "4k_uhd"),
    (re.compile(r"blu[\s\-]?ray|b[\s\-]?ray|bd", re.IGNORECASE), "blu_ray"),
    (re.compile(r"dvd", re.IGNORECASE), "dvd"),
    (re.compile(r"download|digital", re.IGNORECASE), "download"),
]


def normalise_formats(raw: str) -> list[str]:
    """
    Convert a free-text format cell to a deduplicated list of format codes.

    Examples:
        "Blu-ray"                          → ["blu_ray"]
        "4K UHD"                           → ["4k_uhd"]
        "Blu-ray + DVD + Download"         → ["blu_ray", "dvd", "download"]
        "4K Blu-ray"                       → ["4k_uhd"]
        "DVD / Download"                   → ["dvd", "download"]
    """
    # Split on common separators while keeping each token for matching
    tokens = re.split(r"[+/,&]|\band\b", raw, flags=re.IGNORECASE)
    seen: list[str] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        for pattern, code in _FORMAT_RULES:
            if pattern.search(token):
                if code not in seen:
                    seen.append(code)
                break
    return seen


# ---------------------------------------------------------------------------
# Location normalisation
# ---------------------------------------------------------------------------

# Known section keywords (case-insensitive prefix match)
_SECTIONS: list[str] = ["Front", "Back", "Lounge", "Garage", "Digital"]

_ORDINAL_RE = re.compile(
    r"\b(\d+(?:st|nd|rd|th)?)\b",
    re.IGNORECASE,
)


def parse_location(raw: str) -> tuple[str | None, str | None]:
    """
    Extract (section, shelf) from a free-text location string.

    Examples:
        "Front 2nd shelf"  → ("Front", "2nd")
        "Back 3rd"         → ("Back", "3rd")
        "front 1st shelf"  → ("Front", "1st")
        "Lounge"           → ("Lounge", None)
        "Digital"          → ("Digital", None)
        ""                 → (None, None)
    """
    stripped = raw.strip()
    if not stripped:
        return None, None

    section: str | None = None
    for name in _SECTIONS:
        if stripped.lower().startswith(name.lower()):
            section = name
            break

    shelf: str | None = None
    m = _ORDINAL_RE.search(stripped)
    if m:
        shelf = m.group(1).lower()
        # Normalise bare digits: "2" → "2nd" etc.
        if shelf.isdigit():
            shelf = _add_ordinal_suffix(int(shelf))

    return section, shelf


def _add_ordinal_suffix(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ---------------------------------------------------------------------------
# Title normalisation
# ---------------------------------------------------------------------------

# Articles that stay lowercase when not the first word (English)
_LOWERCASE_ARTICLES = frozenset(
    ["a", "an", "the", "and", "but", "or", "for", "nor", "on", "at", "to", "by", "in", "of"]
)


def normalise_title(raw: str) -> str:
    """
    Title-case a movie title, preserving known all-caps acronyms and respecting
    leading articles.

    The cell value is used as-is if it already looks correctly cased; otherwise
    we apply a conservative title-case transform.
    """
    stripped = raw.strip()
    if not stripped:
        return stripped
    # If it's already mixed-case (contains at least one lowercase letter after
    # the first char), trust the spreadsheet.
    if re.search(r"[a-z]", stripped[1:]):
        return stripped
    # Otherwise apply title-case with article lowercasing
    words = stripped.split()
    result: list[str] = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i > 0 and lower in _LOWERCASE_ARTICLES:
            result.append(lower)
        else:
            result.append(word.capitalize())
    return " ".join(result)


def _clean_str(value: Any) -> str:
    """Coerce a cell value to a stripped string."""
    if value is None:
        return ""
    return str(value).strip()


# ---------------------------------------------------------------------------
# Row parser
# ---------------------------------------------------------------------------

# Expected column headers (case-insensitive).  The spreadsheet may have extra
# columns; we only care about these six.
_COL_TITLE = "title"
_COL_FORMAT = "format"
_COL_LOCATION = "location"
_COL_CATEGORY = "category"
_COL_SUBCATEGORY = "sub category"
_COL_TYPE = "type"


def _build_header_map(header_row: tuple[Any, ...]) -> dict[str, int]:
    """Return a mapping of normalised column name → 0-based column index."""
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        key = _clean_str(cell).lower()
        mapping[key] = idx
    return mapping


def parse_row(
    row: tuple[Any, ...],
    header_map: dict[str, int],
    row_number: int,
) -> ImportCandidate | None:
    """
    Parse a single data row (tuple of cell values) into an ImportCandidate.

    Returns None if the row is effectively empty (no title).
    """

    def get(col_name: str) -> str:
        idx = header_map.get(col_name)
        if idx is None or idx >= len(row):
            return ""
        return _clean_str(row[idx])

    raw_title = get(_COL_TITLE)
    if not raw_title:
        return None

    raw_format = get(_COL_FORMAT)
    raw_location = get(_COL_LOCATION)

    title = normalise_title(raw_title)
    formats = normalise_formats(raw_format) if raw_format else []
    section, shelf = parse_location(raw_location)

    raw_cat = get(_COL_CATEGORY)
    raw_sub = get(_COL_SUBCATEGORY)
    raw_type = get(_COL_TYPE)

    return ImportCandidate(
        row_number=row_number,
        title=title,
        formats=formats,
        location_raw=raw_location,
        section=section,
        shelf=shelf,
        category=raw_cat if raw_cat else None,
        sub_category=raw_sub if raw_sub else None,
        item_type=raw_type if raw_type else None,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_xlsx(path: Path) -> list[ImportCandidate]:
    """
    Read an xlsx collection spreadsheet and return one ImportCandidate per
    non-empty data row.

    The first row must be a header row containing at minimum a "Title" column.
    Rows with no title value are silently skipped.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError(f"No active worksheet found in {path}")

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header_map = _build_header_map(tuple(rows[0]))
    if _COL_TITLE not in header_map:
        raise ValueError(
            f"Spreadsheet {path} has no 'Title' column. Found columns: {list(header_map.keys())}"
        )

    candidates: list[ImportCandidate] = []
    for row_idx, raw_row in enumerate(rows[1:], start=2):  # 1-based, skip header
        candidate = parse_row(tuple(raw_row), header_map, row_idx)
        if candidate is not None:
            candidates.append(candidate)

    wb.close()
    return candidates
