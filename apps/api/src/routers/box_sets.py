"""Box sets — roadmap §11.3 (CRUD), §11.4 (display and completion), §6.32.

**Reads are open to both people, writes are admin-only**, matching §6.5's own table and
Batch 7's write surface. Cataloguing which discs came in which box is the same kind of
act as cataloguing the discs.

Every write records an :class:`AdminAction` in the *same* transaction as the change,
exactly as ``routers/collection.py`` does — an audit row that commits separately can
claim something happened that was rolled back.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AdminUser, CurrentUser
from src.models.box_set import BOX_SETS_TABLE, BoxSet, BoxSetItem
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.routers.movies import Database, location_label
from src.schemas.collections import (
    BoxSetCreateRequest,
    BoxSetDetailResponse,
    BoxSetItemAddRequest,
    BoxSetListResponse,
    BoxSetMemberResponse,
    BoxSetResponse,
    BoxSetUpdateRequest,
)
from src.services.audit import record_action

router = APIRouter(prefix="/api/v1", tags=["box-sets"])


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _live_set(db: AsyncSession, box_set_id: uuid.UUID) -> BoxSet:
    box_set = await db.get(BoxSet, box_set_id)
    if box_set is None or box_set.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Box set not found")
    return box_set


async def _owned_counts(db: AsyncSession, box_set_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
    """How many *live* discs each set holds, in one grouped query.

    Live only. A membership row survives a soft delete of its disc — the disc may come
    back out of the trash — but a set whose discs are in the bin is not complete, and
    counting them would make "4 of 4" mean "4 of 4, three of which you have thrown
    away".
    """
    if not box_set_ids:
        return {}
    rows = (
        await db.execute(
            select(BoxSetItem.box_set_id, func.count(BoxSetItem.collection_item_id))
            .join(CollectionItem, CollectionItem.id == BoxSetItem.collection_item_id)
            .where(
                BoxSetItem.box_set_id.in_(box_set_ids),
                owned_copy(),
            )
            .group_by(BoxSetItem.box_set_id)
        )
    ).all()
    return {box_set_id: int(count) for box_set_id, count in rows}


def _response(box_set: BoxSet, owned: int, series_name: str | None) -> BoxSetResponse:
    return BoxSetResponse(
        id=box_set.id,
        name=box_set.name,
        label=box_set.label,
        volumeNumber=box_set.volume_number,
        seriesId=box_set.series_id,
        seriesName=series_name,
        expectedCount=box_set.expected_count,
        posterUrl=box_set.poster_url,
        notes=box_set.notes,
        ownedCount=owned,
        # `None`, not `False`, when nobody recorded how big the box is. See
        # `BoxSetResponse.isComplete` — an unmeasured set is not an incomplete one.
        isComplete=(None if box_set.expected_count is None else owned >= box_set.expected_count),
        createdAt=box_set.created_at,
        updatedAt=box_set.updated_at,
    )


async def _series_names(db: AsyncSession, box_sets: Sequence[BoxSet]) -> dict[uuid.UUID, str]:
    parent_ids = {s.series_id for s in box_sets if s.series_id is not None}
    if not parent_ids:
        return {}
    rows = (await db.execute(select(BoxSet.id, BoxSet.name).where(BoxSet.id.in_(parent_ids)))).all()
    return {row_id: name for row_id, name in rows}


async def _responses(db: AsyncSession, box_sets: Sequence[BoxSet]) -> list[BoxSetResponse]:
    owned = await _owned_counts(db, [s.id for s in box_sets])
    names = await _series_names(db, box_sets)
    return [
        _response(
            box_set,
            owned.get(box_set.id, 0),
            names.get(box_set.series_id) if box_set.series_id else None,
        )
        for box_set in box_sets
    ]


async def _members(db: AsyncSession, box_set_id: uuid.UUID) -> list[BoxSetMemberResponse]:
    rows = (
        await db.execute(
            select(BoxSetItem, CollectionItem, Movie)
            .join(CollectionItem, CollectionItem.id == BoxSetItem.collection_item_id)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(BoxSetItem.box_set_id == box_set_id, owned_copy())
            .order_by(
                BoxSetItem.disc_number.asc().nulls_last(),
                func.lower(Movie.title).asc(),
            )
        )
    ).all()
    return [
        BoxSetMemberResponse(
            collectionItemId=item.id,
            movieId=movie.id,
            movieTitle=movie.title,
            posterPath=movie.poster_path,
            year=movie.year,
            formats=item.formats,
            locationLabel=location_label(item.section, item.shelf),
            discNumber=member.disc_number,
        )
        for member, item, movie in rows
    ]


async def _validate_series(
    db: AsyncSession, series_id: uuid.UUID | None, *, self_id: uuid.UUID | None
) -> None:
    """A volume may point at a series parent; a parent may not point at anything.

    §3.24's ``series_id`` is a self-FK with no depth limit, which invites a chain — or a
    cycle, which would hang any reader that walked it. One level is all the feature needs
    ("all Columbia Noir vols"), so it is enforced here rather than left to discipline.
    """
    if series_id is None:
        return
    if self_id is not None and series_id == self_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A box set cannot be its own series",
        )
    parent = await db.get(BoxSet, series_id)
    if parent is None or parent.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Series box set not found"
        )
    if parent.series_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Series nesting is one level deep — that box set is itself a volume",
        )
    if self_id is not None:
        # The row being edited may already be some other volume's parent. Letting it
        # become a volume would orphan them into a two-level chain by the back door.
        child = await db.scalar(
            select(BoxSet.id).where(BoxSet.series_id == self_id, BoxSet.deleted_at.is_(None))
        )
        if child is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This box set is a series with volumes of its own",
            )


async def _live_items(db: AsyncSession, item_ids: Sequence[uuid.UUID]) -> list[CollectionItem]:
    if not item_ids:
        return []
    rows = (
        (
            await db.execute(
                select(CollectionItem).where(CollectionItem.id.in_(item_ids), owned_copy())
            )
        )
        .scalars()
        .all()
    )
    missing = set(item_ids) - {item.id for item in rows}
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{len(missing)} collection item(s) not found",
        )
    return list(rows)


def _fields(box_set: BoxSet, payload: BoxSetUpdateRequest | BoxSetCreateRequest) -> None:
    box_set.name = payload.name.strip()
    box_set.label = (payload.label or "").strip() or None
    box_set.volume_number = payload.volumeNumber
    box_set.series_id = payload.seriesId
    box_set.expected_count = payload.expectedCount
    box_set.poster_url = (payload.posterUrl or "").strip() or None
    box_set.notes = payload.notes


def _snapshot(box_set: BoxSet) -> dict[str, object]:
    return {
        "name": box_set.name,
        "label": box_set.label,
        "volume_number": box_set.volume_number,
        "series_id": str(box_set.series_id) if box_set.series_id else None,
        "expected_count": box_set.expected_count,
        "poster_url": box_set.poster_url,
        "notes": box_set.notes,
    }


@router.get("/box-sets", response_model=BoxSetListResponse)
async def list_box_sets(_user: CurrentUser, db: Database) -> BoxSetListResponse:
    """Every live box set with its completion status — §11.4's acceptance criterion.

    Unpaginated on purpose. The whole point of the grid is that it shows *all* of them
    with status, and the ceiling is the number of physical boxes on the shelves — a
    couple of dozen, against 1,857 discs. A page control here would hide sets behind a
    "next" button for no benefit.
    """
    box_sets = (
        (
            await db.execute(
                select(BoxSet)
                .where(BoxSet.deleted_at.is_(None))
                .order_by(func.lower(BoxSet.name).asc(), BoxSet.volume_number.asc().nulls_last())
            )
        )
        .scalars()
        .all()
    )
    items = await _responses(db, list(box_sets))
    return BoxSetListResponse(items=items, total=len(items))


@router.get("/box-sets/{box_set_id}", response_model=BoxSetDetailResponse)
async def get_box_set(
    box_set_id: uuid.UUID, _user: CurrentUser, db: Database
) -> BoxSetDetailResponse:
    box_set = await _live_set(db, box_set_id)
    owned = await _owned_counts(db, [box_set.id])
    names = await _series_names(db, [box_set])
    volumes = (
        (
            await db.execute(
                select(BoxSet)
                .where(BoxSet.series_id == box_set.id, BoxSet.deleted_at.is_(None))
                .order_by(BoxSet.volume_number.asc().nulls_last(), func.lower(BoxSet.name).asc())
            )
        )
        .scalars()
        .all()
    )
    base = _response(
        box_set,
        owned.get(box_set.id, 0),
        names.get(box_set.series_id) if box_set.series_id else None,
    )
    return BoxSetDetailResponse(
        **base.model_dump(),
        items=await _members(db, box_set.id),
        volumes=await _responses(db, list(volumes)),
    )


@router.post("/box-sets", response_model=BoxSetDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_box_set(
    payload: BoxSetCreateRequest, user: AdminUser, db: Database
) -> BoxSetDetailResponse:
    """Create a box set, optionally with its discs — §11.3's acceptance in one call."""
    await _validate_series(db, payload.seriesId, self_id=None)
    items = await _live_items(db, payload.itemIds)

    box_set = BoxSet(id=uuid.uuid4())
    _fields(box_set, payload)
    db.add(box_set)
    await db.flush()

    for position, item in enumerate(
        sorted(items, key=lambda i: payload.itemIds.index(i.id)), start=1
    ):
        db.add(
            BoxSetItem(
                box_set_id=box_set.id,
                collection_item_id=item.id,
                # The order they were chosen in. A box's discs are numbered on the
                # spines, and the person adding them is looking at the box.
                disc_number=position,
            )
        )

    record_action(
        db,
        user_id=user.id,
        action_type="create",
        target_table=BOX_SETS_TABLE,
        target_id=box_set.id,
        changes={**_snapshot(box_set), "item_count": len(items)},
    )
    await db.commit()
    await db.refresh(box_set)
    return await get_box_set(box_set.id, user, db)


