"""Wire models for streaming availability and recommendations — Batch 16, §7.1 and §7.2."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

from src.schemas.wire import UtcDatetime

#: How a film can be watched somewhere. TMDB's own three buckets, kept apart because
#: "included in your subscription" and "£13.99 to buy" are not the same answer to
#: "can I watch this tonight?".
OfferKind = Literal["flatrate", "rent", "buy"]

#: What this collection already has to say about a recommended film.
#:
#: Three states since **Batch 18** built §3.5's `wanted_list`. Batch 16 shipped two,
#: because a ``wanted`` value the app could never produce would have been a legend entry
#: pointing at nothing — this is the third arriving with the table behind it.
OwnershipState = Literal["owned", "wanted", "unowned"]


class StreamingOfferResponse(BaseModel):
    providerId: int
    providerName: str
    logoPath: str | None
    kind: OfferKind


class StreamingResponse(BaseModel):
    movieId: uuid.UUID
    region: str
    #: TMDB's deep link into its own "where to watch" page for this film and region.
    #: Their terms require it to be shown when their availability data is; it is also
    #: the only honest "prices may vary" surface, since the API gives no prices.
    link: str | None
    offers: list[StreamingOfferResponse]
    #: True when the film has no TMDB id, so nothing could be looked up. Distinct from
    #: "TMDB has no offers for it", which is a real answer.
    unidentified: bool
    #: True when TMDB could not be reached. **Also** distinct from an empty list — and
    #: the reason this is a flag rather than a 502: a 5xx is classified as a network
    #: failure by the web client (`DECISIONS.md` #43, correctly — a gateway, a proxy or a
    #: booting container all produce one), so the page would tell the reader to check
    #: their connection when the connection is fine and it is TMDB that is down.
    unavailable: bool


class RecommendationResponse(BaseModel):
    tmdbId: int
    title: str
    year: int | None
    overview: str
    posterPath: str | None
    ownership: OwnershipState
    #: Set when ``ownership`` is "owned", so the card can link to the film already here.
    movieId: uuid.UUID | None


class RecommendationListResponse(BaseModel):
    movieId: uuid.UUID
    items: list[RecommendationResponse]
    ownedCount: int
    #: As :attr:`StreamingResponse.unavailable` — "TMDB did not answer" is a different
    #: fact from "TMDB has no recommendations", and only one of them is worth retrying.
    unavailable: bool = False


class NewReleaseResponse(BaseModel):
    tmdbId: int
    title: str
    releaseDate: str | None
    posterPath: str | None
    overview: str
    #: Which of this collection's own genres put the film in the feed. Shown so a
    #: suggestion can explain itself rather than appearing to come from nowhere.
    matchedGenres: list[str]
    ownership: OwnershipState
    movieId: uuid.UUID | None


class NewReleaseListResponse(BaseModel):
    items: list[NewReleaseResponse]
    #: The genres the feed was filtered by — this collection's most-collected ones.
    basedOnGenres: list[str]


# ---------------------------------------------------------------------------
# Release calendar and iCal feed (Batch 17) — §3.26, §7.3, §7.4
# ---------------------------------------------------------------------------

ReleaseType = Literal[
    "4k_uhd_release",
    "blu_ray_release",
    "streaming_release",
    "theatrical",
    "award_ceremony",
    "sale_event",
]


class CalendarEntryResponse(BaseModel):
    id: uuid.UUID
    title: str
    releaseType: ReleaseType
    typeLabel: str
    releaseDate: date
    label: str | None
    region: str
    url: str | None
    posterPath: str | None
    overview: str | None
    #: Set when the film is already in the collection, so a row can link to it.
    movieId: uuid.UUID | None


class CalendarMonthResponse(BaseModel):
    """One month's entries, grouped by day — §7.4's "monthly calendar view".

    Grouped server-side so the grid does not have to bucket dates in the browser, and so
    a month with nothing in it is an explicit empty list rather than a gap the client
    infers.
    """

    month: str
    days: dict[str, list[CalendarEntryResponse]]
    total: int


class CalendarListResponse(BaseModel):
    items: list[CalendarEntryResponse]
    total: int


class CalendarSubscriptionResponse(BaseModel):
    """The feed path, returned **once**.

    The token is hashed at rest and never retrievable again — so this response is the only
    time it exists in plaintext, and asking again rotates it. That is what makes an
    accidentally-pasted link recoverable.

    **A path, not an absolute URL.** The API does not know its own public origin: deriving
    it from the request's ``Host`` header would reflect an attacker-controlled value into a
    link, and configuring it would mean a new Railway variable — a hosting change this
    project keeps explicit. The web app already holds the origin in ``VITE_API_URL`` and
    composes the URL there, which is the one place it is known for certain.
    """

    path: str
    createdAt: UtcDatetime
    #: True when this call revoked a previous link, so the UI can say the old one stopped
    #: working rather than leaving someone with two URLs they believe both work.
    replacedPrevious: bool


class CalendarIngestResponse(BaseModel):
    created: int
    updated: int
    unchanged: int
    skipped: int
    total: int
    errors: list[str]
    dryRun: bool


class MaybeOwnedResponse(BaseModel):
    """An owned film with no TMDB id yet whose title reads the same as this result."""

    movieId: uuid.UUID
    title: str


class BeyondResultResponse(BaseModel):
    """A film the search found on TMDB that is not on the shelf — Batch T2."""

    tmdbId: int
    title: str
    year: int | None = None
    posterPath: str | None = None
    overview: str = ""
    #: A ``movies`` row with this TMDB id and **no** live disc: a film you have watched,
    #: wanted or sold. Its own page exists, with its history.
    movieId: uuid.UUID | None = None
    #: The caller's latest watch, when that row carries one.
    lastWatchedAt: date | None = None
    #: Subscription services in the caller's region.
    streamingOn: list[str] = []
    #: Whether ``streamingOn`` was looked up at all. Only the first few results are, so an
    #: empty list means "none" only when this is true.
    streamingChecked: bool = False
    #: Set when this may be an owned film that nothing has identified yet. **Flagged, not
    #: hidden** — two films can share a title, and hiding the wrong one is worse.
    maybeOwned: MaybeOwnedResponse | None = None


class BeyondSearchResponse(BaseModel):
    query: str
    items: list[BeyondResultResponse]
    #: TMDB could not be asked. Distinct from "asked, and found nothing" — see
    #: :attr:`StreamingResponse.unavailable` for why this is a flag and not a 502.
    unavailable: bool = False


class ExternalFilmResponse(BaseModel):
    """The film card for something the collection does not hold — Batch T2."""

    tmdbId: int
    title: str
    year: int | None = None
    posterPath: str | None = None
    backdropPath: str | None = None
    overview: str = ""
    runtimeMinutes: int | None = None
    genres: list[str] = []
    cast: list[str] = []
    directors: list[str] = []
    #: A ``movies`` row with this TMDB id, if one exists.
    movieId: uuid.UUID | None = None
    #: True when that row has a live disc. The web app sends an owned film to its own page.
    owned: bool = False
    #: True when it is on the wanted list (active, not removed).
    wanted: bool = False
    region: str
    #: TMDB's "where to watch" page for this film and region. Their terms require it
    #: alongside their availability data.
    link: str | None = None
    offers: list[StreamingOfferResponse] = []
