"""The film entity and its cast/crew, per roadmap §3.2 and §3.3.

One row per unique film, populated from the spreadsheet import and enriched from TMDB.
TV series are single rows with ``is_tv = true`` — no per-episode tracking, matching how
the physical collection actually works.

Three columns here are **derived and never written by application code**:
``best_format_owned``, ``best_hdr_owned`` and ``best_audio_owned`` are recalculated by a
Postgres trigger on every ``collection_items`` change (`DECISIONS.md` #7). Writing them
from Python would race the trigger and lose.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin


class Movie(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "movies"

    #: TMDB's id, unique but **not** the primary key.
    #:
    #: The April schema made the TMDB id the primary key outright. That leaks a third
    #: party's identifier into every foreign key in the app and leaves nowhere to put a
    #: film TMDB does not know about, so §3.2 separates the two and this follows it.
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)

    #: A TV series' TMDB id — Batch Y3 (migration 056). TMDB numbers films and series
    #: separately, and ``tmdb_id`` is read as a film's everywhere, so a series keeps its id
    #: here. A row has at most one of the two; one with either is identified.
    tmdb_tv_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    imdb_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    #: Release year rather than the full date — §3.2's choice. The collection is browsed
    #: and filtered by decade, never by release day.
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Not listed in §3.2, kept because the search trigger weights it (weight B, between
    #: title and overview) and TMDB returns it for free. Dropping it would silently
    #: narrow full-text search against the behaviour the trigger tests assert.
    tagline: Mapped[str | None] = mapped_column(Text, nullable=True)

    poster_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tmdb_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    tmdb_vote_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Full genre objects for display; ``genre_ids`` is the GIN-indexed array the
    #: filters actually query. Both, because a card shows names and a filter matches ids.
    genres: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    genre_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)

    #: Top five cast, denormalised onto the row so a grid of 1,857 cards renders without
    #: joining ``movie_credits`` 1,857 times.
    top_cast_summary: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    trailer_key: Mapped[str | None] = mapped_column(String(50), nullable=True)

    #: §3.2 designs this for building a Letterboxd URL. TMDB does not supply it and no
    #: import populates it yet; the read surface falls back to a search URL.
    letterboxd_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)

    media_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_tv: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # --- Derived by trigger. Do not write from application code. ---------------
    best_format_owned: Mapped[str | None] = mapped_column(String(50), nullable=True)
    best_hdr_owned: Mapped[str | None] = mapped_column(String(50), nullable=True)
    best_audio_owned: Mapped[str | None] = mapped_column(String(50), nullable=True)

    #: Maintained by ``movies_update_search_vector()``, not by SQLAlchemy.
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    last_tmdb_sync_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Movie {self.title!r} ({self.year})>"


class MovieCredit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Normalised cast and crew, so "everything with Cary Grant in it" is one query."""

    __tablename__ = "movie_credits"

    #: ``CASCADE``: a credit describes its film and means nothing without it. Contrast
    #: ``collection_items.movie_id``, which is ``RESTRICT`` — a disc is a real object and
    #: must not vanish because its film row was removed.
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    person_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tmdb_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    #: cast · director · writer · producer · composer (§3.3). The April schema stored
    #: only 'cast' / 'crew' with the real job in a separate column, which made
    #: "films directed by X" a two-column query; §3.3's shape makes it one.
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    #: ``Text``, not §3.3's ``VARCHAR(255)``. A performer voicing many parts gets a
    #: slash-separated role list that runs past it — 300 characters for Dan
    #: Castellaneta on *The Simpsons Movie* — and the overflow rolled back the whole
    #: item, not just the credit. See migration 004.
    character_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<MovieCredit {self.person_name!r} as {self.role}>"
