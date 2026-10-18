"""An owned film nothing has identified yet that a TMDB film may be — Batches T2 and X10.

A disc on the shelf whose film has no TMDB id is invisible to every check that asks "do we
hold this TMDB film?": on 10 Oct a scan of *Invasion of the Body Snatchers* (1978) met no
duplicate prompt beside an unidentified Blu-ray of that title (CT46-04). Search has asked
this since T2 ("Might be your copy of …"); since X10 (#280) the add form asks it too,
whichever way the film was found, through the duplicate check.

Titles are compared by the title-key module's catalogue level, so "Mummy, The (Brendan
Fraser)" may be "The Mummy". A key is a may, not an is: a known year on both sides must agree.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.services.title_key import Strictness, title_key, title_key_and_year


@dataclass(frozen=True)
class Unidentified:
    """An owned film with no TMDB id of either kind, its title made comparable."""

    movie_id: uuid.UUID
    title: str
    key: str
    year: int | None


async def unidentified_owned(db: AsyncSession) -> list[Unidentified]:
    """Owned films nothing has matched to TMDB yet.

    A few hundred rows at most, and falling as identification proceeds (1 on 18 Oct).
    """
    has_disc = exists(
        select(CollectionItem.id).where(CollectionItem.movie_id == Movie.id, owned_copy())
    )
    rows = await db.execute(
        select(Movie.id, Movie.title, Movie.year).where(
            Movie.tmdb_id.is_(None),
            # Batch Y3: a series identified is not a film still to identify.
            Movie.tmdb_tv_id.is_(None),
            Movie.deleted_at.is_(None),
            has_disc,
        )
    )
    films: list[Unidentified] = []
    for movie_id, title, year in rows.all():
        key, title_year = title_key_and_year(title)
        films.append(Unidentified(movie_id, title, key, year or title_year))
    return films


def lookalike(films: Sequence[Unidentified], title: str, year: int | None) -> Unidentified | None:
    """The first of ``films`` this title may be: one catalogue title, and no other year."""
    key = title_key(title, Strictness.TITLE)
    if not key:
        return None
    for film in films:
        if film.key != key:
            continue
        if film.year is None or year is None or film.year == year:
            return film
    return None
