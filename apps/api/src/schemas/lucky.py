"""AA6's ephemeral, read-only Archive draw."""

import uuid

from pydantic import BaseModel, Field

from src.schemas.movies import MovieListItemResponse


class LuckyRequest(BaseModel):
    excludedIds: list[uuid.UUID] = Field(default_factory=list, max_length=10_000)
    unwatchedOnly: bool = False
    sessionId: uuid.UUID | None = None


class LuckyResponse(BaseModel):
    film: MovieListItemResponse | None
