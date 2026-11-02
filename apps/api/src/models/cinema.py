"""Public cinema programmes, isolated from ownership, diary and release dates (AB6)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UUIDPrimaryKeyMixin


class CinemaVenue(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cinema_venues"
    __table_args__ = (UniqueConstraint("source", "source_venue_id", name="uq_cinema_source_venue"),)

    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(40))
    source_venue_id: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/London")
    programme_url: Mapped[str] = mapped_column(String(2048))
    official_url: Mapped[str] = mapped_column(String(2048))
    collection_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class CinemaFilm(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cinema_films"
    __table_args__ = (UniqueConstraint("source", "source_key", name="uq_cinema_source_film"),)

    source: Mapped[str] = mapped_column(String(40))
    source_key: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(500))
    movie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="SET NULL"), index=True
    )
    original_year: Mapped[int | None] = mapped_column(Integer)
    source_release_date: Mapped[date | None] = mapped_column(Date)
    first_uk_release_date: Mapped[date | None] = mapped_column(Date)
    identity_status: Mapped[str] = mapped_column(String(30), default="unverified")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_seen_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=UTC_NOW
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class CinemaRefreshRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cinema_refresh_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','healthy','partial','failed','abandoned')",
            name="ck_cinema_run_status",
        ),
        Index(
            "uq_cinema_one_running",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index("ix_cinema_run_started", "started_utc"),
    )

    trigger: Mapped[str] = mapped_column(String(20))
    adapter_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    started_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=UTC_NOW)
    heartbeat_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=UTC_NOW
    )
    lease_expires_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    finished_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    bytes_received: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class CinemaScreening(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cinema_screenings"
    __table_args__ = (
        UniqueConstraint("venue_id", "source_key", name="uq_cinema_venue_showing"),
        CheckConstraint(
            "release_category IN ('newRelease','olderFilm','unclassified')",
            name="ck_cinema_release_category",
        ),
        CheckConstraint(
            "confirmation IN ('confirmed','unconfirmed','cancelled','withdrawn')",
            name="ck_cinema_confirmation",
        ),
        Index("ix_cinema_screening_window", "venue_id", "starts_utc"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_venues.id", ondelete="CASCADE")
    )
    film_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_films.id", ondelete="CASCADE")
    )
    source_key: Mapped[str] = mapped_column(String(500))
    identity_strength: Mapped[str] = mapped_column(String(20))
    local_date: Mapped[date] = mapped_column(Date)
    source_local_start: Mapped[str] = mapped_column(String(50))
    starts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    ends_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    screen: Mapped[str | None] = mapped_column(String(200))
    formats: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_expired: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    booking_url: Mapped[str | None] = mapped_column(String(2048))
    release_category: Mapped[str] = mapped_column(String(20), default="unclassified")
    category_evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confirmation: Mapped[str] = mapped_column(String(20), default="confirmed")
    first_seen_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=UTC_NOW
    )
    last_seen_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=UTC_NOW
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class CinemaCoverage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cinema_coverage"
    __table_args__ = (UniqueConstraint("venue_id", "local_date", name="uq_cinema_coverage_date"),)

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_venues.id", ondelete="CASCADE")
    )
    local_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30))
    observed: Mapped[bool] = mapped_column(Boolean, default=False)
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    last_attempt_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    last_success_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    source_update_label: Mapped[str | None] = mapped_column(String(200))
    upstream_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    error: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_refresh_runs.id", ondelete="SET NULL")
    )
