"""Wire models for the AI assistant — Batch 30, §9.1 and §9.7."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

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
    """Partial. A message cap of zero is meaningful — "no AI for me" — so it is not unset.

    **A cost cap must be more than zero** (Batch X7, AI45-05): zero used to mean "no cost
    ceiling", and a cleared box saved zero, so clearing it quietly lifted the money ceiling.
    Both caps are bounded at four times their defaults (`caps.MAX_MESSAGE_CAP`,
    `caps.MAX_COST_CAP_USD`); they were $1,000 and 10,000 a day.
    """

    dailyMessageCap: int | None = Field(default=None, ge=0, le=200)
    dailyCostCapUsd: Decimal | None = Field(
        default=None, gt=0, le=Decimal("10.00"), max_digits=6, decimal_places=2
    )


class AiStatusResponse(BaseModel):
    """Whether the assistant can work in **this** deployment.

    `configured` is false when Railway holds no `ANTHROPIC_API_KEY`. That is the TMDB
    shape — a feature absent from the deployment with the front end unable to say so —
    and this is what lets the UI say it plainly instead of failing at the first question.
    """

    configured: bool
    model: str


# ---------------------------------------------------------------------------
# Conversations, tools and the confirmation boundary (Batch 31) — §9.2–§9.4
# ---------------------------------------------------------------------------


class ToolSummary(BaseModel):
    """One tool this person may use.

    `writes` is on the wire because §9.4's prompt is the visible consequence of it, and a
    UI that has to guess which tools ask for confirmation will guess wrong eventually.
    """

    name: str
    description: str
    writes: bool


class ToolListResponse(BaseModel):
    """§9.2's acceptance, made directly observable: ask as an admin, ask as a viewer."""

    role: str
    items: list[ToolSummary]
    total: int = Field(ge=0)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    createdAt: UtcDatetime
    updatedAt: UtcDatetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int = Field(ge=0)


class ChatMessageResponse(BaseModel):
    """One rendered turn. `tool_result` rows never reach here — see the router."""

    id: uuid.UUID
    role: str
    text: str
    sequence: int = Field(ge=1)
    createdAt: UtcDatetime


class PendingToolCallResponse(BaseModel):
    """A write Claude asked for and has **not** performed.

    The input is included in full because §9.4's prompt has to say what will actually
    happen — "Claude wants to use a tool" is not a decision anyone can make.
    """

    id: uuid.UUID
    toolName: str
    input: dict[str, Any]


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    createdAt: UtcDatetime
    updatedAt: UtcDatetime
    messages: list[ChatMessageResponse]
    #: Survives the stream that raised it: a person can close the tab and come back.
    pendingToolCalls: list[PendingToolCallResponse] = Field(default_factory=list)


class ToolCallResolveRequest(BaseModel):
    """`confirm: false` is a real answer, not an absence of one."""

    confirm: bool
