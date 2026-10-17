"""Wire models for box sets and smart collections — Batch 12, roadmap §11.3–11.5.

camelCase field names written directly, no ``alias_generator``, no envelope
(`DECISIONS.md` #6). Every one of these has a zod twin in ``packages/shared`` that ships
with it, because a schema added later never gets added.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.collection_item import SECTIONS
from src.models.smart_collection import SMART_COLLECTION_ICONS
from src.schemas.movies import MovieListItemResponse
from src.schemas.wire import UtcDatetime

Icon = Literal[
    "sparkles", "star", "heart", "clapperboard", "disc", "eye", "flame", "bookmark", "layers"
]
SortBy = Literal["title", "year", "rating"]
SortOrder = Literal["asc", "desc"]

# A literal cannot be built from a tuple at type-check time, so the two are asserted to
# agree instead. Without this, adding an icon to the model constant would leave the wire
# silently refusing it — the kind of drift `DECISIONS.md` #14 warns about.
assert set(Icon.__args__) == set(SMART_COLLECTION_ICONS)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Box sets (§3.24, §3.25)
# ---------------------------------------------------------------------------


class BoxSetFieldsMixin(BaseModel):
    """The fields an admin supplies, shared by create and update."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=255)]
    label: Annotated[str | None, Field(max_length=100)] = None
    volumeNumber: Annotated[int | None, Field(gt=0)] = None
    seriesId: uuid.UUID | None = None
    expectedCount: Annotated[int | None, Field(gt=0)] = None
    posterUrl: Annotated[str | None, Field(max_length=2000)] = None
    notes: str | None = None


class BoxSetCreateRequest(BoxSetFieldsMixin):
    """Optionally seeds the set with items, so "create with 4 items" is one call.

    §11.3's acceptance is *"Admin creates 'Columbia Noir Vol 4' with 4 items"*. Two calls
    would leave a half-built set behind whenever the second failed; one transaction
    cannot.
    """

    itemIds: Annotated[list[uuid.UUID], Field(max_length=200)] = []

    @model_validator(mode="after")
    def _no_duplicate_items(self) -> BoxSetCreateRequest:
        if len(set(self.itemIds)) != len(self.itemIds):
            raise ValueError("itemIds contains the same collection item twice")
        return self


class BoxSetUpdateRequest(BoxSetFieldsMixin):
    pass


class BoxSetItemAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collectionItemId: uuid.UUID
    discNumber: Annotated[int | None, Field(gt=0)] = None


class BoxSetMemberResponse(BaseModel):
    """One disc in the box, with enough of its film to render a row."""

    collectionItemId: uuid.UUID
    movieId: uuid.UUID
    movieTitle: str
    posterPath: str | None
    year: int | None
    formats: list[str]
    locationLabel: str
    discNumber: int | None = Field(gt=0)


class BoxSetResponse(BaseModel):
    id: uuid.UUID
    name: str
    label: str | None
    volumeNumber: int | None = Field(gt=0)
    seriesId: uuid.UUID | None
    seriesName: str | None
    expectedCount: int | None = Field(gt=0)
    posterUrl: str | None
    notes: str | None
    #: Live members only — a soft-deleted disc stops counting towards completion the
    #: moment it is deleted, which is the only reading that keeps "3 of 4" true.
    ownedCount: int = Field(ge=0)
    #: ``None`` when ``expectedCount`` is unknown. Not ``False``: a set whose size nobody
    #: recorded is not incomplete, it is unmeasured, and rendering that as "incomplete"
    #: would put a permanent red mark against every set an admin did not fill in.
    isComplete: bool | None
    createdAt: UtcDatetime
    updatedAt: UtcDatetime


class BoxSetDetailResponse(BoxSetResponse):
    items: list[BoxSetMemberResponse]
    #: Volumes pointing at this row as their series parent, name-ordered.
    volumes: list[BoxSetResponse]


class BoxSetListResponse(BaseModel):
    items: list[BoxSetResponse]
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Smart collections (§3.23)
# ---------------------------------------------------------------------------


