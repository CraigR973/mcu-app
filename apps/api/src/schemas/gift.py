"""Wire models for gift links — Batch 27, §3.21, §6.26, §12.1, §12.2.

**The public response is a separate model from the admin one, on purpose.** They could
share a base and they must not: the admin view carries the slug, the view count and who
created it, and the whole risk of this feature is one of those fields reaching the public
page because a model was reused. Two models mean adding a field to one cannot leak it
through the other.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.wire import UtcDatetime, UtcDatetimeIn

FormatCode = Literal["4k_uhd", "blu_ray", "dvd", "download"]


class GiftFilterConfig(BaseModel):
    """§3.21's "optional filters (max price, genres, formats)", as a closed vocabulary.

    ``extra="forbid"``, like `SmartCollectionFilters`, and for a sharper reason: this blob
    is read by an **unauthenticated** endpoint. A key that survived into JSONB and was then
    interpreted somewhere else would be a stranger-facing query built from stored input.
    """

    model_config = ConfigDict(extra="forbid")

    maxPrice: Annotated[str | None, Field(max_length=12)] = None
    formats: Annotated[list[FormatCode], Field(max_length=4)] = []

    @field_validator("maxPrice")
    @classmethod
    def _check_price(cls, value: str | None) -> str | None:
        from src.schemas.wanted import _validate_max_price

        return _validate_max_price(value)

    def stored(self) -> dict[str, object]:
        return self.model_dump(exclude_none=True, mode="json")


class GiftLinkFieldsMixin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=255)]
    filterConfig: GiftFilterConfig = GiftFilterConfig()
    expiresAt: UtcDatetimeIn | None = None
    isActive: bool = True


class GiftLinkCreateRequest(GiftLinkFieldsMixin):
    pass


class GiftLinkUpdateRequest(GiftLinkFieldsMixin):
    pass


class GiftLinkResponse(BaseModel):
    """The **admin** view. Carries the slug, the counts and the provenance."""

    id: uuid.UUID
    slug: str
    #: The path, not an absolute URL — the API does not know its own public origin without
    #: trusting the `Host` header, which is attacker-controlled. Same reasoning as Batch
    #: 17's calendar subscription.
    path: str
    title: str
    filterConfig: GiftFilterConfig
    expiresAt: UtcDatetime | None
    viewCount: int
    lastViewedAt: UtcDatetime | None
    isActive: bool
    #: False when deactivated, expired or deleted — so the list can say "this link has
    #: stopped working" rather than leaving someone to work it out from three fields.
    isUsable: bool
    createdAt: UtcDatetime


class GiftLinkListResponse(BaseModel):
    items: list[GiftLinkResponse]
    total: int


class GiftFilmResponse(BaseModel):
    """One film on the **public** page.

    Everything here is something a person buying a present needs. Nothing here says whether
    the recipient already owns it, what they have watched, when they added it, or who they
    are.
    """

    title: str
    year: int | None
    posterPath: str | None
    preferredFormat: str | None
    maxPrice: str | None
    currency: str
    #: Where to buy it. Built from `retailers.search_url_template`, which is http/https by
    #: CHECK — an admin-supplied URL rendered onto a public page.
    retailerLinks: list[GiftRetailerLink]


class GiftRetailerLink(BaseModel):
    name: str
    url: str


class GiftPageResponse(BaseModel):
    """The **public** view. Deliberately not a superset of anything.

    No slug (the caller has it), no view count, no creator, no ids of any kind, and no
    indication of what the recipient already owns.
    """

    title: str
    films: list[GiftFilmResponse]
    total: int
    #: Echoed so the page can show what it is filtered by, which §12.2 asks for as
    #: "basic filters visible to viewer".
    filterConfig: GiftFilterConfig


GiftFilmResponse.model_rebuild()
