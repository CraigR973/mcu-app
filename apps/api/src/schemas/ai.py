"""Wire models for the AI assistant — Batch 30, §9.1 and §9.7."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime


class AskRequest(BaseModel):
    """One question."""

    prompt: str = Field(min_length=1, max_length=4000)


class AskResponse(BaseModel):
    """The answer, and what producing it cost — §9.1's "tokens logged".

    The token counts are on the wire, not only in the log, because the person paying for
    them is the person reading the answer. `costUsd` is a string: it is a decimal, and a
    float would round a fraction-of-a-penny call to something that is not what was billed.
    """

    id: uuid.UUID
    text: str
    model: str
    inputTokens: int = Field(ge=0)
    outputTokens: int = Field(ge=0)
    cacheReadTokens: int = Field(ge=0)
    cacheWriteTokens: int = Field(ge=0)
    costUsd: str
    stopReason: str | None = None
    latencyMs: int = Field(ge=0)
    #: Present when the call failed. `text` is still a sentence a person can read.
    error: str | None = None


class UsageResponse(BaseModel):
    """§9.7's counters, as the settings page and the chat header show them."""

    messages: int = Field(ge=0)
    messageCap: int = Field(ge=0)
    messagesRemaining: int = Field(ge=0)
    costUsd: str
    costCapUsd: str
    blocked: bool
    #: Non-null exactly when `blocked` — the sentence §9.7 calls a "graceful limit
    #: reached message", naming which ceiling and when it lifts.
    limitMessage: str | None = None
    resetsAt: UtcDatetime


class AiSettingsResponse(BaseModel):
    dailyMessageCap: int = Field(ge=0, le=10000)
    dailyCostCapUsd: str


class AiSettingsUpdateRequest(BaseModel):
    """Partial. Zero is a meaningful cap — "no AI for me" — so it is not treated as unset."""

    dailyMessageCap: int | None = Field(default=None, ge=0, le=10000)
    dailyCostCapUsd: float | None = Field(default=None, ge=0, le=1000)


class AiStatusResponse(BaseModel):
    """Whether the assistant can work in **this** deployment.

    `configured` is false when Railway holds no `ANTHROPIC_API_KEY`. That is the TMDB
    shape — a feature absent from the deployment with the front end unable to say so —
    and this is what lets the UI say it plainly instead of failing at the first question.
    """

    configured: bool
    model: str
