"""Wire models for streaming availability and recommendations — Batch 16, §7.1 and §7.2."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

#: How a film can be watched somewhere. TMDB's own three buckets, kept apart because
#: "included in your subscription" and "£13.99 to buy" are not the same answer to
#: "can I watch this tonight?".
OfferKind = Literal["flatrate", "rent", "buy"]

#: What this collection already has to say about a recommended film.
#:
#: ``wanted`` is **absent on purpose**. §7.2 lists "owned / wanted / unowned", and the
#: wanted list is §3.5 — a table Batch 18 builds. A third state the app cannot produce
#: would be a legend entry that never appears.
OwnershipState = Literal["owned", "unowned"]


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
