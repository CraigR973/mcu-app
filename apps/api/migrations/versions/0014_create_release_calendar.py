"""create release_calendar table

Upcoming physical and streaming releases Mark cares about, populated from TMDB
and curated sources. Subscribable as an iCal feed at /api/v1/calendar.ics.

movie_id is nullable — upcoming releases may reference films not yet in the TMDB
catalogue (pre-announcement boutique titles, etc.).

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_RELEASE_TYPE = (
    "4k_uhd_release",
    "blu_ray_release",
    "streaming_release",
    "theatrical",
    "award_ceremony",
    "sale_event",
)


def upgrade() -> None:
    op.create_table(
        "release_calendar",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # Nullable — pre-TMDB-catalogue titles won't have a movie row yet
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="SET NULL"),
        ),
        # Used when movie_id is NULL or as a display override
        sa.Column("title", sa.String(500)),
        sa.Column("release_type", sa.String(50), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        # Publisher / distributor (e.g. Criterion, Arrow)
        sa.Column("label", sa.String(100)),
        sa.Column(
            "region",
            sa.String(2),
            nullable=False,
            server_default=sa.text("'GB'"),
        ),
        # Source page or pre-order link
        sa.Column("url", sa.Text()),
        # True when this entry matches an active wanted_list item
        sa.Column(
            "is_wishlist_match",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        # Prevents duplicate push notifications for the same event
        sa.Column(
            "notified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_release_calendar_release_type",
        "release_calendar",
        f"release_type IN {_RELEASE_TYPE}",
    )

    op.create_index("idx_release_calendar_movie_id", "release_calendar", ["movie_id"])
    op.create_index("idx_release_calendar_release_date", "release_calendar", ["release_date"])
    op.create_index("idx_release_calendar_release_type", "release_calendar", ["release_type"])
    # iCal feed and notification job both query upcoming events
    op.create_index(
        "idx_release_calendar_upcoming",
        "release_calendar",
        ["release_date", "notified"],
    )


def downgrade() -> None:
    op.drop_index("idx_release_calendar_upcoming", table_name="release_calendar")
    op.drop_index("idx_release_calendar_release_type", table_name="release_calendar")
    op.drop_index("idx_release_calendar_release_date", table_name="release_calendar")
    op.drop_index("idx_release_calendar_movie_id", table_name="release_calendar")
    op.drop_constraint("ck_release_calendar_release_type", "release_calendar", type_="check")
    op.drop_table("release_calendar")