class SmartCollectionFilters(BaseModel):
    """The complete, closed vocabulary a saved collection may constrain on.

    **These are exactly the query parameters ``GET /movies`` accepts**, by name and by
    type, and that is the point: a saved collection is a saved filter-bar state, so
    anything expressible here must mean the same thing there. ``extra="forbid"`` is what
    keeps an unrecognised key from being persisted and then quietly ignored at
    evaluation — a collection that silently drops half its criteria would list the wrong
    films with total confidence.
    """

    model_config = ConfigDict(extra="forbid")

    genreId: Annotated[int | None, Field(gt=0)] = None
    #: Batch Y5 — a TMDB keyword, as ``GET /movies``' ``keywordId``: Film Noir is 9807.
    keywordId: Annotated[int | None, Field(gt=0)] = None
    year: Annotated[int | None, Field(ge=1870, le=2200)] = None
    format: Annotated[str | None, Field(min_length=1, max_length=50)] = None
    section: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    shelf: Annotated[str | None, Field(min_length=1, max_length=50)] = None
    decadeFrom: Annotated[int | None, Field(ge=1870, le=2200)] = None
    decadeTo: Annotated[int | None, Field(ge=1870, le=2200)] = None
    minRating: Annotated[float | None, Field(ge=0, le=10)] = None
    #: Batch T3 — minutes, inclusive, matching ``GET /movies``' ``runtimeMin``/``runtimeMax``.
    runtimeMin: Annotated[int | None, Field(ge=1, le=1000)] = None
    runtimeMax: Annotated[int | None, Field(ge=1, le=1000)] = None
    watched: bool | None = None

    @model_validator(mode="after")
    def _check_vocabulary_and_range(self) -> SmartCollectionFilters:
        if self.section is not None and self.section not in SECTIONS:
            raise ValueError(f"Unknown section. Expected one of: {', '.join(SECTIONS)}")
        if (
            self.runtimeMin is not None
            and self.runtimeMax is not None
            and self.runtimeMin > self.runtimeMax
        ):
            raise ValueError("runtimeMin must not be more than runtimeMax")
        for name, value in (("decadeFrom", self.decadeFrom), ("decadeTo", self.decadeTo)):
            if value is not None and value % 10 != 0:
                raise ValueError(f"{name} must be the first year of a decade, such as 1940")
        if (
            self.decadeFrom is not None
            and self.decadeTo is not None
            and self.decadeFrom > self.decadeTo
        ):
            raise ValueError("decadeFrom must not be later than decadeTo")
        return self

    def stored(self) -> dict[str, object]:
        """The JSONB to persist: only the fields this collection actually constrains."""
        return self.model_dump(exclude_none=True, mode="json")


class SmartCollectionFieldsMixin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=255)]
    icon: Icon = "sparkles"
    filters: SmartCollectionFilters = SmartCollectionFilters()
    sortBy: SortBy = "title"
    sortOrder: SortOrder = "asc"
    isPinned: bool = False
    displayOrder: Annotated[int, Field(ge=0, le=9999)] = 0


class SmartCollectionCreateRequest(SmartCollectionFieldsMixin):
    pass


class SmartCollectionUpdateRequest(SmartCollectionFieldsMixin):
    pass


class SmartCollectionResponse(BaseModel):
    id: uuid.UUID
    name: str
    icon: Icon
    filters: SmartCollectionFilters
    sortBy: SortBy
    sortOrder: SortOrder
    isPinned: bool
    displayOrder: int = Field(ge=0)
    createdAt: UtcDatetime
    updatedAt: UtcDatetime


class SmartCollectionListResponse(BaseModel):
    items: list[SmartCollectionResponse]
    total: int = Field(ge=0)


class SmartCollectionResultsResponse(BaseModel):
    """A page of films, plus the collection that produced it.

    Deliberately the same ``items`` shape as ``GET /movies`` so the results page can
    reuse the grid rather than growing a second card component that renders the same
    film differently.
    """

    collection: SmartCollectionResponse
    items: list[MovieListItemResponse]
    totalMovies: int = Field(ge=0)
    totalItems: int = Field(ge=0)
    page: int = Field(gt=0)
    perPage: int = Field(gt=0)
    pages: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Completion sets and insights (§3.15, §11.1, §11.2)
# ---------------------------------------------------------------------------

SetType = Literal["director", "actor", "franchise", "box_set", "award", "curated_list"]


class CompletionFilmResponse(BaseModel):
    """One film in a set, owned or not.

    ``movieId`` is ``None`` for a film that is missing — it has no row in this database,
    which is precisely what "missing" means. The title, year and poster therefore come
    from the set's cached metadata rather than from ``movies``.
    """

    tmdbId: int = Field(gt=0)
    title: str
    year: int | None
    posterPath: str | None
    owned: bool
    movieId: uuid.UUID | None


