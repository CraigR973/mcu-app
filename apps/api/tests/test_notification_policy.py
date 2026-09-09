"""§6.1's delivery policy — quiet hours, digest mode and the category toggles.

These run without a database on purpose. The rules are pure functions of a preference row
and an instant, and gotcha 15 means anything needing Postgres skips on this machine and is
only ever exercised in CI. Keeping the *decisions* testable locally is what lets a change
to them be checked before it is pushed; :mod:`tests.test_notifications_api` then proves
the same rules through the real endpoints against a real database.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, time

import pytest

from src.models.notification import (
    DEFERRED_DIGEST,
    DEFERRED_QUIET_HOURS,
    Notification,
    NotificationPreference,
)
from src.services.notifications import (
    notification_payload,
    quiet_hours_cover,
    scheduled_delivery,
)

#: Every default spelled out, because these rows are never flushed here.
#:
#: SQLAlchemy applies a ``default=`` when the INSERT is built, not in ``__init__`` — so a
#: constructed-but-unflushed row reads ``None`` for every column that has one. Relying on
#: that would make each toggle read as *off*, and the suppression tests below would then
#: pass for entirely the wrong reason.
_DEFAULTS: dict[str, object] = {
    "deals_enabled": True,
    "sale_events_enabled": True,
    "releases_enabled": True,
    "loans_enabled": True,
    "movie_night_enabled": True,
    "digest_mode": False,
    "digest_hour_local": 9,
    "quiet_hours_start": None,
    "quiet_hours_end": None,
    "quiet_hours_timezone": "Europe/London",
}


def _preference(**overrides: object) -> NotificationPreference:
    """A preference row as constructed, never flushed."""
    preference = NotificationPreference(user_id=uuid.uuid4())
    for name, value in {**_DEFAULTS, **overrides}.items():
        setattr(preference, name, value)
    return preference


def test_the_model_declares_every_default_this_module_assumes() -> None:
    """Guard the fixture against the model's defaults moving underneath it.

    Without this, changing a column's default would leave these tests asserting against a
    world that no longer exists — passing, and proving nothing about the app.
    """
    columns = NotificationPreference.__table__.columns
    for name, expected in _DEFAULTS.items():
        declared = columns[name].default
        assert (declared.arg if declared is not None else None) == expected, name


def _evening_quiet() -> NotificationPreference:
    """The window anybody actually sets: 22:00 to 07:00, wrapping midnight."""
    return _preference(
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(7, 0),
        quiet_hours_timezone="Europe/London",
    )


class TestQuietHours:
    def test_an_alert_before_the_window_goes_out_immediately(self) -> None:
        # 21:00 GMT on a January evening — an hour before quiet hours begin.
        deliver_after, reason = scheduled_delivery(_evening_quiet(), datetime(2026, 1, 15, 21, 0))

        assert deliver_after is None
        assert reason is None

    def test_an_evening_alert_is_held_until_the_morning(self) -> None:
        """§6.1's acceptance: *"quiet hours suppress evening alerts"*."""
        preference = _evening_quiet()
        during = datetime(2026, 1, 15, 23, 30)  # 23:30 GMT

        assert quiet_hours_cover(preference, during)
        deliver_after, reason = scheduled_delivery(preference, during)

        assert deliver_after == datetime(2026, 1, 16, 7, 0), "released at 07:00 local"
        assert reason == DEFERRED_QUIET_HOURS

    def test_an_alert_after_midnight_is_held_until_the_same_morning(self) -> None:
        """The wrapping half of the window — 02:00 is still last night's quiet hours."""
        preference = _evening_quiet()

        deliver_after, reason = scheduled_delivery(preference, datetime(2026, 1, 16, 2, 0))

        assert deliver_after == datetime(2026, 1, 16, 7, 0)
        assert reason == DEFERRED_QUIET_HOURS

    def test_quiet_hours_follow_british_summer_time(self) -> None:
        """**The gotcha 26 case, and the reason the timezone is stored at all.**

        21:30 UTC is 21:30 in London in January and 22:30 in July. A quiet window of
        22:00–07:00 must therefore cover the July instant and not the January one. Reading
        the window in UTC would get this wrong for the seven months of BST — silently, and
        in the direction of delivering alerts during the evening the setting exists to
        protect.
        """
        preference = _evening_quiet()

        assert not quiet_hours_cover(preference, datetime(2026, 1, 15, 21, 30))
        assert quiet_hours_cover(preference, datetime(2026, 7, 15, 21, 30))

    def test_the_summer_release_time_is_also_local(self) -> None:
        """07:00 BST is 06:00 UTC, so the held alert leaves an hour earlier in UTC terms."""
        preference = _evening_quiet()

        deliver_after, _ = scheduled_delivery(preference, datetime(2026, 7, 15, 23, 0))

        assert deliver_after == datetime(2026, 7, 16, 6, 0)

    def test_no_quiet_hours_means_no_delay(self) -> None:
        deliver_after, reason = scheduled_delivery(_preference(), datetime(2026, 1, 15, 23, 30))

        assert deliver_after is None
        assert reason is None

    def test_a_zero_width_window_is_not_a_window(self) -> None:
        """A start equal to its end would otherwise read as "quiet all day"."""
        preference = _preference(quiet_hours_start=time(22, 0), quiet_hours_end=time(22, 0))

        assert not quiet_hours_cover(preference, datetime(2026, 1, 15, 22, 0))

    def test_a_daytime_window_does_not_wrap(self) -> None:
        """09:00–17:00 is the working day, and 20:00 is outside it."""
        preference = _preference(quiet_hours_start=time(9, 0), quiet_hours_end=time(17, 0))

        assert quiet_hours_cover(preference, datetime(2026, 1, 15, 11, 0))
        assert not quiet_hours_cover(preference, datetime(2026, 1, 15, 20, 0))

    def test_an_unknown_timezone_falls_back_rather_than_failing(self) -> None:
        """One bad row must not be able to stop every notification in the app."""
        preference = _preference(
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(7, 0),
            quiet_hours_timezone="Mars/Olympus_Mons",
        )

        assert quiet_hours_cover(preference, datetime(2026, 1, 15, 23, 0)) is True


