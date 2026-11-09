"""Typed review assignments and observations; never an identity-write payload."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime

ReviewKind = Literal["titanic_disc", "wanted_identity", "shetland_series"]
ReviewAnswer = Literal["1953", "1997", "1940", "2004", "use_series", "keep_separate", "unsure"]
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


class ReviewChoice(BaseModel):
    value: ReviewAnswer
    label: str


class ReviewProposal(AssignReview):
    title: str


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
    status: Literal["open", "answered", "changed", "resolved"]
    canAnswer: bool
