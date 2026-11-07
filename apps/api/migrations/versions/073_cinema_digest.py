"""Daily cinema digest (AC6, owner approved #348). Frozen DDL; no application imports.

Revision ID: 073
Revises: 072
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "073"
down_revision: str | None = "072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "'deals','sale_events','releases','loans','movie_night','attention','collection_additions'"
_DDL = [
    """

CREATE TABLE cinema_digest_films (
tmdb_id INTEGER NOT NULL,
first_observed_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
last_present_day DATE,
absent_since_day DATE,
absence_checked_through_day DATE,
episode_number INTEGER DEFAULT '0' NOT NULL,
baseline BOOLEAN DEFAULT 'false' NOT NULL,
id UUID NOT NULL,
created_at_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
PRIMARY KEY (id),
CONSTRAINT ck_digest_film_numbers CHECK (tmdb_id > 0 AND episode_number >= 0),
CONSTRAINT ck_digest_absence CHECK ((absent_since_day IS NULL AND
absence_checked_through_day IS NULL) OR (absent_since_day IS NOT NULL AND
absence_checked_through_day IS NOT NULL AND absence_checked_through_day >=
absent_since_day)),
UNIQUE (tmdb_id)
)

    """,
    """

CREATE TABLE cinema_digest_listings (
source VARCHAR(40) NOT NULL,
source_key VARCHAR(300) NOT NULL,
source_fingerprint VARCHAR(64) NOT NULL,
film_id UUID,
cinema_film_id UUID,
first_observed_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
last_observed_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
baseline BOOLEAN DEFAULT 'false' NOT NULL,
id UUID NOT NULL,
created_at_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
PRIMARY KEY (id),
CONSTRAINT uq_digest_listing UNIQUE (source, source_key, source_fingerprint),
FOREIGN KEY(film_id) REFERENCES cinema_digest_films (id) ON DELETE RESTRICT,
FOREIGN KEY(cinema_film_id) REFERENCES cinema_films (id) ON DELETE SET NULL
)

    """,
    """
CREATE INDEX ix_cinema_digest_listings_cinema_film_id ON cinema_digest_listings
(cinema_film_id)
    """,
    """
CREATE INDEX ix_cinema_digest_listings_film_id ON cinema_digest_listings (film_id)
    """,
    """

CREATE TABLE cinema_digest_appearances (
film_id UUID NOT NULL,
episode_number INTEGER NOT NULL,
first_listing_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
recognised_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
run_id UUID,
title VARCHAR(500) NOT NULL,
run_labels JSONB NOT NULL,
run_reasons JSONB NOT NULL,
is_return BOOLEAN NOT NULL,
id UUID NOT NULL,
created_at_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
PRIMARY KEY (id),
CONSTRAINT uq_digest_episode UNIQUE (film_id, episode_number),
CONSTRAINT ck_digest_episode_positive CHECK (episode_number > 0),
CONSTRAINT ck_digest_labels CHECK (jsonb_typeof(run_labels) = 'array' AND
jsonb_typeof(run_reasons) = 'array'),
FOREIGN KEY(film_id) REFERENCES cinema_digest_films (id) ON DELETE RESTRICT,
FOREIGN KEY(run_id) REFERENCES cinema_refresh_runs (id) ON DELETE SET NULL
)

    """,
    """
CREATE INDEX ix_cinema_digest_appearances_film_id ON cinema_digest_appearances (film_id)
    """,
    """
CREATE INDEX ix_cinema_digest_appearances_recognised_utc ON cinema_digest_appearances
(recognised_utc)
    """,
    """
CREATE INDEX ix_cinema_digest_appearances_run_id ON cinema_digest_appearances (run_id)
    """,
    """

CREATE TABLE cinema_digest_days (
local_date DATE NOT NULL,
run_id UUID,
evaluated_at_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
report JSONB NOT NULL,
id UUID NOT NULL,
created_at_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
PRIMARY KEY (id),
CONSTRAINT ck_digest_day_report CHECK (jsonb_typeof(report) = 'object'),
UNIQUE (local_date),
FOREIGN KEY(run_id) REFERENCES cinema_refresh_runs (id) ON DELETE SET NULL
)

    """,
    """
CREATE INDEX ix_cinema_digest_days_run_id ON cinema_digest_days (run_id)
    """,
    """

