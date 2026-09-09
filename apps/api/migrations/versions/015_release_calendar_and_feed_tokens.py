"""create release_calendar and calendar_feed_tokens

Revision ID: 015
Revises: 014
Create Date: 2026-09-09

Roadmap §3.26's calendar, and the table that makes §7.4's `.ics` feed safe.

**`/api/v1/calendar.ics` is this application's first unauthenticated surface.** Everything
else refuses without a bearer token. A calendar subscription cannot carry one — Apple
Calendar and Google Calendar fetch a bare URL on a schedule, with no way to attach a header
and no way to refresh anything — so the URL itself is the credential.

That shapes this table more than §3.26 does:

**The token is stored hashed, never in plaintext.** SHA-256, exactly as
``refresh_tokens.token_hash`` already does. A database leak then yields no working feed
URLs, and the lookup is an indexed equality test on a hash rather than a scan — so it is
also constant-time in the way that matters, since every candidate row is found the same way.

**One live token per person, and revoking is a row you can point at.** `revoked_at_utc`
rather than a delete, so "this link stopped working on Tuesday" is answerable. A new
subscribe call revokes the old token and issues another, which is the only way an
accidentally-shared link can be taken back.

**`last_used_at_utc` exists so an unused link is visible.** A subscription that has never
been fetched is either not set up or leaked and idle, and both are worth seeing.

§3.26's ``is_wishlist_match`` is created and never written: `wanted_list` is §3.5 and
**Batch 18** builds it. The column is here because §3.26 designs it and a later batch
filling it in is cheaper than a migration then; nothing reads it, and the API does not
expose it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RELEASE_TYPES = (
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
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("release_type", sa.String(50), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("region", sa.String(2), nullable=False, server_default="GB"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("poster_path", sa.String(255), nullable=True),
        sa.Column(
            "is_wishlist_match", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # SET NULL, not CASCADE: §3.26 says the film may not exist yet, so a calendar row
        # standing on its own is the *normal* case, not a broken one.
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "release_type IN (" + ", ".join(f"'{value}'" for value in RELEASE_TYPES) + ")",
            name="ck_release_calendar_type",
        ),
        sa.CheckConstraint("region ~ '^[A-Z]{2}$'", name="ck_release_calendar_region"),
        # What makes re-ingestion idempotent. A TMDB film has one theatrical date per
        # region; running the job twice must update that row, not add a second.
        sa.UniqueConstraint(
            "tmdb_id",
            "release_type",
            "region",
            name="uq_release_calendar_tmdb_type_region",
        ),
    )
    # The calendar's only ordering, and the `.ics` feed's window.
    op.create_index("ix_release_calendar_date", "release_calendar", ["release_date"])
    op.create_index("ix_release_calendar_movie_id", "release_calendar", ["movie_id"])

    op.create_table(
        "calendar_feed_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # SHA-256 hex, like `refresh_tokens.token_hash`. The plaintext is returned once,
        # at creation, and never stored — so a database leak yields no working URLs.
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("revoked_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_calendar_feed_tokens_hash", "calendar_feed_tokens", ["token_hash"], unique=True
    )
    # One live token per person. A partial unique index rather than application logic,
    # because "there is exactly one working link" is the property the revoke story rests on.
    op.create_index(
        "uq_calendar_feed_tokens_live",
        "calendar_feed_tokens",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at_utc IS NULL"),
    )
    op.execute(
        """
        CREATE TRIGGER release_calendar_set_updated_at
        BEFORE UPDATE ON release_calendar
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS release_calendar_set_updated_at ON release_calendar;")
    op.drop_index("uq_calendar_feed_tokens_live", table_name="calendar_feed_tokens")
    op.drop_index("ix_calendar_feed_tokens_hash", table_name="calendar_feed_tokens")
    op.drop_table("calendar_feed_tokens")
    op.drop_index("ix_release_calendar_movie_id", table_name="release_calendar")
    op.drop_index("ix_release_calendar_date", table_name="release_calendar")
    op.drop_table("release_calendar")
