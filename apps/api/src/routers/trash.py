"""Trash is admin-only; both people manage physical loans and shelf confirmations.

AA11 separates requests, handover, physical return and shelving.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AdminUser, CurrentUser
from src.clock import latest_plausible_today, utc_today, utcnow
from src.models.box_set import BoxSet
from src.models.collection_item import CollectionItem, location_text
from src.models.loan import LOANS_TABLE, Loan, loan_state
from src.models.movie import Movie
from src.models.notification import NotificationCategory
from src.models.profile import Profile
from src.models.wanted import Retailer, WantedItem
from src.models.watch_log import WatchLog
from src.routers.movies import Database, location_label
from src.schemas.collections import (
    LoanCreateRequest,
    LoanListResponse,
    LoanResponse,
    LoanReturnRequest,
    LoanTransitionRequest,
    PurgePreviewResponse,
    TrashCountResponse,
    TrashListResponse,
    TrashRowResponse,
    TrashTable,
)
from src.services import trash as trash_service
from src.services.audit import record_action
from src.services.format_names import formats_phrase
from src.services.movie_night.sessions import deliver_now
from src.services.notifications import queue_notification

router = APIRouter(prefix="/api/v1", tags=["trash", "loans"])


def _require_table(table: str) -> TrashTable:
    if not trash_service.is_trash_table(table):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("Unknown table. Expected one of: " + ", ".join(trash_service.TRASH_TABLES)),
        )
    return cast(TrashTable, table)


async def _describe(
    db: AsyncSession, table: TrashTable, rows: Sequence[Any]
) -> list[TrashRowResponse]:
    """Render four different row types into one list shape.

    A trash page that changed layout per tab would be four components maintaining one
    idea. ``label`` is what the row *is*; ``sublabel`` is how to tell it from a sibling.
    """
    if table == "collection_items":
        items: list[CollectionItem] = list(rows)
        movies = await _movies_by_id(db, [item.movie_id for item in items])
        return [
            TrashRowResponse(
                id=item.id,
                table=table,
                label=_title(movies.get(item.movie_id)),
                sublabel=formats_phrase(item.formats or [])
                + f" · {location_label(item.section, item.shelf)}",
                posterPath=_poster(movies.get(item.movie_id)),
                movieId=item.movie_id,
                deletedAt=_deleted_at(item.deleted_at),
            )
            for item in items
        ]

    if table == "watch_log":
        entries: list[WatchLog] = list(rows)
        movies = await _movies_by_id(db, [entry.movie_id for entry in entries])
        return [
            TrashRowResponse(
                id=entry.id,
                table=table,
                label=_title(movies.get(entry.movie_id)),
                sublabel=f"watched {entry.watched_at.isoformat()}",
                posterPath=_poster(movies.get(entry.movie_id)),
                movieId=entry.movie_id,
                deletedAt=_deleted_at(entry.deleted_at),
            )
            for entry in entries
        ]

    if table == "movies":
        films: list[Movie] = list(rows)
        return [
            TrashRowResponse(
                id=movie.id,
                table=table,
                label=movie.title,
                sublabel=str(movie.year) if movie.year else None,
                posterPath=movie.poster_path,
                movieId=movie.id,
                deletedAt=_deleted_at(movie.deleted_at),
            )
            for movie in films
        ]

    if table == "box_sets":
        box_sets: list[BoxSet] = list(rows)
        return [
            TrashRowResponse(
                id=box_set.id,
                table=table,
                label=box_set.name,
                sublabel=box_set.label,
                posterPath=None,
                movieId=None,
                deletedAt=_deleted_at(box_set.deleted_at),
            )
            for box_set in box_sets
        ]

    if table == "wanted_list":
        # Batch 15 refused this table by name rather than answering an empty page for
        # something that did not exist. Batch 18 built it, so it renders here.
        wanted: list[WantedItem] = list(rows)
        wanted_films = await _movies_by_id(db, [item.movie_id for item in wanted])
        return [
            TrashRowResponse(
                id=item.id,
                table=table,
                label=_title(wanted_films.get(item.movie_id)),
                sublabel=item.preferred_format,
                posterPath=_poster(wanted_films.get(item.movie_id)),
                movieId=item.movie_id,
                deletedAt=_deleted_at(item.deleted_at),
            )
            for item in wanted
        ]

    # Retailers. The last branch, so it falls through rather than testing its own name —
    # ``_require_table`` has already refused anything outside ``TRASH_TABLES``, and every
    # other member is handled above.
    retailers: list[Retailer] = list(rows)
    return [
        TrashRowResponse(
            id=retailer.id,
            table=table,
            label=retailer.name,
            sublabel=retailer.base_url,
            posterPath=None,
            movieId=None,
            deletedAt=_deleted_at(retailer.deleted_at),
        )
        for retailer in retailers
    ]


def _title(movie: Movie | None) -> str:
    """A deleted disc whose film row is gone still needs a name in the list."""
    return movie.title if movie else "Unknown film"


def _poster(movie: Movie | None) -> str | None:
    return movie.poster_path if movie else None


def _deleted_at(value: datetime | None) -> datetime:
    """Narrow a ``deleted_at`` the WHERE clause already guaranteed.

    Batch 7's note on the same problem applies: a ``type: ignore`` asserting non-null
    reads as *unused* on CI's mypy and as *necessary* on this machine's, and
    ``warn_unused_ignores`` makes that disagreement a red gate (`STATUS.md` gotcha 21).
    Narrowing in a function is the version that is true on both.
    """
    if value is None:  # pragma: no cover - excluded by the query
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Row is not deleted",
        )
    return value


async def _movies_by_id(db: AsyncSession, movie_ids: list[uuid.UUID]) -> dict[uuid.UUID, Movie]:
    if not movie_ids:
        return {}
    rows = (await db.execute(select(Movie).where(Movie.id.in_(movie_ids)))).scalars().all()
    return {movie.id: movie for movie in rows}


@router.get("/trash/all", response_model=TrashListResponse)
async def list_trash_table(
    _user: AdminUser,
    db: Database,
    table: Annotated[str, Query()] = "collection_items",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(alias="perPage", ge=1, le=200)] = 50,
) -> TrashListResponse:
    """§13.5's "list soft-deleted items per table", with every table's count for the tabs.

    A separate path from Batch 7's `/trash`, which serves only `collection_items` and is
    what the existing trash page and the offline queue already call. Replacing that
    endpoint's shape would have broken both for a rename.
    """
    checked = _require_table(table)
    model = trash_service.model_for(checked)

    total = int(
        (
            await db.execute(select(func.count(model.id)).where(model.deleted_at.is_not(None)))
        ).scalar_one()
    )
    rows = (
        (
            await db.execute(
                trash_service.deleted_rows(checked)
                .order_by(model.deleted_at.desc(), model.id)
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        )
        .scalars()
        .all()
    )

    return TrashListResponse(
        items=await _describe(db, checked, list(rows)),
        total=total,
        page=page,
        perPage=per_page,
        pages=math.ceil(total / per_page),
        counts=[
            TrashCountResponse(table=cast(TrashTable, entry.table), count=entry.count)
            for entry in await trash_service.counts(db)
        ],
    )


@router.post("/trash/{table}/{row_id}/restore-row", status_code=status.HTTP_204_NO_CONTENT)
async def restore_row(table: str, row_id: uuid.UUID, user: AdminUser, db: Database) -> None:
    """§13.5's acceptance: "restoring brings it back with full state".

    Only ``deleted_at`` is cleared. Every other column is exactly as it was, because a
    soft delete never removed them — a restore is not a re-create, and treating it as one
    is how a restored row comes back subtly different from the one that was deleted.
    """
    checked = _require_table(table)
    restored = await trash_service.restore(db, checked, row_id)
    if restored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No deleted row with that id"
        )
    record_action(
        db,
        user_id=user.id,
        action_type="restore",
        target_table=checked,
        target_id=row_id,
        changes={"restored": True},
    )
    await db.commit()


@router.delete("/trash/{table}/{row_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
async def permanently_delete_row(
    table: str, row_id: uuid.UUID, user: AdminUser, db: Database
) -> None:
    """**Irreversible.** §13.5's permanent delete, and the first one in this app.

    Only a row already in the trash can be destroyed. That makes it a deliberate two
    steps — delete, then destroy — rather than one mis-tap away from losing a disc's
    history for good.

    The audit row is written **before** the delete and in the same transaction, because
    afterwards there is nothing left to describe. `admin_actions.target_id` is TEXT with
    no foreign key so the entry outlives its subject (`DECISIONS.md` #5).
    """
    checked = _require_table(table)
    model = trash_service.model_for(checked)
    row = await db.get(model, row_id)
    if row is None or row.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No deleted row with that id"
        )

    record_action(
        db,
        user_id=user.id,
        action_type="delete",
        target_table=checked,
        target_id=row_id,
        changes={"permanent": True},
    )
    try:
        destroyed = await trash_service.permanently_delete(db, checked, row_id)
    except trash_service.PermanentDeleteRefused as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not destroyed:  # pragma: no cover - the get above already checked
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No deleted row with that id"
        )
    await db.commit()


@router.post("/trash/purge", response_model=PurgePreviewResponse)
async def purge_trash(
    user: AdminUser,
    db: Database,
    table: Annotated[str, Query()] = "collection_items",
    dry_run: Annotated[bool, Query(alias="dryRun")] = True,
) -> PurgePreviewResponse:
    """§6.30's 90-day purge, **on demand and dry by default**.

    "Auto-purged" would be a cron, which is a hosting change this project keeps explicit
    (`DECISIONS.md` #60) — and a timer that permanently destroys rows is the last thing to
    add without a person deciding to. ``dryRun`` defaults to **true** so the destructive
    call is the one you have to ask for, not the one you get by forgetting a parameter.
    """
    checked = _require_table(table)
    candidates = await trash_service.purge_candidates(db, checked)

    deleted = 0
    if not dry_run:
        for row in candidates:
            record_action(
                db,
                user_id=user.id,
                action_type="delete",
                target_table=checked,
                target_id=row.id,
                changes={"permanent": True, "reason": "purge"},
            )
            if await trash_service.permanently_delete(db, checked, row.id):
                deleted += 1
        await db.commit()

    return PurgePreviewResponse(
        table=checked,
        olderThanDays=trash_service.PURGE_AFTER.days,
        count=len(candidates),
        dryRun=dry_run,
        deleted=deleted,
    )


# ---------------------------------------------------------------------------
# §12.5 — the lending tracker
# ---------------------------------------------------------------------------


def _loan_response(
    loan: Loan, item: CollectionItem, movie: Movie, *, current: bool = True
) -> LoanResponse:
    today = utc_today()
    open_loan = loan_state(loan) == "out"
    # Derived, never stored: a stored `is_overdue` needs a job to keep it true and is
    # wrong between runs. The only input is a date and today.
    overdue = open_loan and loan.due_date is not None and loan.due_date < today
    days = (loan.due_date - today).days if open_loan and loan.due_date else None
    return LoanResponse(
        id=loan.id,
        collectionItemId=loan.collection_item_id,
        movieId=movie.id,
        movieTitle=movie.title,
        posterPath=movie.poster_path,
        formats=item.formats or [],
        locationLabel=location_label(item.section, item.shelf),
        borrowerName=loan.borrower_name,
        borrowerProfileId=loan.borrower_profile_id,
        lentDate=loan.lent_date,
        state=cast(Any, loan_state(loan)),
        neededBy=loan.needed_by_date,
        returnedByProfileId=loan.returned_by_profile_id,
        shelvedAt=loan.shelved_at_utc,
        isCurrent=current,
        section=item.section,
        shelf=item.shelf,
        dueDate=loan.due_date,
        returnedDate=loan.returned_date,
        isOverdue=overdue,
        daysUntilDue=days,
        notes=loan.notes,
    )


async def _loan_rows(
    db: AsyncSession, *, open_only: bool
) -> list[tuple[Loan, CollectionItem, Movie]]:
    predicates = []
    if open_only:
        predicates.append(Loan.returned_date.is_(None))
    rows = (
        await db.execute(
            select(Loan, CollectionItem, Movie)
            .join(CollectionItem, CollectionItem.id == Loan.collection_item_id)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(*predicates)
            .order_by(
                Loan.returned_date.is_(None).desc(),
                Loan.due_date.asc().nulls_last(),
                Loan.updated_at.desc(),
                Loan.created_at.desc(),
                Loan.id.desc(),
            )
        )
    ).all()
    return [(loan, item, movie) for loan, item, movie in rows]


@router.get("/loans", response_model=LoanListResponse)
async def list_loans(
    _user: CurrentUser,
    db: Database,
    open_only: Annotated[bool, Query(alias="openOnly")] = False,
) -> LoanListResponse:
    """§12.5's loans page — "active and past loans", per §6.5.

    Open loans first, soonest due first. Readable by both people: knowing where a disc
    went and recording its handover are shared actions.
    """
    rows = await _loan_rows(db, open_only=open_only)
    # The first row per copy is current. Returned history never creates duplicate tasks.
    current_ids: dict[uuid.UUID, uuid.UUID] = {}
    for loan, _, _ in sorted(
        rows,
        key=lambda row: (
            row[0].returned_date is None,
            row[0].updated_at,
            row[0].created_at,
            row[0].id,
        ),
        reverse=True,
    ):
        current_ids.setdefault(loan.collection_item_id, loan.id)
    items = [
        _loan_response(loan, item, movie, current=current_ids[item.id] == loan.id)
        for loan, item, movie in rows
    ]
    return LoanListResponse(
        items=items,
        total=len(items),
        openCount=sum(1 for item in items if item.returnedDate is None),
        overdueCount=sum(1 for item in items if item.isOverdue),
    )


async def _borrower(db: AsyncSession, payload: LoanCreateRequest) -> tuple[str, uuid.UUID | None]:
    """The borrower's name and, for one of the app's people, their profile — Batch W3.

    A profile's name is read from the profile rather than trusted from the client, so the two
    cannot disagree. Only an active, undeleted profile can borrow.
    """
    if payload.borrowerProfileId is None:
        assert payload.borrowerName is not None  # `LoanCreateRequest` allows exactly one
        return payload.borrowerName.strip(), None
    # Filtered in SQL, not read off the object: `is_active` is a server default, so on a
    # profile created in this session it is not loaded, and an async session cannot load it.
    person = (
        await db.execute(
            select(Profile).where(
                Profile.id == payload.borrowerProfileId,
                Profile.deleted_at.is_(None),
                Profile.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower not found")
    return person.display_name, person.id


@router.post("/loans", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
async def lend_disc(payload: LoanCreateRequest, user: CurrentUser, db: Database) -> LoanResponse:
    """Record taking a copy, or request it without inventing a handover date."""
    item = (
        await db.execute(
            select(CollectionItem)
            .where(CollectionItem.id == payload.collectionItemId)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if item is None or item.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection item not found"
        )
    if item.listing_status in ("sold", "donated") or item.section == "Digital":
        raise HTTPException(status_code=422, detail="Only an owned physical copy can be lent")
    if await db.scalar(
        select(Loan.id)
        .where(Loan.collection_item_id == item.id, Loan.returned_date.is_(None))
        .limit(1)
    ):
        raise HTTPException(
            status_code=409, detail="That disc already has a request or an open loan"
        )
    movie = await db.get(Movie, item.movie_id)
    if movie is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    asked = payload.state == "asked_for"
    lent = None if asked else payload.lentDate or utc_today()
    if asked and (
        payload.borrowerProfileId != user.id
        or payload.neededBy is None
        or payload.lentDate is not None
    ):
        raise HTTPException(
            status_code=422, detail="Ask for yourself with a needed-by date and no lent date"
        )
    if payload.neededBy is not None and payload.neededBy < utc_today():
        raise HTTPException(status_code=422, detail="neededBy cannot be in the past")
    if lent is not None and lent > latest_plausible_today():
        raise HTTPException(status_code=422, detail="lentDate cannot be in the future")
    if payload.dueDate is not None and payload.dueDate < (lent or payload.neededBy or utc_today()):
        raise HTTPException(status_code=422, detail="dueDate cannot be before lentDate or neededBy")
    if not asked and payload.neededBy is not None:
        raise HTTPException(status_code=422, detail="neededBy belongs to a request")

    borrower_name, borrower_profile_id = await _borrower(db, payload)
    loan = Loan(
        id=uuid.uuid4(),
        collection_item_id=item.id,
        borrower_name=borrower_name,
        borrower_profile_id=borrower_profile_id,
        lent_date=lent,
        state=payload.state,
        needed_by_date=payload.neededBy,
        due_date=payload.dueDate,
        notes=payload.notes,
    )
    db.add(loan)
    record_action(
        db,
        user_id=user.id,
        action_type="create",
        target_table=LOANS_TABLE,
        target_id=loan.id,
        changes={
            "borrower": loan.borrower_name,
            "borrower_profile": str(borrower_profile_id) if borrower_profile_id else None,
            "item": str(item.id),
        },
    )
    recipients: list[uuid.UUID] = []
    if asked:
        recipients = list(
            (
                await db.execute(
                    select(Profile.id).where(
                        Profile.id != user.id,
                        Profile.deleted_at.is_(None),
                        Profile.is_active.is_(True),
                    )
                )
            ).scalars()
        )
        for recipient in recipients:
            await queue_notification(
                db,
                user_id=recipient,
                category=NotificationCategory.loans,
                title=f"{borrower_name} asked for {movie.title}",
                body=(
                    f"Needed by {payload.neededBy:%-d %B}. "
                    "Record Taken when the copy is handed over."
                ),
                url="/loans",
                dedupe_key=f"loan-request:{loan.id}:{recipient}",
                now=utcnow(),
            )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # `uq_loans_one_open_per_item`. Two open loans on one disc give two people a
        # claim on one object and no way to tell which is real.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That disc is already lent out and has not been returned",
        ) from exc
    await db.refresh(loan)
    if recipients:
        await deliver_now(db, recipients)
    return _loan_response(loan, item, movie)


@router.put("/loans/{loan_id}/return", response_model=LoanResponse)
async def return_disc(
    loan_id: uuid.UUID,
    payload: LoanReturnRequest,
    user: CurrentUser,
    db: Database,
) -> LoanResponse:
    """Mark a disc as returned. §6.5's own verb for this. Either person, since Batch W3."""
    loan, item, movie = await _locked_loan(db, loan_id)
    if loan_state(loan) != "out":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That loan is already closed"
        )

    returned: date = payload.returnedDate or utc_today()
    assert loan.lent_date is not None
    if returned < loan.lent_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="returnedDate cannot be before lentDate",
        )
    if returned > latest_plausible_today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="returnedDate cannot be in the future",
        )

    loan.returned_date = returned
    loan.state = "back"
    loan.returned_by_profile_id = user.id
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table=LOANS_TABLE,
        target_id=loan.id,
        changes={"returned_date": {"from": None, "to": returned.isoformat()}},
    )
    await db.commit()
    await db.refresh(loan)

    return _loan_response(loan, item, movie)


