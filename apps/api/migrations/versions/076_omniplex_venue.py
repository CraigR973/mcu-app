"""The Omniplex on Renfrew Street, a tenth cinema, off until it is enabled (AE4, #355). Frozen data.

Revision ID: 076
Revises: 075

A row like the nine 071 seeded, with ``collection_enabled`` left at false: the existing guarded
enable step switches it on only after a natural morning run has read its page and its coverage
was accepted. No application imports, so later code cannot change what this wrote.
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "076"
down_revision: str | None = "075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: uuid5(NAMESPACE_URL, "mcu:cinema:omniplex-glasgow-renfrew-street"), as `Venue.id` derives it.
OMNIPLEX_ID = "17b98515-0823-5764-9a63-908310891bc0"
OMNIPLEX = {
    "id": UUID(OMNIPLEX_ID),
    "slug": "omniplex-glasgow-renfrew-street",
    "name": "Omniplex Glasgow - Renfrew Street",
    "source": "cinematimes",
    "source_venue_id": "omniplex-glasgow-renfrew-street-city",
    "timezone": "Europe/London",
    "programme_url": "https://cinematimes.com/uk/glasgow/cinemas/omniplex-glasgow-renfrew-street-city/",
    "official_url": "https://www.omniplexcinemas.co.uk/cinema/showtimes/glasgow-renfrew-street",
}


def upgrade() -> None:
    venues = sa.table(
        "cinema_venues",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("source", sa.String()),
        sa.column("source_venue_id", sa.String()),
        sa.column("timezone", sa.String()),
        sa.column("programme_url", sa.String()),
        sa.column("official_url", sa.String()),
    )
    op.bulk_insert(venues, [OMNIPLEX])


def downgrade() -> None:
    # Its screenings and coverage would cascade away, and a trip to it would lose its cinema:
    # once anything was recorded against it, taking the row out is the owner's call.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM cinema_screenings WHERE venue_id = "
        f"'{OMNIPLEX_ID}') OR EXISTS (SELECT FROM cinema_coverage WHERE venue_id = "
        f"'{OMNIPLEX_ID}') OR EXISTS (SELECT FROM cinema_trips WHERE venue_id = "
        f"'{OMNIPLEX_ID}') THEN RAISE EXCEPTION 'The Omniplex has screenings, coverage or "
        "trips; downgrade 076 requires owner review'; END IF; END $$"
    )
    op.execute(f"DELETE FROM cinema_venues WHERE id = '{OMNIPLEX_ID}'")