CREATE TABLE cinema_digest_deliveries (
user_id UUID NOT NULL,
local_date DATE NOT NULL,
claimed_at_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
finished_at_utc TIMESTAMP WITHOUT TIME ZONE,
notification_ids JSONB NOT NULL,
appearance_ids JSONB NOT NULL,
device_ids JSONB NOT NULL,
payload JSONB NOT NULL,
outcome VARCHAR(20) DEFAULT 'claimed' NOT NULL,
delivered_count INTEGER DEFAULT '0' NOT NULL,
id UUID NOT NULL,
created_at_utc TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now()) NOT NULL,
PRIMARY KEY (id),
CONSTRAINT uq_digest_delivery_day UNIQUE (user_id, local_date),
CONSTRAINT ck_digest_delivery_outcome CHECK (outcome IN
('claimed','sent','failed','unknown') AND delivered_count >= 0),
CONSTRAINT ck_digest_delivery_payload CHECK (jsonb_typeof(notification_ids) = 'array'
AND jsonb_typeof(appearance_ids) = 'array' AND jsonb_typeof(device_ids) = 'array' AND
jsonb_typeof(payload) = 'object'),
FOREIGN KEY(user_id) REFERENCES profiles (id) ON DELETE CASCADE
)

    """,
    """
CREATE INDEX ix_cinema_digest_deliveries_user_id ON cinema_digest_deliveries (user_id)
    """,
]


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("cinemas_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "notification_preferences",
        sa.Column("cinemas_older_only", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.drop_constraint("ck_notifications_category", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_category", "notifications", f"category IN ({_OLD},'cinemas')"
    )
    for ddl in _DDL:
        op.execute(ddl)
    op.execute("""
        WITH known AS (
          SELECT CASE WHEN jsonb_typeof(evidence->'tmdbId')='number'
            AND (evidence->>'tmdbId') ~ '^[0-9]{1,10}$'
            THEN (evidence->>'tmdbId')::bigint END AS tmdb_id,
            coalesce((SELECT min(s.first_seen_utc) FROM cinema_screenings s
              WHERE s.film_id=f.id), f.last_seen_utc) AS first_observed
          FROM cinema_films f WHERE identity_status='verified'
        )
        INSERT INTO cinema_digest_films (id,tmdb_id,first_observed_utc,baseline)
        SELECT gen_random_uuid(),tmdb_id,min(first_observed),true FROM known
          WHERE tmdb_id BETWEEN 1 AND 2147483647 GROUP BY tmdb_id
        """)
    op.execute("""
        INSERT INTO cinema_digest_listings
          (id,source,source_key,source_fingerprint,film_id,cinema_film_id,
           first_observed_utc,last_observed_utc,baseline)
        SELECT gen_random_uuid(), f.source, f.source_key,
          coalesce(f.evidence->>'sourceFingerprint',''), d.id, f.id,
          coalesce((SELECT min(s.first_seen_utc) FROM cinema_screenings s
            WHERE s.film_id=f.id), f.last_seen_utc), f.last_seen_utc, true
        FROM cinema_films f LEFT JOIN cinema_digest_films d
          ON f.evidence->>'tmdbId'=d.tmdb_id::text AND f.identity_status='verified'
        """)
    for role in ("mcu_readonly", "mcu_backup"):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN "
            f"GRANT SELECT (cinemas_enabled,cinemas_older_only) "
            f"ON notification_preferences TO {role}; "
            f"GRANT SELECT ON cinema_digest_films,cinema_digest_listings,"
            f"cinema_digest_appearances,cinema_digest_days,cinema_digest_deliveries "
            f"TO {role}; END IF; END $$"
        )


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM cinema_digest_days)
            OR EXISTS (SELECT FROM cinema_digest_appearances)
            OR EXISTS (SELECT FROM cinema_digest_deliveries)
            OR EXISTS (SELECT FROM notifications WHERE category='cinemas')
            OR EXISTS (SELECT FROM notification_preferences
              WHERE NOT cinemas_enabled OR cinemas_older_only)
          THEN RAISE EXCEPTION
            'Retain cinema digest history; downgrade 073 requires owner review';
          END IF;
        END $$
        """)
    for table in (
        "cinema_digest_deliveries",
        "cinema_digest_days",
        "cinema_digest_appearances",
        "cinema_digest_listings",
        "cinema_digest_films",
    ):
        op.drop_table(table)
    op.drop_column("notification_preferences", "cinemas_older_only")
    op.drop_column("notification_preferences", "cinemas_enabled")
    op.drop_constraint("ck_notifications_category", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_category", "notifications", f"category IN ({_OLD})"
    )
