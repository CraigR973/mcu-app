"""One physical (or digital) copy owned, per roadmap §3.4.

A film owned on both 4K and DVD is two rows; a combo pack sold as one box is one row
whose ``formats`` array holds both.

**``location``, ``section`` and ``shelf`` are the point of this table's existence.**
The April schema omitted all three even though §3.4 designed them and the spreadsheet
parser had always extracted them, so the import fell back to stuffing the raw location
string into ``notes`` and the structure was discarded for all 1,857 rows. The result was
a physical-media catalogue that could not answer "where is this disc?" — see
`STATUS.md` gotcha 0b. They are first-class columns here, and ``notes`` is returned to
meaning notes.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

#: The five areas the collection is stored in (§3.4). A location the parser does not
#: recognise — "Top Big Cabinet", "Black Box next to cabinet" — keeps its raw text in
#: :attr:`CollectionItem.location` and leaves ``section`` NULL rather than being forced
#: into a bucket it does not belong to.
SECTIONS = ("Front", "Back", "Lounge", "Garage", "Digital")

#: Format codes, best to worst. This ordering is duplicated in the
#: ``recalculate_movie_derived_fields`` trigger, which is where it is enforced; the
#: constant exists so the API layer can sort and label without re-deriving it.
FORMAT_RANK = ("4k_uhd", "blu_ray", "dvd", "download")

#: §3.4's condition vocabulary.
CONDITIONS = ("new", "like_new", "good", "acceptable", "damaged")

#: §3.4's listing states.
LISTING_STATUSES = ("in_collection", "listed_for_sale", "sold", "donated")


class CollectionItem(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "collection_items"

    #: ``RESTRICT``, not ``CASCADE``: the disc is a real object on a real shelf and must
    #: not be deleted as a side effect of tidying up a film row.
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    #: e.g. ``["blu_ray", "download"]`` for a combo pack. An array rather than a scalar
    #: because that is what the object is — one box holding two discs is one item, and
    #: the April schema's scalar column split it into two rows that then looked like two
    #: separate purchases. GIN-indexed for "everything I own on 4K".
    formats: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")

    # --- Where it actually is --------------------------------------------------
    #: The location cell exactly as entered — "Front 2nd shelf", "Top Big Cabinet",
    #: "E:\\Movies". Always populated when the source had one, so nothing is lost when
    #: the two normalised columns below cannot classify it.
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: One of :data:`SECTIONS`, or NULL when the location names somewhere the five
    #: sections do not cover.
    section: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    #: Normalised shelf within the section — "1st", "2nd", … NULL for a section that has
    #: no shelves, such as Garage or Digital.
    shelf: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    sub_category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: Genuine notes only. Before Batch 4 this column held the raw location string for
    #: every imported row and real notes for anything added by hand, with nothing to
    #: tell the two apart.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Purchase --------------------------------------------------------------
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    #: True when the price was looked up automatically rather than typed in, so the UI
    #: can avoid presenting a guess as a fact.
    price_is_estimate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    purchase_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Condition -------------------------------------------------------------
    condition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    condition_updated_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    has_playback_issues: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    playback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggest_exclude: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    photo_urls: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # --- AV specs --------------------------------------------------------------
    #: ``{"resolution": "2160p", "hdr": ["Dolby Vision"], "codec": "HEVC"}``. The ``hdr``
    #: array is what the ``best_hdr_owned`` trigger reads.
    video_specs: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    #: ``[{"language": "English", "format": "Dolby Atmos", "channels": "7.1.4"}]``. The
    #: ``format`` of each entry is what the ``best_audio_owned`` trigger reads.
    audio_specs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    special_features: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    region_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    release_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    specs_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    specs_last_synced_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # --- Listing ---------------------------------------------------------------
    listing_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="in_collection"
    )
    ebay_listing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    listing_price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    # --- Provenance ------------------------------------------------------------
    #: ``SET NULL``: who added an item is useful, but losing the profile must not take
    #: the item with it.
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    added_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    #: Set by the ``collection_items_soft_delete`` trigger, which turns a DELETE into an
    #: UPDATE of this column. That is also what lets the derived-field recalculation see
    #: a deletion at all — it rides the AFTER UPDATE branch.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CollectionItem {self.formats} @ {self.section} {self.shelf}>"
