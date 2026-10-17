"""Smart collections — roadmap §11.5, §3.23, §6.31.

A saved filter-bar state that is evaluated when it is read, never materialised. §3.23 is
explicit: *"Evaluated at query time — no materialisation. Results update instantly as the
collection changes."* That sentence is the feature. A cached result set would be wrong
the moment a disc was added, and wrong silently.

**Every collection is private to its owner.** §3.23 says "private by default" and there is
no sharing surface, so "by default" has no second case here: reads, writes and results are
all scoped to ``user.id``, and another person's id returns 404 rather than 403 — whether a
given id exists in someone else's sidebar is not something this response should confirm.

Delete is a hard delete, unlike everywhere else in this app. A smart collection owns no
data: it is a saved question, and deleting it destroys no disc, no watch and no history.
There is nothing for a trash to hold.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal, cast

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.models.smart_collection import SmartCollection
from src.routers.movies import Database, MovieFilters, movie_page
from src.schemas.collections import (
    SmartCollectionCreateRequest,
    SmartCollectionFilters,
    SmartCollectionListResponse,
    SmartCollectionResponse,
    SmartCollectionResultsResponse,
    SmartCollectionUpdateRequest,
)

router = APIRouter(prefix="/api/v1", tags=["smart-collections"])


def _stored_filters(collection: SmartCollection) -> SmartCollectionFilters:
    """Re-validate the stored blob on the way out.

    The column is written only through :class:`SmartCollectionFilters`, so this should
    never fail — but "should never" is how a JSONB column that feeds a query earns a
    check rather than a comment. A row edited by hand in the database, or written by a
    future migration that got the shape wrong, is refused here instead of being turned
    into predicates.
    """
    try:
        return SmartCollectionFilters.model_validate(collection.filters)
    except ValueError as exc:  # pragma: no cover - unreachable through the API
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This smart collection's saved filters are no longer valid",
        ) from exc


def _movie_filters(filters: SmartCollectionFilters, user_id: uuid.UUID) -> MovieFilters:
    """Map the saved vocabulary onto the one ``GET /movies`` evaluates.

    A field-by-field mapping rather than a loop over the dict: the two models are
    deliberately the same vocabulary under two naming conventions (camelCase on the
    wire, snake_case in the query), and spelling the pairs out is what makes a
    mismatch a type error here instead of a silently dropped filter at runtime.
    """
    return MovieFilters(
        genre_id=filters.genreId,
        keyword_id=filters.keywordId,
        year=filters.year,
        format_code=filters.format,
        section=filters.section,
        shelf=filters.shelf,
        decade_from=filters.decadeFrom,
        decade_to=filters.decadeTo,
        min_rating=filters.minRating,
        runtime_min=filters.runtimeMin,
        runtime_max=filters.runtimeMax,
        watched=filters.watched,
        user_id=user_id,
    )


def _response(collection: SmartCollection) -> SmartCollectionResponse:
    return SmartCollectionResponse(
        id=collection.id,
        name=collection.name,
        icon=cast(
            Literal[
                "sparkles",
                "star",
                "heart",
                "clapperboard",
                "disc",
                "eye",
                "flame",
                "bookmark",
                "layers",
            ],
            collection.icon,
        ),
        filters=_stored_filters(collection),
        sortBy=cast(Literal["title", "year", "rating"], collection.sort_by),
        sortOrder=cast(Literal["asc", "desc"], collection.sort_order),
        isPinned=collection.is_pinned,
        displayOrder=collection.display_order,
        createdAt=collection.created_at,
        updatedAt=collection.updated_at,
    )


async def _own_collection(
    db: AsyncSession, collection_id: uuid.UUID, user_id: uuid.UUID
) -> SmartCollection:
    collection = await db.get(SmartCollection, collection_id)
    if collection is None or collection.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Smart collection not found"
        )
    return collection


def _apply(
    collection: SmartCollection,
    payload: SmartCollectionCreateRequest | SmartCollectionUpdateRequest,
) -> None:
    collection.name = payload.name.strip()
    collection.icon = payload.icon
    collection.filters = payload.filters.stored()
    collection.sort_by = payload.sortBy
    collection.sort_order = payload.sortOrder
    collection.is_pinned = payload.isPinned
    collection.display_order = payload.displayOrder


@router.get("/smart-collections", response_model=SmartCollectionListResponse)
async def list_smart_collections(
    user: CurrentUser,
    db: Database,
    pinned: Annotated[bool | None, Query()] = None,
) -> SmartCollectionListResponse:
    """The caller's own collections, in sidebar order.

    ``pinned=true`` is what the dashboard asks for — §6.31's "can be pinned to the home
    dashboard" — rather than the dashboard fetching everything and filtering in the
    browser, which would ship the whole sidebar to render three tiles.
    """
    predicates = [SmartCollection.user_id == user.id]
    if pinned is not None:
        predicates.append(SmartCollection.is_pinned.is_(pinned))
    rows = (
        (
            await db.execute(
                select(SmartCollection)
                .where(*predicates)
                .order_by(
                    SmartCollection.display_order.asc(),
                    func.lower(SmartCollection.name).asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    items = [_response(collection) for collection in rows]
    return SmartCollectionListResponse(items=items, total=len(items))


@router.post(
    "/smart-collections",
    response_model=SmartCollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_smart_collection(
    payload: SmartCollectionCreateRequest, user: CurrentUser, db: Database
) -> SmartCollectionResponse:
    collection = SmartCollection(id=uuid.uuid4(), user_id=user.id, filters={})
    _apply(collection, payload)
    db.add(collection)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # `uq_smart_collections_user_name`. Two identically named entries in one
        # sidebar are indistinguishable to the person reading it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a smart collection with that name",
        ) from exc
    await db.refresh(collection)
    return _response(collection)


@router.put("/smart-collections/{collection_id}", response_model=SmartCollectionResponse)
async def update_smart_collection(
    collection_id: uuid.UUID,
    payload: SmartCollectionUpdateRequest,
    user: CurrentUser,
    db: Database,
) -> SmartCollectionResponse:
    collection = await _own_collection(db, collection_id, user.id)
    _apply(collection, payload)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a smart collection with that name",
        ) from exc
    await db.refresh(collection)
    return _response(collection)


@router.delete("/smart-collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_smart_collection(
    collection_id: uuid.UUID, user: CurrentUser, db: Database
) -> None:
    collection = await _own_collection(db, collection_id, user.id)
    await db.delete(collection)
    await db.commit()


@router.get(
    "/smart-collections/{collection_id}/results",
    response_model=SmartCollectionResultsResponse,
)
async def smart_collection_results(
    collection_id: uuid.UUID,
    user: CurrentUser,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(alias="perPage", ge=1, le=2000)] = 60,
) -> SmartCollectionResultsResponse:
    """Evaluate the saved filters now — §11.5's "lists correct films and updates live".

    Nothing is cached and nothing is stored. The page is produced by
    :func:`src.routers.movies.movie_page`, the same function behind ``GET /movies``, so
    "Unwatched 4Ks from the 2010s" saved here and typed into the filter bar are the same
    query by construction rather than by agreement.
    """
    collection = await _own_collection(db, collection_id, user.id)
    page_response = await movie_page(
        db,
        viewer_id=user.id,
        filters=_movie_filters(_stored_filters(collection), user.id),
        sort_by=cast(Literal["title", "year", "rating"], collection.sort_by),
        order=cast(Literal["asc", "desc"], collection.sort_order),
        page=page,
        per_page=per_page,
    )
    return SmartCollectionResultsResponse(
        collection=_response(collection),
        items=page_response.items,
        totalMovies=page_response.totalMovies,
        totalItems=page_response.totalItems,
        page=page_response.page,
        perPage=page_response.perPage,
        pages=page_response.pages,
    )
