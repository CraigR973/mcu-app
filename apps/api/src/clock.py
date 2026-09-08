"""What "now" and "today" mean in this application.

``AGENTS.md`` states the rule these implement: *"UTC everywhere."* It held for
timestamps — every domain column is naive-UTC and :data:`src.schemas.wire.UtcDatetime`
stamps the offset at the wire — and it did **not** hold for calendar dates. Two
validators asked :func:`datetime.date.today`, which reads the *server's local timezone*,
while the value they were validating had been produced in UTC. The two agree on Railway,
which runs UTC, and disagree on a British developer's laptop for the hour after midnight
— so the disagreement was invisible in CI and in production, and surfaced only as a test
that failed between 00:00 and 01:00 BST.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def utcnow() -> datetime:
    """The naive-UTC instant every domain timestamp column holds."""
    return datetime.now(UTC).replace(tzinfo=None)


def utc_today() -> date:
    """Today in UTC — the date a server-side default should use."""
    return datetime.now(UTC).date()


def latest_plausible_today() -> date:
    """The latest calendar date that is *today* somewhere on Earth.

    The ceiling for "this date cannot be in the future". A date is supplied by a person
    holding a phone, in their timezone, and the server has no idea what that timezone is;
    the honest bound is therefore the furthest-ahead one that exists. Kiritimati is
    UTC+14, so that is UTC today plus a day.

    Comparing against UTC today alone is not merely stricter, it is **wrong**: at 00:30
    in London on the 9th, UTC still says the 8th, and a person logging tonight's film
    would be told the date they are looking at on their own calendar is in the future.
    The guard exists to catch a typed year of 2126, not to arbitrate timezones.
    """
    return utc_today() + timedelta(days=1)
