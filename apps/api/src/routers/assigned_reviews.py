"""AD1: personal review observations, with administrator assignment/inspection only."""

import uuid

from fastapi import APIRouter, HTTPException

from src.auth import AdminUser, CurrentUser
from src.clock import utcnow
from src.routers.movies import Database
from src.schemas.assigned_reviews import (
    AnswerReview,
    AssignedReviewResponse,
    AssignReview,
    ReassignReview,
    ReviewProposal,
)
from src.services import assigned_reviews as reviews

router = APIRouter(prefix="/api/v1/needs-you/reviews", tags=["needs-you"])


@router.get("", response_model=list[AssignedReviewResponse])
async def list_reviews(
    user: CurrentUser, db: Database, allAssignees: bool = False
) -> list[AssignedReviewResponse]:
    return await reviews.list_reviews(db, user, all_assignees=allAssignees)


@router.get("/proposals", response_model=list[ReviewProposal])
async def proposals(_user: AdminUser, db: Database) -> list[ReviewProposal]:
    return await reviews.proposals(db)


@router.post("", response_model=AssignedReviewResponse)
async def assign(payload: AssignReview, user: AdminUser, db: Database) -> AssignedReviewResponse:
    row = await reviews.assign(db, payload, user)
    await db.commit()
    return await reviews.describe(db, row, user)


@router.get("/{review_id}", response_model=AssignedReviewResponse)
async def detail(review_id: uuid.UUID, user: CurrentUser, db: Database) -> AssignedReviewResponse:
    return await reviews.describe(db, await reviews.review_for(db, review_id, user), user)


@router.post("/{review_id}/answer", response_model=AssignedReviewResponse)
async def answer(
    review_id: uuid.UUID, payload: AnswerReview, user: CurrentUser, db: Database
) -> AssignedReviewResponse:
    row = await reviews.review_for(db, review_id, user, lock=True)
    # Administrator inspection is not permission to answer on another person's behalf.
    if row.assigned_to != user.id:
        raise HTTPException(403, "Only the assigned person can answer this review")
    choices = {value for value, _label in reviews.WORDS[row.kind][3]} | {"unsure"}
    if payload.answer not in choices:
        raise HTTPException(422, "Choose an answer offered by this review")
    if row.answer == payload.answer and payload.revision in (row.revision, row.revision - 1):
        return await reviews.describe(db, row, user)
    if payload.revision != row.revision:
        raise HTTPException(409, "This review changed. Re-open it before answering.")
    current, resolved = await reviews.context(db, row.kind, row.target_id, lock=True)
    if resolved or current != row.snapshot:
        raise reviews._conflict()
    before = row.answer
    row.answer = payload.answer
    row.answered_at_utc = utcnow()
    row.revision += 1
    reviews.audit(
        db, row, user, {"answer": {"from": before, "to": row.answer}, "revision": row.revision}
    )
    await db.commit()
    return await reviews.describe(db, row, user)


@router.patch("/{review_id}/assignee", response_model=AssignedReviewResponse)
async def reassign(
    review_id: uuid.UUID, payload: ReassignReview, user: AdminUser, db: Database
) -> AssignedReviewResponse:
    row = await reviews.review_for(db, review_id, user, lock=True)
    if payload.assignedTo == row.assigned_to and payload.revision in (
        row.revision,
        row.revision - 1,
    ):
        return await reviews.describe(db, row, user)
    if payload.revision != row.revision:
        raise HTTPException(409, "This review changed. Re-open it before reassigning.")
    await reviews.active_person(db, payload.assignedTo)
    before = row.assigned_to
    old_answer = row.answer
    row.assigned_to = payload.assignedTo
    row.answer = None
    row.answered_at_utc = None
    row.revision += 1
    reviews.audit(
        db,
        row,
        user,
        {
            "assignedTo": {"from": str(before), "to": str(row.assigned_to)},
            "previousAnswer": old_answer,
            "revision": row.revision,
        },
    )
    await db.commit()
    return await reviews.describe(db, row, user)