class TestDigestMode:
    def test_digest_mode_holds_until_the_next_digest_hour(self) -> None:
        preference = _preference(digest_mode=True, digest_hour_local=9)

        deliver_after, reason = scheduled_delivery(preference, datetime(2026, 1, 15, 14, 0))

        assert deliver_after == datetime(2026, 1, 16, 9, 0), "today's 09:00 has passed"
        assert reason == DEFERRED_DIGEST

    def test_a_morning_notification_waits_for_the_same_days_digest(self) -> None:
        preference = _preference(digest_mode=True, digest_hour_local=9)

        deliver_after, _ = scheduled_delivery(preference, datetime(2026, 1, 15, 6, 0))

        assert deliver_after == datetime(2026, 1, 15, 9, 0)

    def test_the_digest_hour_is_local_too(self) -> None:
        """09:00 BST is 08:00 UTC."""
        preference = _preference(digest_mode=True, digest_hour_local=9)

        deliver_after, _ = scheduled_delivery(preference, datetime(2026, 7, 15, 6, 0))

        assert deliver_after == datetime(2026, 7, 15, 8, 0)

    def test_a_digest_hour_inside_quiet_hours_still_waits_for_the_quiet_hours(self) -> None:
        """The two rules compose in one order only, and this is the case that proves it.

        A digest set for 23:00 with quiet hours from 22:00 must not fire at 23:00 — quiet
        hours are applied to the digest time, not the other way round.
        """
        preference = _preference(
            digest_mode=True,
            digest_hour_local=23,
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(7, 0),
        )

        deliver_after, reason = scheduled_delivery(preference, datetime(2026, 1, 15, 14, 0))

        assert deliver_after == datetime(2026, 1, 16, 7, 0)
        assert reason == DEFERRED_QUIET_HOURS


class TestPayload:
    def _notification(self, title: str) -> Notification:
        return Notification(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            category="deals",
            title=title,
            body=f"body of {title}",
            url="/wanted",
        )

    def test_one_notification_renders_as_itself(self) -> None:
        payload = json.loads(notification_payload([self._notification("Deep Red")]))

        assert payload["title"] == "Deep Red"
        assert payload["body"] == "body of Deep Red"
        assert payload["url"] == "/wanted"
        assert payload["category"] == "deals"

    def test_several_notifications_render_as_one_digest(self) -> None:
        """The point of digest mode: one push, not one per item."""
        items = [self._notification(f"Film {index}") for index in range(3)]

        payload = json.loads(notification_payload(items))

        assert payload["title"] == "3 updates from your collection"
        assert payload["body"].count("•") == 3
        assert payload["url"] == "/notifications"

    def test_a_long_digest_is_summarised_rather_than_listed(self) -> None:
        """A notification body is a few lines on a phone, not a scrollable list."""
        items = [self._notification(f"Film {index}") for index in range(9)]

        payload = json.loads(notification_payload(items))

        assert payload["body"].count("•") == 5
        assert "and 4 more" in payload["body"]

    def test_the_payload_fits_a_single_push_record(self) -> None:
        """4096 bytes is the ceiling; a digest of long titles must not sail past it."""
        items = [self._notification("A Very Long Film Title " * 8) for _ in range(50)]

        assert len(notification_payload(items)) < 3000


@pytest.mark.parametrize("hour", [0, 9, 23])
def test_every_permitted_digest_hour_produces_a_future_time(hour: int) -> None:
    """Midnight and 23:00 are the edges the modulo arithmetic could get wrong."""
    preference = _preference(digest_mode=True, digest_hour_local=hour)
    now = datetime(2026, 1, 15, 12, 0)

    deliver_after, _ = scheduled_delivery(preference, now)

    assert deliver_after is not None and deliver_after > now
