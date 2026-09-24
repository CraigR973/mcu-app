"""The Blu-ray.com backfill's working state — Batch T7, `DECISIONS.md` #202.

- :class:`SpecRun`: one nightly batch, with its search and fetch budgets and what it did,
  so Brave spend is counted and a batch can be read back. One runs at a time.
- :class:`SpecLookup`: one per disc the backfill has searched for. Its status says where the
  disc is: waiting for Craig, accepted and waiting to be fetched, done, skipped, or nothing
  found.
- :class:`SpecCandidate`: the pages a search proposed for a lookup, judged. Craig picks from
  these on the Disc specs page.

**A page address is checked twice.** The code accepts only what #110's predicate accepts,
and the tables refuse any address that is not a Blu-ray.com release path, so a bug cannot
store a search route or another site.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

#: Where a disc is. ``needs_you`` and ``no_match`` wait for Craig; ``accepted`` waits for
#: the nightly fetch; ``done`` has specs; ``skipped`` is Craig saying not this one.
LOOKUP_STATUSES = ("needs_you", "no_match", "accepted", "done", "skipped")

#: How the page was chosen: by the matcher, by Craig from the list, by Craig pasting a
#: link, or from the 10 Sep test once its page was confirmed as a UK edition.
ACCEPTED_HOW = ("auto", "confirmed", "pasted", "restored")

SPEC_RUN_STATUSES = ("running", "finished", "budget_spent", "stopped", "halted", "abandoned")

#: The address shape both page columns are held to: Blu-ray.com's release path.
RELEASE_PATH_SQL = r"~ '^https?://(www\.)?blu-ray\.com/movies/'"


class SpecRun(Base, UUIDPrimaryKeyMixin):
    """One batch: up to a budget of searches, then up to a budget of page fetches."""

    __tablename__ = "spec_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('job', 'admin')", name="ck_spec_runs_trigger"),
        CheckConstraint(
            "status IN ('running', 'finished', 'budget_spent', 'stopped', 'halted', 'abandoned')",
            name="ck_spec_runs_status",
        ),
        CheckConstraint(
            "search_budget >= 0 AND fetch_budget >= 0 AND searches >= 0",
            name="ck_spec_runs_counts",
        ),
        Index("ix_spec_runs_started_utc", "started_utc"),
        Index(
            "uq_spec_runs_one_running",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    started_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    heartbeat_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    finished_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    #: Brave requests this batch may send, and sent. Each is billed.
    search_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    searches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Discs searched for, and what became of them.
    searched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_match: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    restored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Blu-ray.com pages this batch may fetch, and what the fetches did.
    fetch_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Fetched pages that failed the year check and went back to Craig.
    sent_back: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetch_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SpecLookup(Base, UUIDPrimaryKeyMixin):
    """The backfill's record of one disc."""

    __tablename__ = "spec_lookups"
    __table_args__ = (
        UniqueConstraint("collection_item_id", name="uq_spec_lookups_item"),
        CheckConstraint(
            "status IN ('needs_you', 'no_match', 'accepted', 'done', 'skipped')",
            name="ck_spec_lookups_status",
        ),
        CheckConstraint(
            "how IS NULL OR how IN ('auto', 'confirmed', 'pasted', 'restored')",
            name="ck_spec_lookups_how",
        ),
        # A page is chosen exactly when the disc is accepted or done.
        CheckConstraint(
            "(status IN ('accepted', 'done')) = (accepted_url IS NOT NULL)",
            name="ck_spec_lookups_url_when_chosen",
        ),
        CheckConstraint(
            f"accepted_url IS NULL OR accepted_url {RELEASE_PATH_SQL}",
            name="ck_spec_lookups_release_path",
        ),
        Index("ix_spec_lookups_status", "status"),
    )

    collection_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collection_items.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    how: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    decided_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    #: The words sent to Brave, so a surprising result can be searched again by hand.
    search_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    searched_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spec_runs.id", ondelete="SET NULL"), nullable=True
    )
    #: Why it is where it is, in the words the Disc specs page shows.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )


class SpecCandidate(Base, UUIDPrimaryKeyMixin):
    """One page a search proposed for a disc, as the matcher judged it."""

    __tablename__ = "spec_candidates"
    __table_args__ = (
        UniqueConstraint("lookup_id", "url", name="uq_spec_candidates_lookup_url"),
        CheckConstraint(f"url {RELEASE_PATH_SQL}", name="ck_spec_candidates_release_path"),
        CheckConstraint("origin IN ('search', 'restored')", name="ck_spec_candidates_origin"),
    )

    lookup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spec_lookups.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    #: The page title as the search engine gave it, which is what Craig chooses between.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    format_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The edition brackets, joined: "SteelBook", "HMV Exclusive DigiPack". Null when plain.
    edition: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Same film, same format, UK edition.
    matches: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: ``restored`` marks the page the 10 Sep test fetched for this disc.
    origin: Mapped[str] = mapped_column(Text, nullable=False, default="search")
    created_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
