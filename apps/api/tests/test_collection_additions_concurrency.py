"""Real commits and two connections prove AB3's race/rollback guarantees."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import Settings
from src.models.admin_action import AdminAction
from src.models.collection_add_request import CollectionAddRequest
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.notification import Notification, NotificationCategory, PushSubscription
from src.models.profile import Profile, UserRole
from src.routers import collection as route
from src.schemas.collection import CollectionItemCreateRequest
from src.services import collection_additions as additions
from src.services.notifications import (
    deliver_pending,
    get_or_create_preferences,
    queue_notification,
)
from tests.conftest import DATABASE_URL
from tests.test_collection_write_api import FakeTmdbClient
from tests.test_notifications_api import RecordingSender, _subscription_keys


@pytest_asyncio.fixture
async def committed(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[tuple]:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set — Postgres-backed tests skipped")
    engine = create_async_engine(Settings(database_url=DATABASE_URL).database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    mark, recipient, film = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with sessions() as db:
        db.add_all(
            [
                Profile(id=mark, display_name=f"ab3-mark-{mark}", role=UserRole.viewer),
                Profile(
                    id=recipient, display_name=f"ab3-recipient-{recipient}", role=UserRole.admin
                ),
                Movie(id=film, title=f"AB3 concurrent {film}", original_title="AB3 concurrent"),
            ]
        )
        await db.commit()
    monkeypatch.setattr(additions, "MARK_PROFILE_ID", mark)

    async def no_delivery(*args):
        pass

    monkeypatch.setattr(route, "deliver_additions", no_delivery)
    try:
        yield sessions, mark, recipient, film
    finally:
        async with sessions() as db:
            await db.execute(text("SET LOCAL app.permanent_delete = 'on'"))
            await db.execute(delete(Notification).where(Notification.url == f"/movies/{film}"))
            await db.execute(
                delete(CollectionAddRequest).where(
                    CollectionAddRequest.user_id.in_([mark, recipient])
                )
            )
            await db.execute(delete(AdminAction).where(AdminAction.user_id.in_([mark, recipient])))
            await db.execute(delete(CollectionItem).where(CollectionItem.movie_id == film))
            await db.execute(delete(Movie).where(Movie.id == film))
            await db.execute(delete(Profile).where(Profile.id.in_([mark, recipient])))
            await db.commit()
        await engine.dispose()


async def wait_blocked(sessions, pid: int) -> None:
    async def poll():
        while True:
            async with sessions() as observer:
                if await observer.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid}
                ):
                    return
            await asyncio.sleep(0.01)

    await asyncio.wait_for(poll(), 10)


@pytest.mark.parametrize("rollback", [False, True])
@pytest.mark.parametrize("same_key", [False, True])
async def test_concurrent_add_commit_or_rollback(
    committed: tuple,
    monkeypatch: pytest.MonkeyPatch,
    rollback: bool,
    same_key: bool,
):
    sessions, mark, recipient, film = committed
    entered, release = asyncio.Event(), asyncio.Event()
    original = route.queue_addition
    calls = 0

    async def paused(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = await original(*args, **kwargs)
        if calls == 1:
            entered.set()
            await release.wait()
            if rollback:
                raise RuntimeError("AB3 injected add rollback")
        return result

    monkeypatch.setattr(route, "queue_addition", paused)
    first_key, second_key = uuid.uuid4(), uuid.uuid4()
    if same_key:
        second_key = first_key

    def payload(key):
        return CollectionItemCreateRequest(
            movieId=film, formats=["download"], confirmDuplicate="another_copy", clientRequestId=key
        )

    async with sessions() as first, sessions() as second:
        actor1 = await first.get(Profile, mark)
        actor2 = await second.get(Profile, mark)
        pid = await second.scalar(text("SELECT pg_backend_pid()"))

        async def attempt(db, actor, key):
            try:
                return await route.add_collection_item(payload(key), actor, db, FakeTmdbClient())
            except RuntimeError:
                await db.rollback()
                return None

        a = asyncio.create_task(attempt(first, actor1, first_key))
        await asyncio.wait_for(entered.wait(), 10)
        b = asyncio.create_task(attempt(second, actor2, second_key))
        try:
            await wait_blocked(sessions, pid)
            assert not b.done()
        finally:
            release.set()
        first_result, second_result = await asyncio.gather(a, b)
        assert second_result is not None
        if same_key and not rollback:
            assert first_result.id == second_result.id
    async with sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == recipient, Notification.url == f"/movies/{film}")
            )
            == 1
        )
        copies = await db.scalar(
            select(func.count()).select_from(CollectionItem).where(CollectionItem.movie_id == film)
        )
        assert copies == (1 if same_key or rollback else 2)
        receipts = await db.scalar(
            select(func.count())
            .select_from(CollectionAddRequest)
            .where(CollectionAddRequest.user_id == mark)
        )
        assert receipts == copies


async def test_different_actors_serialise_the_first_owned_transition(
    committed: tuple, monkeypatch: pytest.MonkeyPatch
):
    sessions, mark, recipient, film = committed
    entered, release = asyncio.Event(), asyncio.Event()
    original = route._duplicate_state
    calls = 0

    async def paused(*args, **kwargs):
        nonlocal calls
        result = await original(*args, **kwargs)
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
        return result

    monkeypatch.setattr(route, "_duplicate_state", paused)
    async with sessions() as first, sessions() as second:
        craig, actor = await first.get(Profile, recipient), await second.get(Profile, mark)
        pid = await second.scalar(text("SELECT pg_backend_pid()"))
        payload = CollectionItemCreateRequest(
            movieId=film, formats=["dvd"], confirmDuplicate="another_copy"
        )
        a = asyncio.create_task(route.add_collection_item(payload, craig, first, FakeTmdbClient()))
        await asyncio.wait_for(entered.wait(), 10)
        b = asyncio.create_task(route.add_collection_item(payload, actor, second, FakeTmdbClient()))
        try:
            await wait_blocked(sessions, pid)
        finally:
            release.set()
        await asyncio.gather(a, b)
    async with sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.url == f"/movies/{film}")
            )
            == 0
        )


async def test_preference_initialisation_race_and_delivery_claims(committed: tuple):
    sessions, mark, recipient, film = committed
    async with sessions() as first, sessions() as second:
        await get_or_create_preferences(first, recipient)
        pid = await second.scalar(text("SELECT pg_backend_pid()"))
        task = asyncio.create_task(get_or_create_preferences(second, recipient))
        try:
            await wait_blocked(sessions, pid)
        finally:
            await first.commit()
        assert (await task).user_id == recipient
        await second.commit()
    p256dh, auth = _subscription_keys()
    async with sessions() as db:
        db.add(
            PushSubscription(
                user_id=recipient,
                endpoint=f"https://push.test/{recipient}",
                p256dh=p256dh,
                auth=auth,
            )
        )
        await queue_notification(
            db,
            user_id=recipient,
            category=NotificationCategory.collection_additions,
            title="Mark added a title",
            body="AB3 claim",
            url=f"/movies/{film}",
        )
        await db.commit()
    entered, release = asyncio.Event(), asyncio.Event()

    class PausedSender(RecordingSender):
        async def send(self, subscription, payload):
            entered.set()
            await release.wait()
            return await super().send(subscription, payload)

    sender = PausedSender()
    async with sessions() as first, sessions() as second:
        a = asyncio.create_task(deliver_pending(first, sender=sender, user_id=recipient))
        await asyncio.wait_for(entered.wait(), 10)
        try:
            other = await deliver_pending(second, sender=sender, user_id=recipient)
            assert other.considered == 0
        finally:
            release.set()
        await a
        await first.commit()
        await second.commit()
    assert len(sender.sent) == 1


async def test_transport_exception_cannot_undo_real_commit(
    committed: tuple, monkeypatch: pytest.MonkeyPatch
):
    sessions, mark, recipient, film = committed
    # Restore actual post-commit delivery; the fixture only disables it for race tests.
    monkeypatch.setattr(route, "deliver_additions", additions.deliver_additions)
    p256dh, auth = _subscription_keys()
    async with sessions() as db:
        db.add(
            PushSubscription(
                user_id=recipient,
                endpoint=f"https://push.test/{recipient}",
                p256dh=p256dh,
                auth=auth,
            )
        )
        await db.commit()

    class BrokenSender(RecordingSender):
        async def send(self, subscription, payload):
            raise RuntimeError("AB3 simulated transport exception")

    from src.services.push_transport import set_push_sender

    set_push_sender(BrokenSender())
    payload = CollectionItemCreateRequest(
        movieId=film, formats=["dvd"], clientRequestId=uuid.uuid4()
    )
    try:
        async with sessions() as db:
            actor = await db.get(Profile, mark)
            first = await route.add_collection_item(payload, actor, db, FakeTmdbClient())
        async with sessions() as db:
            actor = await db.get(Profile, mark)
            replay = await route.add_collection_item(payload, actor, db, FakeTmdbClient())
            # Compare the API contract: receipt parsing normalises naive UTC to aware UTC.
            assert replay.model_dump(mode="json") == first.model_dump(mode="json")
            assert await db.get(CollectionItem, first.id) is not None
            [event] = (
                await db.scalars(
                    select(Notification).where(
                        Notification.user_id == recipient, Notification.url == f"/movies/{film}"
                    )
                )
            ).all()
            assert event.status == "queued"
    finally:
        set_push_sender(None)