@router.put("/box-sets/{box_set_id}", response_model=BoxSetDetailResponse)
async def update_box_set(
    box_set_id: uuid.UUID, payload: BoxSetUpdateRequest, user: AdminUser, db: Database
) -> BoxSetDetailResponse:
    box_set = await _live_set(db, box_set_id)
    await _validate_series(db, payload.seriesId, self_id=box_set.id)

    before = _snapshot(box_set)
    _fields(box_set, payload)
    await db.flush()
    after = _snapshot(box_set)

    changes = {
        name: {"from": before[name], "to": after[name]}
        for name in before
        if before[name] != after[name]
    }
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table=BOX_SETS_TABLE,
        target_id=box_set.id,
        changes=changes,
    )
    await db.commit()
    return await get_box_set(box_set.id, user, db)


@router.delete("/box-sets/{box_set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_box_set(box_set_id: uuid.UUID, user: AdminUser, db: Database) -> None:
    """Soft-delete the grouping. The discs are untouched.

    Soft because the row groups real objects and the realistic mistake is deleting the
    wrong set. Nothing surfaces these in the trash yet — §13.5's Trash is Batch 15, and
    widening ``TRASH_TABLES`` is that batch's job.
    """
    box_set = await _live_set(db, box_set_id)
    box_set.deleted_at = _utcnow()
    record_action(
        db,
        user_id=user.id,
        action_type="delete",
        target_table=BOX_SETS_TABLE,
        target_id=box_set.id,
        changes=_snapshot(box_set),
    )
    await db.commit()


@router.post(
    "/box-sets/{box_set_id}/items",
    response_model=BoxSetDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_box_set_item(
    box_set_id: uuid.UUID, payload: BoxSetItemAddRequest, user: AdminUser, db: Database
) -> BoxSetDetailResponse:
    box_set = await _live_set(db, box_set_id)
    await _live_items(db, [payload.collectionItemId])

    existing = await db.get(BoxSetItem, (box_set.id, payload.collectionItemId))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That disc is already in this box set"
        )

    db.add(
        BoxSetItem(
            box_set_id=box_set.id,
            collection_item_id=payload.collectionItemId,
            disc_number=payload.discNumber,
        )
    )
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table=BOX_SETS_TABLE,
        target_id=box_set.id,
        changes={"added_item": str(payload.collectionItemId)},
    )
    await db.commit()
    return await get_box_set(box_set.id, user, db)


@router.delete(
    "/box-sets/{box_set_id}/items/{collection_item_id}",
    response_model=BoxSetDetailResponse,
)
async def remove_box_set_item(
    box_set_id: uuid.UUID, collection_item_id: uuid.UUID, user: AdminUser, db: Database
) -> BoxSetDetailResponse:
    box_set = await _live_set(db, box_set_id)
    member = await db.get(BoxSetItem, (box_set.id, collection_item_id))
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That disc is not in this box set"
        )
    await db.delete(member)
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table=BOX_SETS_TABLE,
        target_id=box_set.id,
        changes={"removed_item": str(collection_item_id)},
    )
    await db.commit()
    return await get_box_set(box_set.id, user, db)
