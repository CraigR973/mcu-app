"""Cinema trips: a proposer, a showing kept as a snapshot, and one reply per invitee (AC5, #345).

Revision ID: 072
Revises: 071
Create Date: 2026-11-07

DDL is frozen here, as 071's is: this migration imports no mutable application model, so the
film-address pattern and the clock default are written out rather than imported.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "072"
down_revision: str | None = "071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: ``src.models.base.UTC_NOW`` as it stood on 7 Nov: a bare ``now()`` writes the session's
#: local time (migration 063).
_UTC_NOW = sa.text("timezone('utc', now())")

#: AC4's film address (#341), exactly as ``services.cinemas.films`` parsed it on 7 Nov.
_FILM_KEY = (
    r"^(tmdb-[0-9]{1,10}|imdb-tt[0-9]{7,10}"
    r"|(movie|listing)-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=False), nullable=False, server_default=_UTC_NOW
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), nullable=False, server_default=_UTC_NOW
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "cinema_trips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("film_key", sa.String(80), nullable=False),
        sa.Column("film_title", sa.String(500), nullable=False),
        sa.Column("poster_path", sa.String(255), nullable=True),
        sa.Column("showing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("venue_name", sa.String(200), nullable=False),
        sa.Column("venue_timezone", sa.String(50), nullable=False, server_default="Europe/London"),
        sa.Column("starts_utc", sa.DateTime(timezone=False), nullable=False),
        sa.Column("ends_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("screen", sa.String(200), nullable=True),
        sa.Column(
            "formats", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("booking_url", sa.String(2048), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("moved_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("cancelled_at_utc", sa.DateTime(timezone=False), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["proposer_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["showing_id"], ["cinema_screenings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["venue_id"], ["cinema_venues.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("proposer_id", "client_request_id", name="uq_cinema_trip_request"),
        sa.CheckConstraint(f"film_key ~ '{_FILM_KEY}'", name="ck_cinema_trip_film_key"),
        sa.CheckConstraint("revision >= 1", name="ck_cinema_trip_revision"),
        sa.CheckConstraint("(revision = 1) = (moved_at_utc IS NULL)", name="ck_cinema_trip_moved"),
        sa.CheckConstraint("ends_utc IS NULL OR ends_utc > starts_utc", name="ck_cinema_trip_ends"),
        sa.CheckConstraint("jsonb_typeof(formats) = 'array'", name="ck_cinema_trip_formats"),
    )
    op.create_index("ix_cinema_trips_proposer", "cinema_trips", ["proposer_id"])
    op.create_index(
        "ix_cinema_trips_upcoming",
        "cinema_trips",
        ["starts_utc"],
        postgresql_where=sa.text("cancelled_at_utc IS NULL"),
    )
    op.create_index("ix_cinema_trips_film", "cinema_trips", ["film_key"])
    # The programme's clean-up deletes up to 500 showings at a time; without this each one
    # would scan trips to null its link.
    op.create_index("ix_cinema_trips_showing", "cinema_trips", ["showing_id"])

    op.create_table(
        "cinema_trip_invitees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reply", sa.String(20), nullable=False, server_default="invited"),
        sa.Column("reply_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replied_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("suggested_showing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("suggested_venue_name", sa.String(200), nullable=True),
        sa.Column("suggested_starts_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("suggested_formats", postgresql.JSONB(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["trip_id"], ["cinema_trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["suggested_showing_id"], ["cinema_screenings.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("trip_id", "profile_id", name="uq_cinema_trip_invitee"),
        sa.CheckConstraint(
            "reply IN ('invited', 'going', 'not_going', 'another_time')",
            name="ck_cinema_trip_reply",
        ),
        sa.CheckConstraint("reply_revision >= 0", name="ck_cinema_trip_reply_revision"),
        sa.CheckConstraint(
            "(reply = 'invited') = (replied_at_utc IS NULL)", name="ck_cinema_trip_replied"
        ),
        # The suggested showing's id is left out: the programme's clean-up may null it.
        sa.CheckConstraint(
            "(reply = 'another_time') = (suggested_starts_utc IS NOT NULL)"
            " AND (suggested_starts_utc IS NULL) = (suggested_venue_name IS NULL)"
            " AND (suggested_formats IS NULL OR jsonb_typeof(suggested_formats) = 'array')",
            name="ck_cinema_trip_suggestion",
        ),
    )
    op.create_index(
        "ix_cinema_trip_invitees_profile", "cinema_trip_invitees", ["profile_id", "reply"]
    )
    op.create_index(
        "ix_cinema_trip_invitees_suggested",
        "cinema_trip_invitees",
        ["suggested_showing_id"],
        postgresql_where=sa.text("suggested_showing_id IS NOT NULL"),
    )
    for table in ("cinema_trips", "cinema_trip_invitees"):
        op.execute(
            f"CREATE TRIGGER {table}_set_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )
    # Neither table holds a credential: no token, no link that works without sign-in (#335).
    for role in ("mcu_readonly", "mcu_backup"):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN "
            f"GRANT SELECT ON cinema_trips, cinema_trip_invitees TO {role}; END IF; END $$"
        )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM cinema_trips) "
        "OR EXISTS (SELECT FROM cinema_trip_invitees) THEN "
        "RAISE EXCEPTION 'Cinema trips exist; downgrade 072 requires owner review'; "
        "END IF; END $$"
    )
    for table in ("cinema_trip_invitees", "cinema_trips"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_set_updated_at ON {table};")
    op.drop_table("cinema_trip_invitees")
    op.drop_table("cinema_trips")
