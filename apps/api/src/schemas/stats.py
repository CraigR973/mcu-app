"""Wire models for the stats dashboard, activity feed and export — Batch 14, §13.1–13.4.

Every count here is derived at request time. §17 row 33 designs a 5-minute per-user cache
for the dashboard; nothing is cached yet, because the whole point of measuring first was to
find out whether it needs to be — see the router for the numbers.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime


class CountSlice(BaseModel):
    """One wedge, bar or column. ``key`` is the machine value, ``label`` the display one."""

    key: str
    label: str
    #: Discs, not films — the same disc can hold several formats and a film several discs.
    itemCount: int = Field(ge=0)
    movieCount: int = Field(ge=0)


class DecadeSlice(BaseModel):
    decade: int
    label: str
    movieCount: int = Field(ge=0)


class WatchedFilm(BaseModel):
    movieId: uuid.UUID
    title: str
    posterPath: str | None
    watchCount: int = Field(gt=0)
    lastWatched: str | None


class SpendPoint(BaseModel):
    """Cumulative spend at a point in time, for §13.1's "collection value over time"."""

    month: str
    spentCents: int
    cumulativeCents: int
    itemCount: int = Field(ge=0)


class StatsResponse(BaseModel):
    totalMovies: int = Field(ge=0)
    totalItems: int = Field(ge=0)
    #: Batch X12a: how many of `totalItems` carry the download format, so Home can say
    #: "1,923: 1,335 discs, 588 downloads" and the discs it counts are the ones it names.
    downloadCopies: int = Field(default=0, ge=0)
    identifiedMovies: int = Field(ge=0)
    watchedMovies: int = Field(ge=0)

    formats: list[CountSlice]
    genres: list[CountSlice]
    decades: list[DecadeSlice]
    sections: list[CountSlice]

    #: Empty until somebody logs a watch. The client says so rather than drawing a zero —
    #: an empty chart reads as a broken chart, which is `STATUS.md` gotcha 19's lesson
    #: applied to a dashboard instead of a list.
    mostWatched: list[WatchedFilm]

    #: Empty until purchase prices exist. All 1,857 imported rows have `purchase_price`
    #: NULL, because the spreadsheet never carried one; the series fills in as discs are
    #: edited or added by hand.
    spendOverTime: list[SpendPoint]
    #: How many live discs carry a price at all — the denominator that tells a reader
    #: whether an empty series means "nothing bought" or "nothing recorded".
    itemsWithPrice: int = Field(ge=0)


ActivityKind = Literal["added", "watched", "edited", "removed", "restored"]


class ActivityEvent(BaseModel):
    id: str
    kind: ActivityKind
    at: UtcDatetime
    actorName: str | None
    actorId: uuid.UUID | None = None
    movieId: uuid.UUID | None
    movieTitle: str | None
    posterPath: str | None
    detail: str | None


class ActivityResponse(BaseModel):
    items: list[ActivityEvent]
    total: int = Field(ge=0)
