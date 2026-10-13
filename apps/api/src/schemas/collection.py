"""Camel-case wire contracts for Batch 7's write surface.

Separate from ``schemas/movies.py`` because this is a different surface with a different
audience: everything here is admin-only, and everything there is readable by both users.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from src.clock import latest_plausible_today
from src.models.collection_item import CONDITIONS, FORMAT_RANK
from src.schemas.wire import UtcDatetime, UtcDatetimeIn

#: A disc has at least one format and, realistically, at most a handful. The cap is
#: there so a malformed client cannot write an array the derived-field trigger then has
#: to walk on every recalculation.
MAX_FORMATS = 8

Condition = Literal["new", "like_new", "good", "acceptable", "damaged"]
FormatCode = Annotated[str, StringConstraints(min_length=1, max_length=50)]

# Keep the wire vocabulary and the model's constants from drifting apart. Both are
# imported so this fails at import time rather than at the first bad request.
assert set(CONDITIONS) == {"new", "like_new", "good", "acceptable", "damaged"}


class CollectionItemFieldsMixin(BaseModel):
    """The fields a person edits, shared by the create and update bodies.

    Deliberately **not** every column on the table. AV specs are phase 3.7/23's, photos
    are 3.10/25's, listing status and eBay fields are 4.x/29's. Batch 24's barcode sits on
    the create body alone because it belongs to the scanner flow, not to an ordinary copy
    edit. Silently accepting any of these here would let both create and update write
    columns their shared form cannot show, read back or correct.
    """

    formats: list[FormatCode] = Field(min_length=1, max_length=MAX_FORMATS)
    #: The location cell as a person would write it — "Front 2nd shelf". When
    #: ``section``/``shelf`` are left out, the API parses them out of this with the same
    #: function that read the 1,857 imported rows, so a hand-added disc is filed exactly
    #: like an imported one.
    location: str | None = Field(default=None, max_length=255)
    #: Explicit overrides for the two normalised columns. Supplied by the pickers, which
    #: are built from ``GET /collection/facets`` and so can only offer real places.
    section: str | None = Field(default=None, max_length=100)
    shelf: str | None = Field(default=None, max_length=50)
    subCategory: str | None = Field(default=None, max_length=255)
    #: Batch U2 — which edition this disc is: "SteelBook", "Masters of Cinema". Free text,
    #: like the Wanted list's ``preferredEdition``, and the same length. **Unlike every
    #: other field here, leaving it out of an edit keeps it**: a client built before
    #: editions existed (a cached app, an edit queued offline) never sends one, and must not
    #: clear what the spec batch or a person wrote.
    edition: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)
    condition: Condition | None = None
    hasPlaybackIssues: bool = False
    playbackNotes: str | None = Field(default=None, max_length=2000)
    purchasePrice: Decimal | None = Field(default=None, ge=0, le=99999.99, decimal_places=2)
    purchaseSource: str | None = Field(default=None, max_length=255)
    purchaseDate: date | None = None

    @field_validator("formats")
    @classmethod
    def _known_and_unique_formats(cls, value: list[str]) -> list[str]:
        """Reject an unknown or repeated format code.

        The derived-field trigger ranks anything it does not recognise at 99, so an
        unknown code does not error — it silently makes the film's ``best_format_owned``
        wrong. Catching it at the wire is the only place it is still visible.
        """
        seen: list[str] = []
        for code in value:
            if code not in FORMAT_RANK:
                raise ValueError(f"Unknown format. Expected one of: {', '.join(FORMAT_RANK)}")
            if code in seen:
                raise ValueError(f"Duplicate format: {code}")
            seen.append(code)
        return seen

    @field_validator("edition")
    @classmethod
    def _edition_or_nothing(cls, value: str | None) -> str | None:
        """Browsing shows it, so blank is no edition rather than an invisible one."""
        text = (value or "").strip()
        return text or None

    @field_validator("purchaseDate")
    @classmethod
    def _not_in_the_future(cls, value: date | None) -> date | None:
        if value is not None and value > latest_plausible_today():
            raise ValueError("purchaseDate cannot be in the future")
        return value


class CollectionItemCreateRequest(CollectionItemFieldsMixin):
    """Add one disc.

    Exactly one of ``movieId`` and ``tmdbId`` identifies the film: ``movieId`` when it
    is already in the catalogue, ``tmdbId`` when the add form found it on TMDB and the
    row has to be created. Two fields rather than one polymorphic id because the two
    cases do genuinely different work and a caller always knows which it has.
    """

    movieId: uuid.UUID | None = None
    tmdbId: int | None = Field(default=None, gt=0)
    #: Present only when this create follows Batch 24's scanner confirmation. The edit
    #: body deliberately does not carry it: changing which physical product a row means
    #: is not an ordinary copy edit.
    barcode: str | None = Field(default=None, min_length=1, max_length=64)
    #: Set after the admin answers the duplicate prompt. Without it a film that already
    #: has a live copy is refused with 409 and the existing copies in the body — so the
    #: §3.5 confirmation holds even for a client that skipped the preflight check.
    confirmDuplicate: Literal["another_copy", "upgrade"] | None = None

    @model_validator(mode="after")
    def _exactly_one_film_reference(self) -> CollectionItemCreateRequest:
        """Reject a body naming both films, or neither.

        A ``field_validator`` on ``tmdbId`` looked equivalent and was not: pydantic does
        not run field validators for a field the request omits, so a body with *neither*
        id passed validation untouched and reached the router, which then had nothing to
        look the film up by. Caught in CI by this batch's own test — the "neither" case
        returned a 500 rather than a 422.
        """
        if (self.movieId is None) == (self.tmdbId is None):
            raise ValueError("Supply exactly one of movieId or tmdbId")
        return self


class CollectionItemUpdateRequest(CollectionItemFieldsMixin):
    """Replace the editable fields of one disc.

    A full replacement of a bounded field set rather than a patch: the edit form holds
    every one of these, so "absent" unambiguously means "the user cleared it" instead of
    being indistinguishable from "the client is an older build that never knew about it".
    """

    #: The ``updatedAt`` the edit was made against, if the caller knows it.
    #:
    #: This is what makes Batch 8's acceptance criterion — *"an edit made offline lands
    #: once reconnected **without overwriting a newer change**"* — mean anything. An
    #: offline edit can sit in the queue for hours; flushing it blind is last-write-wins,
    #: and last-write-wins is precisely the thing that criterion forbids. Phase 13.9 says
    #: "last-write-wins" and the batch's own acceptance contradicts it; the acceptance is
    #: newer and is what this implements (`DECISIONS.md` #42).
    #:
    #: Optional, because an online edit that has just read the row does not need it and a
    #: client that never goes offline should not have to care.
    baseUpdatedAt: UtcDatetimeIn | None = None


class CollectionItemResponse(BaseModel):
    """One disc, as the write endpoints return it.

    Carries ``movieId`` — which ``CollectionCopyResponse`` does not, because there the
    film is already the thing being looked at — so a client that just created an item
    knows which film's caches to refresh.
    """

    id: uuid.UUID
    movieId: uuid.UUID
    movieTitle: str
    formats: list[str]
    location: str | None = None
    section: str | None = None
    shelf: str | None = None
    locationLabel: str
    subCategory: str | None = None
    #: Batch U2.
    edition: str | None = None
    notes: str | None = None
    condition: str | None = None
    conditionUpdatedAt: UtcDatetime | None = None
    hasPlaybackIssues: bool
    playbackNotes: str | None = None
    purchasePrice: str | None = None
    purchaseSource: str | None = None
    purchaseDate: date | None = None
    listingStatus: str
    #: Batch 29 §4.2/§4.4. Null until the disc is listed. `listingPrice` is what it was
    #: advertised at — the number §4.2's "admin adjusts or accepts" settled on, kept so a
    #: sold disc records what it actually fetched rather than only that it went.
    ebayListingUrl: str | None = None
    listingPrice: str | None = None
    #: The value a later edit sends back as ``baseUpdatedAt``. Without it on the way out
    #: there is nothing for the offline queue to have based itself on.
    updatedAt: UtcDatetime
    deletedAt: UtcDatetime | None = None


class ExistingCopyResponse(BaseModel):
    """One copy already owned, as the duplicate prompt shows it.

    §3.5 asks for "existing formats and locations" — exactly these two fields plus
    enough to tell two copies of the same film apart.
    """

    id: uuid.UUID
    formats: list[str]
    locationLabel: str
    condition: str | None = None


class DuplicateCheckResponse(BaseModel):
    """Whether this film is already on a shelf, and what the prompt should offer.

    ``isUpgrade`` is what makes §3.5's acceptance criterion — "adding a 4K when Blu-ray
    exists triggers the **upgrade** prompt" — answerable without the web app
    re-implementing the format ranking that the database already enforces.
    """

    movieId: uuid.UUID | None = None
    movieTitle: str | None = None
    #: False when the film is not in the catalogue at all, or has no live copies.
    isDuplicate: bool
    existingCopies: list[ExistingCopyResponse] = Field(default_factory=list)
    #: True when the format being added outranks every format already owned.
    isUpgrade: bool = False
    #: The best format already owned, so the prompt can say "you own this on Blu-ray".
    bestFormatOwned: str | None = None


class TmdbSearchResultResponse(BaseModel):
    """A film the add form found on TMDB but the catalogue does not have yet."""

    tmdbId: int = Field(gt=0)
    title: str
    year: int | None = None
    overview: str
    posterPath: str | None = None
    #: True when a ``movies`` row already carries this ``tmdb_id`` — the add form uses
    #: it to route the choice down the ``movieId`` path instead of creating a duplicate.
    inCollection: bool = False
    movieId: uuid.UUID | None = None


class TmdbSearchResponse(BaseModel):
    query: str
    results: list[TmdbSearchResultResponse]


class TrashItemResponse(BaseModel):
    """One soft-deleted row, as §13.5's trash lists it."""

    id: uuid.UUID
    targetTable: str
    movieId: uuid.UUID
    movieTitle: str
    posterPath: str | None = None
    formats: list[str]
    locationLabel: str
    deletedAt: UtcDatetime


