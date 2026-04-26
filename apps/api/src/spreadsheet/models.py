from __future__ import annotations

from pydantic import BaseModel


class ImportCandidate(BaseModel):
    """One row from the collection spreadsheet, normalised and ready for DB import."""

    row_number: int
    title: str
    formats: list[str]  # e.g. ["blu_ray", "download"]
    location_raw: str
    section: str | None  # Front | Back | Lounge | Garage | Digital
    shelf: str | None  # e.g. "1st", "2nd", "3rd"
    category: str | None
    sub_category: str | None
    item_type: str | None
