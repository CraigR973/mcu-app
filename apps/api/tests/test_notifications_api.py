"""Batch 11's acceptance criteria, proved through the real endpoints.

**What these do and do not prove.** They run against a real Postgres in CI, so the schema,
the constraints and the upsert are genuinely exercised. The push *transport* is stubbed —
`RecordingSender` stands in for a push service — so what is proved is that the right
payload is handed to the right devices at the right time, and **not** that a phone lights
up. §6.2's acceptance ("admin connects phone + laptop; both receive pushes") needs two real
devices and is deferred to the owner, exactly as Batch 19's live-retailer criterion was.
:mod:`tests.test_webpush` covers the half of the transport that can be proved here.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user, require_admin
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.loan import Loan
from src.models.movie import Movie
from src.models.notification import (
    SUPPRESSED_CATEGORY_DISABLED,
    SUPPRESSED_NO_SUBSCRIPTIONS,
    Notification,
    NotificationCategory,
    PushSubscription,
)
from src.models.profile import Profile, UserRole
from src.models.release_calendar import ReleaseCalendarEntry
from src.routers.notifications import set_push_sender
from src.services import webpush
from src.services.notifications import (
    DeliveryOutcome,
    DeliveryResult,
    deliver_pending,
    queue_notification,
)
from src.services.reminders import SALE_LEAD_DAYS, run_reminders
from src.services.sale_seasons import SALE_EVENT_TYPE, black_friday, seed_year

pytestmark = pytest.mark.asyncio


class RecordingSender:
    """A push service that records instead of sending.

    Per-endpoint outcomes are settable so a ``410`` on one device can be proved not to
    affect another — which is the mechanism behind §6.2's "removing one doesn't silence
    the other".
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []
        self.outcomes: dict[str, DeliveryOutcome] = {}

    async def send(self, subscription: PushSubscription, payload: bytes) -> DeliveryResult:
        self.sent.append((subscription.endpoint, payload))
        outcome = self.outcomes.get(subscription.endpoint, DeliveryOutcome.delivered)
        status = {
            DeliveryOutcome.delivered: 201,
            DeliveryOutcome.gone: 410,
            DeliveryOutcome.failed: 500,
        }[outcome]
        return DeliveryResult(outcome, status)

    def endpoints(self) -> list[str]:
        return [endpoint for endpoint, _ in self.sent]


def _subscription_keys() -> tuple[str, str]:
    """A structurally valid ``(p256dh, auth)`` pair — 87 and 22 base64url characters."""
    key = ec.generate_private_key(ec.SECP256R1())
    return (
        webpush.b64url_encode(webpush.vapid_public_key_bytes(key)),
        webpush.b64url_encode(os.urandom(16)),
    )


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _profile(session: AsyncSession, role: UserRole) -> Profile:
    profile = Profile(
        id=uuid.uuid4(), display_name=f"{role.value} {uuid.uuid4().hex[:8]}", role=role
    )
    session.add(profile)
    await session.flush()
    return profile


@pytest_asyncio.fixture
async def admin(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, UserRole.admin)


@pytest_asyncio.fixture
async def sender() -> AsyncIterator[RecordingSender]:
    recorder = RecordingSender()
    set_push_sender(recorder)
    try:
        yield recorder
    finally:
        set_push_sender(None)


@pytest_asyncio.fixture
async def client(api_session: AsyncSession, admin: Profile) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user() -> Profile:
        return admin

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[require_admin] = override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


