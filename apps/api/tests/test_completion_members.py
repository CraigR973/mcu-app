"""What counts as a member of a completion set — roadmap §11.1.

Split out from ``test_completion_sets.py`` because none of it needs a database: these are
assertions about which of TMDB's answers become members, which is where a wrong
denominator would come from. A set that reported "12 of 91" where the truth is "12 of 54"
would look entirely plausible, so every filter is pinned here rather than left to the
service's docstring.
"""

from __future__ import annotations

from src.services.completion import select_members
from src.tmdb.models import PersonMovieCredit, PersonMovieCredits

#: Hitchcock's real TMDB person id, as it appears in this collection's own credits.
HITCHCOCK = 2636


def _credit(
    tmdb_id: int,
    title: str,
    *,
    year: str | None = "1958",
    job: str | None = None,
    order: int | None = None,
    votes: int | None = 100,
) -> PersonMovieCredit:
    return PersonMovieCredit(
        id=tmdb_id,
        title=title,
        release_date=year,
        poster_path=f"/{tmdb_id}.jpg",
        vote_count=votes,
        job=job,
        order=order,
    )


def test_a_directors_set_holds_only_what_he_directed() -> None:
    """TMDB returns a director's producing and writing credits in the same array.

    "The Hitchcock films" means the ones he directed. Counting the rest would report
    "12 of 91" where the truth is "12 of 54" — a plausible-looking wrong number, which is
    the failure mode this whole batch has to avoid.
    """
    credits = PersonMovieCredits(
        id=HITCHCOCK,
        crew=[
            _credit(1, "Vertigo", job="Director"),
            _credit(2, "Psycho", job="Director"),
            _credit(3, "A Film He Only Produced", job="Producer"),
            _credit(4, "A Film He Only Wrote", job="Writer"),
        ],
    )
    # A set, not a list: these two share a year, so the documented ordering (year, then
    # title) puts Psycho first. What is under test here is *membership*; the ordering has
    # its own test below.
    assert {m.title for m in select_members(credits, "director")} == {"Vertigo", "Psycho"}


def test_a_person_credited_twice_on_one_film_is_counted_once() -> None:
    """TMDB lists a person once per job, so a writer-director appears twice."""
    credits = PersonMovieCredits(
        id=HITCHCOCK,
        crew=[
            _credit(1, "Rope", job="Director"),
            _credit(1, "Rope", job="Producer"),
            _credit(1, "Rope", job="Director"),
        ],
    )
    assert [m.id for m in select_members(credits, "director")] == [1]


def test_an_unreleased_film_is_not_a_missing_film() -> None:
    """A credit with no release date has not come out.

    Counting it as missing makes every set permanently incomplete by construction — the
    denominator grows every time a project is announced, and the bar never reaches 100%.
    """
    credits = PersonMovieCredits(
        id=HITCHCOCK,
        crew=[
            _credit(1, "Released", job="Director"),
            _credit(2, "Announced Only", year=None, job="Director"),
            _credit(3, "Empty Date", year="", job="Director"),
        ],
    )
    assert [m.title for m in select_members(credits, "director")] == ["Released"]


def test_a_credit_with_no_votes_is_treated_as_a_phantom() -> None:
    credits = PersonMovieCredits(
        id=HITCHCOCK,
        crew=[
            _credit(1, "A Real Film", job="Director"),
            _credit(2, "A Fragment TMDB Has Not Cleaned Up", job="Director", votes=0),
        ],
    )
    assert [m.title for m in select_members(credits, "director")] == ["A Real Film"]


def test_an_actors_set_stops_at_billed_roles() -> None:
    """An actor's set is films they were *in*, not every crowd scene."""
    credits = PersonMovieCredits(
        id=HITCHCOCK,
        cast=[
            _credit(1, "A Leading Role", order=0),
            _credit(2, "A Supporting Role", order=8),
            _credit(3, "A Walk-On", order=40),
            _credit(4, "Unbilled", order=None),
        ],
    )
    assert [m.title for m in select_members(credits, "actor")] == [
        "A Leading Role",
        "A Supporting Role",
    ]


def test_members_are_ordered_oldest_first() -> None:
    credits = PersonMovieCredits(
        id=HITCHCOCK,
        crew=[
            _credit(1, "Later", year="1960", job="Director"),
            _credit(2, "Earlier", year="1940", job="Director"),
        ],
    )
    assert [m.title for m in select_members(credits, "director")] == ["Earlier", "Later"]
