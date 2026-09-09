"""Cached reference filmographies for completion tracking — roadmap §3.15.

A completion set answers one question: *of everything that belongs in this group, how much
of it is on the shelf?* "You own 12 of the 54 films Hitchcock directed."

**The members are cached, and that is the entire point of the table.** The alternative is
asking TMDB for a filmography every time the insights page is opened, which would make a
page of 25 sets 25 API calls and would put the whole feature behind TMDB being up.
§3.15's own note says the same: *"Enables fast completion queries ... by intersecting
member_tmdb_ids with the movies table."*

**Where the sets come from is decided by the collection, not by a list someone typed.**
`movie_credits` already knows that this collection holds 26 Clint Eastwood films and 12
Hitchcocks, with real TMDB person ids attached. Seeding from that means every set is one
this collection has a stake in, and there is no name-matching step to get wrong — which
matters, because `STATUS.md` gotcha 1b is the record of what fuzzy TMDB matching did to
this app once already.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

#: §3.15's vocabulary. Two of the six have a producer in Batch 13 — ``director`` and
#: ``actor``, both derived from ``movie_credits``.
#:
#: ``franchise`` needs TMDB's ``belongs_to_collection``, which the ``movies`` table does
#: not store; learning it for the 1,086 identified films is a column plus a backfill of
#: 1,086 API calls, which is its own piece of work rather than a corner of this one.
#: ``award`` has **no source at all**: TMDB has no awards API, so a Best Picture set would
#: have to be typed by hand — which is what ``curated_list`` is for. ``box_set`` is Batch
#: 12's `box_sets` table, a different thing: a box is an object you own, a completion set
#: is a list you are measured against.
SET_TYPES = ("director", "actor", "franchise", "box_set", "award", "curated_list")

#: How many owned films a person needs before they are worth tracking. Below three, "you
#: own 1 of 42" is noise rather than an insight — the collection has 117 directors above
#: this line and several hundred below it.
MIN_OWNED_FOR_SET = 3


class CompletionSet(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "completion_sets"

    set_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    #: The identifier *within* the type — a TMDB person id for a director or actor, a
    #: slug for a curated list. Unique with ``set_type``, which is what makes the refresh
    #: idempotent: a second run updates Hitchcock's row rather than adding a second one.
    set_key: Mapped[str] = mapped_column(String(255), nullable=False)

    set_name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: Every TMDB movie id in the set. Intersected with ``movies.tmdb_id`` to count what
    #: is owned, which is a single query for the whole page rather than one per set.
    member_tmdb_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, server_default="{}"
    )

    #: ``{"members": [{tmdbId, title, year, posterPath}], ...}``.
    #:
    #: The display half of the membership, cached alongside the ids. §11.2 asks for a
    #: "missing films list **with posters**", and a missing film is by definition one this
    #: database has no row for — so without this the page would need a TMDB call per
    #: missing film, on every view, for films nobody owns.
    set_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    last_refreshed: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CompletionSet {self.set_type}:{self.set_key} {self.set_name!r}>"


def member_display(metadata: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """The cached display rows, keyed by TMDB id.

    Tolerant of a row written before a field existed: a set refreshed by an older version
    of the job should render with whatever it has rather than 500 the insights page.
    """
    members = metadata.get("members")
    if not isinstance(members, list):
        return {}
    out: dict[int, dict[str, Any]] = {}
    for member in members:
        if isinstance(member, dict) and isinstance(member.get("tmdbId"), int):
            out[member["tmdbId"]] = member
    return out
