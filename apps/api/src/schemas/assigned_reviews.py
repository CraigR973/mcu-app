"""Typed review assignments and observations; never an identity-write payload."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime

ReviewKind = Literal["titanic_disc", "wanted_identity", "shetland_series"]
#: A year for Titanic's disc and any want's film (AG5: a want's choices are the years its shop
#: listings name), or one of Shetland's two words, or "unsure". The router checks the answer is
#: one the row offers.
ReviewAnswer = Annotated[str, Field(pattern=r"^(use_series|keep_separate|unsure|(19|20)[0-9]{2})$")]
Revision = Annotated[int, Field(ge=1)]


class AssignReview(BaseModel):
    kind: ReviewKind
    targetId: uuid.UUID
    assignedTo: uuid.UUID
    expectedFingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class AnswerReview(BaseModel):
    revision: Revision
    answer: ReviewAnswer


class ReassignReview(BaseModel):
    revision: Revision
    assignedTo: uuid.UUID


class CloseReview(BaseModel):
    """AH2 (#401): close or reopen, at the revision the admin was shown."""

    revision: Revision


class ReviewChoice(BaseModel):
    value: ReviewAnswer
    label: str


class ReviewProposal(AssignReview):
    title: str


class WantProposal(ReviewProposal):
    """AG5: a want whose shop listings name another film's year, and what it would ask."""

    question: str
    choices: list[ReviewChoice]
    #: Who it would be asked of, by name, for the admin's button.
    assigneeName: str


class AssignedReviewResponse(BaseModel):
    id: uuid.UUID
    kind: ReviewKind
    targetId: uuid.UUID
    assignedTo: uuid.UUID
    assigneeName: str
    movieId: uuid.UUID | None
    title: str
    question: str
    evidence: str
    choices: list[ReviewChoice]
    revision: Revision
    answer: ReviewAnswer | None
    answeredAt: UtcDatetime | None
    status: Literal["open", "answered", "changed", "resolved", "closed"]
    canAnswer: bool
    #: AH2 (#401): the admin closed it: when, and by whom. Null while it is open.
    closedAt: UtcDatetime | None = None
    closedByName: str | None = None
    #: The admin may close an answered or changed question, and reopen a closed one.
    canClose: bool = False
    canReopen: bool = False
