"""AG5 (MK53-03, CT52-04): a want's shop prices are its film's, and no other film's.

The shop job matched a listing to a want by its title's words, and a year is one of the words a
shop adds, so 101 Films' "Bad Lieutenant (1992)" was priced 27 times as the 2009 film's want,
and pushed once. One rule now says when a listing is another film's (``extract.another_film``):
the shop job applies it to each listing it reads, and :func:`rejudge_stored` applies it to the
stored ones at the start of each run, so a want whose film is corrected, or that has just asked
which film it is, is judged by its film as it is now. A listing judged another film's is kept,
marked (``price_checks.another_film``), and never read as a price (``PRICED``).

A want that has asked "which film?" (:func:`wants_asked`) has a title two films share, so a
listing naming no year is not its price either: the shops' *Dead Man's Shoes* is the 2004
film's disc, and the want is the 1940 film's.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Final

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.assigned_review import AssignedReview
from src.models.movie import Movie
from src.models.price_check import ANOTHER_YEAR, PriceCheck
from src.models.wanted import WantedItem
from src.services.scraping.extract import BRACKETED_YEAR, another_film

logger = structlog.get_logger(__name__)

#: The question that asks which film a want is (``services/assigned_reviews.py``).
WANT_QUESTION: Final = "wanted_identity"


async def wants_asked(db: AsyncSession) -> set[uuid.UUID]:
    """Wants with a "which film?" question, answered or not: their title is two films'."""
    rows = await db.scalars(
        select(AssignedReview.target_id).where(
            AssignedReview.kind == WANT_QUESTION, AssignedReview.deleted_at.is_(None)
        )
    )
    return set(rows.all())


@dataclass
class Rejudged:
    """What one pass over the stored listings changed, by the reason each now has."""

    hidden: Counter[str] = field(default_factory=Counter)
    shown: int = 0
    #: Hidden rows by want, for the log and the owner's count.
    by_want: Counter[uuid.UUID] = field(default_factory=Counter)

    @property
    def changed(self) -> int:
        return sum(self.hidden.values()) + self.shown


async def rejudge_stored(db: AsyncSession) -> Rejudged:
    """Judge every stored listing of a want by the want's film as it is now; flush the changes.

    The same rule as a new listing's, so a stored price and tonight's never disagree. A listing
    is shown again when the rule no longer finds it another film's, as when a want's film is
    corrected to the one the shop lists. Only the marker changes: nothing is deleted.
    """
    asked = await wants_asked(db)
    rows = (
        await db.execute(
            select(PriceCheck, WantedItem.id, Movie.year)
            .join(WantedItem, WantedItem.id == PriceCheck.wanted_id)
            .join(Movie, Movie.id == WantedItem.movie_id)
        )
    ).all()
    result = Rejudged()
    for check, want_id, year in rows:
        verdict = another_film(check.title_snapshot, year, needs_year=want_id in asked)
        if verdict == check.another_film:
            continue
        check.another_film = verdict
        if verdict is None:
            result.shown += 1
        else:
            result.hidden[verdict] += 1
            result.by_want[want_id] += 1
    if result.changed:
        await db.flush()
        logger.info(
            "shop_listings_rejudged",
            hidden=dict(result.hidden),
            shown=result.shown,
            by_want={str(want): count for want, count in result.by_want.items()},
        )
    return result


def other_film_label(title: str, year: int) -> str:
    """ "Bad Lieutenant (1992)" from "Bad Lieutenant (1992) (Standard Edition) (4K-UHD)"."""
    for match in BRACKETED_YEAR.finditer(title):
        if int(match.group(1)) == year:
            name = title[: match.start()].strip(" -–:|")
            return f"{name} ({year})" if name else title
    return title


@dataclass(frozen=True)
class OtherFilm:
    """A year a want's shop listings name that is not its film's, and who lists it."""

    year: int
    label: str
    shops: tuple[str, ...]


async def other_films(db: AsyncSession, want_id: uuid.UUID) -> list[OtherFilm]:
    """The other years a want's stored shop listings name, oldest year first."""
    rows = (
        await db.execute(
            select(PriceCheck.title_snapshot, PriceCheck.retailer_name_snapshot)
            .where(PriceCheck.wanted_id == want_id, PriceCheck.another_film == ANOTHER_YEAR)
            .order_by(PriceCheck.checked_at.desc())
        )
    ).all()
    labels: dict[int, str] = {}
    shops: dict[int, set[str]] = {}
    for title, shop in rows:
        for found in {int(year) for year in BRACKETED_YEAR.findall(title or "")}:
            labels.setdefault(found, other_film_label(title or "", found))
            shops.setdefault(found, set()).add(shop)
    return [OtherFilm(year, labels[year], tuple(sorted(shops[year]))) for year in sorted(labels)]