class CompletionSetResponse(BaseModel):
    id: uuid.UUID
    setType: SetType
    setKey: str
    setName: str
    ownedCount: int = Field(ge=0)
    totalCount: int = Field(ge=0)
    missingCount: int = Field(ge=0)
    #: 0–100, computed server-side so the bar and the caption cannot disagree.
    percentComplete: int = Field(ge=0)
    lastRefreshed: UtcDatetime | None


class CompletionSetDetailResponse(CompletionSetResponse):
    films: list[CompletionFilmResponse]


class CompletionInsightsResponse(BaseModel):
    items: list[CompletionSetResponse]
    total: int = Field(ge=0)
    #: When the whole table was last rebuilt — the oldest ``lastRefreshed`` of any set,
    #: because a page is only as current as its stalest row.
    oldestRefresh: UtcDatetime | None


class CompletionRefreshResponse(BaseModel):
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    skipped: int = Field(ge=0)
    total: int = Field(ge=0)
    errors: list[str]
    dryRun: bool


# ---------------------------------------------------------------------------
# Trash, audit and lending (Batch 15) — §13.5, §13.6, §12.5
# ---------------------------------------------------------------------------

TrashTable = Literal[
    "collection_items",
    "watch_log",
    "movies",
    "box_sets",
    "wanted_list",
    "retailers",
]


class TrashCountResponse(BaseModel):
    table: TrashTable
    count: int = Field(ge=0)


class TrashRowResponse(BaseModel):
    """One soft-deleted row, in a shape that reads the same whatever table it came from.

    §13.5 lists items "per table", and four tables with four response shapes would mean
    four list components. ``label`` and ``sublabel`` are composed server-side so the trash
    is one list.
    """

    id: uuid.UUID
    table: TrashTable
    label: str
    sublabel: str | None
    posterPath: str | None
    movieId: uuid.UUID | None
    deletedAt: UtcDatetime


class TrashListResponse(BaseModel):
    items: list[TrashRowResponse]
    total: int = Field(ge=0)
    page: int = Field(gt=0)
    perPage: int = Field(gt=0)
    pages: int = Field(ge=0)
    counts: list[TrashCountResponse]


class PurgePreviewResponse(BaseModel):
    """What a 90-day purge would destroy. ``dryRun`` is the default, deliberately."""

    table: TrashTable
    olderThanDays: int = Field(gt=0)
    count: int = Field(ge=0)
    dryRun: bool
    deleted: int = Field(ge=0)


class LoanCreateRequest(BaseModel):
    """A loan names its borrower one of two ways — Batch W3 (#249).

    ``borrowerName`` for anyone, as before; or ``borrowerProfileId`` for one of the people
    who use the app ("I'm borrowing it"), whose name the server fills in. Exactly one.
    """

    model_config = ConfigDict(extra="forbid")

    collectionItemId: uuid.UUID
    borrowerName: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    borrowerProfileId: uuid.UUID | None = None
    lentDate: date | None = None
    dueDate: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _one_borrower(self) -> LoanCreateRequest:
        named = self.borrowerName is not None and self.borrowerName.strip() != ""
        if named == (self.borrowerProfileId is not None):
            raise ValueError(
                "Give the borrower's name, or borrowerProfileId for one of you, not both"
            )
        return self


class LoanReturnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    returnedDate: date | None = None


class LoanResponse(BaseModel):
    id: uuid.UUID
    collectionItemId: uuid.UUID
    movieId: uuid.UUID
    movieTitle: str
    posterPath: str | None
    formats: list[str]
    locationLabel: str
    borrowerName: str
    #: Batch W3. The borrower's profile when they are one of the people who use the app;
    #: null for a friend, and for every loan made before W3.
    borrowerProfileId: uuid.UUID | None
    lentDate: date
    dueDate: date | None
    returnedDate: date | None
    #: Derived, never stored: a loan with a due date in the past and no return date. A
    #: stored flag would need a job to keep it true and would be wrong between runs.
    isOverdue: bool
    #: Negative when overdue. ``None`` when no due date was set — "no deadline" is not
    #: "due today", and rendering it as 0 would put every open-ended loan in the red.
    daysUntilDue: int | None
    notes: str | None


class LoanListResponse(BaseModel):
    items: list[LoanResponse]
    total: int = Field(ge=0)
    openCount: int = Field(ge=0)
    overdueCount: int = Field(ge=0)
