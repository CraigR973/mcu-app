"""Adding, editing, deleting and restoring discs — roadmap §3.1, §3.2, §3.5 and §3.11.

Everything here is **admin-only**. §3.1's acceptance criterion depends on the
distinction — *"Admin adds a movie; viewer immediately sees it"* — so the two roles are
not interchangeable on this surface the way `DECISIONS.md` #33 made them on the identify
flow.

Every write records an :class:`AdminAction` **in its own transaction**. A log entry that
commits separately from the change it describes is worse than no log at all: it can
claim something happened that was rolled back.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AdminUser, CurrentUser
from src.models.admin_action import COLLECTION_ITEMS_TABLE, AdminAction
from src.models.collection_item import FORMAT_RANK, SECTIONS, CollectionItem, owned_copy
from src.models.movie import Movie, MovieCredit
from src.models.profile import Profile
from src.routers.movies import Database, TmdbClient, location_label
from src.schemas.collection import (
    AuditEntryResponse,
    AuditPageResponse,
    CollectionItemCreateRequest,
    CollectionItemFieldsMixin,
    CollectionItemResponse,
    CollectionItemUpdateRequest,
    DuplicateCheckResponse,
    ExistingCopyResponse,
    ListingUpdateRequest,
    TmdbSearchResponse,
    TmdbSearchResultResponse,
    TrashItemResponse,
    TrashPageResponse,
)
from src.services.audit import diff_snapshots, item_snapshot, record_action
from src.services.barcode import check_digit_valid, normalise
from src.services.movie_metadata import credit_rows, movie_metadata_values, parse_year
from src.spreadsheet.parser import parse_location

router = APIRouter(prefix="/api/v1", tags=["collection"])

#: The one table this batch's trash and restore understand. §13.5 widens it to wanted
#: entries, watch logs and movies; accepting only what is implemented keeps a
#: mistyped table from returning a confidently empty page.
TRASH_TABLES = (COLLECTION_ITEMS_TABLE,)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive_utc(value: datetime) -> datetime:
    """A filter bound, normalised to the naive UTC the column holds.

    A client sends back what this app serialised, so it arrives *aware* — and an aware
    datetime cannot be compared with a naive column at all: Python raises ``TypeError``
    rather than answering wrongly. The same rule :data:`src.schemas.wire.UtcDatetimeIn`
    applies to request bodies, applied here to a query parameter.
    """
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _best_rank(formats: Iterable[str]) -> int | None:
    """Position of the best format in :data:`FORMAT_RANK`, lower being better.

    ``None`` when nothing in the list is a known format — which the create body's
    validator already rules out for new writes, but not for the 1,857 imported rows this
    is also asked about.
    """
    ranks = [FORMAT_RANK.index(code) for code in formats if code in FORMAT_RANK]
    return min(ranks) if ranks else None


def _resolve_location(
    payload: CollectionItemFieldsMixin,
) -> tuple[str | None, str | None, str | None]:
    """Work out ``(location, section, shelf)`` from whatever the form supplied.

    Two routes in, because the add form has two: the section and shelf pickers, which
    are built from ``GET /collection/facets`` and can only offer real places, and a free
    text box for anywhere they do not cover.

    An explicit ``section``/``shelf`` wins over anything parsed out of the text. When
    only text arrives it goes through :func:`parse_location` — the same function that
    read all 1,857 imported rows — so a hand-added disc is filed by exactly the rules an
    imported one was, including the fix for the bare-digit shelf bug (`STATUS.md`
    gotcha 17).
    """
    text = (payload.location or "").strip() or None
    section = (payload.section or "").strip() or None
    shelf = (payload.shelf or "").strip() or None

    if section is None and shelf is None and text is not None:
        section, shelf = parse_location(text)

    if text is None and section is not None:
        # Compose what the person would have typed, so `location` is never empty for a
        # disc that has a place. It is the column every other surface falls back to.
        text = f"{section} {shelf} shelf" if shelf else section

    if section is not None and section not in SECTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown section. Expected one of: {', '.join(SECTIONS)}",
        )
    return text, section, shelf


def _item_response(item: CollectionItem, movie_title: str) -> CollectionItemResponse:
    return CollectionItemResponse(
        id=item.id,
        movieId=item.movie_id,
        movieTitle=movie_title,
        formats=item.formats,
        location=item.location,
        section=item.section,
        shelf=item.shelf,
        locationLabel=location_label(item.section, item.shelf),
        subCategory=item.sub_category,
        edition=item.edition,
        notes=item.notes,
        condition=item.condition,
        conditionUpdatedAt=item.condition_updated_at_utc,
        hasPlaybackIssues=item.has_playback_issues,
        playbackNotes=item.playback_notes,
        purchasePrice=(str(item.purchase_price) if item.purchase_price is not None else None),
        purchaseSource=item.purchase_source,
        purchaseDate=item.purchase_date,
        listingStatus=item.listing_status,
        ebayListingUrl=item.ebay_listing_url,
        listingPrice=(str(item.listing_price) if item.listing_price is not None else None),
        updatedAt=item.updated_at,
        deletedAt=item.deleted_at,
    )


def _apply_fields(item: CollectionItem, payload: CollectionItemFieldsMixin) -> None:
    """Write the editable field set onto an item, condition timestamp included."""
    location, section, shelf = _resolve_location(payload)

    if payload.condition != item.condition:
        # §3.11 wants to know *when* a disc's condition last changed, which is only
        # meaningful if it moves when the condition does and not when a note is edited.
        item.condition_updated_at_utc = _utcnow() if payload.condition is not None else None

    item.formats = payload.formats
    item.location = location
    item.section = section
    item.shelf = shelf
    item.sub_category = payload.subCategory
    if "edition" in payload.model_fields_set:
        # Batch U2: only when the body carries it, so an older client cannot clear it.
        item.edition = payload.edition
    item.notes = payload.notes
    item.condition = payload.condition
    item.has_playback_issues = payload.hasPlaybackIssues
    item.playback_notes = payload.playbackNotes
    item.purchase_price = payload.purchasePrice
    item.purchase_source = payload.purchaseSource
    item.purchase_date = payload.purchaseDate


async def _live_copies(db: AsyncSession, movie_id: uuid.UUID) -> Sequence[CollectionItem]:
    return (
        (
            await db.execute(
                select(CollectionItem)
                .where(
                    CollectionItem.movie_id == movie_id,
                    owned_copy(),
                )
                .order_by(CollectionItem.created_at, CollectionItem.id)
            )
        )
        .scalars()
        .all()
    )


async def _duplicate_state(
    db: AsyncSession,
    movie: Movie,
    incoming_formats: Sequence[str],
) -> DuplicateCheckResponse:
    """Whether this film is already on a shelf, and whether this disc beats what is there.

    §3.5's acceptance is *"adding a 4K when Blu-ray exists triggers the upgrade prompt"*,
    so the ranking decision is made here rather than in the web app — the same
    :data:`FORMAT_RANK` order the ``best_format_owned`` trigger enforces, read once.
    """
    copies = await _live_copies(db, movie.id)
    owned = [code for copy in copies for code in copy.formats]
    owned_rank = _best_rank(owned)
    incoming_rank = _best_rank(incoming_formats)

    return DuplicateCheckResponse(
        movieId=movie.id,
        movieTitle=movie.title,
        isDuplicate=bool(copies),
        existingCopies=[
            ExistingCopyResponse(
                id=copy.id,
                formats=copy.formats,
                locationLabel=location_label(copy.section, copy.shelf),
                condition=copy.condition,
            )
            for copy in copies
        ],
        isUpgrade=(
            incoming_rank is not None and owned_rank is not None and incoming_rank < owned_rank
        ),
        bestFormatOwned=(FORMAT_RANK[owned_rank] if owned_rank is not None else None),
    )


async def _get_live_movie(db: AsyncSession, movie_id: uuid.UUID) -> Movie:
    movie = await db.get(Movie, movie_id)
    if movie is None or movie.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    return movie


async def _movie_from_tmdb(db: AsyncSession, tmdb: TmdbClient, tmdb_id: int) -> Movie:
    """Find or create the ``movies`` row for a TMDB id.

    An existing row wins: ``movies.tmdb_id`` is unique, so creating a second one for a
    film already in the catalogue would fail at the constraint — and if it did not, it
    would split one film's discs across two rows and hide half of them from every view.
    """
    existing = await db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
    if existing is not None:
        if existing.deleted_at is not None:
            existing.deleted_at = None
        return existing

    try:
        tmdb_movie = await tmdb.get_movie_full(tmdb_id)
    except httpx.HTTPError as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail="TMDB movie could not be loaded") from exc

    movie = Movie(id=uuid.uuid4(), **movie_metadata_values(tmdb_movie))
    db.add(movie)
    # The credits reference the movie row, and the search_vector trigger reads the
    # title and overview this flush writes.
    await db.flush()
    for row in credit_rows(movie.id, tmdb_movie):
        db.add(
            MovieCredit(
                id=uuid.UUID(row[0]),
                movie_id=movie.id,
                person_name=row[2],
                tmdb_person_id=row[3],
                role=row[4],
                character_name=row[5],
                display_order=row[6],
            )
        )
    return movie


# ---------------------------------------------------------------------------
# Add (§3.1) and duplicate detection (§3.5)
# ---------------------------------------------------------------------------


@router.get("/collection/duplicate-check", response_model=DuplicateCheckResponse)
async def check_duplicate(
    # Batch S4 (`DECISIONS.md` #155): a viewer, because the add form asks this and a
    # viewer can now use the add form. A duplicate check that 403s would let Mark fill in
    # a disc and only discover the clash when `POST /collection` refused it.
    _user: CurrentUser,
    db: Database,
    movie_id: Annotated[uuid.UUID | None, Query(alias="movieId")] = None,
    tmdb_id: Annotated[int | None, Query(alias="tmdbId", gt=0)] = None,
    formats: Annotated[list[str] | None, Query(alias="format")] = None,
) -> DuplicateCheckResponse:
    """The warning §3.1 wants *before* saving.

    A read, so the add form can ask as soon as a film is chosen rather than discovering
    the clash by being rejected. ``POST /collection`` enforces the same rule
    independently — this endpoint is the courtesy, not the guard.
    """
    if (movie_id is None) == (tmdb_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supply exactly one of movieId or tmdbId",
        )

    if movie_id is not None:
        movie = await db.get(Movie, movie_id)
    else:
        movie = await db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))

    if movie is None or movie.deleted_at is not None:
        # Not an error: "we have never heard of this film" is the answer the add form
        # needs most of the time, and it is not a duplicate.
        return DuplicateCheckResponse(isDuplicate=False)

    return await _duplicate_state(db, movie, formats or [])


@router.post(
    "/collection",
    response_model=CollectionItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_collection_item(
    payload: CollectionItemCreateRequest,
    # Batch S4. **The widening is here, not in the UI.** `DECISIONS.md` #155: `profiles`
    # holds exactly two rows and there is no public sign-up, so "only Mark and Craig" was
    # already true of every page; what Craig meant was that Mark should be able to add a
    # disc. Every write is attributed to whoever made it, so the audit log tells them
    # apart — which is the property that makes this safe rather than merely convenient.
    user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
) -> CollectionItemResponse:
    """Add one disc, refusing an unconfirmed duplicate with 409.

    The 409 carries the existing copies, so a client that skipped
    ``/collection/duplicate-check`` still gets everything §3.5's prompt needs and the
    confirmation cannot be bypassed by not asking.
    """
    barcode: str | None = None
    if payload.barcode is not None:
        barcode = normalise(payload.barcode)
        if not check_digit_valid(barcode):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="That does not look like a product barcode.",
            )

    if payload.movieId is not None:
        movie = await _get_live_movie(db, payload.movieId)
    elif payload.tmdbId is not None:
        movie = await _movie_from_tmdb(db, tmdb, payload.tmdbId)
    else:  # pragma: no cover - the model validator rejects this body first
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supply exactly one of movieId or tmdbId",
        )

    duplicate = await _duplicate_state(db, movie, payload.formats)
    if duplicate.isDuplicate and payload.confirmDuplicate is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=duplicate.model_dump(mode="json"),
        )

    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=[],
        added_by=user.id,
        added_at_utc=_utcnow(),
    )
    _apply_fields(item, payload)
    item.barcode = barcode
    db.add(item)
    await db.flush()

    changes = item_snapshot(item)
    if payload.confirmDuplicate is not None:
        # Keep *why* a second copy was allowed. "Upgrade" is the input phase 4.2's
        # sale tracking will want, and it is unrecoverable if only the click knew.
        changes["duplicate_reason"] = payload.confirmDuplicate
    record_action(
        db,
        user_id=user.id,
        action_type="create",
        target_table=COLLECTION_ITEMS_TABLE,
        target_id=item.id,
        changes=changes,
    )
    await db.commit()
    await db.refresh(item)
    return _item_response(item, movie.title)


# ---------------------------------------------------------------------------
# Edit, delete and restore (§3.2, §3.11)
# ---------------------------------------------------------------------------


async def _get_item(
    db: AsyncSession, item_id: uuid.UUID, *, deleted: bool = False
) -> tuple[CollectionItem, Movie]:
    item = await db.get(CollectionItem, item_id)
    if item is None or (item.deleted_at is not None) != deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection item not found"
        )
    movie = await db.get(Movie, item.movie_id)
    if movie is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    return item, movie


@router.put("/collection/{item_id}", response_model=CollectionItemResponse)
async def update_collection_item(
    item_id: uuid.UUID,
    payload: CollectionItemUpdateRequest,
    user: CurrentUser,
    db: Database,
) -> CollectionItemResponse:
    """Replace the editable fields of one disc, logging the diff.

    Either person may edit, which is also how a disc moves shelf (`DECISIONS.md` #264,
    superseding #37): Mark adds discs since #155, and a disc he could add but not correct
    was the gap. The audit row names whoever acted.

    Also §3.11's "mark as damaged" quick action: the client already holds the whole
    copy, so setting one field and re-submitting is the same request. A second endpoint
    for it would be a second place for the condition timestamp to be forgotten.
    """
    item, movie = await _get_item(db, item_id)

    if payload.baseUpdatedAt is not None and item.updated_at > payload.baseUpdatedAt:
        # Batch 8's acceptance criterion, enforced where it can actually be enforced.
        # An edit queued offline may be hours old; flushing it blind is last-write-wins,
        # and last-write-wins is exactly what "without overwriting a newer change"
        # forbids. The current row rides along in the 409 so the client can show what it
        # would have clobbered rather than only reporting that it failed
        # (`DECISIONS.md` #42).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "STALE_EDIT",
                "message": "This disc changed after your edit was made.",
                "current": _item_response(item, movie.title).model_dump(mode="json"),
            },
        )

    before = item_snapshot(item)
    _apply_fields(item, payload)
    await db.flush()
    after = item_snapshot(item)

    changes = diff_snapshots(before, after)
    if changes:
        # A submit that changed nothing writes no audit row. §13.6's acceptance counts
        # entries against changes made, and a no-op logged as an entry breaks that count.
        record_action(
            db,
            user_id=user.id,
            action_type="update",
            target_table=COLLECTION_ITEMS_TABLE,
            target_id=item.id,
            changes=changes,
        )
    await db.commit()
    await db.refresh(item)
    return _item_response(item, movie.title)


@router.put("/collection/{item_id}/listing", response_model=CollectionItemResponse)
async def update_listing_status(
    item_id: uuid.UUID,
    payload: ListingUpdateRequest,
    # Batch S4, and **this one is what makes the upgrade flow actually work for a viewer**
    # rather than merely start. The two eBay endpoints only price and link; "List for sale"
    # lands here, so leaving it `AdminUser` would have given Mark a prompt he could see, a
    # price he could fetch, and a button that 403s — the precise defect `DECISIONS.md` #155
    # says is worse than no change at all. Found by following the button rather than the
    # criterion, which named the two eBay routes and not this one.
    user: CurrentUser,
    db: Database,
) -> CollectionItemResponse:
    """Move a disc between §3.4's listing states — phases 4.2 and 4.4.

    **Sold is not deleted, and that distinction is the batch.** §4.4 asks that marking
    sold *"removes from active views, remains in audit/trash"*, and the obvious reading —
    soft-delete it, so the existing trash machinery hides it — is wrong for one reason
    that only shows up in ninety days: §6.30 **auto-purges the trash after 90 days**
    (`services/trash.py`). A sold disc routed through `deleted_at` would be permanently
    destroyed a quarter later, taking the record of what it fetched with it.

    So the row stays, undeleted, and ``owned_copy()`` is what removes it from the active
    views — see that predicate for the nineteen places the word "owned" was previously
    spelled out. "Remains in audit" is this function's audit row; "remains in trash" is
    unchanged, because a sold disc can still be deleted and restored like any other.

    **`listed_for_sale` stays visible.** A disc that is advertised is still a disc on the
    shelf until somebody buys it; hiding it at the moment of listing would make listing
    indistinguishable from losing.
    """
    item, movie = await _get_item(db, item_id)

    before = item_snapshot(item)
    previous = item.listing_status
    item.listing_status = payload.status

    if payload.listingPrice is not None:
        item.listing_price = Decimal(payload.listingPrice)
    if payload.ebayListingUrl is not None:
        item.ebay_listing_url = payload.ebayListingUrl

    if payload.status == "in_collection":
        # Un-listing clears the advert. Keeping a stale eBay URL on a disc that is back
        # on the shelf is how a link to a dead listing outlives the sale it described.
        item.ebay_listing_url = None
        item.listing_price = None

    await db.flush()
    changes = diff_snapshots(before, item_snapshot(item))
    if changes:
        record_action(
            db,
            user_id=user.id,
            # **`update`, not `listing_sold`.** §3.20's vocabulary is a closed set —
            # `create`/`update`/`delete`/`restore`/`bulk_import` — enforced by
            # `ck_admin_actions_action_type` in migration 008 *"because the log's value
            # is that it can be trusted later"*. A listing transition is an update to
            # the disc, and widening a settled vocabulary is a decision for its own
            # batch, not a side effect of this one. The transition is fully legible in
            # `changes` regardless: `listing_status` carries from/to.
            action_type="update",
            target_table=COLLECTION_ITEMS_TABLE,
            target_id=item.id,
            # The previous state is in `changes` as the diff's left-hand side, but naming
            # it here too means the audit row reads as a sentence on its own — which is
            # what §13.6's log is for.
            changes={**changes, "previous_listing_status": previous},
        )
    await db.commit()
    await db.refresh(item)
    return _item_response(item, movie.title)


@router.delete("/collection/{item_id}", response_model=CollectionItemResponse)
async def delete_collection_item(
    item_id: uuid.UUID,
    user: CurrentUser,
    db: Database,
) -> CollectionItemResponse:
    """Soft-delete one disc — §3.2's "move to trash".

    Either person may delete (#264); only the admin may list the Trash or restore from it,
    so a disc Mark removes by mistake is Craig's to bring back.

    Sets ``deleted_at`` directly rather than issuing a ``DELETE``. The
    ``collection_items_soft_delete`` trigger would turn a ``DELETE`` into this same
    update, but going through the trigger would leave the session holding an object it
    believes is gone, and the row it must be refreshed from is the one being returned.

    Returns the item rather than 204 so the client can show what it just removed and
    offer an undo without a second round trip.
    """
    item, movie = await _get_item(db, item_id)
    item.deleted_at = _utcnow()
    record_action(
        db,
        user_id=user.id,
        action_type="delete",
        target_table=COLLECTION_ITEMS_TABLE,
        target_id=item.id,
        changes=item_snapshot(item),
    )
    await db.commit()
    await db.refresh(item)
    return _item_response(item, movie.title)


@router.get("/trash", response_model=TrashPageResponse)
async def list_trash(
    _user: AdminUser,
    db: Database,
    table: Annotated[str, Query()] = COLLECTION_ITEMS_TABLE,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(alias="perPage", ge=1, le=200)] = 50,
) -> TrashPageResponse:
    """Soft-deleted discs, newest first.

    §13.5 widens this to every soft-deleting table; this batch serves the one it
    deletes from, and rejects the others rather than answering "nothing here" for a
    table it has not implemented.
    """
    if table not in TRASH_TABLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown table. Expected one of: {', '.join(TRASH_TABLES)}",
        )

    predicates = [CollectionItem.deleted_at.is_not(None)]
    total = int(
        (await db.execute(select(func.count(CollectionItem.id)).where(*predicates))).scalar_one()
    )
    rows = (
        await db.execute(
            select(CollectionItem, Movie)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(*predicates)
            .order_by(CollectionItem.deleted_at.desc(), CollectionItem.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    # Built in a loop rather than a comprehension so `deleted_at` narrows on its own.
    # The WHERE clause already guarantees it is non-null, and a `type: ignore` saying so
    # is the kind of claim `warn_unused_ignores` exists to keep honest — it read as
    # unused on CI's mypy and as necessary on this machine's.
    trash: list[TrashItemResponse] = []
    for item, movie in rows:
        deleted_at = item.deleted_at
        if deleted_at is None:  # pragma: no cover - excluded by the query
            continue
        trash.append(
            TrashItemResponse(
                id=item.id,
                targetTable=COLLECTION_ITEMS_TABLE,
                movieId=movie.id,
                movieTitle=movie.title,
                posterPath=movie.poster_path,
                formats=item.formats,
                locationLabel=location_label(item.section, item.shelf),
                deletedAt=deleted_at,
            )
        )

    return TrashPageResponse(
        items=trash,
        total=total,
        page=page,
        perPage=per_page,
        pages=math.ceil(total / per_page),
    )


@router.post("/trash/{table}/{item_id}/restore", response_model=CollectionItemResponse)
async def restore_collection_item(
    table: str,
    item_id: uuid.UUID,
    user: AdminUser,
    db: Database,
) -> CollectionItemResponse:
    """Put a soft-deleted disc back, with everything it had.

    §13.5's acceptance is *"restoring brings it back with full state"* — which holds
    here because a soft delete never cleared anything. Clearing ``deleted_at`` fires the
    derived-field trigger's UPDATE branch, so the film's ``best_format_owned`` comes
    back with it.
    """
    if table not in TRASH_TABLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown table. Expected one of: {', '.join(TRASH_TABLES)}",
        )

    item, movie = await _get_item(db, item_id, deleted=True)
    item.deleted_at = None
    record_action(
        db,
        user_id=user.id,
        action_type="restore",
        target_table=COLLECTION_ITEMS_TABLE,
        target_id=item.id,
        changes=item_snapshot(item),
    )
    await db.commit()
    await db.refresh(item)
    return _item_response(item, movie.title)


# ---------------------------------------------------------------------------
# Audit log (§3.20) — read surface
# ---------------------------------------------------------------------------


@router.get("/admin/audit", response_model=AuditPageResponse)
async def list_audit_entries(
    _user: AdminUser,
    db: Database,
    target_table: Annotated[str | None, Query(alias="targetTable", max_length=50)] = None,
    target_id: Annotated[str | None, Query(alias="targetId", max_length=200)] = None,
    movie_id: Annotated[uuid.UUID | None, Query(alias="movieId")] = None,
    action_type: Annotated[
        Literal["create", "update", "delete", "restore", "bulk_import"] | None,
        Query(alias="actionType"),
    ] = None,
    # Batch 15 (§13.6, "filterable log of all admin actions"). Who and when are the two
    # questions a person actually brings to an audit log — "what did I change last
    # Tuesday" — and neither was answerable before.
    actor_id: Annotated[uuid.UUID | None, Query(alias="actorId")] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(alias="perPage", ge=1, le=200)] = 50,
) -> AuditPageResponse:
    """The audit log, newest first.

    ``movieId`` is what §3.11's condition history on the detail page uses: it resolves
    to every one of that film's discs — **including soft-deleted ones**, because the
    history of a disc that was thrown away is exactly the history worth keeping.
    """
    predicates = []
    if target_table is not None:
        predicates.append(AdminAction.target_table == target_table)
    if target_id is not None:
        predicates.append(AdminAction.target_id == target_id)
    if action_type is not None:
        predicates.append(AdminAction.action_type == action_type)
    if actor_id is not None:
        predicates.append(AdminAction.user_id == actor_id)
    if since is not None:
        predicates.append(AdminAction.created_at >= _naive_utc(since))
    # Inclusive of the whole day when a date is given: `until=2026-09-09` means "up to the
    # end of the 9th", not "up to midnight at its start", which would silently exclude
    # everything the reader is looking for.
    if until is not None:
        predicates.append(AdminAction.created_at <= _naive_utc(until))

    if movie_id is not None:
        item_ids = (
            (await db.execute(select(CollectionItem.id).where(CollectionItem.movie_id == movie_id)))
            .scalars()
            .all()
        )
        predicates.append(AdminAction.target_table == COLLECTION_ITEMS_TABLE)
        # `in_([])` is a valid empty predicate — a film with no discs has no history,
        # which is the right answer rather than an unfiltered log.
        predicates.append(AdminAction.target_id.in_([str(value) for value in item_ids]))

    total = int(
        (await db.execute(select(func.count(AdminAction.id)).where(*predicates))).scalar_one()
    )
    rows = (
        await db.execute(
            select(AdminAction, Profile.display_name)
            # Outer join: an audit row whose actor was deleted still has to be readable,
            # which is the whole point of `user_id` being SET NULL (`DECISIONS.md` #5).
            .outerjoin(Profile, Profile.id == AdminAction.user_id)
            .where(*predicates)
            .order_by(AdminAction.created_at.desc(), AdminAction.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    return AuditPageResponse(
        items=[
            AuditEntryResponse(
                id=entry.id,
                actorId=entry.user_id,
                actorName=display_name,
                actionType=entry.action_type,
                targetTable=entry.target_table,
                targetId=entry.target_id,
                changes=entry.changes,
                createdAt=entry.created_at,
            )
            for entry, display_name in rows
        ],
        total=total,
        page=page,
        perPage=per_page,
        pages=math.ceil(total / per_page),
    )


# ---------------------------------------------------------------------------
# TMDB search for the add form (§3.1's "movie search")
# ---------------------------------------------------------------------------


@router.get("/tmdb/search", response_model=TmdbSearchResponse)
async def search_tmdb(
    # Batch S4. The add form's first step. Admin-only here would make `/collection/add`
    # reachable by a viewer and useless to one.
    _user: CurrentUser,
    db: Database,
    tmdb: TmdbClient,
    q: Annotated[str, Query(min_length=2, max_length=200)],
) -> TmdbSearchResponse:
    """Find a film that is not in the catalogue yet.

    ``GET /search`` answers "do we already own this?"; this answers "what is this disc I
    am holding?". Each result says whether the catalogue already has that TMDB id, so
    the add form can attach to the existing film rather than creating a second row for it.
    """
    query = q.strip()
    try:
        results = await tmdb.search_movie(query)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TMDB search is temporarily unavailable",
        ) from exc

    top = results.results[:10]
    known = {
        tmdb_id: movie_id
        for movie_id, tmdb_id in (
            await db.execute(
                select(Movie.id, Movie.tmdb_id).where(
                    Movie.tmdb_id.in_([result.id for result in top]),
                    Movie.deleted_at.is_(None),
                )
            )
        ).all()
    }

    return TmdbSearchResponse(
        query=query,
        results=[
            TmdbSearchResultResponse(
                tmdbId=result.id,
                title=result.title,
                year=parse_year(result.release_date),
                overview=result.overview,
                posterPath=result.poster_path,
                inCollection=result.id in known,
                movieId=known.get(result.id),
            )
            for result in top
        ],
    )
