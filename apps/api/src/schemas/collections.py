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
    discNumber: int | None


class BoxSetResponse(BaseModel):
    id: uuid.UUID
    name: str
    label: str | None
    volumeNumber: int | None
    seriesId: uuid.UUID | None
    seriesName: str | None
    expectedCount: int | None
    posterUrl: str | None
    notes: str | None
    #: Live members only — a soft-deleted disc stops counting towards completion the
    #: moment it is deleted, which is the only reading that keeps "3 of 4" true.
    ownedCount: int
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
    total: int


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
    year: Annotated[int | None, Field(ge=1870, le=2200)] = None
    format: Annotated[str | None, Field(min_length=1, max_length=50)] = None
    section: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    shelf: Annotated[str | None, Field(min_length=1, max_length=50)] = None
    decadeFrom: Annotated[int | None, Field(ge=1870, le=2200)] = None
    decadeTo: Annotated[int | None, Field(ge=1870, le=2200)] = None
    minRating: Annotated[float | None, Field(ge=0, le=10)] = None
    watched: bool | None = None

    @model_validator(mode="after")
    def _check_vocabulary_and_range(self) -> SmartCollectionFilters:
        if self.section is not None and self.section not in SECTIONS:
            raise ValueError(f"Unknown section. Expected one of: {', '.join(SECTIONS)}")
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
    displayOrder: int
    createdAt: UtcDatetime
    updatedAt: UtcDatetime


class SmartCollectionListResponse(BaseModel):
    items: list[SmartCollectionResponse]
    total: int


class SmartCollectionResultsResponse(BaseModel):
    """A page of films, plus the collection that produced it.

    Deliberately the same ``items`` shape as ``GET /movies`` so the results page can
    reuse the grid rather than growing a second card component that renders the same
    film differently.
    """

    collection: SmartCollectionResponse
    items: list[MovieListItemResponse]
    totalMovies: int
    totalItems: int
    page: int
    perPage: int
    pages: int


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

    tmdbId: int
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
    ownedCount: int
    totalCount: int
    missingCount: int
    #: 0–100, computed server-side so the bar and the caption cannot disagree.
    percentComplete: int
    lastRefreshed: UtcDatetime | None


class CompletionSetDetailResponse(CompletionSetResponse):
    films: list[CompletionFilmResponse]


class CompletionInsightsResponse(BaseModel):
    items: list[CompletionSetResponse]
    total: int
    #: When the whole table was last rebuilt — the oldest ``lastRefreshed`` of any set,
    #: because a page is only as current as its stalest row.
    oldestRefresh: UtcDatetime | None


class CompletionRefreshResponse(BaseModel):
    created: int
    updated: int
    unchanged: int
    skipped: int
    total: int
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
    "gift_links",
]


class TrashCountResponse(BaseModel):
    table: TrashTable
    count: int


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
    total: int
    page: int
    perPage: int
    pages: int
    counts: list[TrashCountResponse]


class PurgePreviewResponse(BaseModel):
    """What a 90-day purge would destroy. ``dryRun`` is the default, deliberately."""

    table: TrashTable
    olderThanDays: int
    count: int
    dryRun: bool
    deleted: int


class LoanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collectionItemId: uuid.UUID
    borrowerName: Annotated[str, Field(min_length=1, max_length=255)]
    lentDate: date | None = None
    dueDate: date | None = None
    notes: str | None = None


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
    total: int
    openCount: int
    overdueCount: int