async def _register(client: AsyncClient, label: str) -> dict[str, object]:
    p256dh, auth = _subscription_keys()
    response = await client.post(
        "/api/v1/notifications/subscriptions",
        json={
            "endpoint": f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}",
            "keys": {"p256dh": p256dh, "auth": auth},
            "deviceLabel": label,
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


class TestDeviceRegistration:
    """§6.2 — per-device subscription records."""

    async def test_a_device_registers_and_is_listed(self, client: AsyncClient) -> None:
        created = await _register(client, "Craig's phone")

        listed = (await client.get("/api/v1/notifications/subscriptions")).json()

        assert listed["total"] == 1
        assert listed["items"][0]["id"] == created["id"]
        assert listed["items"][0]["deviceLabel"] == "Craig's phone"

    async def test_two_devices_are_two_records(self, client: AsyncClient) -> None:
        await _register(client, "phone")
        await _register(client, "laptop")

        listed = (await client.get("/api/v1/notifications/subscriptions")).json()

        assert listed["total"] == 2
        assert {item["deviceLabel"] for item in listed["items"]} == {"phone", "laptop"}

    async def test_the_full_endpoint_is_never_returned(self, client: AsyncClient) -> None:
        """It is a bearer capability — anyone holding it can push to that device."""
        created = await _register(client, "phone")

        assert "endpoint" not in created
        assert created["endpointPreview"].startswith("…")
        assert len(created["endpointPreview"]) <= 13
        assert created["pushService"] == "fcm.googleapis.com"

    async def test_re_subscribing_the_same_browser_updates_one_row(
        self, client: AsyncClient, api_session: AsyncSession, admin: Profile
    ) -> None:
        """A push service returns the same endpoint, and an insert would double every push."""
        endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"
        p256dh, auth = _subscription_keys()
        body = {
            "endpoint": endpoint,
            "keys": {"p256dh": p256dh, "auth": auth},
            "deviceLabel": "phone",
        }

        first = await client.post("/api/v1/notifications/subscriptions", json=body)
        second = await client.post(
            "/api/v1/notifications/subscriptions", json={**body, "deviceLabel": "renamed phone"}
        )

        assert first.status_code == 201 and second.status_code == 201
        assert first.json()["id"] == second.json()["id"], "same row, not a second one"
        rows = (
            (
                await api_session.execute(
                    select(PushSubscription).where(PushSubscription.user_id == admin.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].device_label == "renamed phone"

    async def test_a_non_https_endpoint_is_refused(self, client: AsyncClient) -> None:
        p256dh, auth = _subscription_keys()

        response = await client.post(
            "/api/v1/notifications/subscriptions",
            json={
                "endpoint": "http://internal.local/push",
                "keys": {"p256dh": p256dh, "auth": auth},
            },
        )

        assert response.status_code == 422

    async def test_a_truncated_key_is_refused_with_422_not_500(self, client: AsyncClient) -> None:
        """The migration's CHECK would also catch this; a 422 says which field."""
        _, auth = _subscription_keys()

        response = await client.post(
            "/api/v1/notifications/subscriptions",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
                "keys": {"p256dh": "too-short", "auth": auth},
            },
        )

        assert response.status_code == 422

    async def test_removing_a_device_takes_it_off_the_list(self, client: AsyncClient) -> None:
        phone = await _register(client, "phone")
        await _register(client, "laptop")

        removed = await client.delete(f"/api/v1/notifications/subscriptions/{phone['id']}")

        assert removed.status_code == 204
        listed = (await client.get("/api/v1/notifications/subscriptions")).json()
        assert [item["deviceLabel"] for item in listed["items"]] == ["laptop"]

    async def test_one_person_cannot_remove_anothers_device(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """Two profiles, one of them the owner's — this would be a surveillance feature."""
        other = await _profile(api_session, UserRole.viewer)
        p256dh, auth = _subscription_keys()
        theirs = PushSubscription(
            id=uuid.uuid4(),
            user_id=other.id,
            endpoint=f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}",
            p256dh=p256dh,
            auth=auth,
            device_label="their phone",
        )
        api_session.add(theirs)
        await api_session.flush()

        response = await client.delete(f"/api/v1/notifications/subscriptions/{theirs.id}")

        assert response.status_code == 404


class TestMultiDeviceDelivery:
    """§6.2's acceptance, as far as a stub can carry it."""

    async def test_both_devices_receive_the_same_push(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        phone = await _register(client, "phone")
        laptop = await _register(client, "laptop")
        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Deep Red dropped to £15",
            body="Arrow Video",
        )

        summary = await deliver_pending(api_session, sender=sender)

        assert summary.sent == 1
        assert summary.pushes_delivered == 2, "one notification, two devices"
        assert len(sender.sent) == 2
        assert phone["id"] != laptop["id"]

    async def test_removing_one_device_does_not_silence_the_other(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        """§6.2's third clause, stated exactly."""
        phone = await _register(client, "phone")
        await _register(client, "laptop")
        await client.delete(f"/api/v1/notifications/subscriptions/{phone['id']}")
        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Still arriving",
            body="on the laptop",
        )

        summary = await deliver_pending(api_session, sender=sender)

        assert summary.pushes_delivered == 1
        assert len(sender.endpoints()) == 1

    async def test_a_dead_device_is_removed_and_the_others_still_get_it(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        """A ``410`` is the only answer that proves a subscription is really gone."""
        await _register(client, "phone")
        await _register(client, "laptop")
        subscriptions = (
            (
                await api_session.execute(
                    select(PushSubscription).where(PushSubscription.user_id == admin.id)
                )
            )
            .scalars()
            .all()
        )
        sender.outcomes[subscriptions[0].endpoint] = DeliveryOutcome.gone
        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="One device is gone",
            body="the other is not",
        )

        summary = await deliver_pending(api_session, sender=sender)

        assert summary.pushes_delivered == 1
        assert summary.subscriptions_removed == 1
        assert summary.sent == 1, "delivered to at least one device counts as sent"

    async def test_a_transient_failure_does_not_delete_the_subscription(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        """Gotcha 23: a 5xx is the *unknown* case, not proof the device is dead."""
        await _register(client, "phone")
        subscription = (
            (
                await api_session.execute(
                    select(PushSubscription).where(PushSubscription.user_id == admin.id)
                )
            )
            .scalars()
            .one()
        )
        sender.outcomes[subscription.endpoint] = DeliveryOutcome.failed
        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Nobody home",
            body="for now",
        )

        summary = await deliver_pending(api_session, sender=sender)

        assert summary.failed == 1
        assert summary.subscriptions_removed == 0
        await api_session.refresh(subscription)
        assert subscription.failure_count == 1

    async def test_a_notification_with_no_devices_says_so(
        self, api_session: AsyncSession, admin: Profile, sender: RecordingSender
    ) -> None:
        """ "Nobody to tell" must not read back as a green "sent"."""
        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Into the void",
            body="no devices",
        )

        summary = await deliver_pending(api_session, sender=sender)

        assert summary.sent == 0 and summary.suppressed == 1
        row = (await api_session.execute(select(Notification))).scalars().one()
        assert row.suppressed_reason == SUPPRESSED_NO_SUBSCRIPTIONS


class TestTestNotificationButton:
    """§6.2's "test notification button"."""

    async def test_the_button_pushes_to_the_one_device_it_names(
        self, client: AsyncClient, sender: RecordingSender
    ) -> None:
        phone = await _register(client, "phone")
        await _register(client, "laptop")

        response = await client.post(f"/api/v1/notifications/subscriptions/{phone['id']}/test")

        assert response.status_code == 200
        assert response.json()["delivered"] == 1
        assert response.json()["devicesTried"] == 1
        assert len(sender.sent) == 1, "the laptop must not receive the phone's test"

    async def test_the_button_reports_a_refusal_rather_than_claiming_success(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        phone = await _register(client, "phone")
        subscription = (
            (
                await api_session.execute(
                    select(PushSubscription).where(PushSubscription.user_id == admin.id)
                )
            )
            .scalars()
            .one()
        )
        sender.outcomes[subscription.endpoint] = DeliveryOutcome.failed

        response = await client.post(f"/api/v1/notifications/subscriptions/{phone['id']}/test")

        assert response.json()["delivered"] == 0
        assert response.json()["status"] == "failed"

    async def test_the_button_ignores_quiet_hours(
        self, client: AsyncClient, sender: RecordingSender
    ) -> None:
        """Being told the test will arrive at nine tomorrow is not a test of anything."""
        phone = await _register(client, "phone")
        await client.put(
            "/api/v1/notifications/preferences",
            json={"quietHoursStart": "00:00:00", "quietHoursEnd": "23:59:00"},
        )

        response = await client.post(f"/api/v1/notifications/subscriptions/{phone['id']}/test")

        assert response.json()["delivered"] == 1


class TestPreferences:
    """§6.1 — per-category toggles, digest mode and quiet hours."""

    async def test_preferences_default_to_everything_on(self, client: AsyncClient) -> None:
        preferences = (await client.get("/api/v1/notifications/preferences")).json()

        assert preferences["dealsEnabled"] is True
        assert preferences["digestMode"] is False
        assert preferences["quietHoursStart"] is None
        assert preferences["quietHoursTimezone"] == "Europe/London"

    async def test_disabling_deals_stops_deal_pushes(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        """**§6.1's acceptance criterion, stated exactly.**

        The notification is still written — with ``suppressed`` and the reason — because
        "why did I not get that" deserves an answer. What must not happen is a push.
        """
        await _register(client, "phone")
        await client.put("/api/v1/notifications/preferences", json={"dealsEnabled": False})

        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Deep Red dropped to £15",
            body="Arrow Video",
        )
        summary = await deliver_pending(api_session, sender=sender)

        assert sender.sent == [], "no deal push may leave the building"
        assert summary.sent == 0
        row = (await api_session.execute(select(Notification))).scalars().one()
        assert row.status == "suppressed"
        assert row.suppressed_reason == SUPPRESSED_CATEGORY_DISABLED

    async def test_disabling_deals_leaves_the_other_categories_alone(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        """A per-category toggle that switched everything off would also pass the test above."""
        await _register(client, "phone")
        await client.put("/api/v1/notifications/preferences", json={"dealsEnabled": False})

        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.releases,
            title="Nosferatu on 4K",
            body="out Friday",
        )
        summary = await deliver_pending(api_session, sender=sender)

        assert summary.sent == 1
        assert len(sender.sent) == 1

    async def test_re_enabling_deals_lets_them_through_again(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        await _register(client, "phone")
        await client.put("/api/v1/notifications/preferences", json={"dealsEnabled": False})
        await client.put("/api/v1/notifications/preferences", json={"dealsEnabled": True})

        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Back on",
            body="£15",
        )
        summary = await deliver_pending(api_session, sender=sender)

        assert summary.sent == 1

    async def test_quiet_hours_suppress_evening_alerts(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        """**§6.1's second acceptance criterion**, through the endpoints.

        The alert is raised at 23:30 GMT, inside a 22:00–07:00 window, and must not be
        pushed then. Running the delivery pass at 07:30 the next morning releases it —
        "suppress" here means *not in the evening*, not *never*.
        """
        await _register(client, "phone")
        await client.put(
            "/api/v1/notifications/preferences",
            json={"quietHoursStart": "22:00:00", "quietHoursEnd": "07:00:00"},
        )
        evening = datetime(2026, 1, 15, 23, 30)

        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Late deal",
            body="£12",
            now=evening,
        )
        held = await deliver_pending(api_session, sender=sender, now=evening)

        assert sender.sent == [], "nothing may be pushed during quiet hours"
        assert held.considered == 0, "the row is not even due yet"
        row = (await api_session.execute(select(Notification))).scalars().one()
        assert row.status == "queued"
        assert row.deliver_after_utc == datetime(2026, 1, 16, 7, 0)
        assert row.deferred_reason == "quiet_hours"

        morning = await deliver_pending(
            api_session, sender=sender, now=datetime(2026, 1, 16, 7, 30)
        )

        assert morning.sent == 1
        assert len(sender.sent) == 1

    async def test_digest_mode_collapses_several_alerts_into_one_push(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        """The point of the setting: one push at nine, not three during the day."""
        await _register(client, "phone")
        await client.put("/api/v1/notifications/preferences", json={"digestMode": True})
        afternoon = datetime(2026, 1, 15, 14, 0)

        for index in range(3):
            await queue_notification(
                api_session,
                user_id=admin.id,
                category=NotificationCategory.deals,
                title=f"Deal {index}",
                body="cheap",
                now=afternoon,
            )
        summary = await deliver_pending(
            api_session, sender=sender, now=datetime(2026, 1, 16, 9, 30)
        )

        assert summary.sent == 3, "three notifications…"
        assert len(sender.sent) == 1, "…one push"
        assert b"3 updates" in sender.sent[0][1]

    async def test_an_invalid_timezone_is_refused(self, client: AsyncClient) -> None:
        """The delivery pass falls back on a bad zone, so a typo must be caught here."""
        response = await client.put(
            "/api/v1/notifications/preferences",
            json={"quietHoursTimezone": "Mars/Olympus_Mons"},
        )

        assert response.status_code == 422

    async def test_half_a_quiet_window_is_refused(self, client: AsyncClient) -> None:
        response = await client.put(
            "/api/v1/notifications/preferences", json={"quietHoursStart": "22:00:00"}
        )

        assert response.status_code == 422

    async def test_quiet_hours_can_be_cleared(self, client: AsyncClient) -> None:
        await client.put(
            "/api/v1/notifications/preferences",
            json={"quietHoursStart": "22:00:00", "quietHoursEnd": "07:00:00"},
        )

        cleared = await client.put(
            "/api/v1/notifications/preferences", json={"clearQuietHours": True}
        )

        assert cleared.json()["quietHoursStart"] is None
        assert cleared.json()["quietHoursEnd"] is None

    async def test_an_absent_field_is_left_alone(self, client: AsyncClient) -> None:
        await client.put("/api/v1/notifications/preferences", json={"dealsEnabled": False})

        updated = await client.put("/api/v1/notifications/preferences", json={"digestMode": True})

        assert updated.json()["dealsEnabled"] is False, "a partial update stayed partial"
        assert updated.json()["digestMode"] is True


class TestSaleSeasons:
    """§5.11 — seeded sale-season data and its pre-sale reminders."""

    async def test_seeding_creates_the_seasons_for_a_year(self, api_session: AsyncSession) -> None:
        created = await seed_year(api_session, 2026)

        titles = {entry.title for entry in created}
        assert "Black Friday" in titles
        assert "Boxing Day Sales" in titles
        assert "Amazon Prime Day (expected)" in titles, "an estimate must say so"
        assert all(entry.release_type == SALE_EVENT_TYPE for entry in created)

    async def test_seeding_twice_creates_nothing_the_second_time(
        self, api_session: AsyncSession
    ) -> None:
        first = await seed_year(api_session, 2026)
        second = await seed_year(api_session, 2026)

        assert len(first) > 0
        assert second == []

    async def test_black_friday_is_the_day_after_the_fourth_thursday(self) -> None:
        """Checked against the real calendar, not against the implementation."""
        assert black_friday(2026) == date(2026, 11, 27)
        assert black_friday(2027) == date(2027, 11, 26)
        assert black_friday(2028) == date(2028, 11, 24)

    async def test_a_date_two_weeks_before_a_sale_triggers_a_reminder(
        self,
        client: AsyncClient,
        api_session: AsyncSession,
        admin: Profile,
        sender: RecordingSender,
    ) -> None:
        """**§5.11's acceptance criterion, stated exactly.**

        *"Test date set 2 weeks before a seeded event triggers a reminder."*
        """
        await _register(client, "phone")
        await seed_year(api_session, 2026)
        two_weeks_before = black_friday(2026) - timedelta(days=SALE_LEAD_DAYS)

        summary = await run_reminders(
            api_session, as_of=two_weeks_before, now=datetime(2026, 11, 13, 10, 0)
        )
        delivery = await deliver_pending(
            api_session, sender=sender, now=datetime(2026, 11, 13, 10, 0)
        )

        assert summary.sale_events >= 1
        rows = (
            (
                await api_session.execute(
                    select(Notification).where(Notification.category == "sale_events")
                )
            )
            .scalars()
            .all()
        )
        assert any("Black Friday" in row.title for row in rows)
        assert delivery.sent >= 1
        assert sender.sent, "a reminder reached the device"

    async def test_a_sale_further_out_than_the_lead_window_is_not_announced_yet(
        self, api_session: AsyncSession, admin: Profile
    ) -> None:
        """Fifteen days is one day too early; the window is exactly the criterion's."""
        await seed_year(api_session, 2026)
        too_early = black_friday(2026) - timedelta(days=SALE_LEAD_DAYS + 1)

        await run_reminders(api_session, as_of=too_early, seed_seasons=False)

        rows = (
            (
                await api_session.execute(
                    select(Notification).where(Notification.category == "sale_events")
                )
            )
            .scalars()
            .all()
        )
        assert not any("Black Friday" in row.title for row in rows)

    async def test_running_the_pass_twice_sends_one_reminder(
        self, client: AsyncClient, api_session: AsyncSession, admin: Profile
    ) -> None:
        """A cron that fires twice, or a retried run, must not double every reminder."""
        await _register(client, "phone")
        await seed_year(api_session, 2026)
        as_of = black_friday(2026) - timedelta(days=SALE_LEAD_DAYS)

        first = await run_reminders(api_session, as_of=as_of, seed_seasons=False)
        second = await run_reminders(api_session, as_of=as_of, seed_seasons=False)

        assert first.sale_events >= 1
        assert second.sale_events == 0, "already notified"
        assert second.queued == 0

    async def test_a_disabled_sale_category_suppresses_the_reminder(
        self, client: AsyncClient, api_session: AsyncSession, sender: RecordingSender
    ) -> None:
        await _register(client, "phone")
        await client.put("/api/v1/notifications/preferences", json={"saleEventsEnabled": False})
        await seed_year(api_session, 2026)

        await run_reminders(
            api_session,
            as_of=black_friday(2026) - timedelta(days=SALE_LEAD_DAYS),
            seed_seasons=False,
        )
        await deliver_pending(api_session, sender=sender)

        assert sender.sent == []

    async def test_the_reminder_endpoint_refuses_a_future_date(self, client: AsyncClient) -> None:
        """Reminding somebody about a sale nobody has announced is not a feature."""
        tomorrow = (date.today() + timedelta(days=400)).isoformat()

        response = await client.post(f"/api/v1/notifications/run-reminders?asOf={tomorrow}")

        assert response.status_code == 422


class TestOverdueLoans:
    """§12.5's second clause — the debt Batch 15 left for this batch."""

    async def _overdue_loan(self, session: AsyncSession, *, due: date) -> Loan:
        movie = Movie(
            id=uuid.uuid4(),
            tmdb_id=None,
            title="Heat",
            original_title="Heat",
            media_type="film",
        )
        session.add(movie)
        await session.flush()
        item = CollectionItem(id=uuid.uuid4(), movie_id=movie.id)
        session.add(item)
        await session.flush()
        loan = Loan(
            id=uuid.uuid4(),
            collection_item_id=item.id,
            borrower_name="Dave",
            lent_date=due - timedelta(days=14),
            due_date=due,
        )
        session.add(loan)
        await session.flush()
        return loan

    async def test_an_overdue_loan_triggers_a_push(
        self, client: AsyncClient, api_session: AsyncSession, sender: RecordingSender
    ) -> None:
        """*"Overdue loan triggers a push"* — unmet since Batch 15, met here."""
        await _register(client, "phone")
        as_of = date(2026, 3, 1)
        await self._overdue_loan(api_session, due=as_of - timedelta(days=3))

        summary = await run_reminders(api_session, as_of=as_of, seed_seasons=False)
        await deliver_pending(api_session, sender=sender)

        assert summary.overdue_loans == 1
        row = (
            (
                await api_session.execute(
                    select(Notification).where(Notification.category == "loans")
                )
            )
            .scalars()
            .one()
        )
        assert row.title == "Heat is overdue"
        assert "Dave" in row.body
        assert sender.sent

    async def test_a_loan_that_is_not_yet_due_is_left_alone(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        await _register(client, "phone")
        as_of = date(2026, 3, 1)
        await self._overdue_loan(api_session, due=as_of + timedelta(days=3))

        summary = await run_reminders(api_session, as_of=as_of, seed_seasons=False)

        assert summary.overdue_loans == 0

    async def test_the_reminder_is_sent_once(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        """`loans.reminder_sent` is the column Batch 15 left; this is what writes it."""
        await _register(client, "phone")
        as_of = date(2026, 3, 1)
        loan = await self._overdue_loan(api_session, due=as_of - timedelta(days=3))

        await run_reminders(api_session, as_of=as_of, seed_seasons=False)
        second = await run_reminders(api_session, as_of=as_of, seed_seasons=False)

        await api_session.refresh(loan)
        assert loan.reminder_sent is True
        assert second.overdue_loans == 0


class TestOutbox:
    async def test_the_outbox_lists_the_callers_own_notifications(
        self, client: AsyncClient, api_session: AsyncSession, admin: Profile
    ) -> None:
        await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Mine",
            body="body",
        )

        listed = (await client.get("/api/v1/notifications")).json()

        assert listed["total"] == 1
        assert listed["items"][0]["title"] == "Mine"
        assert listed["queuedCount"] == 1

    async def test_the_outbox_does_not_show_another_persons_notifications(
        self, client: AsyncClient, api_session: AsyncSession
    ) -> None:
        other = await _profile(api_session, UserRole.viewer)
        await queue_notification(
            api_session,
            user_id=other.id,
            category=NotificationCategory.deals,
            title="Theirs",
            body="body",
        )

        listed = (await client.get("/api/v1/notifications")).json()

        assert listed["total"] == 0

    async def test_a_deduplicated_notification_is_not_written_twice(
        self, api_session: AsyncSession, admin: Profile
    ) -> None:
        first = await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Once",
            body="body",
            dedupe_key="deal:abc",
        )
        second = await queue_notification(
            api_session,
            user_id=admin.id,
            category=NotificationCategory.deals,
            title="Twice",
            body="body",
            dedupe_key="deal:abc",
        )

        assert first is not None
        assert second is None
        rows = (await api_session.execute(select(Notification))).scalars().all()
        assert len(rows) == 1


class TestVapidKeyEndpoint:
    async def test_it_reports_unconfigured_when_railway_has_no_key(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The state the TMDB outage was in — and the front end must be able to say so."""
        from src.config import settings

        monkeypatch.setattr(settings, "vapid_private_key", "")
        monkeypatch.setattr(settings, "vapid_public_key", "")

        response = await client.get("/api/v1/notifications/vapid-key")

        assert response.json() == {"publicKey": None, "configured": False}

    async def test_the_public_key_is_derived_from_the_private_one(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two variables can disagree; a derived one cannot."""
        from src.config import settings

        key = ec.generate_private_key(ec.SECP256R1())
        raw = key.private_numbers().private_value.to_bytes(32, "big")
        monkeypatch.setattr(settings, "vapid_private_key", webpush.b64url_encode(raw))
        monkeypatch.setattr(settings, "vapid_public_key", "a-stale-mismatched-value")

        response = await client.get("/api/v1/notifications/vapid-key")

        assert response.json()["configured"] is True
        assert response.json()["publicKey"] == webpush.b64url_encode(
            webpush.vapid_public_key_bytes(key)
        )


class TestReleaseReminders:
    async def test_an_imminent_release_is_announced(
        self, client: AsyncClient, api_session: AsyncSession, sender: RecordingSender
    ) -> None:
        await _register(client, "phone")
        as_of = date(2026, 4, 1)
        api_session.add(
            ReleaseCalendarEntry(
                id=uuid.uuid4(),
                title="Nosferatu",
                release_type="4k_uhd_release",
                release_date=as_of + timedelta(days=3),
                region="GB",
            )
        )
        await api_session.flush()

        summary = await run_reminders(api_session, as_of=as_of, seed_seasons=False)
        await deliver_pending(api_session, sender=sender)

        assert summary.releases == 1
        row = (
            (
                await api_session.execute(
                    select(Notification).where(Notification.category == "releases")
                )
            )
            .scalars()
            .one()
        )
        assert row.title == "Nosferatu — 4K UHD"
        assert sender.sent
