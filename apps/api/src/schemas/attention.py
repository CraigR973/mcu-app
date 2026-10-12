"""The Home row's "Needs attention" — Batch X2 (DS44-01, UX48-02)."""

from __future__ import annotations

from pydantic import BaseModel

from src.schemas.wire import UtcDatetime


class AttentionItemResponse(BaseModel):
    #: Stable per check ("job:cron-ebay", "ebay:listings"), for the list's keys.
    key: str
    #: The problem in words: "No eBay listings read in the last 6 scans (since 9 Oct)."
    message: str
    #: When the problem first appeared; null for one the row works out as it is read.
    since: UtcDatetime | None = None


class AttentionResponse(BaseModel):
    items: list[AttentionItemResponse]
    #: When the daily check last ran; null before its first run.
    checkedAt: UtcDatetime | None = None
