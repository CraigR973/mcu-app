"""Photos of a disc — §3.10.

**Admin writes, both read**, matching Batch 7's write surface: a photo of a shelf is
catalogue data, and adding to the catalogue is an admin action. Serving is `CurrentUser`
because both people browse the collection.

**The bytes are served from their own endpoint, not embedded in JSON.** A five-photo
gallery as base64 in a list is roughly a megabyte re-sent on every render; a URL with a
strong `ETag` is cached by the browser, answered `304` on a revisit, and stored by Batch 8's
service worker. §3.10's *"no CSP change is needed"* follows from this: the images come from
the API origin, which `connect-src` already allows.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import func, select

from src.auth import AdminUser, CurrentUser
from src.clock import utcnow
from src.models.collection_item import CollectionItem
from src.models.item_photo import MAX_PHOTOS_PER_ITEM, ItemPhoto
from src.routers.movies import Database
from src.schemas.photos import PhotoListResponse, PhotoResponse
from src.services.photos import MAX_UPLOAD_BYTES, PhotoRejected, process

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["photos"])

#: Immutable: a photo's bytes never change, and a new upload is a new id. A year is the
#: conventional ceiling, and `immutable` is what stops a revalidation request on every view.
CACHE_CONTROL = "private, max-age=31536000, immutable"


def _response(photo: ItemPhoto) -> PhotoResponse:
    return PhotoResponse(
        id=photo.id,
        url=f"/api/v1/photos/{photo.id}",
        caption=photo.caption,
        width=photo.width,
        height=photo.height,
        byteSize=photo.byte_size,
        position=photo.position,
        createdAt=photo.created_at_utc,
    )


async def _item_or_404(db: Database, item_id: uuid.UUID) -> CollectionItem:
    item = await db.get(CollectionItem, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection item not found"
        )
    return item


@router.get("/collection/{item_id}/photos", response_model=PhotoListResponse)
async def list_photos(item_id: uuid.UUID, _user: CurrentUser, db: Database) -> PhotoListResponse:
    """§3.10's gallery, as metadata. The bytes come from `/photos/{id}`."""
    await _item_or_404(db, item_id)
    photos = list(
        (
            await db.execute(
                select(ItemPhoto)
                .where(ItemPhoto.collection_item_id == item_id)
                .order_by(ItemPhoto.position.asc(), ItemPhoto.created_at_utc.asc())
            )
        )
        .scalars()
        .all()
    )
    return PhotoListResponse(
        items=[_response(photo) for photo in photos],
        total=len(photos),
        remaining=max(MAX_PHOTOS_PER_ITEM - len(photos), 0),
    )


@router.post(
    "/collection/{item_id}/photos",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    item_id: uuid.UUID,
    user: AdminUser,
    db: Database,
    file: Annotated[UploadFile, File()],
    caption: Annotated[str | None, Form()] = None,
) -> PhotoResponse:
    """Upload one photo. Resized before it is stored — see `services/photos.py`.

    **Read with a ceiling, not with `await file.read()`.** An unbounded read pulls whatever
    was sent into memory before anything has had a chance to refuse it, which is a
    denial-of-service in one line.
    """
    await _item_or_404(db, item_id)

    count = (
        await db.execute(
            select(func.count())
            .select_from(ItemPhoto)
            .where(ItemPhoto.collection_item_id == item_id)
        )
    ).scalar_one()
    if count >= MAX_PHOTOS_PER_ITEM:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"That disc already has {MAX_PHOTOS_PER_ITEM} photos. Remove one first.",
        )

    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"That photo is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        processed = process(raw)
    except PhotoRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    existing = (
        await db.execute(
            select(ItemPhoto).where(
                ItemPhoto.collection_item_id == item_id,
                ItemPhoto.checksum == processed.checksum,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        # The same photo twice is a double-tapped upload. Returning the row that exists is
        # kinder than a 409 and leaves the gallery correct either way.
        return _response(existing)

    photo = ItemPhoto(
        id=uuid.uuid4(),
        collection_item_id=item_id,
        data=processed.data,
        content_type=processed.content_type,
        byte_size=processed.byte_size,
        width=processed.width,
        height=processed.height,
        checksum=processed.checksum,
        caption=(caption or None),
        position=count,
        uploaded_by=user.id,
        created_at_utc=utcnow(),
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    logger.info(
        "photo_stored",
        item_id=str(item_id),
        bytes=photo.byte_size,
        dimensions=f"{photo.width}x{photo.height}",
    )
    return _response(photo)


@router.get("/photos/{photo_id}")
async def serve_photo(
    photo_id: uuid.UUID, request: Request, _user: CurrentUser, db: Database
) -> Response:
    """The bytes, cacheable.

    A strong `ETag` and a conditional `304` mean a gallery re-render costs nothing, and
    Batch 8's service worker can store the response. `private` because a photo of somebody's
    shelves is not for a shared cache to hold.
    """
    photo = await db.get(ItemPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    etag = f'"{photo.checksum}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})

    return Response(
        content=photo.data,
        media_type=photo.content_type,
        headers={"ETag": etag, "Cache-Control": CACHE_CONTROL},
    )


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(photo_id: uuid.UUID, _user: AdminUser, db: Database) -> None:
    """§3.10's "deletion works".

    **A hard delete, unlike most of this app.** §13.5's Trash exists for things somebody
    might want back, and it restores *rows*; a soft-deleted photo would keep its bytes in
    the database for ever, which is the one cost this whole batch is arranged to avoid.
    """
    photo = await db.get(ItemPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    await db.delete(photo)
    await db.commit()
