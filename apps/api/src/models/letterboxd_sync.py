"""What one Letterboxd sync did — Batch S5, snag 10a.

**This table exists because of the 50-entry cap.** The public diary feed returns only the
most recent 50 viewings. Craig's reaches back to 2026-01-26; **Mark's only to 2026-07-20**,
because he watches far more (`DECISIONS.md` #159). A sync running less often than roughly
monthly drops his entries *silently* — the feed simply stops mentioning them.

So "when did this last run" is a correctness property, not a nicety, and a number nobody
wrote down cannot be checked. `scrape_runs` was built on the same argument in Batch 20,
after a scraper "test" showed results on screen while saving nothing.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

LETTERBOXD_SYNCS_TABLE = "letterboxd_syncs"


class LetterboxdSync(Base, UUIDPrimaryKeyMixin):
    __tablename__ = LETTERBOXD_SYNCS_TABLE

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )

    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    #: NULL while in flight, so a sync that died halfway is visible as one that died
    #: halfway rather than as no row at all.
    finished_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    #: ``manual`` today. Both Railway crons are crashing (`OWNER-ACTIONS.md` item 1), so
    #: #156 requires the first version to work from a manual sync the way the scraper does
    #: — the column is here so a cron can be added later without a migration.
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")

    entries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    written: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    #: On a healthy weekly sync this is most of the feed, and that is the sign it works.
    already_imported: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ambiguous: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    not_in_collection: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    #: Set when the sync itself failed — an unreachable feed, a username that names no
    #: diary. Distinct from an entry that could not be matched, which is not a failure.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LetterboxdSync {self.started_at_utc} written={self.written}>"
