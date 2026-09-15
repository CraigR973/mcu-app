"""Letterboxd watch history — Batch S8 (file import) and Batch S5 (RSS sync).

**The app never scrapes Letterboxd** (`DECISIONS.md` #161). S8 reads a CSV that already
exists on disk; S5 reads the sanctioned public RSS feed. No scraper, no Cloudflare
dependency and no stored Letterboxd credential ships.

The split of work here is deliberate, because S5 reuses all of it:

- :mod:`.diary` parses a file into :class:`~.diary.DiaryEntry` records.
- :mod:`.matcher` decides which film in *this* collection an entry refers to.
- :mod:`.importer` writes the rows, identifies what it can, and reports.

Only the *reader* is source-specific. An RSS entry becomes the same ``DiaryEntry`` and
travels the same path — which is the waste the S8-before-S5 ordering exists to avoid.
"""

from src.services.letterboxd.diary import DiaryEntry, DiaryParseError, read_diary_csv
from src.services.letterboxd.importer import ImportReport, run_import
from src.services.letterboxd.matcher import (
    Ambiguity,
    MatchOutcome,
    build_index,
    match_entry,
    normalise_title,
)

__all__ = [
    "Ambiguity",
    "DiaryEntry",
    "DiaryParseError",
    "ImportReport",
    "MatchOutcome",
    "build_index",
    "match_entry",
    "normalise_title",
    "read_diary_csv",
    "run_import",
]
