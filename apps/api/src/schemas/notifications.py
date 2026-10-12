"""Wire models for notification preferences, devices and the outbox — Batch 11."""

from __future__ import annotations

import uuid
from datetime import date, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator

from src.schemas.wire import UtcDatetime

NotificationCategoryName = Literal["deals", "sale_events", "releases", "loans", "movie_night"]
NotificationStatusName = Literal["queued", "sent", "suppressed", "failed"]

#: The two base64url lengths a valid subscription has: a 65-byte P-256 point and a 16-byte
#: auth secret. Enforced here as well as by the migration's CHECK so a bad subscription is
#: refused with a 422 that says which field, rather than a 500 from the constraint.
_P256DH_LENGTH = 87
_AUTH_LENGTH = 22


class VapidKeyResponse(BaseModel):
    """The application server's public key, for ``pushManager.subscribe``.

    Served rather than shipped as a build-time `VITE_` variable — see the note on
    :class:`src.config.Settings`. ``configured`` is false when Railway has no key, which
    is the state that produced the TMDB outage: a feature that is simply absent, with the
    front end unable to say so.
    """

    publicKey: str | None = None
    configured: bool


class PushSubscriptionKeys(BaseModel):
    """The ``keys`` object exactly as ``PushSubscription.toJSON()`` emits it."""

    p256dh: str = Field(min_length=_P256DH_LENGTH, max_length=_P256DH_LENGTH)
    auth: str = Field(min_length=_AUTH_LENGTH, max_length=_AUTH_LENGTH)


class PushSubscriptionCreateRequest(BaseModel):
    """Register this browser. The body is the browser's own subscription JSON, plus a label.

    Taking the browser's shape verbatim rather than flattening it means the client posts
    ``{...subscription.toJSON(), deviceLabel}`` and nothing has to be transcribed — which
    is one fewer place for ``p256dh`` to be mistyped into a subscription that encrypts to
    nobody and still gets a 201 from the push service.
    """

    endpoint: str = Field(min_length=1, max_length=2000)
    keys: PushSubscriptionKeys
    deviceLabel: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _endpoint_must_be_https(self) -> PushSubscriptionCreateRequest:
        # A push endpoint is always HTTPS. Anything else is either a mistake or an attempt
        # to point the server's outbound request somewhere it should not go — the SSRF
        # shape Batch 19's fetcher already guards for scraping.
        if not self.endpoint.startswith("https://"):
            raise ValueError("endpoint must be an https URL")
        return self


class PushSubscriptionResponse(BaseModel):
    """One registered device.

    **The endpoint is not returned in full.** It is a bearer capability — anyone holding
    it can push to that device — and the UI only needs enough to tell two rows apart.
    """

    id: uuid.UUID
    deviceLabel: str | None = None
    endpointPreview: str
    pushService: str
    userAgent: str | None = None
    createdAt: UtcDatetime
    lastUsedAt: UtcDatetime | None = None
    failureCount: int = Field(ge=0)


class PushSubscriptionListResponse(BaseModel):
    items: list[PushSubscriptionResponse]
    total: int = Field(ge=0)
    #: Batch X3: when the push service last refused one of this person's devices, while none
    #: is live; null otherwise. The app shows a banner until notifications are on again.
    stoppedAt: UtcDatetime | None = None


class PushDeviceStatusRequest(BaseModel):
    """Batch X3: "does the server hold this browser's subscription?" — by its endpoint."""

    endpoint: str = Field(min_length=1, max_length=2000)


class PushDeviceStatusResponse(BaseModel):
    """What the server holds for this browser, for the signed-in person.

    ``live``: it pushes here. ``refused``: the push service refused it, so the page registers
    the phone again, with a fresh subscription. ``removed``: the person took it off their
    list, so the page leaves it alone. ``unknown``: the server has no such device for this
    person, so the page registers it.
    """

    state: Literal["live", "refused", "removed", "unknown"]
    revokedAt: UtcDatetime | None = None


class NotificationPreferenceResponse(BaseModel):
    """§6.1's toggles as the settings page reads them."""

    dealsEnabled: bool
    saleEventsEnabled: bool
    releasesEnabled: bool
    loansEnabled: bool
    movieNightEnabled: bool
    digestMode: bool
    digestHourLocal: int = Field(ge=0, le=23)
    quietHoursStart: time | None = None
    quietHoursEnd: time | None = None
    quietHoursTimezone: str


class NotificationPreferenceUpdateRequest(BaseModel):
    """A partial update — every field optional, absent means unchanged.

    ``quietHours`` is the exception: the two ends move together or not at all, because a
    start without an end is a window that never closes. The migration's CHECK says the
    same thing; this says it with a 422 instead of a 500.
    """

    dealsEnabled: bool | None = None
    saleEventsEnabled: bool | None = None
    releasesEnabled: bool | None = None
    loansEnabled: bool | None = None
    movieNightEnabled: bool | None = None
    digestMode: bool | None = None
    digestHourLocal: int | None = Field(default=None, ge=0, le=23)
    quietHoursStart: time | None = None
    quietHoursEnd: time | None = None
    #: ``True`` clears quiet hours. Needed because ``null`` on the two times above is
    #: indistinguishable from "not supplied" in a partial update.
    clearQuietHours: bool = False
    quietHoursTimezone: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _validate(self) -> NotificationPreferenceUpdateRequest:
        start, end = self.quietHoursStart, self.quietHoursEnd
        if (start is None) != (end is None):
            raise ValueError("quietHoursStart and quietHoursEnd must be supplied together")
        if self.clearQuietHours and start is not None:
            raise ValueError("cannot set and clear quiet hours in one request")
        if self.quietHoursTimezone is not None:
            try:
                ZoneInfo(self.quietHoursTimezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                # Validated at the door because the delivery pass falls back on an unknown
                # zone rather than failing — so a typo here would quietly move somebody's
                # evening to London's and nothing would ever say so.
                raise ValueError("quietHoursTimezone must be an IANA timezone name") from exc
        return self


class NotificationResponse(BaseModel):
    """One row of the outbox, as the notifications page shows it."""

    id: uuid.UUID
    category: str
    status: NotificationStatusName
    title: str
    body: str
    url: str | None = None
    createdAt: UtcDatetime
    deliverAfter: UtcDatetime | None = None
    deferredReason: str | None = None
    suppressedReason: str | None = None
    sentAt: UtcDatetime | None = None
    deliveredCount: int = Field(ge=0)


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int = Field(ge=0)
    #: How many are still waiting — the number worth showing next to "digest mode is on".
    queuedCount: int = Field(ge=0)


class TestNotificationResponse(BaseModel):
    """What §6.2's test button did.

    ``delivered`` is the count of devices that actually took the push, so "I pressed test
    and nothing happened" separates into *no devices*, *the push service refused*, and
    *it was delivered and your browser did not show it* — three different problems.
    """

    notificationId: uuid.UUID
    delivered: int = Field(ge=0)
    devicesTried: int = Field(ge=0)
    subscriptionsRemoved: int = Field(ge=0)
    status: NotificationStatusName
    suppressedReason: str | None = None


class ReminderRunResponse(BaseModel):
    """What one reminder pass found and queued."""

    asOf: date
    seasonsSeeded: int = Field(ge=0)
    saleEvents: int = Field(ge=0)
    releases: int = Field(ge=0)
    overdueLoans: int = Field(ge=0)
    queued: int = Field(ge=0)
    delivered: int = Field(ge=0)
