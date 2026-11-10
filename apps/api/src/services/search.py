"""Search that finds what you mean — AE7 (#355).

The search page and the top bar ask one question: which films on the shelf does this mean? A
title answers first: the same title, then one that starts so, then one close to it (a typo, a
missing accent or hyphen). A person answers next: a director, a cast member or a character whose
name is close to it ("hitchcok"; "bond" for James Bond), the best billed first. The full-text match
on cast, crew, genre and plot answers last, as it alone did before.

Every comparison folds both sides with the database's own ``search_fold()`` (migration 077):
lower case, no accents, every run of anything but letters and digits one space. "Spider-Man" and
"spiderman" also meet with the spaces taken out. ``pg_trgm``'s ``<%`` operator (word similarity,
its threshold 0.6 by default) is the "close" test, and the trigram indexes serve it.
"""

from __future__ import annotations

import re

from sqlalchemy import ColumnElement, and_, case, func, literal, or_, select, union
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import Select

from src.models.movie import Movie, MovieCredit

#: Names people search by that no title contains. A short fixed list, reviewed with the change.
ALIASES: dict[str, str] = {
    "lotr": "the lord of the rings",
    "hp": "harry potter",
    "sw": "star wars",
    "esb": "the empire strikes back",
    "rotj": "return of the jedi",
    "t2": "terminator 2",
    "mi": "mission impossible",
    "bttf": "back to the future",
    "potc": "pirates of the caribbean",
}

#: The order answers come in: a title the same, one starting so, one close; a person; the text.
EXACT, STARTS, CLOSE, PERSON, TEXT = 1, 2, 3, 4, 5


def searched(query: str) -> str:
    """The query as searched: an alias's title, else the query itself."""
    return ALIASES.get(re.sub(r"[^a-z0-9]+", "", query.casefold()), query)


def _fold(
    value: ColumnElement[str] | InstrumentedAttribute[str] | InstrumentedAttribute[str | None],
) -> ColumnElement[str]:
    return func.search_fold(value)


def _close(query: ColumnElement[str], target: ColumnElement[str]) -> ColumnElement[bool]:
    return query.op("<%")(target)


def ranked(query: str, *filters: ColumnElement[bool]) -> Select[tuple[Movie, int, float, float]]:
    """Every film the query finds under ``filters``, with its tier and two scores, best first.

    Two steps, so a keystroke stays quick: which films it could mean, each way through its own
    index (folded titles and people's names by trigram, the text by its full-text index); then
    how well, for those films alone. Within a tier: titles by how much of the title the query is
    (so "godf" puts The Godfather before Part II), people by how close the name is and then
    billing (a director or the lead before a supporting part, so the Bond films come before Joan
    of Arc's Ward Bond), the text by its full-text rank. Then the title, the year and the id, so
    a tie always reads the same.
    """
    term = searched(query)
    q = _fold(literal(term))
    some = q != ""

    # Which films it could mean. Each condition is written as its index is, to be served by it.
    title = _fold(Movie.title)
    original_title = _fold(Movie.original_title)
    by_title = select(Movie.id.label("id")).where(
        some,
        or_(
            title.startswith(q),
            _close(q, title),
            original_title.startswith(q),
            _close(q, original_title),
        ),
    )
    person = _fold(MovieCredit.person_name)
    character = _fold(MovieCredit.character_name)
    people = (
        select(
            MovieCredit.movie_id.label("movie_id"),
            func.max(
                func.greatest(func.word_similarity(q, person), func.word_similarity(q, character))
            ).label("closeness"),
            func.min(
                case(
                    (MovieCredit.role == "director", 0),
                    (MovieCredit.role == "cast", 1 + func.coalesce(MovieCredit.display_order, 99)),
                    else_=200,
                )
            ).label("billing"),
        )
        .where(some, or_(_close(q, person), _close(q, character)))
        .group_by(MovieCredit.movie_id)
        .cte("people")
    )
    tsquery = func.websearch_to_tsquery("english", term)
    by_text = select(Movie.id.label("id")).where(Movie.search_vector.op("@@")(tsquery))
    found = union(by_title, select(people.c.movie_id.label("id")), by_text).subquery("found")

    # How well, for those films alone: the same title also without a leading article, and with
    # the spaces taken out ("spiderman" is Spider-Man).
    original = func.coalesce(original_title, "")
    bare = func.regexp_replace(title, "^(the|a|an) ", "")
    names = (title, original, bare)
    compact = tuple(func.replace(name, " ", "") for name in names)
    compact_q = func.replace(q, " ", "")
    exact = and_(
        some, or_(*(name == q for name in names), *(name == compact_q for name in compact))
    )
    starts = and_(
        some,
        or_(
            *(name.startswith(q) for name in names),
            *(name.startswith(compact_q) for name in compact),
        ),
    )
    close = and_(some, or_(_close(q, title), _close(q, original)))
    named = people.c.movie_id.is_not(None)
    tier = case(
        (exact, EXACT),
        (starts, STARTS),
        (close, CLOSE),
        (named, PERSON),
        else_=TEXT,
    ).label("tier")
    word = func.greatest(func.word_similarity(q, title), func.word_similarity(q, original))
    whole = func.greatest(func.similarity(q, title), func.similarity(q, original))
    one = case(
        (or_(exact, starts, close), word),
        (named, people.c.closeness),
        else_=func.ts_rank_cd(Movie.search_vector, tsquery),
    ).label("rank_one")
    two = case(
        (or_(exact, starts, close), whole),
        (named, -people.c.billing),
        else_=0.0,
    ).label("rank_two")
    return (
        select(Movie, tier, one, two)
        .join(found, found.c.id == Movie.id)
        .outerjoin(people, people.c.movie_id == Movie.id)
        .where(*filters)
        .order_by(tier, one.desc(), two.desc(), func.lower(Movie.title), Movie.year, Movie.id)
    )
