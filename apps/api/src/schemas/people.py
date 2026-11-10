"""A page for each person — AE9 (#355). Read-only, and only what the shelves and the diary say.

Nothing from Settings is ever here: no PIN, session, notification setting or connected account.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class PersonDiaryEntry(BaseModel):
    """One watch from the person's diary."""

    movieId: uuid.UUID
    title: str
    year: int | None
    posterPath: str | None
    watchedOn: date
    #: Their own rating, 0.5 to 5; null when they gave none.
    rating: float | None = Field(default=None, ge=0.5, le=5)
    rewatch: bool


class PersonAddedCopy(BaseModel):
    """A copy they added in the app, still on the shelves."""

    copyId: uuid.UUID
    movieId: uuid.UUID
    title: str
    posterPath: str | None
    formats: list[str]
    addedOn: date


class PersonFilm(BaseModel):
    """A film they want."""

    movieId: uuid.UUID
    title: str
    year: int | None
    posterPath: str | None


class PersonLoan(BaseModel):
    """A disc they have, or have asked for."""

    loanId: uuid.UUID
    movieId: uuid.UUID
    title: str
    posterPath: str | None
    state: Literal["asked_for", "out"]
    lentDate: date | None
    dueDate: date | None
    neededBy: date | None


class PersonPageResponse(BaseModel):
    profileId: uuid.UUID
    displayName: str
    #: The reader's own page: the web opens You instead.
    isYou: bool
    #: Different films watched this calendar year (London), and ever.
    watchedThisYear: int = Field(ge=0)
    watchedTotal: int = Field(ge=0)
    #: The last ten diary entries, newest first.
    diary: list[PersonDiaryEntry]
    #: The last ten copies they added that are still on the shelves, newest first.
    recentlyAdded: list[PersonAddedCopy]
    #: Their wants, newest first, the first twenty, and how many in all.
    wants: list[PersonFilm]
    wantsTotal: int = Field(ge=0)
    #: Discs they have, or have asked for, now.
    loans: list[PersonLoan]
