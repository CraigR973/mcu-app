"""Upcoming releases, and the tokens that let a calendar app read them — §3.26, §7.3, §7.4."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

#: §3.26's vocabulary.
RELEASE_TYPES = (
    "4k_uhd_release",
    "blu_ray_release",
    "streaming_release",
    "theatrical",
    "award_ceremony",
    "sale_event",
)

#: The types that are a disc going on sale: what a release reminder is for.
DISC_RELEASE_TYPES = ("4k_uhd_release", "blu_ray_release")

#: How each type reads in a calendar app, where the event title is all there is.
RELEASE_TYPE_LABELS = {
    "4k_uhd_release": "4K UHD",
    "blu_ray_release": "Blu-ray",
    "streaming_release": "Streaming",
    "theatrical": "In cinemas",
    "award_ceremony": "Awards",
    "sale_event": "Sale",
}


class ReleaseCalendarEntry(Base, UUIDPrimaryKeyMixin):
    """One upcoming release.

    **Not** ``UpdatedAtMixin``: that brings a ``created_at`` column, and §3.26 names this
    table's creation timestamp ``added_at``. Inheriting it gave the model a column the
    table does not have, and every insert failed with "column created_at does not exist".
    The two timestamps are declared explicitly here so the model and the migration cannot
    drift again.
    """

    __tablename__ = "release_calendar"

    #: ``SET NULL``, and nullable from the start: §3.26 says an upcoming film may not be
    #: in this collection at all, so a row standing on its own is the normal case.
    movie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    release_type: Mapped[str] = mapped_column(String(50), nullable=False)
    release_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str] = mapped_column(String(2), nullable=False, server_default="GB")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Not in §3.26, and needed by every one of them: it is what makes re-ingestion
    #: idempotent and what lets a row be matched to a film later.
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: §3.26's column. **Nothing writes it**: `wanted_list` is §3.5 and Batch 18 builds
    #: it. Present because §3.26 designs it and adding a column later costs a migration;
    #: absent from every response, because a flag that is always false would read as "none
    #: of these are on your wishlist" rather than "there is no wishlist".
    is_wishlist_match: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    #: For Batch 11's notifications. Nothing writes it yet, for the same reason.
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    #: Moved by `015`'s trigger, so a client can tell an edited event from a new one —
    #: which is what makes a release date shifting update a subscriber's event rather than
    #: duplicating it.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ReleaseCalendarEntry {self.title!r} {self.release_date}>"


class CalendarFeedToken(Base, UUIDPrimaryKeyMixin):
    """The credential for §7.4's unauthenticated `.ics` URL.

    **Stored hashed.** A calendar app fetches a bare URL on a schedule with no way to
    attach a header, so the URL *is* the credential — which makes it exactly as sensitive
    as a refresh token and is why it is treated like one (`refresh_tokens.token_hash` uses
    the same SHA-256 scheme). The plaintext is returned once, at creation, and never
    stored: a database leak then yields no working feed URLs.
    """

    __tablename__ = "calendar_feed_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    #: So an unused link is visible. A subscription never fetched is either not set up or
    #: leaked and idle, and both are worth being able to see.
    last_used_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    #: Revoked rather than deleted, so "this link stopped working on Tuesday" is
    #: answerable. A partial unique index keeps exactly one live token per person.
    revoked_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CalendarFeedToken {self.user_id} revoked={self.revoked_at_utc is not None}>"


class CalendarRefreshState(Base):
    """When the release calendar last refreshed, and what it found — Batch T5.

    **One row.** The calendar refreshes itself when it is read and is more than a day old,
    and this is how two readers at once start one refresh rather than two: the claim is a
    conditional update of this row. It is also how the page says how fresh it is.
    """

    __tablename__ = "calendar_refresh_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_calendar_refresh_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_started_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    last_finished_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: The last run's failures, joined. A refresh that half-worked is still recorded as
    #: finished, because its rows are real; this is where the other half is said.
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: How many films had a disc date in the window. The number T5's acceptance is stated in.
    last_disc_releases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
