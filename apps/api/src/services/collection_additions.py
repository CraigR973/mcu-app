"""AB3: serialised adds, durable request replay and Mark's transactional outbox."""

from __future__ import annotations

import hashlib
import json
import uuid

import structlog
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_add_request import CollectionAddRequest
from src.models.movie import Movie
from src.models.notification import NotificationCategory
from src.models.profile import Profile
from src.schemas.collection import CollectionItemCreateRequest, CollectionItemResponse
from src.services.notifications import deliver_pending, queue_notification
from src.services.push_transport import push_sender

# Owner-verified account, never inferred from role or mutable display name (#306).
MARK_PROFILE_ID = uuid.UUID("d900b8bc-a46c-4691-9c16-cde3b4d72cd5")
logger = structlog.get_logger(__name__)


async def hold_add_lock(db: AsyncSession, identity: str) -> None:
    """Transaction-scoped advisory lock, shared across API processes and connections."""
    key = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def request_hash(payload: CollectionItemCreateRequest) -> str:
    value = payload.model_dump(mode="json", exclude={"clientRequestId"})
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def replay_add(
    db: AsyncSession, user_id: uuid.UUID, payload: CollectionItemCreateRequest
) -> CollectionItemResponse | None:
    if payload.clientRequestId is None:
        return None
    await hold_add_lock(db, f"collection-request:{user_id}:{payload.clientRequestId}")
    receipt = await db.scalar(
        select(CollectionAddRequest).where(
            CollectionAddRequest.user_id == user_id,
            CollectionAddRequest.client_request_id == payload.clientRequestId,
        )
    )
    if receipt is None:
        return None
    if receipt.request_hash != request_hash(payload):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CLIENT_REQUEST_ID_REUSED",
                "message": (
                    "This add request ID was already used for different details. Start a new add."
                ),
            },
        )
    return CollectionItemResponse.model_validate(receipt.response_payload)


async def queue_addition(
    db: AsyncSession, *, actor: Profile, movie: Movie, item_id: uuid.UUID
) -> list[uuid.UUID]:
    if actor.id != MARK_PROFILE_ID or not actor.is_active or actor.deleted_at is not None:
        return []
    recipients = list(
        (
            await db.scalars(
                select(Profile.id)
                .where(
                    Profile.id != MARK_PROFILE_ID,
                    Profile.is_active.is_(True),
                    Profile.deleted_at.is_(None),
                )
                .order_by(Profile.id)
            )
        ).all()
    )
    title = f"{movie.title} ({movie.year})" if movie.year is not None else movie.title
    for recipient in recipients:
        await queue_notification(
            db,
            user_id=recipient,
            category=NotificationCategory.collection_additions,
            title="Mark added a title",
            body=f"{title} is now in the collection.",
            url=f"/movies/{movie.id}",
            dedupe_key=f"collection-addition:{item_id}:{recipient}",
        )
    return recipients


async def deliver_additions(db: AsyncSession, recipients: list[uuid.UUID]) -> None:
    """Transport runs after the successful add commit; failure leaves the durable queue."""
    if not recipients:
        return
    try:
        async with push_sender() as sender:
            for recipient in recipients:
                await deliver_pending(db, sender=sender, user_id=recipient)
        await db.commit()
    except Exception:  # noqa: BLE001 - delivery must never fail an already committed add
        logger.warning("collection_addition_push_failed", exc_info=True)
        await db.rollback()