async def _locked_loan(db: AsyncSession, loan_id: uuid.UUID) -> tuple[Loan, CollectionItem, Movie]:
    # Every operation locks the copy first, then its loan, including create/reborrow.
    copy_id = await db.scalar(select(Loan.collection_item_id).where(Loan.id == loan_id))
    if copy_id is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    item = (
        await db.execute(
            select(CollectionItem).where(CollectionItem.id == copy_id).with_for_update()
        )
    ).scalar_one()
    loan = (
        await db.execute(
            select(Loan)
            .where(Loan.id == loan_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    movie = await db.get(Movie, item.movie_id)
    assert movie is not None
    current_id = await db.scalar(
        select(Loan.id)
        .where(Loan.collection_item_id == copy_id)
        .order_by(
            Loan.returned_date.is_(None).desc(),
            Loan.updated_at.desc(),
            Loan.created_at.desc(),
            Loan.id.desc(),
        )
        .limit(1)
    )
    if current_id != loan.id:
        raise HTTPException(
            status_code=409, detail="This copy has a newer loan; reload its current state"
        )
    return loan, item, movie


@router.patch("/loans/{loan_id}", response_model=LoanResponse)
async def transition_loan(
    loan_id: uuid.UUID, payload: LoanTransitionRequest, user: CurrentUser, db: Database
) -> LoanResponse:
    """Explicit handover or shelf confirmation; dates and jobs never advance a state."""
    loan, item, movie = await _locked_loan(db, loan_id)
    before = loan_state(loan)
    if (before, payload.state) not in (("asked_for", "out"), ("back", "shelved")):
        raise HTTPException(status_code=409, detail="That loan cannot make this transition")
    if payload.state == "out":
        lent = payload.lentDate or utc_today()
        if lent > latest_plausible_today() or (loan.due_date is not None and lent > loan.due_date):
            raise HTTPException(
                status_code=422, detail="Invalid handover date: future or after return due date"
            )
        loan.lent_date = lent
    else:
        loan.shelved_at_utc = utcnow()
        if payload.section is not None:
            old = {"section": item.section, "shelf": item.shelf, "location": item.location}
            item.section = payload.section
            item.shelf = payload.shelf
            item.location = location_text(payload.section, payload.shelf)
            record_action(
                db,
                user_id=user.id,
                action_type="update",
                target_table="collection_items",
                target_id=item.id,
                changes={
                    "location": {
                        "from": old,
                        "to": {
                            "section": item.section,
                            "shelf": item.shelf,
                            "location": item.location,
                        },
                    }
                },
            )
        elif not item.section and not item.location:
            raise HTTPException(status_code=422, detail="Choose a shelf location before confirming")
    loan.state = payload.state
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table=LOANS_TABLE,
        target_id=loan.id,
        changes={"state": {"from": before, "to": payload.state}},
    )
    await db.commit()
    await db.refresh(loan)
    return _loan_response(loan, item, movie)
