"""create push_subscriptions, notification_preferences and notifications

Revision ID: 020
Revises: 019
Create Date: 2026-09-09

Batch 11 — roadmap §6.1, §6.2 and §5.11.

**This is the schema Batch 9 refused to pretend it had.** `DECISIONS.md` #50 dropped the
onboarding wizard's notifications step rather than ship a button that enabled push against
"zero infrastructure: no VAPID key, no subscription, no endpoint, no `push_subscription`
column". The column arrives here, along with the other two.

**`endpoint` is unique, and that is the important constraint in this file.** A push service
returns the same endpoint when a browser re-subscribes, so registration upserts on it. An
ordinary insert would give one device two rows and every future push two copies, which is
the kind of defect that looks like a working feature.

**No `soft_delete` trigger on any of these.** A revoked subscription carries
`revoked_at_utc` and a suppressed notification carries its reason, so both already record
their own end; §13.5's Trash is for things a person might want back, and neither of these
is one.

**Seeding §5.11's sale seasons is deliberately not done here.** Prime Day and Black Friday
recur annually, so a migration freezing two years of dates would be stale by 2028 and
un-rerunnable. `src/services/sale_seasons.py` generates them per year and the admin
endpoint is idempotent — gotcha 18's point about a migration being unable to prove a data
operation applies just as much to one that writes rows nobody has counted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Kept in step with :class:`src.models.notification.NotificationCategory`. A CHECK rather
#: than a Postgres ENUM: the vocabulary will grow as batches add senders, and adding a
#: value to a CHECK is one migration where adding one to an ENUM under a downgrade path is
#: several.
_CATEGORIES = ("deals", "sale_events", "releases", "loans", "movie_night")
_STATUSES = ("queued", "sent", "suppressed", "failed")


def _quoted(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Text, not String(n): FCM endpoints run well past 200 characters and a truncated
        # endpoint is a subscription that belongs to nobody.
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(50), nullable=False),
        sa.Column("device_label", sa.String(100), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("last_used_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("failure_count >= 0", name="ck_push_subscriptions_failure_count"),
        # An uncompressed P-256 point is 65 bytes and the auth secret is 16, which in
        # unpadded base64url are exactly 87 and 22 characters. Pinned so a subscription
        # that would fail to encrypt is refused at the door rather than at send time,
        # where the push service answers 201 and nothing arrives.
        sa.CheckConstraint("length(p256dh) = 87", name="ck_push_subscriptions_p256dh_length"),
        sa.CheckConstraint("length(auth) = 22", name="ck_push_subscriptions_auth_length"),
    )
    op.create_index(
        "ix_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"], unique=True
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.execute(
        """
        CREATE TRIGGER push_subscriptions_set_updated_at
        BEFORE UPDATE ON push_subscriptions
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deals_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "sale_events_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("releases_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("loans_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "movie_night_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("digest_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("digest_hour_local", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column(
            "quiet_hours_timezone", sa.String(64), nullable=False, server_default="Europe/London"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "digest_hour_local BETWEEN 0 AND 23", name="ck_notification_preferences_digest_hour"
        ),
        # Both or neither. A start with no end is a quiet period that never ends, which
        # would silently hold every notification for ever.
        sa.CheckConstraint(
            "(quiet_hours_start IS NULL) = (quiet_hours_end IS NULL)",
            name="ck_notification_preferences_quiet_hours_pair",
        ),
    )
    op.create_index(
        "ix_notification_preferences_user_id", "notification_preferences", ["user_id"], unique=True
    )
    op.execute(
        """
        CREATE TRIGGER notification_preferences_set_updated_at
        BEFORE UPDATE ON notification_preferences
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("dedupe_key", sa.String(200), nullable=True),
        sa.Column("deliver_after_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("deferred_reason", sa.String(30), nullable=True),
        sa.Column("suppressed_reason", sa.String(30), nullable=True),
        sa.Column("sent_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            f"category IN ({_quoted(_CATEGORIES)})", name="ck_notifications_category"
        ),
        sa.CheckConstraint(f"status IN ({_quoted(_STATUSES)})", name="ck_notifications_status"),
        sa.CheckConstraint("delivered_count >= 0", name="ck_notifications_delivered_count"),
        # A sent notification reached at least one device. Zero devices is `suppressed`
        # with `no_subscriptions`, which is a far more useful thing to read back than a
        # green "sent" that went nowhere — the exact shape of Batch 9's dead button.
        sa.CheckConstraint(
            "status <> 'sent' OR (sent_at_utc IS NOT NULL AND delivered_count > 0)",
            name="ck_notifications_sent_has_delivery",
        ),
    )
    # The unique index is what makes a reminder job safe to re-run. Partial, because a
    # notification without a dedupe key is a one-off (a test push) and several of those
    # must be allowed to coexist — a plain UNIQUE would collapse them all into one row.
    op.create_index(
        "ix_notifications_dedupe_key",
        "notifications",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    # The delivery pass's own query: queued rows, oldest first. Partial so it stays small
    # as sent rows accumulate — they are the overwhelming majority after a week.
    op.create_index(
        "ix_notifications_pending",
        "notifications",
        ["deliver_after_utc"],
        postgresql_where=sa.text("status = 'queued'"),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_pending", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_dedupe_key", table_name="notifications")
    op.drop_table("notifications")

    op.execute(
        "DROP TRIGGER IF EXISTS notification_preferences_set_updated_at "
        "ON notification_preferences;"
    )
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")

    op.execute("DROP TRIGGER IF EXISTS push_subscriptions_set_updated_at ON push_subscriptions;")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
