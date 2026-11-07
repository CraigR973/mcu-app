"""Durable cinema appearance history and at-most-once delivery claims (AC6, #348)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import UTC_NOW, Base, UUIDPrimaryKeyMixin


class DigestCreated:
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=UTC_NOW
    )


class CinemaDigestFilm(Base, UUIDPrimaryKeyMixin, DigestCreated):
    __tablename__ = "cinema_digest_films"
    __table_args__ = (
        CheckConstraint("tmdb_id > 0 AND episode_number >= 0", name="ck_digest_film_numbers"),
        CheckConstraint(
            "(absent_since_day IS NULL AND absence_checked_through_day IS NULL) OR "
            "(absent_since_day IS NOT NULL AND absence_checked_through_day IS NOT NULL "
            "AND absence_checked_through_day >= absent_since_day)",
            name="ck_digest_absence",
        ),
    )
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True)
    first_observed_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    last_present_day: Mapped[date | None] = mapped_column(Date)
    absent_since_day: Mapped[date | None] = mapped_column(Date)
    absence_checked_through_day: Mapped[date | None] = mapped_column(Date)
    episode_number: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    baseline: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class CinemaDigestListing(Base, UUIDPrimaryKeyMixin, DigestCreated):
    __tablename__ = "cinema_digest_listings"
    __table_args__ = (
        UniqueConstraint("source", "source_key", "source_fingerprint", name="uq_digest_listing"),
    )
    source: Mapped[str] = mapped_column(String(40))
    source_key: Mapped[str] = mapped_column(String(300))
    source_fingerprint: Mapped[str] = mapped_column(String(64))
    film_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_digest_films.id", ondelete="RESTRICT"), index=True
    )
    cinema_film_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_films.id", ondelete="SET NULL"), index=True
    )
    first_observed_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    last_observed_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    baseline: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class CinemaDigestAppearance(Base, UUIDPrimaryKeyMixin, DigestCreated):
    __tablename__ = "cinema_digest_appearances"
    __table_args__ = (
        UniqueConstraint("film_id", "episode_number", name="uq_digest_episode"),
        CheckConstraint("episode_number > 0", name="ck_digest_episode_positive"),
        CheckConstraint(
            "jsonb_typeof(run_labels) = 'array' AND jsonb_typeof(run_reasons) = 'array'",
            name="ck_digest_labels",
        ),
    )
    film_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_digest_films.id", ondelete="RESTRICT"), index=True
    )
    episode_number: Mapped[int] = mapped_column(Integer)
    first_listing_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    recognised_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_refresh_runs.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    run_labels: Mapped[list[str]] = mapped_column(JSONB)
    run_reasons: Mapped[list[str]] = mapped_column(JSONB)
    is_return: Mapped[bool] = mapped_column(Boolean)


class CinemaDigestDay(Base, UUIDPrimaryKeyMixin, DigestCreated):
    __tablename__ = "cinema_digest_days"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(report) = 'object'", name="ck_digest_day_report"),
    )
    local_date: Mapped[date] = mapped_column(Date, unique=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cinema_refresh_runs.id", ondelete="SET NULL"), index=True
    )
    evaluated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)


class CinemaDigestDelivery(Base, UUIDPrimaryKeyMixin, DigestCreated):
    __tablename__ = "cinema_digest_deliveries"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="uq_digest_delivery_day"),
        CheckConstraint(
            "outcome IN ('claimed','sent','failed','unknown') AND delivered_count >= 0",
            name="ck_digest_delivery_outcome",
        ),
        CheckConstraint(
            (
                "jsonb_typeof(notification_ids) = 'array' AND jsonb_typeof(ap"
                "pearance_ids) = 'array' AND jsonb_typeof(device_ids) = 'arra"
                "y' AND jsonb_typeof(payload) = 'object'"
            ),
            name="ck_digest_delivery_payload",
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    local_date: Mapped[date] = mapped_column(Date)
    claimed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    finished_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    notification_ids: Mapped[list[str]] = mapped_column(JSONB)
    appearance_ids: Mapped[list[str]] = mapped_column(JSONB)
    device_ids: Mapped[list[str]] = mapped_column(JSONB)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    outcome: Mapped[str] = mapped_column(String(20), default="claimed", server_default="claimed")
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
