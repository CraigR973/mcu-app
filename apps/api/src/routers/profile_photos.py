"""Both people read photos; each person manages only their own (AA7)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from starlette.concurrency import run_in_threadpool

from src.auth import CurrentUser
from src.models.profile import Profile
from src.models.profile_photo import ProfilePhoto
from src.routers.movies import Database
from src.services.photos import MAX_UPLOAD_BYTES, PhotoRejected, process

router = APIRouter(prefix="/api/v1/profile-photos", tags=["profile photos"])


@router.put("/me", status_code=204)
async def upload_photo(
    user: CurrentUser, db: Database, file: Annotated[UploadFile, File()]
) -> None:
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That photo is larger than 12 MB.")
    try:
        photo = await run_in_threadpool(process, raw)
    except PhotoRejected as exc:
        raise HTTPException(422, str(exc)) from exc
    if photo.byte_size > 300 * 1024:
        raise HTTPException(422, "That photo could not be reduced to 300 KB.")
    statement = insert(ProfilePhoto).values(
        profile_id=user.id, data=photo.data, checksum=photo.checksum
    )
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[ProfilePhoto.profile_id],
            set_={"data": statement.excluded.data, "checksum": statement.excluded.checksum},
        )
    )
    await db.commit()


@router.delete("/me", status_code=204)
async def remove_photo(user: CurrentUser, db: Database) -> None:
    photo = await db.get(ProfilePhoto, user.id)
    if photo is not None:
        await db.delete(photo)
        await db.commit()


@router.get("/{profile_id}")
async def read_photo(profile_id: uuid.UUID, _user: CurrentUser, db: Database) -> Response:
    photo = (
        await db.execute(
            select(ProfilePhoto)
            .join(Profile, Profile.id == ProfilePhoto.profile_id)
            .where(
                Profile.id == profile_id, Profile.deleted_at.is_(None), Profile.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if photo is None:
        raise HTTPException(404, "No profile photo.")
    # Mutable URL: always re-read, including after deletion. No public or offline cache.
    return Response(
        photo.data,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store", "ETag": f'"{photo.checksum}"'},
    )
