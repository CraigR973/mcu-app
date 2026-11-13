"""What the daily check found and the lines sent to Craig — Batch X2 (DS44-01, UX48-02).

Since AF1 (#372) they are rows in Craig's Needs you rather than a row of their own.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from src.schemas.wire import UtcDatetime


class AttentionItemResponse(BaseModel):
    #: Stable per check ("job:cron-ebay", "ebay:listings"), for the list's keys.
    key: str
    #: The problem in words: "No eBay listings read in the last 6 scans (since 9 Oct)."
    message: str
    #: When the problem first appeared; null for one the row works out as it is read.
    since: UtcDatetime | None = None
    #: Batch X12a: set on a line a person sent with "Tell Craig", which Craig clears; null on
    #: a problem the daily check found, which clears itself when the problem goes.
    noteId: uuid.UUID | None = None
    #: AF1 (#372): on a line, who sent it and what they said, so Needs you can label the row
    #: with them and show their words alone. ``message`` keeps "<name> says: …" for older builds.
    fromProfileId: uuid.UUID | None = None
    fromName: str | None = None
    body: str | None = None


class NoteRequest(BaseModel):
    """What a person types on the You page."""

    model_config = ConfigDict(extra="forbid")

    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class AttentionResponse(BaseModel):
    items: list[AttentionItemResponse]
    #: When the daily check last ran; null before its first run.
    checkedAt: UtcDatetime | None = None
