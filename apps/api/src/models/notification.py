"""Push subscriptions, per-person notification preferences, and the outbox — §6.1, §6.2.

**Three tables rather than a column on `profiles`,** because each answers a different
question and only one of them is one-per-person: a person has several devices, one set of
preferences, and many notifications.

The outbox is the part that is not obvious. A push could be sent inline from whatever
noticed the thing worth telling someone about — a price drop, a due date — and Batch 9's
lesson (`DECISIONS.md` #50) is that a notification path with nothing durable behind it
cannot be proved to work. Writing the notification down first makes every one of §6.1's
behaviours a row you can read: a disabled category leaves a ``suppressed`` row saying so,
quiet hours leave a ``queued`` row with a ``deliver_after_utc`` in the morning, and digest
mode leaves several sharing one. It also makes the send idempotent, which matters because
a reminder that fires twice is worse than one that fires late.
"""

import uuid
from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin


class NotificationCategory(StrEnum):
    """§6.1's per-category toggles.

    One member per thing in this app that can generate a push, and nothing speculative:
    every one of these has, or is about to have, a sender that writes it.

    ``deals`` is §6.1's own example — *"disabling deals stops deal pushes"* — and means a
    price drop on something on the wanted list (§5.6, Batch 20). ``sale_events`` is kept
    separate from it because §5.11's Black Friday reminder is a different question from
    "the disc you want got cheaper", and someone may plausibly want one without the other.
    """

    deals = "deals"
    sale_events = "sale_events"
    releases = "releases"
    loans = "loans"
    movie_night = "movie_night"
    #: Batch X2: the daily check telling Craig a problem has appeared. No toggle, and only
    #: the admin receives it: switching off the one channel that says push broke would hide
    #: the next failure the way the last seven were hidden.
    attention = "attention"


class NotificationStatus(StrEnum):
    """Where a notification is in its life.

    ``suppressed`` is terminal and ``queued`` is not: a category the person switched off
    is never delivered, whereas quiet hours and digest mode only move *when*.
    """

    queued = "queued"
    sent = "sent"
    suppressed = "suppressed"
    failed = "failed"


#: Why a notification was never delivered. Recorded rather than inferred so "I did not get
#: that" has an answer — the failure mode Batch 9 refused to ship blind.
SUPPRESSED_CATEGORY_DISABLED = "category_disabled"
SUPPRESSED_NO_SUBSCRIPTIONS = "no_subscriptions"

#: How a held notification is released. Both are *delays*, not refusals.
DEFERRED_QUIET_HOURS = "quiet_hours"
DEFERRED_DIGEST = "digest"


class PushSubscription(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """One browser on one device — §6.2's "per-device subscription records".

    The endpoint is the identity. A push service mints a distinct URL per subscription, so
    two browsers on one laptop are two rows and re-subscribing the same browser returns
    the same endpoint — which is why ``endpoint`` is unique and registration upserts on it
    rather than inserting. Without that, "enable notifications" tapped twice would double
    every future push to that device.
    """

    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: The push service URL. ``Text`` because FCM's endpoints run past 200 characters and
    #: a truncated endpoint is a subscription that silently belongs to nobody.
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    #: The device's P-256 public key, unpadded base64url, as ``PushSubscription.getKey``
    #: hands it over. Stored in that form because it is what the encryption consumes.
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)

    #: The subscription's 16-byte auth secret, unpadded base64url.
    auth: Mapped[str] = mapped_column(String(50), nullable=False)

    #: What the person calls this device. §6.2's criterion is about telling one from the
    #: other — "removing one doesn't silence the other" is unprovable in a UI that lists
    #: two identical rows.
    device_label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: Kept so an unlabelled device is still recognisable, and so a stale row can be
    #: identified after the fact. Never shown in place of a label.
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_used_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    #: Consecutive transient send failures. A push service answering 5xx is not evidence
    #: the subscription is dead — only ``404``/``410`` are, and those delete the row.
    failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    #: Set when the person removes this device. Soft, so §6.2's "removing one doesn't
    #: silence the other" is answerable afterwards rather than merely observed once.
    revoked_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PushSubscription {self.device_label or self.endpoint[:40]!r}>"


class NotificationPreference(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """§6.1 — one row per person, created on first read.

    **Categories are columns, not a JSONB map.** There are five of them, they are a closed
    vocabulary, and a column can be queried, defaulted and constrained. A map would let a
    typo turn a toggle into a silent no-op, which is precisely the class of defect this
    batch exists to stop repeating.
    """

    __tablename__ = "notification_preferences"

    # Every column below declares a Python `default` as well as a `server_default`. The
    # DDL default is what an INSERT from anywhere else gets; the Python one is what an
    # in-memory instance has *before* it reaches the database — without it a freshly
    # constructed preference reads `None` for every toggle, and "is this category on?"
    # would answer falsely for the whole window between construction and flush.

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    deals_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sale_events_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    releases_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    loans_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    movie_night_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    #: When on, nothing is delivered as it happens; everything waits for
    #: :attr:`digest_hour_local` and arrives as one push.
    digest_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    #: The local hour the digest is delivered at. Local, not UTC — see
    #: :attr:`quiet_hours_timezone`.
    digest_hour_local: Mapped[int] = mapped_column(
        Integer, nullable=False, default=9, server_default="9"
    )

    #: Quiet hours, in local time, or ``NULL`` for none. Both or neither: a start with no
    #: end is a window that never closes.
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)

    #: **The one place this app is deliberately not UTC.** "Quiet hours 22:00–07:00" is a
    #: statement about the person's evening, and gotcha 26 is the standing record of what
    #: happens when a local question is answered in UTC: from late March to late October
    #: a British evening is an hour off, so a 22:00 UTC window would start at 23:00 for
    #: the person it belongs to and §6.1's "suppress evening alerts" would fail for half
    #: the year. Stored as an IANA name so the offset is derived per instant, not frozen.
    quiet_hours_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Europe/London", server_default="Europe/London"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<NotificationPreference {self.user_id} digest={self.digest_mode}>"


class Notification(Base, UUIDPrimaryKeyMixin):
    """One thing worth telling one person — the outbox.

    Not ``UpdatedAtMixin``: a notification is written once and then transitions, and the
    transitions each have their own timestamp so "when was it suppressed" and "when was it
    sent" are different columns rather than one that has forgotten.
    """

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", server_default="queued"
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    #: Where tapping the notification lands, as an app-relative path. Relative because the
    #: service worker resolves it against its own origin, and because an absolute URL in a
    #: notification is a redirect waiting to be got wrong.
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    #: **What makes a reminder job safe to re-run.** A unique key derived from the thing
    #: being reported — ``sale-event:<id>``, ``loan-overdue:<id>:<date>`` — so a second
    #: run inserts nothing rather than sending a second copy. `loans.reminder_sent` says
    #: the same thing for loans specifically; this generalises it.
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)

    #: ``NULL`` means "as soon as the next delivery pass runs". A value means quiet hours
    #: or digest mode moved it, and :attr:`deferred_reason` says which.
    deliver_after_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    deferred_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)

    #: Why this was never delivered, for a ``suppressed`` row.
    suppressed_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)

    sent_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    #: How many devices the send actually reached. Zero with status ``sent`` is impossible;
    #: zero devices is ``suppressed`` with :data:`SUPPRESSED_NO_SUBSCRIPTIONS`, which is a
    #: different and much more useful thing to read than a green "sent".
    delivered_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Notification {self.category} {self.status} {self.title!r}>"
