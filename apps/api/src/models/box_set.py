"""Physical box sets and the discs that belong to them — roadmap §3.24 and §3.25.

§6.32's premise is that a box set is currently *"captured only as a ``sub_category``
string"*, and the live data bears that out: 627 of the 1,857 items carry one, across 106
distinct values, and they mix genuine boxes ("The James Bond Collection Box Set",
"Columbia Noir #4") with director and actor groupings ("Clint Eastwood", 64 items) that
are not boxes at all. A string cannot tell those apart, cannot say how many discs the box
was sold with, and cannot link volume 4 to volumes 1–3.

**Nothing here reads or rewrites ``sub_category``.** The column stays exactly as
imported. A box set is built by an admin choosing items, which is the only way to get the
distinction between "these six discs came in one box" and "these sixty-four films happen
to star the same person" right.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

#: ``admin_actions.target_table`` for a box set, mirroring
#: :data:`src.models.admin_action.COLLECTION_ITEMS_TABLE`.
BOX_SETS_TABLE = "box_sets"


class BoxSet(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """One box, or one series that boxes belong to."""

    __tablename__ = "box_sets"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: Publisher — Criterion, Arrow, Indicator. Free text rather than a vocabulary:
    #: the live data already contains labels this app has never heard of, and refusing
    #: one at the point of cataloguing would lose information to no benefit.
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    volume_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: §3.24's self-FK. One row stands for the series ("Columbia Noir") and each volume
    #: points at it, which is what makes "know when new volumes are released" answerable
    #: later without a second table.
    #:
    #: ``SET NULL`` rather than ``CASCADE``: deleting the series row must not take four
    #: volumes of real discs with it. Chains are refused at the API — a series parent
    #: may not itself have a parent — so this is one level deep by construction and a
    #: reader never has to walk it.
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("box_sets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    #: How many films the box was sold with. **Nullable on purpose**: an unknown
    #: expected count must not be rendered as "6 of 0" or silently completed. §11.4's
    #: "3 of 4" needs a denominator, and inventing one is the failure mode.
    expected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    poster_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Soft delete, per the house convention and because a box set groups real discs:
    #: an accidental delete on a 20-item set should be recoverable. Nothing surfaces
    #: these in the trash yet — §13.5's Trash is Batch 15, and widening
    #: ``TRASH_TABLES`` is that batch's job, not this one's.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<BoxSet {self.name!r}>"


class BoxSetItem(Base):
    """§3.25's junction. Composite PK on ``(box_set_id, collection_item_id)``."""

    __tablename__ = "box_set_items"

    #: ``CASCADE``: the junction row is a statement about a box that no longer exists.
    #: Contrast ``collection_item_id`` — the disc outlives any grouping of it.
    box_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("box_sets.id", ondelete="CASCADE"),
        primary_key=True,
    )

    #: ``CASCADE`` as well, but for the opposite reason: ``collection_items`` are soft
    #: deleted, so this only fires for the genuinely destructive path Batch 7's audit
    #: test exercises. A membership row pointing at a row that no longer exists would
    #: make every completion count wrong.
    collection_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_items.id", ondelete="CASCADE"),
        primary_key=True,
    )

    #: Position in the box. Nullable because plenty of boxes do not number their discs.
    disc_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<BoxSetItem {self.box_set_id}/{self.collection_item_id}>"
