"""Authenticated programme wire contract; dates, certainty and coverage stay separate."""

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas.wire import UtcDatetime

ReleaseCategory = Literal["newRelease", "olderFilm", "unclassified"]
ReleaseFilter = Literal["all", "newRelease", "olderFilm", "unclassified"]
CoverageStatus = Literal[
    "notEnabled", "unavailable", "failed", "empty", "partial", "healthy", "stale"
]


class ProgrammeWindow(BaseModel):
    dateFrom: date
    dateTo: date


class ProgrammeDateCoverage(BaseModel):
    localDate: date
    status: CoverageStatus
    observed: bool
    complete: bool
    lastAttemptUtc: UtcDatetime | None
    lastSuccessUtc: UtcDatetime | None
    sourceUpdateLabel: str | None
    upstreamUtc: UtcDatetime | None
    upstreamAge: Literal["unknown", "current", "stale"]
    error: str | None


class ProgrammeVenue(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    source: str
    sourceUrl: str
    officialUrl: str
    collectionEnabled: bool
    coverage: list[ProgrammeDateCoverage]


class ProgrammeCategoryEvidence(BaseModel):
    sourceUrl: str | None
    description: str


class ProgrammeShowing(BaseModel):
    id: uuid.UUID
    venueId: uuid.UUID
    sourceTitle: str
    startsAtUtc: UtcDatetime
    endsAtUtc: UtcDatetime | None
    screen: str | None
    formats: list[str]
    releaseCategory: ReleaseCategory
    sourceReleaseDate: date | None
    reissue: bool | None
    categoryConfidence: Literal["verified", "unverified"]
    categoryEvidence: ProgrammeCategoryEvidence
    #: AC3 (#335): the run's reason in words, "UK release 1975 · rerun"; null when unlinked.
    categoryReason: str | None = None
    confirmation: Literal["confirmed", "unconfirmed"]
    lastSeenUtc: UtcDatetime
    observationStale: bool
    upstreamAge: Literal["unknown", "current", "stale"]
    bookingUrl: str | None


class ProgrammeFilm(BaseModel):
    id: str
    title: str
    movieId: uuid.UUID | None
    originalYear: int | None
    yearConfidence: Literal["verified", "unverified"]
    #: AC3 (#335): "review" waits for Craig's review list; "event" is never one film.
    identityStatus: Literal["verified", "unverified", "conflict", "review", "event"]
    owned: bool | None
    watched: bool | None
    showings: list[ProgrammeShowing]


class ProgrammeCategoryCounts(BaseModel):
    newRelease: int = Field(ge=0)
    olderFilm: int = Field(ge=0)
    unclassified: int = Field(ge=0)


class CinemaProgrammeResponse(BaseModel):
    generatedAtUtc: UtcDatetime
    window: ProgrammeWindow
    venues: list[ProgrammeVenue]
    films: list[ProgrammeFilm]
    categoryCounts: ProgrammeCategoryCounts
    matchedShowingCount: int = Field(ge=0)
    returnedShowingCount: int = Field(ge=0)
    truncated: bool
    selectionComplete: bool


class ReviewCandidate(BaseModel):
    """One film the lookup found with the programme's title, for Craig to choose."""

    tmdbId: int = Field(gt=0)
    title: str
    year: int | None
    posterPath: str | None
    voteCount: int = Field(ge=0)


class ReviewItem(BaseModel):
    """One programme film AC3 could not settle alone (#335): its rows across the listings that
    share a title and facts, so a film listed once per showing reads as one film."""

    key: str
    title: str
    sourceTitles: list[str]
    venues: list[str]
    futureShowings: int = Field(ge=0)
    reason: str
    candidates: list[ReviewCandidate]


class ReviewList(BaseModel):
    #: Most showings first; only films still showing.
    items: list[ReviewItem]


class ReviewDecision(BaseModel):
    """Exactly one: the TMDB film it is, from the item's own candidates, or not a film."""

    model_config = ConfigDict(extra="forbid")

    tmdbId: int | None = Field(default=None, gt=0)
    notAFilm: bool = False

    @model_validator(mode="after")
    def exactly_one(self) -> "ReviewDecision":
        if (self.tmdbId is None) == (not self.notAFilm):
            raise ValueError("Choose one of the films, or say it is not a film")
        return self


# AC4: At the cinema, film first. A film is one TMDB film across every cinema and listing title
# (AC3); anything not linked to one stays its cinema's own listing.
FilmKind = Literal["film", "listing", "event"]
IdentityStatus = Literal["verified", "unverified", "conflict", "review", "event"]


class CinemaFilmSlot(BaseModel):
    """One cinema's showings of a film on one day, in one run, still to start."""

    venueId: uuid.UUID
    localDate: date
    releaseCategory: ReleaseCategory
    #: AC3's reason in words, "UK release 1977 · rerun"; null when the run rests on no reason.
    runReason: str | None
    startsAtUtc: list[UtcDatetime] = Field(min_length=1)


class CinemaFilmFacts(BaseModel):
    """What the film-first views say about a film or listing, above its showings."""

    #: The film page's stable address: `tmdb-603` for a linked film, `listing-<uuid>` for a
    #: cinema's listing that is not (yet) one film. A listing's address follows it once linked.
    key: str = Field(
        pattern=r"^(tmdb-\d+|movie-[0-9a-f-]{36}|imdb-tt\d{7,10}|listing-[0-9a-f-]{36})$"
    )
    #: "film": linked to one film; "listing": not matched to a film yet; "event": never one film.
    kind: FilmKind
    title: str
    #: Every title the cinemas list it under, the film's own first.
    sourceTitles: list[str]
    posterPath: str | None
    tmdbId: Annotated[int, Field(gt=0)] | None
    movieId: uuid.UUID | None
    originalYear: int | None
    yearConfidence: Literal["verified", "unverified"]
    directors: list[str]
    runtimeMinutes: Annotated[int, Field(gt=0)] | None
    identityStatus: IdentityStatus
    #: Why a listing is not one film: "not yet looked up on TMDB", "more than one film matches".
    identityReason: str | None
    owned: bool | None
    watched: bool | None


class CinemaFilmCard(CinemaFilmFacts):
    slots: list[CinemaFilmSlot]


class CinemaDigestCard(BaseModel):
    key: str
    title: str
    firstListedAtUtc: UtcDatetime
    recognisedAtUtc: UtcDatetime
    isReturn: bool
    runLabels: list[str]
    runReasons: list[str]
    card: CinemaFilmCard | None


class CinemaFilmsResponse(BaseModel):
    """Every film and listing still to show in the stored programme's fortnight."""

    generatedAtUtc: UtcDatetime
    window: ProgrammeWindow
    #: The last day of "This week": today and the six days after it.
    thisWeekTo: date
    venues: list[ProgrammeVenue]
    films: list[CinemaFilmCard]
    newThisWeek: list[CinemaDigestCard] = Field(default_factory=list)
    #: Every venue and date checked in full.
    complete: bool


class AlsoListed(BaseModel):
    """Another film or listing with the same title: maybe the same film, maybe not."""

    key: str
    kind: FilmKind
    title: str
    venueIds: list[uuid.UUID]
    showingCount: int = Field(ge=0)


class CinemaFilmDetail(BaseModel):
    """One film's every showing across the nine, earliest first."""

    generatedAtUtc: UtcDatetime
    window: ProgrammeWindow
    thisWeekTo: date
    film: CinemaFilmFacts
    venues: list[ProgrammeVenue]
    showings: list[ProgrammeShowing]
    alsoListed: list[AlsoListed]