class TrashPageResponse(BaseModel):
    items: list[TrashItemResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    perPage: int = Field(ge=1)
    pages: int = Field(ge=0)


class AuditEntryResponse(BaseModel):
    """One audit row.

    ``actorName`` is resolved at read time from the joined profile and is ``None`` when
    the profile is gone — the row itself outlives it (`DECISIONS.md` #5), so the log
    still shows what happened even when it can no longer show who.
    """

    id: uuid.UUID
    actorId: uuid.UUID | None = None
    actorName: str | None = None
    #: The table's CHECK vocabulary (`models.admin_action.ACTION_TYPES`), declared so the web's
    #: closed enum and the API agree in the contract test (Batch X8).
    actionType: Literal["create", "update", "delete", "restore", "bulk_import"]
    targetTable: str
    targetId: str
    changes: dict[str, Any] | None = None
    createdAt: UtcDatetime


class AuditPageResponse(BaseModel):
    items: list[AuditEntryResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    perPage: int = Field(ge=1)
    pages: int = Field(ge=0)


class ListingUpdateRequest(BaseModel):
    """Move a disc between §3.4's listing states — Batch 29, phases 4.2 and 4.4.

    **One endpoint for every transition rather than a verb each.** "List for sale", "mark
    sold", "mark donated" and "put it back" are the same write with a different target
    state, and four endpoints would be four places to remember the audit row, the price
    and the guard. Phase 4.4's acceptance turns on a transition being *recorded*, not on
    which URL performed it.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["in_collection", "listed_for_sale", "sold", "donated"]
    #: What it is advertised at, or what it fetched. Kept through the sale: §4.2's "admin
    #: adjusts or accepts" produces a number, and a sold disc that records only *that* it
    #: went has thrown that number away.
    listingPrice: str | None = None
    ebayListingUrl: str | None = None

    @field_validator("listingPrice")
    @classmethod
    def _check_price(cls, value: str | None) -> str | None:
        return _validate_listing_price(value)


def _validate_listing_price(value: str | None) -> str | None:
    """A sale price, as a decimal string.

    The same shape as `wanted._validate_max_price`, and for the same reason: `Decimal`
    parses ``"NaN"`` and ``"Infinity"`` happily, and every later comparison against a NaN
    raises rather than answering — so the guard has to be `is_finite`, not `> 0`.
    """
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("listingPrice must be a decimal number") from exc
    if not parsed.is_finite():
        raise ValueError("listingPrice must be a real number")
    if parsed < 0:
        raise ValueError("listingPrice cannot be negative")
    if parsed >= Decimal("1000000"):
        raise ValueError("listingPrice is implausibly large")
    return value


#: Batch Y2's ceiling. Mark moving a pile of discs is tens; two hundred is a whole shelf
#: with room to spare, and keeps one request inside one short transaction.
MAX_MOVES = 200


class CollectionMoveEntry(BaseModel):
    """One disc and where it goes — Batch Y2 (`DECISIONS.md` #265).

    **Each entry carries its own place**, not one target for the whole request. A move
    sends the same place on every entry; "Move them back" sends each disc's own previous
    place, through the same endpoint, so the undo is not a second write path. The three
    place fields mean what they mean on the copy form, resolved by the same function.
    """

    model_config = ConfigDict(extra="forbid")

    itemId: uuid.UUID
    #: The ``updatedAt`` the disc was picked against. Required, unlike the edit's: a tray
    #: can sit on a phone for an afternoon, and a move made against an hours-old copy is
    #: exactly the overwrite #42 forbids.
    baseUpdatedAt: UtcDatetimeIn
    location: str | None = Field(default=None, max_length=255)
    section: str | None = Field(default=None, max_length=100)
    shelf: str | None = Field(default=None, max_length=50)


class CollectionMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moves: list[CollectionMoveEntry] = Field(min_length=1, max_length=MAX_MOVES)

    @field_validator("moves")
    @classmethod
    def _each_disc_once(cls, value: list[CollectionMoveEntry]) -> list[CollectionMoveEntry]:
        """Two entries for one disc would make the result depend on their order."""
        ids = [entry.itemId for entry in value]
        if len(set(ids)) != len(ids):
            raise ValueError("Each disc may appear only once")
        return value


class CollectionMoveResult(BaseModel):
    """What happened to one disc. A stale or missing disc does not stop the others."""

    itemId: uuid.UUID
    #: ``moved``: written, with an audit row. ``unchanged``: already there, nothing
    #: written. ``stale``: changed elsewhere after it was picked, left alone. ``not_found``:
    #: deleted, sold or never existed.
    status: Literal["moved", "unchanged", "stale", "not_found"]
    #: The disc as it now stands; for ``stale``, where it actually is. Null for
    #: ``not_found``.
    item: CollectionItemResponse | None = None


class CollectionMoveResponse(BaseModel):
    """Batch Y2's partial-success shape, as #6 allows a batch endpoint."""

    results: list[CollectionMoveResult]
    moved: int = Field(ge=0)
