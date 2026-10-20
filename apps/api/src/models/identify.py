"""Identifying the films TMDB never matched — Batch T9.

- :class:`IdentifyRun`: one live run of a dry run's plan, with the Brave searches the plan
  spent, so they count against the ceiling T7's batches share. One runs at a time.
- :class:`IdentifyLookup`: what identification decided about one film, or why it waits for
  Craig, with the candidates he chooses from on the Identify films page.
- :class:`MovieTitleAlias`: a title a film used to have. The spreadsheet keeps its own
  spelling ("Peepiing Tom") after identification tidies the film ("Peeping Tom"), and the
  collection refresh looks films up by these too, so #198's guard still finds them.
- :class:`IdentifyDoubt` (Batch X9): a proposal that a film already identified is the wrong
  one, waiting on Identify films with its evidence until Craig settles it.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UUIDPrimaryKeyMixin

#: ``needs_you`` waits on the Identify films page; the rest are settled.
IDENTIFY_LOOKUP_STATUSES = ("needs_you", "identified", "set_aside", "skipped")
SET_ASIDE_AS = ("tv", "not_film")
#: How a film was identified: by the matcher, by Craig from the offered films, or by Craig
#: after searching again.
IDENTIFIED_HOW = ("auto", "picked", "searched")
IDENTIFY_RUN_STATUSES = ("running", "finished", "stopped", "abandoned")
#: Where a doubt came from: the re-check of the old paths' films, a disc page, a review.
IDENTIFY_DOUBT_SOURCES = ("recheck", "specs", "review")
#: ``open`` waits on Identify films; Craig keeps the film, identifies it again, or moves the
#: copy to another film.
IDENTIFY_DOUBT_STATUSES = ("open", "kept", "corrected", "moved")


class IdentifyRun(Base, UUIDPrimaryKeyMixin):
    """One live run of a plan."""

    __tablename__ = "identify_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('job', 'admin')", name="ck_identify_runs_trigger"),
        CheckConstraint(
            "status IN ('running', 'finished', 'stopped', 'abandoned')",
            name="ck_identify_runs_status",
        ),
        CheckConstraint("searches >= 0", name="ck_identify_runs_searches"),
        Index("ix_identify_runs_started_utc", "started_utc"),
        Index(
            "uq_identify_runs_one_running",
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
    #: When the dry run behind this plan was made.
    planned_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    #: Brave requests the plan spent, billed and counted against the month's ceiling.
    searches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    films: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    identified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    set_aside: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Films left alone because they changed after the dry run, or Craig had decided them.
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class IdentifyLookup(Base, UUIDPrimaryKeyMixin):
    """Identification's record of one film."""

    __tablename__ = "identify_lookups"
    __table_args__ = (
        UniqueConstraint("movie_id", name="uq_identify_lookups_movie"),
        CheckConstraint(
            "status IN ('needs_you', 'identified', 'set_aside', 'skipped')",
            name="ck_identify_lookups_status",
        ),
        CheckConstraint(
            "(status = 'set_aside') = (set_aside_as IS NOT NULL)",
            name="ck_identify_lookups_set_aside_as",
        ),
        CheckConstraint(
            "set_aside_as IS NULL OR set_aside_as IN ('tv', 'not_film')",
            name="ck_identify_lookups_set_aside_kind",
        ),
        CheckConstraint(
            "how IS NULL OR how IN ('auto', 'picked', 'searched')",
            name="ck_identify_lookups_how",
        ),
        CheckConstraint(
            "(status = 'identified') = (tmdb_id IS NOT NULL)",
            name="ck_identify_lookups_tmdb_when_identified",
        ),
        CheckConstraint("media_type IN ('film', 'tv')", name="ck_identify_lookups_media_type"),
        Index("ix_identify_lookups_status", "status"),
    )

    #: ``CASCADE``: a film merged away takes its lookup with it. The audit log keeps the
    #: record, including what an undo needs to put the lookup back.
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    set_aside_as: Mapped[str | None] = mapped_column(Text, nullable=True)
    how: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Why it waits, or what was decided, in the words the page shows.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: What spoke for the identification, one sentence each.
    evidence: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    #: The films offered, best first, as the dry run described them.
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    proposed_tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Which TMDB index ``tmdb_id`` is from: ``film``, or ``tv`` for a series (Batch Y3).
    media_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="film", server_default="film"
    )
    #: The spreadsheet title identification replaced.
    replaced_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identify_runs.id", ondelete="SET NULL"), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    decided_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )


class MovieTitleAlias(Base, UUIDPrimaryKeyMixin):
    """A title a film used to have, so the spreadsheet's spelling still finds it."""

    __tablename__ = "movie_title_aliases"
    __table_args__ = (
        UniqueConstraint("movie_id", "title", name="uq_movie_title_aliases_movie_title"),
        CheckConstraint("source IN ('identification')", name="ck_movie_title_aliases_source"),
        CheckConstraint("length(btrim(title)) > 0", name="ck_movie_title_aliases_title"),
        Index("ix_movie_title_aliases_movie", "movie_id"),
    )

    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="identification")
    created_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )


class IdentifyDoubt(Base, UUIDPrimaryKeyMixin):
    """A proposal that an identified film is the wrong one — Batch X9 (CT46-01, CT46-03)."""

    __tablename__ = "identify_doubts"
    __table_args__ = (
        CheckConstraint(
            "source IN ('recheck', 'specs', 'review')", name="ck_identify_doubts_source"
        ),
        CheckConstraint(
            "status IN ('open', 'kept', 'corrected', 'moved')", name="ck_identify_doubts_status"
        ),
        CheckConstraint(
            "(status = 'open') = (decided_utc IS NULL)", name="ck_identify_doubts_decided"
        ),
        CheckConstraint("length(btrim(note)) > 0", name="ck_identify_doubts_note"),
        Index("ix_identify_doubts_movie", "movie_id"),
        Index("ix_identify_doubts_status", "status"),
        Index(
            "uq_identify_doubts_open_film",
            "movie_id",
            "source",
            unique=True,
            postgresql_where=text("status = 'open' AND collection_item_id IS NULL"),
        ),
        Index(
            "uq_identify_doubts_open_copy",
            "collection_item_id",
            "source",
            unique=True,
            postgresql_where=text("status = 'open' AND collection_item_id IS NOT NULL"),
        ),
    )

    #: ``CASCADE``, as a lookup's is. A merge moves a film's doubts to the film it joins
    #: first, and an undo moves them back, so only a deleted film takes its doubts with it.
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    #: The copy the doubt is about, when it names one: a disc page is one disc's, and the
    #: re-check reads one spreadsheet row.
    collection_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collection_items.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    #: The film's TMDB id when the doubt was raised.
    identified_as: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Why the film is in doubt, in the words the pages show.
    note: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    #: The films offered instead, best first, in the Identify queue's shape.
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    proposed_tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: What the Identify page searches TMDB for first: the page's title and year.
    search_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The disc page or review that named another year.
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    decided_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    #: The audit row of the change that settled it; undoing that change opens it again.
    decided_action_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=UTC_NOW
    )
