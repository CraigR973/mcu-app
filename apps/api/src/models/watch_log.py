"""Personal watch history, per roadmap §3.7.

One row per viewing, not per film: watching *Heat* three times is three rows, which is
what makes ``is_rewatch`` and the on-this-day memories of Batch 37 possible at all.

**This table had no owning phase.** §3.7 designs it, §6.5 lists its two endpoints, and
Batch 37 is defined as "inert until ``watch_log`` has ~a year of history" — but no phase
in §16 ever created it, so the watched-status facet Batch 6 was asked for had nothing
behind it. Built here by owner decision (`DECISIONS.md` #35).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

#: §3.7's rating scale — half-stars from 0.5 to 5.0. Deliberately not TMDB's 0–10:
#: these are two different judgements and a shared scale would invite averaging them.
RATING_MIN = Decimal("0.5")
RATING_MAX = Decimal("5.0")


class WatchLog(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "watch_log"

    #: ``RESTRICT``, matching :attr:`CollectionItem.movie_id` rather than
    #: ``MovieCredit``'s ``CASCADE``. A credit is a fact *about* the film and dies with
    #: it; a watch is something a person did, and must not be swept away as a side
    #: effect of tidying a film row.
    #:
    #: The app has one hard-delete path for a movie — the identify flow, which merges a
    #: freshly identified row into an existing one and deletes the source. ``RESTRICT``
    #: is what forces that path to repoint these rows explicitly instead of losing them
    #: silently, exactly as it already does for ``collection_items``.
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    #: ``CASCADE``: a watch with no watcher means nothing. Contrast
    #: ``collection_items.added_by``, which is ``SET NULL`` because the disc outlives
    #: whoever catalogued it.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: A ``DATE``, per §3.7, and the one column here that is not a ``*_utc`` timestamp.
    #: People remember watching something "on Saturday", not at an instant, and a date
    #: keeps that answer stable regardless of the timezone the row is read back in.
    watched_at: Mapped[date] = mapped_column(Date, nullable=False)

    #: False = first watch. Set by the caller rather than derived, because a log entered
    #: after the fact for a film watched years ago should not be called a rewatch just
    #: because an earlier row happens to exist.
    is_rewatch: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    #: 0.5–5.0 in half-star steps, or NULL for a watch logged without an opinion.
    personal_rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1), nullable=True)

    review: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Batch S8. The Letterboxd viewing this row came from, or NULL for a watch logged by
    #: hand in the app.
    #:
    #: **The idempotency key for every imported watch, and it is deliberately the *bare*
    #: id.** The diary CSV calls it `ViewingId`; the public RSS feed wraps the same number
    #: as `letterboxd-watch-<id>` in its `<guid>`. Storing what they have in common is
    #: what stops S5's feed re-importing a viewing S8's file already wrote
    #: (`DECISIONS.md` #159, #161).
    #:
    #: A rewatch on a later date is a *different* viewing and correctly becomes a second
    #: row — which is what `is_rewatch` is for.
    letterboxd_viewing_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    #: Batch X5. The TMDB film the viewing was of, as Letterboxd's feed names it (or as the
    #: diary backfill identified it): what the watch is *of*, kept apart from ``movie_id``,
    #: which is the row it hangs on. When the two disagree, the row is the wrong film
    #: (CT46-02), and this is how it can be told. NULL for a watch logged by hand, and for
    #: a file import that matched by title alone.
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Soft delete, so an accidental log is recoverable and §13.5's Trash has something
    #: to show. Every read path filters on it, and the watched facet counts only live
    #: rows.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<WatchLog {self.movie_id} by {self.user_id} on {self.watched_at}>"
