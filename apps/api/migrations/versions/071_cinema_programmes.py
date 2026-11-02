"""Owner-approved isolated cinema programme domain (AB6, decision 327).

Revision ID: 071
Revises: 070
Create Date: 2026-11-02

DDL is frozen here; this migration imports no mutable application model.
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "071"
down_revision: str | None = "070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DDL = (
    """
    CREATE TABLE cinema_venues (
        slug VARCHAR(80) NOT NULL,
        name VARCHAR(200) NOT NULL,
        source VARCHAR(40) NOT NULL,
        source_venue_id VARCHAR(100) NOT NULL,
        timezone VARCHAR(50) NOT NULL,
        programme_url VARCHAR(2048) NOT NULL,
        official_url VARCHAR(2048) NOT NULL,
        collection_enabled BOOLEAN DEFAULT false NOT NULL,
        deleted_at TIMESTAMP WITHOUT TIME ZONE,
        id UUID NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT uq_cinema_source_venue UNIQUE (source, source_venue_id),
        UNIQUE (slug)
    )
    """,
    """
    CREATE TABLE cinema_films (
        source VARCHAR(40) NOT NULL,
        source_key VARCHAR(300) NOT NULL,
        title VARCHAR(500) NOT NULL,
        movie_id UUID,
        original_year INTEGER,
        source_release_date DATE,
        first_uk_release_date DATE,
        identity_status VARCHAR(30) NOT NULL,
        evidence JSONB NOT NULL,
        last_seen_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
        deleted_at TIMESTAMP WITHOUT TIME ZONE,
        id UUID NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT uq_cinema_source_film UNIQUE (source, source_key),
        FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE SET NULL
    )
    """,
    """
    CREATE INDEX ix_cinema_films_movie_id ON cinema_films (movie_id)
    """,
    """
    CREATE TABLE cinema_refresh_runs (
        trigger VARCHAR(20) NOT NULL,
        adapter_version VARCHAR(40) NOT NULL,
        status VARCHAR(20) NOT NULL,
        started_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
        heartbeat_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
        lease_expires_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        finished_utc TIMESTAMP WITHOUT TIME ZONE,
        request_count INTEGER NOT NULL,
        bytes_received INTEGER NOT NULL,
        report JSONB NOT NULL,
        id UUID NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT ck_cinema_run_status CHECK (status IN
    ('running','healthy','partial','failed','abandoned'))
    )
    """,
    """
    CREATE INDEX ix_cinema_run_started ON cinema_refresh_runs (started_utc)
    """,
    """
    CREATE UNIQUE INDEX uq_cinema_one_running ON cinema_refresh_runs (status) WHERE status =
    'running'
    """,
    """
    CREATE TABLE cinema_screenings (
        venue_id UUID NOT NULL,
        film_id UUID NOT NULL,
        source_key VARCHAR(500) NOT NULL,
        identity_strength VARCHAR(20) NOT NULL,
        local_date DATE NOT NULL,
        source_local_start VARCHAR(50) NOT NULL,
        starts_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        ends_utc TIMESTAMP WITHOUT TIME ZONE,
        screen VARCHAR(200),
        formats JSONB NOT NULL,
        source_expired BOOLEAN DEFAULT false NOT NULL,
        booking_url VARCHAR(2048),
        release_category VARCHAR(20) NOT NULL,
        category_evidence JSONB NOT NULL,
        confirmation VARCHAR(20) NOT NULL,
        first_seen_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
        last_seen_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
        deleted_at TIMESTAMP WITHOUT TIME ZONE,
        id UUID NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT uq_cinema_venue_showing UNIQUE (venue_id, source_key),
        CONSTRAINT ck_cinema_release_category CHECK (release_category IN
    ('newRelease','olderFilm','unclassified')),
        CONSTRAINT ck_cinema_confirmation CHECK (confirmation IN
    ('confirmed','unconfirmed','cancelled','withdrawn')),
        FOREIGN KEY(venue_id) REFERENCES cinema_venues (id) ON DELETE CASCADE,
        FOREIGN KEY(film_id) REFERENCES cinema_films (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX ix_cinema_screening_window ON cinema_screenings (venue_id, starts_utc)
    """,
    """
    CREATE TABLE cinema_coverage (
        venue_id UUID NOT NULL,
        local_date DATE NOT NULL,
        status VARCHAR(30) NOT NULL,
        observed BOOLEAN NOT NULL,
        complete BOOLEAN NOT NULL,
        last_attempt_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        last_success_utc TIMESTAMP WITHOUT TIME ZONE,
        source_update_label VARCHAR(200),
        upstream_utc TIMESTAMP WITHOUT TIME ZONE,
        error TEXT,
        run_id UUID,
        id UUID NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT uq_cinema_coverage_date UNIQUE (venue_id, local_date),
        FOREIGN KEY(venue_id) REFERENCES cinema_venues (id) ON DELETE CASCADE,
        FOREIGN KEY(run_id) REFERENCES cinema_refresh_runs (id) ON DELETE SET NULL
    )
    """,
)

_SEEDS = (
    (
        "35c02c3d-cdd6-5acf-be8d-5cfa0cff27ee",
        "odeon-kilmarnock",
        "ODEON Kilmarnock",
        "cinematimes",
        "odeon-kilmarnock",
        "https://cinematimes.com/uk/glasgow/cinemas/odeon-kilmarnock/",
        "https://www.odeon.co.uk/cinemas/kilmarnock/",
    ),
    (
        "32270dfe-dc4e-5e92-905a-08e06a814c50",
        "odeon-glasgow-quay",
        "ODEON Glasgow Quay",
        "cinematimes",
        "odeon-glasgow-springfield-quay",
        "https://cinematimes.com/uk/glasgow/cinemas/odeon-glasgow-springfield-quay/",
        "https://www.odeon.co.uk/cinemas/glasgow-quay/",
    ),
    (
        "4f46de88-159a-549f-b3cc-c4a6eb28f7a1",
        "odeon-braehead",
        "ODEON Braehead",
        "cinematimes",
        "odeon-braehead-renfrew",
        "https://cinematimes.com/uk/glasgow/cinemas/odeon-braehead-renfrew/",
        "https://www.odeon.co.uk/cinemas/braehead/",
    ),
    (
        "2cfb15b3-d5a3-5896-98cc-1a183efa6686",
        "odeon-east-kilbride",
        "ODEON East Kilbride",
        "cinematimes",
        "odeon-east-kilbride-glasgow",
        "https://cinematimes.com/uk/glasgow/cinemas/odeon-east-kilbride-glasgow/",
        "https://www.odeon.co.uk/cinemas/east-kilbride/",
    ),
    (
        "76100a08-b925-5d6a-a5e5-8be68dd82ad5",
        "cineworld-silverburn",
        "Cineworld Glasgow Silverburn",
        "cineworld",
        "X0VQ1",
        "https://www.cineworld.co.uk/cinemas/x0vq1-cineworld-cinema-glasgow-silverburn/",
        "https://www.cineworld.co.uk/cinemas/glasgow-silverburn",
    ),
    (
        "442c47f9-38d4-5484-89cc-e58efacba3b8",
        "vue-st-enoch",
        "Vue Glasgow St Enoch",
        "vue",
        "10097",
        "https://www.myvue.com/cinema/glasgow-st-enoch/whats-on",
        "https://www.myvue.com/cinema/glasgow-st-enoch/whats-on",
    ),
    (
        "b7098632-ec79-5016-b006-d5f366f9118e",
        "everyman-glasgow",
        "Everyman Glasgow, Princes Square",
        "everyman",
        "X11DQ",
        "https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/",
        "https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/",
    ),
    (
        "2569e9b8-06c9-5983-8de6-a825c37c808d",
        "gft",
        "Glasgow Film Theatre",
        "gft",
        "gft",
        "https://www.glasgowfilm.org/all-listings/",
        "https://www.glasgowfilm.org/all-listings/",
    ),
    (
        "4edad6cb-9c2e-5ad4-a4fd-9e6a1ad889b2",
        "science-centre-imax",
        "Glasgow Science Centre IMAX",
        "science",
        "gscimax",
        "https://www.glasgowsciencecentre.org/imax",
        "https://www.glasgowsciencecentre.org/imax",
    ),
)


def upgrade() -> None:
    for statement in _DDL:
        op.execute(statement)
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
    op.bulk_insert(
        venues,
        [
            {
                "id": UUID(row[0]),
                "slug": row[1],
                "name": row[2],
                "source": row[3],
                "source_venue_id": row[4],
                "timezone": "Europe/London",
                "programme_url": row[5],
                "official_url": row[6],
            }
            for row in _SEEDS
        ],
    )
    for role in ("mcu_readonly", "mcu_backup"):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN "
            f"GRANT SELECT ON cinema_venues,cinema_films,cinema_refresh_runs,"
            f"cinema_screenings,cinema_coverage TO {role}; END IF; END $$"
        )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM cinema_screenings) OR "
        "EXISTS (SELECT FROM cinema_films) OR EXISTS (SELECT FROM cinema_refresh_runs) OR "
        "EXISTS (SELECT FROM cinema_coverage) THEN "
        "RAISE EXCEPTION 'Cinema data exists; downgrade 071 requires owner review'; "
        "END IF; END $$"
    )
    for table in (
        "cinema_coverage",
        "cinema_screenings",
        "cinema_films",
        "cinema_refresh_runs",
        "cinema_venues",
    ):
        op.drop_table(table)
