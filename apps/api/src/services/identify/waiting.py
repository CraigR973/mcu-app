"""Which titles are still to identify — one definition for the Archive and the series pass.

#271 gave the Archive's "Still to identify" filter its rule; Batch Y3's series pass
(:mod:`src.services.identify.series_pass`) proposes a series for exactly those titles. The rule
lives here so the two cannot drift: the list Mark works through and the list the pass works
through are the same list.
"""

from __future__ import annotations

from sqlalchemy import and_, exists, select
from sqlalchemy.sql.elements import ColumnElement

from src.models.identify import IdentifyLookup
from src.models.movie import Movie


def still_to_identify() -> ColumnElement[bool]:
    """A title TMDB has matched to neither a film nor a series, and nobody has set aside as
    not a film.

    #271 also left out the series T9 set aside, because the app could identify films only and
    offering them invited a wrong match. Batch Y3 identifies series, so they are listed again,
    to be identified as the series they are. A skipped film is still listed.
    """
    not_a_film = exists(
        select(IdentifyLookup.id).where(
            IdentifyLookup.movie_id == Movie.id,
            IdentifyLookup.status == "set_aside",
            IdentifyLookup.set_aside_as == "not_film",
        )
    )
    return and_(Movie.tmdb_id.is_(None), Movie.tmdb_tv_id.is_(None), ~not_a_film)
