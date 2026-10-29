"""AB3's approved trigger, receipt and delivery contracts through the real API."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, time

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_add_request import CollectionAddRequest
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.notification import Notification, PushSubscription
from src.models.profile import Profile, UserRole
from src.services import collection_additions as additions
from src.services.notifications import get_or_create_preferences
from src.services.push_transport import set_push_sender
from tests.test_collection_write_api import (
    admin as admin,
)
from tests.test_collection_write_api import (
    api_session as api_session,
)
from tests.test_collection_write_api import (
    client as client,
)
from tests.test_collection_write_api import (
    overrides as overrides,
)
from tests.test_collection_write_api import (
    viewer as viewer,
)
from tests.test_collection_write_api import (
    viewer_client as viewer_client,
)
from tests.test_notifications_api import RecordingSender, _subscription_keys


@pytest_asyncio.fixture(autouse=True)
async def bound_mark(viewer: Profile, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(additions, "MARK_PROFILE_ID", viewer.id)
    sender = RecordingSender()
    set_push_sender(sender)
    yield sender
    set_push_sender(None)


@pytest_asyncio.fixture
async def film(api_session: AsyncSession) -> Movie:
    movie = Movie(id=uuid.uuid4(), title="AB3 Heat", original_title="AB3 Heat", year=1995)
    api_session.add(movie)
    await api_session.flush()
    return movie


def body(film: Movie, **changes: object) -> dict[str, object]:
    return {
        "movieId": str(film.id),
        "formats": ["download"],
        "hasPlaybackIssues": False,
        "clientRequestId": str(uuid.uuid4()),
        **changes,
    }


async def events(db: AsyncSession, user: Profile) -> list[Notification]:
    return list(
        (
            await db.scalars(
                select(Notification).where(
                    Notification.user_id == user.id, Notification.category == "collection_additions"
                )
            )
        ).all()
    )


async def test_first_add_exact_wording_replay_and_extra_edition(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    admin: Profile,
    viewer: Profile,
    film: Movie,
    bound_mark: RecordingSender,
):
    p256dh, auth = _subscription_keys()
    api_session.add(
        PushSubscription(
            user_id=admin.id, endpoint="https://push.test/ab3", p256dh=p256dh, auth=auth
        )
    )
    await api_session.flush()
    payload = body(film)
    first = await viewer_client.post("/api/v1/collection", json=payload)
    assert first.status_code == 201, first.text
    again = await viewer_client.post("/api/v1/collection", json=payload)
    assert again.status_code == 201 and again.json() == first.json()
    assert len(await events(api_session, admin)) == 1
    assert await events(api_session, viewer) == []
    assert len(bound_mark.sent) == 1
    push = json.loads(bound_mark.sent[0][1])
    assert push["title"] == "Mark added a title"
    assert push["body"] == "AB3 Heat (1995) is now in the collection."
    assert push["url"] == f"/movies/{film.id}"
    extra = await viewer_client.post(
        "/api/v1/collection", json=body(film, formats=["blu_ray"], confirmDuplicate="another_copy")
    )
    assert extra.status_code == 201, extra.text
    assert len(await events(api_session, admin)) == 1
    assert len(bound_mark.sent) == 1


async def test_replay_after_removal_keeps_original_result_but_new_acquisition_notifies(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    admin: Profile,
    film: Movie,
):
    payload = body(film)
    first = await viewer_client.post("/api/v1/collection", json=payload)
    assert first.status_code == 201
    assert (
        await viewer_client.delete(f"/api/v1/collection/{first.json()['id']}")
    ).status_code == 200
    replay = await viewer_client.post("/api/v1/collection", json=payload)
    assert replay.json() == first.json()
    assert len(await events(api_session, admin)) == 1
    assert (
        await api_session.get(CollectionItem, uuid.UUID(first.json()["id"]))
    ).deleted_at is not None
    new = await viewer_client.post("/api/v1/collection", json=body(film))
    assert new.status_code == 201 and new.json()["id"] != first.json()["id"]
    assert len(await events(api_session, admin)) == 2


async def test_request_key_conflict_and_account_isolation(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    client: AsyncClient,
    admin: Profile,
    film: Movie,
):
    payload = body(film)
    assert (await viewer_client.post("/api/v1/collection", json=payload)).status_code == 201
    conflict = await viewer_client.post("/api/v1/collection", json={**payload, "notes": "changed"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "CLIENT_REQUEST_ID_REUSED"
    other = await client.post(
        "/api/v1/collection", json={**payload, "confirmDuplicate": "another_copy"}
    )
    assert other.status_code == 201
    assert len(await events(api_session, admin)) == 1
    assert (await api_session.scalar(select(func.count()).select_from(CollectionAddRequest))) == 2


@pytest.mark.parametrize(
    "status", ["sold", "donated", "binned", "in_collection", "listed_for_sale"]
)
async def test_owned_copy_predicate_controls_reacquisition(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    admin: Profile,
    film: Movie,
    status: str,
):
    api_session.add(
        CollectionItem(
            movie_id=film.id,
            formats=["dvd"],
            listing_status="in_collection" if status == "binned" else status,
            deleted_at=datetime(2026, 1, 1) if status == "binned" else None,
        )
    )
    await api_session.flush()
    result = await viewer_client.post(
        "/api/v1/collection", json=body(film, confirmDuplicate="another_copy")
    )
    assert result.status_code == 201, result.text
    assert len(await events(api_session, admin)) == (
        0 if status in {"in_collection", "listed_for_sale"} else 1
    )


@pytest.mark.parametrize("kind", ["film", "tv", "manual"])
async def test_series_manual_titles_and_unknown_year(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    admin: Profile,
    film: Movie,
    kind: str,
):
    film.media_type = kind if kind != "manual" else "film"
    film.year = None
    await api_session.flush()
    payload = (
        body(film)
        if kind != "manual"
        else {"title": "AB3 Not on TMDB", "formats": ["dvd"], "clientRequestId": str(uuid.uuid4())}
    )
    result = await viewer_client.post("/api/v1/collection", json=payload)
    assert result.status_code == 201, result.text
    [event] = await events(api_session, admin)
    assert (
        event.body
        == f"{'AB3 Not on TMDB' if kind == 'manual' else 'AB3 Heat'} is now in the collection."
    )


async def test_renamed_mark_still_sends_but_other_viewer_does_not(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    admin: Profile,
    viewer: Profile,
    film: Movie,
    monkeypatch: pytest.MonkeyPatch,
):
    viewer.display_name = "AB3 Renamed owner"
    viewer.role = UserRole.admin
    await api_session.flush()
    first = await viewer_client.post("/api/v1/collection", json=body(film))
    assert first.status_code == 201
    assert len(await events(api_session, admin)) == 1
    monkeypatch.setattr(additions, "MARK_PROFILE_ID", uuid.uuid4())
    assert (
        await viewer_client.delete(f"/api/v1/collection/{first.json()['id']}")
    ).status_code == 200
    viewer.role = UserRole.viewer
    await api_session.flush()
    assert (await viewer_client.post("/api/v1/collection", json=body(film))).status_code == 201
    assert len(await events(api_session, admin)) == 1


async def test_disabled_preference_and_inactive_deleted_recipients(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    admin: Profile,
    film: Movie,
):
    prefs = await get_or_create_preferences(api_session, admin.id)
    prefs.collection_additions_enabled = False
    for inactive, deleted in [(True, None), (False, datetime(2026, 1, 1))]:
        api_session.add(
            Profile(
                display_name=f"ab3-excluded-{uuid.uuid4()}",
                role=UserRole.viewer,
                is_active=not inactive,
                deleted_at=deleted,
            )
        )
    await api_session.flush()
    assert (await viewer_client.post("/api/v1/collection", json=body(film))).status_code == 201
    [event] = await events(api_session, admin)
    assert event.status == "suppressed" and event.suppressed_reason == "category_disabled"
    recipients = set((await api_session.scalars(select(Notification.user_id))).all())
    excluded = (
        await api_session.scalars(
            select(Profile.id).where(Profile.display_name.like("ab3-excluded-%"))
        )
    ).all()
    assert recipients.isdisjoint(excluded)


async def test_default_on_partial_update_and_quiet_digest_preserved(
    api_session: AsyncSession,
    client: AsyncClient,
    viewer_client: AsyncClient,
    admin: Profile,
    film: Movie,
):
    read = await client.get("/api/v1/notifications/preferences")
    assert read.json()["collectionAdditionsEnabled"] is True
    off = await client.put(
        "/api/v1/notifications/preferences", json={"collectionAdditionsEnabled": False}
    )
    assert off.json()["collectionAdditionsEnabled"] is False
    old_client = await client.put("/api/v1/notifications/preferences", json={"dealsEnabled": False})
    assert old_client.json()["collectionAdditionsEnabled"] is False
    prefs = await get_or_create_preferences(api_session, admin.id)
    prefs.collection_additions_enabled = True
    prefs.digest_mode = True
    prefs.quiet_hours_start = time(0, 0)
    prefs.quiet_hours_end = time(23, 59)
    await api_session.flush()
    assert (await viewer_client.post("/api/v1/collection", json=body(film))).status_code == 201
    [event] = await events(api_session, admin)
    assert event.status == "queued" and event.deliver_after_utc is not None
    assert event.deferred_reason in {"quiet_hours", "digest"}


async def test_refused_and_failed_adds_have_no_receipt_or_event(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    admin: Profile,
    film: Movie,
    monkeypatch: pytest.MonkeyPatch,
):
    api_session.add(CollectionItem(movie_id=film.id, formats=["dvd"]))
    await api_session.flush()
    assert (await viewer_client.post("/api/v1/collection", json=body(film))).status_code == 409
    assert await events(api_session, admin) == []
    assert (await api_session.scalar(select(func.count()).select_from(CollectionAddRequest))) == 0
    invalid = await viewer_client.post("/api/v1/collection", json=body(film, formats=[]))
    assert invalid.status_code == 422
    assert await events(api_session, admin) == []


async def test_delivery_exception_keeps_committed_add_and_receipt(
    api_session: AsyncSession,
    viewer_client: AsyncClient,
    admin: Profile,
    viewer: Profile,
    film: Movie,
    bound_mark: RecordingSender,
    monkeypatch: pytest.MonkeyPatch,
):
    p256dh, auth = _subscription_keys()
    api_session.add(
        PushSubscription(
            user_id=admin.id, endpoint="https://push.test/ab3-error", p256dh=p256dh, auth=auth
        )
    )
    await api_session.flush()

    async def broken(*args, **kwargs):
        raise RuntimeError("AB3 transport unavailable")

    monkeypatch.setattr(bound_mark, "send", broken)
    payload = body(film)
    result = await viewer_client.post("/api/v1/collection", json=payload)
    assert result.status_code == 201, result.text
    assert await api_session.get(CollectionItem, uuid.UUID(result.json()["id"])) is not None
    # The shared fixture reuses ORM actors; a real next request loads them afresh.
    await api_session.refresh(viewer)
    await api_session.refresh(admin)
    assert (await viewer_client.post("/api/v1/collection", json=payload)).json() == result.json()
    [event] = await events(api_session, admin)
    assert event.status == "queued"


async def test_updates_restore_and_craig_add_do_not_generate_events(
    api_session: AsyncSession,
    client: AsyncClient,
    viewer_client: AsyncClient,
    admin: Profile,
    film: Movie,
):
    created = await client.post("/api/v1/collection", json=body(film))
    assert created.status_code == 201
    item = created.json()["id"]
    edited = await viewer_client.put(
        f"/api/v1/collection/{item}",
        json={"formats": ["blu_ray"], "notes": "Changed shelf", "hasPlaybackIssues": False},
    )
    assert edited.status_code == 200
    assert (await viewer_client.delete(f"/api/v1/collection/{item}")).status_code == 200
    assert (await client.post(f"/api/v1/trash/collection_items/{item}/restore")).status_code == 200
    assert await events(api_session, admin) == []
