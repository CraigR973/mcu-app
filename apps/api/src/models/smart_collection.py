"""Saved dynamic filter sets — roadmap §3.23, the iTunes-smart-playlist idea of §6.31.

**The filters are stored as JSONB and evaluated into SQL, which is the one genuinely
dangerous thing in this batch.** A blob that becomes a query is an injection surface and,
more quietly, a divergence surface: a saved collection that means something slightly
different from the same filters typed into the filter bar is wrong in a way no error ever
reports.

Both are closed off the same way. The blob is validated on the way in by
:class:`src.schemas.collections.SmartCollectionFilters`, whose fields *are* the filter
vocabulary ``GET /movies`` already accepts, and evaluated on the way out by
:func:`src.routers.movies.movie_page` — the same function that serves ``GET /movies``.
There is no second predicate builder to drift, and an unknown key never reaches the
database because it never survives validation.

Nothing is materialised. §3.23: *"Evaluated at query time — no materialisation."* That is
also what makes "updates live" true rather than a claim.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

#: The icons a collection may carry in the sidebar. A closed set, because the value is
#: written by a user and rendered as a component name: the web app maps these to real
#: lucide imports, and an open vocabulary would mean either a dynamic import of an
#: attacker-chosen name or a silently blank icon. Nine is enough to tell nine
#: collections apart, which is the entire job.
SMART_COLLECTION_ICONS = (
    "sparkles",
    "star",
    "heart",
    "clapperboard",
    "disc",
    "eye",
    "flame",
    "bookmark",
    "layers",
)

#: What a saved collection may be sorted by — the same three the collection views offer.
SMART_COLLECTION_SORTS = ("title", "year", "rating")
SMART_COLLECTION_ORDERS = ("asc", "desc")


class SmartCollection(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "smart_collections"

    #: ``CASCADE``: §3.23 calls these "private by default" and scopes every read to the
    #: caller, so a collection with no owner is unreachable by construction.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    icon: Mapped[str] = mapped_column(String(50), nullable=False, server_default="sparkles")

    #: Validated against :class:`~src.schemas.collections.SmartCollectionFilters` before
    #: it is ever written. Stored with its ``None`` fields dropped, so the JSON says only
    #: what the collection actually constrains.
    filters: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    sort_by: Mapped[str] = mapped_column(String(50), nullable=False, server_default="title")
    sort_order: Mapped[str] = mapped_column(String(10), nullable=False, server_default="asc")

    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<SmartCollection {self.name!r} of {self.user_id}>"
