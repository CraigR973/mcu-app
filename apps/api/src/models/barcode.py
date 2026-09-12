"""A barcode somebody has confirmed the meaning of — Batch 24, Phase 3.4.

The first leg of §3.4's *"try cached mapping, then eBay/Amazon UPC search, then TMDB"*
chain, and the only one that cannot be wrong: a row here exists because a person looked at
the candidates and picked one.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

BARCODE_LOOKUPS_TABLE = "barcode_lookups"

#: Which leg of the chain produced the answer that was confirmed. Recorded rather than
#: inferred, so a run of wrong-edition matches can be traced to the leg that caused them —
#: the batch's risk note expects exactly that failure.
BARCODE_SOURCES = ("collection", "ebay", "tmdb", "manual")


class BarcodeLookup(Base, UUIDPrimaryKeyMixin):
    __tablename__ = BARCODE_LOOKUPS_TABLE

    barcode: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    #: ``SET NULL``: the mapping outlives the film row it points at, which is why
    #: ``tmdb_id`` and ``title`` sit beside it rather than being read through the FK.
    movie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="SET NULL"), nullable=True
    )
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)

    confirmed_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<BarcodeLookup {self.barcode} -> {self.title!r}>"
