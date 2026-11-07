"""Independent committed connections: overlap, crash claims and delayed delivery (AC6)."""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.cinema import (
    CinemaCoverage,
    CinemaFilm,
    CinemaRefreshRun,
    CinemaScreening,
    CinemaVenue,
)
from src.models.cinema_digest import (
    CinemaDigestAppearance,
    CinemaDigestDay,
    CinemaDigestDelivery,
    CinemaDigestFilm,
    CinemaDigestListing,
)
from src.models.notification import Notification, PushSubscription
from src.models.profile import Profile, UserRole
from src.services.cinema_digest import delivery
from src.services.cinema_digest import evaluate as digest
from src.services.cinemas.venues import VENUES
from src.services.notifications import DeliveryOutcome, DeliveryResult, get_or_create_preferences
from tests.test_cinema_digest import finished, showing

NOW = datetime(2039, 6, 7, 8)


class Sender:
    def __init__(self, *, crash=False):
        self.payloads = []
        self.crash = crash

    async def send(self, subscription, body):
        self.payloads.append(json.loads(body))
        await asyncio.sleep(0.02)
        if self.crash:
            raise RuntimeError("transport accepted but answer lost")
        return DeliveryResult(DeliveryOutcome.delivered)


@asynccontextmanager
async def world(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    identity = 1_000_000_000 + uuid.uuid4().int % 1_000_000_000
    owner = uuid.uuid4()
    async with factory() as db, db.begin():
        enabled = dict(
            (await db.execute(select(CinemaVenue.id, CinemaVenue.collection_enabled))).all()
        )
        db.add(
            Profile(id=owner, display_name=f"ac6-{owner.hex}", role=UserRole.viewer, is_active=True)
        )
        await db.flush()
        run = await finished(db, NOW)
        film, _ = await showing(db, VENUES[0], identity=identity, now=NOW)
        db.add(
            PushSubscription(
                user_id=owner,
                endpoint=f"https://push.example/{owner}",
                p256dh="A" * 87,
                auth="A" * 22,
            )
        )
    try:
        yield factory, owner, run.id
    finally:
        async with factory() as db, db.begin():
            await db.execute(delete(Profile).where(Profile.id == owner))
            await db.execute(
                delete(Notification).where(Notification.dedupe_key.like(f"cinemas:%:{NOW.date()}"))
            )
            await db.execute(
                delete(CinemaDigestDay).where(
                    CinemaDigestDay.local_date.between(NOW.date(), (NOW + timedelta(days=2)).date())
                )
            )
            states = select(CinemaDigestFilm.id).where(CinemaDigestFilm.tmdb_id == identity)
            await db.execute(
                delete(CinemaDigestAppearance).where(CinemaDigestAppearance.film_id.in_(states))
            )
            await db.execute(
                delete(CinemaDigestListing).where(CinemaDigestListing.cinema_film_id == film.id)
            )
            await db.execute(delete(CinemaDigestFilm).where(CinemaDigestFilm.tmdb_id == identity))
            await db.execute(delete(CinemaScreening).where(CinemaScreening.film_id == film.id))
            await db.execute(delete(CinemaFilm).where(CinemaFilm.id == film.id))
            await db.execute(delete(CinemaCoverage).where(CinemaCoverage.run_id == run.id))
            await db.execute(delete(CinemaRefreshRun).where(CinemaRefreshRun.id == run.id))
            for venue, value in enabled.items():
                await db.execute(
                    update(CinemaVenue)
                    .where(CinemaVenue.id == venue)
                    .values(collection_enabled=value)
                )


async def evaluation(factory, run_id):
    async with factory() as db, db.begin():
        return await digest.evaluate(db, await db.get(CinemaRefreshRun, run_id), now=NOW)


async def test_two_evaluators_and_two_delivery_workers_make_one_push(db_engine):
    async with world(db_engine) as (factory, owner, run_id):
        barrier = asyncio.Barrier(2)

        async def evaluate_together():
            await barrier.wait()
            return await evaluation(factory, run_id)

        results = await asyncio.gather(evaluate_together(), evaluate_together())
        assert sorted(r["status"] for r in results) == ["already_evaluated", "evaluated"]
        sender = Sender()
        await asyncio.gather(
            delivery.deliver(db_engine, sender, now=NOW, user_id=owner),
            delivery.deliver(db_engine, sender, now=NOW, user_id=owner),
        )
        assert len(sender.payloads) == 1
        assert "Rerun" in sender.payloads[0]["body"]
        assert sender.payloads[0]["url"] == "/movie-night/cinema?view=new-this-week"
        async with factory() as db:
            [claim] = (
                await db.scalars(
                    select(CinemaDigestDelivery).where(CinemaDigestDelivery.user_id == owner)
                )
            ).all()
            assert claim.outcome == "sent" and claim.delivered_count == 1
        await delivery.deliver(db_engine, sender, now=NOW + timedelta(hours=1), user_id=owner)
        assert len(sender.payloads) == 1


async def test_lost_transport_answer_never_retries_even_next_day(db_engine):
    async with world(db_engine) as (factory, owner, run_id):
        await evaluation(factory, run_id)
        sender = Sender(crash=True)
        assert (await delivery.deliver(db_engine, sender, now=NOW, user_id=owner)).failed == 1
        await delivery.deliver(db_engine, sender, now=NOW + timedelta(days=1), user_id=owner)
        assert len(sender.payloads) == 1
        async with factory() as db:
            claim = await db.scalar(
                select(CinemaDigestDelivery).where(CinemaDigestDelivery.user_id == owner)
            )
            assert claim.outcome == "unknown"
            row = await db.scalar(
                select(Notification).where(
                    Notification.user_id == owner, Notification.category == "cinemas"
                )
            )
            assert row.status == "failed" and row.suppressed_reason == "cinema_delivery_unknown"


async def test_crash_between_claim_and_first_send_is_not_replayed(db_engine):
    async with world(db_engine) as (factory, owner, run_id):
        await evaluation(factory, run_id)
        assert await delivery._claim(db_engine, owner, NOW) is not None
        sender = Sender()
        await delivery.deliver(db_engine, sender, now=NOW + timedelta(hours=1), user_id=owner)
        assert sender.payloads == []
        async with factory() as db:
            row = await db.scalar(
                select(Notification).where(
                    Notification.user_id == owner, Notification.category == "cinemas"
                )
            )
            assert row.status == "failed" and row.suppressed_reason == "cinema_delivery_unknown"


async def test_digest_and_quiet_hours_hold_then_recheck_switch(db_engine):
    async with world(db_engine) as (factory, owner, run_id):
        async with factory() as db, db.begin():
            prefs = await get_or_create_preferences(db, owner)
            prefs.digest_mode = True
            prefs.digest_hour_local = 12
            prefs.quiet_hours_start, prefs.quiet_hours_end = time(11), time(14)
        await evaluation(factory, run_id)
        sender = Sender()
        await delivery.deliver(db_engine, sender, now=NOW, user_id=owner)
        assert sender.payloads == []
        async with factory() as db, db.begin():
            row = await db.scalar(
                select(Notification).where(
                    Notification.user_id == owner, Notification.category == "cinemas"
                )
            )
            # June London is UTC+1: noon digest is in quiet hours, ending 13:00 UTC.
            assert row.deliver_after_utc == NOW.replace(hour=13)
            prefs = await get_or_create_preferences(db, owner)
            prefs.cinemas_enabled = False
        await delivery.deliver(db_engine, sender, now=NOW.replace(hour=14), user_id=owner)
        assert sender.payloads == []
        async with factory() as db:
            row = await db.scalar(
                select(Notification).where(
                    Notification.user_id == owner, Notification.category == "cinemas"
                )
            )
            assert row.status == "suppressed" and row.suppressed_reason == "category_disabled"


async def test_evaluation_rollback_can_be_retried_without_lost_or_duplicate_episode(
    db_engine, monkeypatch
):
    async with world(db_engine) as (factory, owner, run_id):
        original = digest.queue_notification

        async def interrupt(*args, **kwargs):
            await original(*args, **kwargs)
            raise RuntimeError("crash after writing outbox, before day commit")

        monkeypatch.setattr(digest, "queue_notification", interrupt)

        with pytest.raises(RuntimeError, match="before day commit"):
            await evaluation(factory, run_id)
        async with factory() as db:
            assert (
                await db.scalar(
                    select(CinemaDigestDay).where(CinemaDigestDay.local_date == NOW.date())
                )
                is None
            )
            assert (
                await db.scalar(
                    select(Notification).where(
                        Notification.user_id == owner, Notification.category == "cinemas"
                    )
                )
                is None
            )
        monkeypatch.setattr(digest, "queue_notification", original)
        assert (await evaluation(factory, run_id))["status"] == "evaluated"
        sender = Sender()
        await delivery.deliver(db_engine, sender, now=NOW, user_id=owner)
        assert len(sender.payloads) == 1


async def test_delivery_rechecks_older_only_against_remaining_showings(db_engine):
    async with world(db_engine) as (factory, owner, run_id):
        await evaluation(factory, run_id)
        async with factory() as db, db.begin():
            prefs = await get_or_create_preferences(db, owner)
            prefs.cinemas_older_only = True
            await db.execute(
                update(CinemaScreening)
                .where(
                    CinemaScreening.film_id.in_(
                        select(CinemaFilm.id).where(
                            CinemaFilm.source_key.in_(select(CinemaDigestListing.source_key))
                        )
                    )
                )
                .values(release_category="newRelease")
            )
        sender = Sender()
        await delivery.deliver(db_engine, sender, now=NOW, user_id=owner)
        assert sender.payloads == []
        async with factory() as db:
            row = await db.scalar(
                select(Notification).where(
                    Notification.user_id == owner, Notification.category == "cinemas"
                )
            )
            assert row.status == "suppressed" and row.suppressed_reason == "cinema_filter_empty"


async def test_late_delivery_obeys_new_quiet_hours_then_sends_once(db_engine):
    async with world(db_engine) as (factory, owner, run_id):
        await evaluation(factory, run_id)
        async with factory() as db, db.begin():
            prefs = await get_or_create_preferences(db, owner)
            prefs.quiet_hours_start, prefs.quiet_hours_end = time(8), time(10)
        sender = Sender()
        await delivery.deliver(db_engine, sender, now=NOW, user_id=owner)
        assert sender.payloads == []
        await delivery.deliver(db_engine, sender, now=NOW + timedelta(hours=1), user_id=owner)
        assert len(sender.payloads) == 1


@pytest.mark.parametrize("reason,days", [("no_subscriptions", 0), ("cinema_digest_expired", 8)])
async def test_missing_devices_and_expired_showings_are_auditable_not_sent(db_engine, reason, days):
    async with world(db_engine) as (factory, owner, run_id):
        await evaluation(factory, run_id)
        async with factory() as db, db.begin():
            if reason == "no_subscriptions":
                await db.execute(delete(PushSubscription).where(PushSubscription.user_id == owner))
        sender = Sender()
        await delivery.deliver(db_engine, sender, now=NOW + timedelta(days=days), user_id=owner)
        assert sender.payloads == []
        async with factory() as db:
            row = await db.scalar(
                select(Notification).where(
                    Notification.user_id == owner, Notification.category == "cinemas"
                )
            )
            assert row.status == "suppressed" and row.suppressed_reason == reason


def test_push_payload_stays_valid_and_bounded_for_long_unicode_titles():
    items = [
        CinemaDigestAppearance(
            id=uuid.uuid4(), title="🎞" * 500, run_labels=["Preview", "First run"], is_return=False
        )
        for _ in range(12)
    ]
    result = delivery.payload(items, False, "test")
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 3000
    assert "Preview / First run" in result["body"] and "And 9 more" in result["body"]
    assert json.loads(json.dumps(result, ensure_ascii=False)) == result


async def test_delayed_rows_coalesce_and_dedupe_titles_on_the_actual_delivery_day(db_engine):
    from src.models.notification import NotificationCategory
    from src.services.notifications import queue_notification

    async with world(db_engine) as (factory, owner, run_id):
        await evaluation(factory, run_id)
        later = NOW + timedelta(days=1)
        async with factory() as db, db.begin():
            day = await db.scalar(
                select(CinemaDigestDay).where(CinemaDigestDay.local_date == NOW.date())
            )
            ids = day.report["recipients"][str(owner)]["appearanceIds"]
            row = await db.scalar(
                select(Notification).where(
                    Notification.user_id == owner, Notification.category == "cinemas"
                )
            )
            row.deliver_after_utc = later
            await db.execute(
                update(CinemaScreening)
                .where(CinemaScreening.film_id.in_(select(CinemaDigestListing.cinema_film_id)))
                .values(starts_utc=later + timedelta(hours=12), local_date=later.date())
            )
            second = await queue_notification(
                db,
                user_id=owner,
                category=NotificationCategory.cinemas,
                title="Later saved summary",
                body="Same film",
                now=later,
                dedupe_key=f"cinemas:{owner}:{later.date()}",
            )
            db.add(
                CinemaDigestDay(
                    local_date=later.date(),
                    evaluated_at_utc=later,
                    report={
                        "recipients": {
                            str(owner): {"notificationId": str(second.id), "appearanceIds": ids}
                        }
                    },
                )
            )
        sender = Sender()
        await delivery.deliver(db_engine, sender, now=later, user_id=owner)
        await delivery.deliver(db_engine, sender, now=later + timedelta(hours=1), user_id=owner)
        assert len(sender.payloads) == 1 and sender.payloads[0]["body"].count("Digest film") == 1
        async with factory() as db:
            rows = (
                await db.scalars(
                    select(Notification)
                    .where(Notification.user_id == owner, Notification.category == "cinemas")
                    .order_by(Notification.created_at_utc)
                )
            ).all()
            assert [(row.status, row.suppressed_reason) for row in rows] == [
                ("suppressed", "cinema_digest_coalesced"),
                ("sent", None),
            ]


async def test_one_refused_device_does_not_repeat_the_other_device(db_engine):
    async with world(db_engine) as (factory, owner, run_id):
        await evaluation(factory, run_id)
        async with factory() as db, db.begin():
            db.add(
                PushSubscription(
                    user_id=owner,
                    endpoint=f"https://push.example/gone-{owner}",
                    p256dh="A" * 87,
                    auth="A" * 22,
                )
            )

        class MixedSender(Sender):
            async def send(self, subscription, body):
                self.payloads.append(json.loads(body))
                return DeliveryResult(
                    DeliveryOutcome.gone
                    if "gone-" in subscription.endpoint
                    else DeliveryOutcome.delivered
                )

        sender = MixedSender()
        result = await delivery.deliver(db_engine, sender, now=NOW, user_id=owner)
        assert result.pushes_delivered == 1 and result.subscriptions_removed == 1
        await delivery.deliver(db_engine, sender, now=NOW + timedelta(hours=1), user_id=owner)
        assert len(sender.payloads) == 2


async def test_late_quiet_check_does_not_restart_an_already_due_digest_clock(db_engine):
    async with world(db_engine) as (factory, owner, run_id):
        async with factory() as db, db.begin():
            prefs = await get_or_create_preferences(db, owner)
            prefs.digest_mode, prefs.digest_hour_local = True, 10
            prefs.quiet_hours_start, prefs.quiet_hours_end = time(22), time(7)
        await evaluation(factory, run_id)
        tomorrow = NOW + timedelta(days=1)
        async with factory() as db, db.begin():
            await db.execute(
                update(CinemaScreening)
                .where(CinemaScreening.film_id.in_(select(CinemaDigestListing.cinema_film_id)))
                .values(starts_utc=tomorrow + timedelta(hours=12), local_date=tomorrow.date())
            )
        sender = Sender()
        await delivery.deliver(db_engine, sender, now=tomorrow.replace(hour=3), user_id=owner)
        assert sender.payloads == []
        async with factory() as db:
            row = await db.scalar(
                select(Notification).where(
                    Notification.user_id == owner, Notification.category == "cinemas"
                )
            )
            assert row.deliver_after_utc == tomorrow.replace(hour=6)
        await delivery.deliver(db_engine, sender, now=tomorrow, user_id=owner)
        assert len(sender.payloads) == 1
