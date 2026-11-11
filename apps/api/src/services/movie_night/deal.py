"""The films a night opens with — AE10's proposal B (#355).

**Ten, not thirty, and each there for a reason.** Of the 11 nights since 10 Sep, the one that
matched was eight films Craig put forward; the night dealt 30 random films ended with eight
added by Mark, one by Craig and no overlap. So a night now opens with up to ``REWATCH_SLOTS``
films someone in the night rated 4½ or 5 (Home's "Worth a rewatch", read per person), and the
rest films in neither person's diary, ten in all. Films people put forward sit on top, as
before; they are never dealt.

**"In neither diary" is not "unseen".** Alien and Ghostbusters are in neither diary, and Mark's
diary was empty after 14 Sep until his first sync (#354), so the app says what it knows: no
viewing logged by anyone in the night.

The order is the same shuffle as before (``md5(session || film)``): stable for one night,
different between nights, identical for everyone in it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import ColumnElement, Text, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_item import CollectionItem, owned_copy, owned_film
from src.models.movie import Movie
from src.models.movie_night import MovieNightSession
from src.models.watch_log import WatchLog

#: How many films a night is dealt, and how many of them may be someone's "Worth a rewatch".
DEAL_SIZE = 10
REWATCH_SLOTS = 4
#: Home's threshold for "Worth a rewatch" (`routers/highlights.TOP_RATING`): 4½ stars or 5.
WORTH_A_REWATCH = Decimal("4.5")
#: "Under two hours", inclusive. A film with no known running time is not under two hours.
SHORT_FILM_MINUTES = 120
FOUR_K = "4k_uhd"

DealtAs = Literal["worthARewatch", "inNeitherDiary"]


@dataclass(frozen=True)
class NightFilters:
    """The filters a night was started with, read from ``movie_night_sessions.filters``.

    The four AE10 filters replace the start form's "Nothing older than" box, which no night
    used. The older keys (``decadeFrom``, ``decadeTo``, ``minRating``) are still honoured, so a
    night stored with them reads the same as before.
    """

    under_two_hours: bool = False
    in_neither_diary: bool = False
    four_k: bool = False
    genre: str | None = None
    decade_from: int | None = None
    decade_to: int | None = None
    min_rating: float | None = None

    @classmethod
    def read(cls, filters: dict[str, Any] | None) -> NightFilters:
        raw = filters or {}

        def year(key: str) -> int | None:
            value = raw.get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) else None

        rating = raw.get("minRating")
        genre = raw.get("genre")
        return cls(
            under_two_hours=raw.get("underTwoHours") is True,
            in_neither_diary=raw.get("inNeitherDiary") is True,
            four_k=raw.get("fourK") is True,
            genre=genre.strip() if isinstance(genre, str) and genre.strip() else None,
            decade_from=year("decadeFrom"),
            decade_to=year("decadeTo"),
            min_rating=float(rating)
            if isinstance(rating, int | float) and not isinstance(rating, bool)
            else None,
        )


def _their_viewings(people: list[uuid.UUID]) -> list[ColumnElement[bool]]:
    """Live viewings of this film by somebody in ``people``.

    A viewing whose own TMDB id names another film is not evidence this one was watched (the
    namesake guard `details.people_history` applies), so it does not count either way.
    """
    return [
        WatchLog.movie_id == Movie.id,
        WatchLog.user_id.in_(people),
        WatchLog.deleted_at.is_(None),
        or_(
            WatchLog.tmdb_id.is_(None),
            Movie.tmdb_id.is_(None),
            WatchLog.tmdb_id == Movie.tmdb_id,
        ),
    ]


def watched_by(people: list[uuid.UUID]) -> ColumnElement[bool]:
    """Somebody in ``people`` has a live viewing of this film."""
    return exists(select(WatchLog.id).where(*_their_viewings(people)))


def rated_worth_a_rewatch(people: list[uuid.UUID]) -> ColumnElement[bool]:
    """Somebody in ``people`` rated this film 4½ or 5 on a live viewing."""
    return exists(
        select(WatchLog.id).where(
            *_their_viewings(people), WatchLog.personal_rating >= WORTH_A_REWATCH
        )
    )


def _filtered(filters: NightFilters, people: list[uuid.UUID]) -> list[ColumnElement[bool]]:
    """The shelf, less TV, narrowed by the night's filters."""
    return [
        Movie.deleted_at.is_(None),
        owned_film(),
        # The 1,852 films the sketch counted are the shelf less its TV series.
        or_(Movie.media_type.is_(None), Movie.media_type != "tv"),
        *night_filters(filters, people),
    ]


def night_filters(filters: NightFilters, people: list[uuid.UUID]) -> list[ColumnElement[bool]]:
    """What a night's filters ask of a film, for anything that deals within them: the night's
    shortlist here, and Feeling lucky on the night (`routers/lucky.py`)."""
    conditions: list[ColumnElement[bool]] = []
    if filters.under_two_hours:
        conditions.append(
            and_(Movie.runtime_minutes.is_not(None), Movie.runtime_minutes <= SHORT_FILM_MINUTES)
        )
    if filters.four_k:
        conditions.append(
            exists(
                select(CollectionItem.id).where(
                    CollectionItem.movie_id == Movie.id,
                    owned_copy(),
                    CollectionItem.formats.contains([FOUR_K]),
                )
            )
        )
    if filters.genre is not None:
        conditions.append(Movie.genres.contains([{"name": filters.genre}]))
    if filters.in_neither_diary and people:
        conditions.append(~watched_by(people))
    if filters.decade_from is not None:
        conditions.append(Movie.year >= filters.decade_from)
    if filters.decade_to is not None:
        conditions.append(Movie.year <= filters.decade_to)
    if filters.min_rating is not None:
        conditions.append(Movie.tmdb_rating >= filters.min_rating)
    return conditions


async def dealt_films(
    db: AsyncSession,
    *,
    session: MovieNightSession,
    people: list[uuid.UUID],
    limit: int = DEAL_SIZE,
) -> list[tuple[Movie, DealtAs]]:
    """Up to ``limit`` films for this night, with why each is there, best reasons first.

    ``people`` are the night's participants when it is dealt: their ratings make "Worth a
    rewatch", and their diaries decide "in neither diary". With nobody (a test's bare
    session), every film counts as in neither diary.
    """
    filters = NightFilters.read(session.filters)
    shuffle = func.md5(func.concat(str(session.id), func.cast(Movie.id, Text)))
    base = _filtered(filters, people)

    rewatch: list[Movie] = []
    if people and not filters.in_neither_diary:
        rewatch = list(
            (
                await db.execute(
                    select(Movie)
                    .where(*base, rated_worth_a_rewatch(people))
                    .order_by(shuffle)
                    .limit(min(REWATCH_SLOTS, limit))
                )
            )
            .scalars()
            .all()
        )

    unseen_query = select(Movie).where(*base)
    if people:
        unseen_query = unseen_query.where(~watched_by(people))
    unseen = list(
        (await db.execute(unseen_query.order_by(shuffle).limit(limit - len(rewatch))))
        .scalars()
        .all()
    )
    return [(movie, "worthARewatch") for movie in rewatch] + [
        (movie, "inNeitherDiary") for movie in unseen
    ]
