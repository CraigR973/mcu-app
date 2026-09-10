"""Wire models for item photos — Batch 25, §3.10."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime


class PhotoResponse(BaseModel):
    """One photo's metadata.

    **No bytes.** A gallery of five photos would otherwise be a megabyte of base64 in a
    JSON list, re-fetched on every render; the browser asks for `url` instead and gets a
    cacheable image with an `ETag`.
    """

    id: uuid.UUID
    url: str
    caption: str | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    byteSize: int = Field(gt=0)
    position: int = Field(ge=0)
    createdAt: UtcDatetime


class PhotoListResponse(BaseModel):
    items: list[PhotoResponse]
    total: int = Field(ge=0)
    #: What is left before §3.10's five-per-item ceiling, so the UI can say so before
    #: somebody picks a sixth file.
    remaining: int = Field(ge=0)
