"""Cinema trips — AC5 (#335, point 4; the contract Craig approved is #345).

**A trip keeps its showing as a snapshot** — cinema, start, screen, formats, booking link —
so a programme change never rewrites it, and a trip still reads correctly after the
programme's 30-day clean-up deletes the showing. ``showing_id`` links the live row while it
exists; the flag ("no longer listed") and the Check tickets link come from that row on every
read, never from the snapshot.

**Every move raises ``revision``, every change to a reply raises its ``reply_revision``.** A
write names the revision it was made against, so a reply typed on a screen showing the old
time is refused rather than applied to the new one, and each push's dedupe key carries the
revision it is about: a retried request inserts nothing, a genuine later change still pushes.

**The proposer is not an invitee row.** They are ``proposer_id`` and always count as going;
to drop out they cancel. No check can see across the two tables, so the API refuses the
proposer as an invitee.

No token and no link that works without sign-in (#335), so neither table holds a credential.
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
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

CINEMA_TRIPS_TABLE = "cinema_trips"
CINEMA_TRIP_INVITEES_TABLE = "cinema_trip_invitees"

#: An invitee's one reply. Invited is "no reply yet".
TRIP_REPLIES = ("invited", "going", "not_going", "another_time")

#: AC4's film address (#341), exactly as `services.cinemas.films` parses it.
FILM_KEY_PATTERN = (
    r"^(tmdb-[0-9]{1,10}|imdb-tt[0-9]{7,10}"
    r"|(movie|listing)-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)


class CinemaTrip(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = CINEMA_TRIPS_TABLE
    __table_args__ = (
        UniqueConstraint("proposer_id", "client_request_id", name="uq_cinema_trip_request"),
        CheckConstraint(f"film_key ~ '{FILM_KEY_PATTERN}'", name="ck_cinema_trip_film_key"),
        CheckConstraint("revision >= 1", name="ck_cinema_trip_revision"),
        CheckConstraint("(revision = 1) = (moved_at_utc IS NULL)", name="ck_cinema_trip_moved"),
        CheckConstraint("ends_utc IS NULL OR ends_utc > starts_utc", name="ck_cinema_trip_ends"),
        CheckConstraint("jsonb_typeof(formats) = 'array'", name="ck_cinema_trip_formats"),
        Index("ix_cinema_trips_proposer", "proposer_id"),
        Index(
            "ix_cinema_trips_upcoming",
            "starts_utc",
            postgresql_where=text("cancelled_at_utc IS NULL"),
        ),
        Index("ix_cinema_trips_film", "film_key"),
        Index("ix_cinema_trips_showing", "showing_id"),
    )

    #: The app's id for this send: a send whose answer was lost returns the same trip.
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proposer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: The film page's address when proposed, after AC4 resolved it (a linked listing reads
    #: as its film).
    film_key: Mapped[str] = mapped_column(String(80), nullable=False)
    film_title: Mapped[str] = mapped_column(String(500), nullable=False)
    poster_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: The live showing, while the programme still holds it.
    showing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cinema_screenings.id", ondelete="SET NULL"),
        nullable=True,
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_venues.id", ondelete="SET NULL"), nullable=True
    )
    venue_name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Times read in the cinema's own zone; all nine are Europe/London.
    venue_timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Europe/London", server_default="Europe/London"
    )
    starts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    ends_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    screen: Mapped[str | None] = mapped_column(String(200), nullable=True)
    formats: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    #: History only: Check tickets comes from the live row under AB7's rule.
    booking_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    moved_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    cancelled_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CinemaTrip {self.film_title!r} {self.starts_utc} r{self.revision}>"


class CinemaTripInvitee(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """One invitee and their one reply. ``created_at`` is when they were invited."""

    __tablename__ = CINEMA_TRIP_INVITEES_TABLE
    __table_args__ = (
        UniqueConstraint("trip_id", "profile_id", name="uq_cinema_trip_invitee"),
        CheckConstraint(
            "reply IN ('invited', 'going', 'not_going', 'another_time')",
            name="ck_cinema_trip_reply",
        ),
        CheckConstraint("reply_revision >= 0", name="ck_cinema_trip_reply_revision"),
        CheckConstraint(
            "(reply = 'invited') = (replied_at_utc IS NULL)", name="ck_cinema_trip_replied"
        ),
        # The suggested showing's id is left out: the programme's clean-up may null it.
        CheckConstraint(
            "(reply = 'another_time') = (suggested_starts_utc IS NOT NULL)"
            " AND (suggested_starts_utc IS NULL) = (suggested_venue_name IS NULL)"
            " AND (suggested_formats IS NULL OR jsonb_typeof(suggested_formats) = 'array')",
            name="ck_cinema_trip_suggestion",
        ),
        Index("ix_cinema_trip_invitees_profile", "profile_id", "reply"),
        Index(
            "ix_cinema_trip_invitees_suggested",
            "suggested_showing_id",
            postgresql_where=text("suggested_showing_id IS NOT NULL"),
        ),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_trips.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    reply: Mapped[str] = mapped_column(
        String(20), nullable=False, default="invited", server_default="invited"
    )
    reply_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    replied_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    suggested_showing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cinema_screenings.id", ondelete="SET NULL"),
        nullable=True,
    )
    suggested_venue_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    suggested_starts_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: ``none_as_null``: clearing a suggestion must write SQL NULL, not JSON ``null``, which
    #: ``ck_cinema_trip_suggestion`` rightly refuses (it is not an array).
    suggested_formats: Mapped[list[Any] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CinemaTripInvitee {self.profile_id} {self.reply} r{self.reply_revision}>"
