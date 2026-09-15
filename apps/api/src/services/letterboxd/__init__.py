"""Letterboxd watch history — Batch S8 (file import) and Batch S5 (RSS sync).

**The app never scrapes Letterboxd** (`DECISIONS.md` #161). S8 reads a CSV that already
exists on disk; S5 reads the sanctioned public RSS feed. No scraper, no Cloudflare
dependency and no stored Letterboxd credential ships.

The split of work here is deliberate, because S5 reuses all of it:

- :mod:`.diary` parses a **file** into :class:`~.diary.DiaryEntry` records.
- :mod:`.feed` parses the **RSS feed** into exactly the same records.
- :mod:`.matcher` decides which film in *this* collection an entry refers to.
- :mod:`.importer` writes the rows, identifies what it can, and reports.
- :mod:`.sync` is S5's thin top: fetch, hand to the importer, record what happened.

**Only the reader is source-specific**, which is the point of building S8 first. S5 added
`feed.py` and `sync.py` and **no second matcher and no second writer** — an RSS entry
becomes the same ``DiaryEntry`` and travels the same path, so a viewing present in both
the file and the feed yields exactly one row (`DECISIONS.md` #176).
"""

from src.services.letterboxd.diary import DiaryEntry, DiaryParseError, read_diary_csv
from src.services.letterboxd.feed import FEED_ENTRY_CAP, feed_url, fetch_feed, parse_feed
from src.services.letterboxd.importer import ImportReport, run_import
from src.services.letterboxd.matcher import (
    Ambiguity,
    MatchOutcome,
    build_index,
    match_entry,
    normalise_title,
)
from src.services.letterboxd.sync import (
    SyncNotConfigured,
    SyncResult,
    last_sync,
    sync_watch_history,
)

__all__ = [
    "FEED_ENTRY_CAP",
    "Ambiguity",
    "SyncNotConfigured",
    "SyncResult",
    "DiaryEntry",
    "DiaryParseError",
    "ImportReport",
    "MatchOutcome",
    "build_index",
    "match_entry",
    "normalise_title",
    "fetch_feed",
    "feed_url",
    "last_sync",
    "parse_feed",
    "read_diary_csv",
    "run_import",
    "sync_watch_history",
]
