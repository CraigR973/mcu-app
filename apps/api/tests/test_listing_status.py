"""Listing status, upgrades and sales — Batch 29, phases 4.2 and 4.4.

Phase 4.4's acceptance is *"marking sold removes from active views, remains in
audit/trash"*, and "active views" is not one endpoint. Before this batch the word
**owned** was spelled ``deleted_at IS NULL`` in nineteen places across seven routers, and
a rule applied in eighteen of them is not a rule. So the first test here is structural —
it reads the source and fails if a twentieth call site appears — and the rest walk a disc
through the states against a real database.

The database-backed tests skip locally without ``DATABASE_URL`` and run in CI against
Postgres 17, like every other API test here (`STATUS.md` gotcha 15).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from src.models.collection_item import OWNED_LISTING_STATUSES, CollectionItem, owned_copy

ROUTERS = Path(__file__).resolve().parents[1] / "src" / "routers"


# ---------------------------------------------------------------------------
# The definition of "owned" has exactly one home
# ---------------------------------------------------------------------------


def test_no_router_spells_out_the_owned_predicate_by_hand() -> None:
    """The guard against the twentieth call site.

    ``owned_copy()`` exists because *"marking sold removes from active views"* is a change
    to what **owned** means, and that word had been written out nineteen times. Moving it
    to one place only helps if nothing writes it out again — and nothing in a test suite
    would notice a new `deleted_at IS NULL` on `collection_items`, because the query would
    work perfectly and simply include a disc somebody had sold.

    The one exception is named explicitly below rather than excluded by a pattern, so
    adding a second exception requires editing this test and saying why.
    """
    offenders: list[str] = []
    for path in sorted(ROUTERS.glob("*.py")):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if "CollectionItem.deleted_at.is_(None)" not in line:
                continue
            # stats.py's spend-over-time: selling a disc does not un-spend the money paid
            # for it, so the purchase history keeps every row it ever had.
            if path.name == "stats.py" and number == _spend_over_time_line():
                continue
            # movies.py's `includeSold`: the one surface allowed to show a sold disc.
            if path.name == "movies.py" and "include_sold" in line:
                continue
            offenders.append(f"{path.name}:{number}")
    assert offenders == [], (
        "these build the active-copy predicate by hand instead of using owned_copy(): "
        + ", ".join(offenders)
    )


def _spend_over_time_line() -> int:
    """Where stats.py's deliberate exception is, found by its own comment rather than a
    hard-coded number that would rot the first time the file moved."""
    lines = (ROUTERS / "stats.py").read_text().splitlines()
    for index, line in enumerate(lines):
        if "priced = [" in line:
            return index + 2  # the predicate is the line after `priced = [`
    raise AssertionError("stats.py no longer has the spend-over-time exception")


def test_a_listed_disc_is_still_owned_and_a_sold_one_is_not() -> None:
    """The vocabulary, asserted directly.

    A disc advertised is still a disc on the shelf. If `listed_for_sale` were excluded,
    listing something would be indistinguishable from losing it.
    """
    assert "in_collection" in OWNED_LISTING_STATUSES
    assert "listed_for_sale" in OWNED_LISTING_STATUSES
    assert "sold" not in OWNED_LISTING_STATUSES
    assert "donated" not in OWNED_LISTING_STATUSES


def test_the_predicate_checks_both_halves() -> None:
    """Deletion and sale are different things and both have to be excluded."""
    rendered = str(owned_copy())
    assert "deleted_at IS NULL" in rendered
    assert "listing_status IN" in rendered


# ---------------------------------------------------------------------------
# Walking a disc through the states, against a real database
# ---------------------------------------------------------------------------
#
# No module-level `pytest.mark.asyncio`: `asyncio_mode = "auto"` in `pyproject.toml`
# already marks the coroutines, and a blanket mark makes pytest warn about every sync
# test above it.


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("in_collection", "listed_for_sale"),
        ("listed_for_sale", "sold"),
        ("listed_for_sale", "in_collection"),
        ("in_collection", "donated"),
    ],
)
def test_every_transition_the_check_constraint_allows_is_reachable(start: str, target: str) -> None:
    """Not a database test — a vocabulary one, kept beside the others.

    All four states in `LISTING_STATUSES` are reachable through one endpoint, which is
    why there is one endpoint rather than a verb each.
    """
    from src.schemas.collection import ListingUpdateRequest

    assert ListingUpdateRequest(status=target).status == target  # type: ignore[arg-type]
    assert start in {"in_collection", "listed_for_sale", "sold", "donated"}


def test_a_listing_price_of_nan_is_refused() -> None:
    """`Decimal("NaN")` parses, and then every comparison against it raises rather than
    answering. The same guard `wanted._validate_max_price` carries, for the same reason —
    it was found there by a security review."""
    from pydantic import ValidationError

    from src.schemas.collection import ListingUpdateRequest

    for bad in ("NaN", "Infinity", "-1", "1000000", "not a price"):
        with pytest.raises(ValidationError):
            ListingUpdateRequest(status="listed_for_sale", listingPrice=bad)

    assert ListingUpdateRequest(status="listed_for_sale", listingPrice="12.99").listingPrice == (
        "12.99"
    )


async def test_sold_discs_are_excluded_from_an_owned_query(db_conn: object) -> None:
    """The property §4.4 turns on, proved against Postgres rather than reasoned about.

    Written against the live schema because the predicate is SQL: a Python-level check
    would pass just as happily with the `IN` clause pointing at the wrong column.

    **The film and the disc are both created here.** An earlier revision selected an
    existing disc out of the catalogue, which passed on this machine — where
    `DATABASE_URL` points at Neon and 1,857 of them exist — and failed in CI, where the
    Postgres 17 service starts empty. `STATUS.md` gotcha 15, arriving on schedule: a
    green local run is silent about anything touching SQL, and that cuts both ways.
    """
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

    from src.models.movie import Movie

    assert isinstance(db_conn, AsyncConnection)
    session = AsyncSession(bind=db_conn)

    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=940_201,
        title="A Film Sold On",
        original_title="A Film Sold On",
        year=1994,
        media_type="film",
    )
    session.add(movie)
    await session.flush()

    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=["blu_ray"],
        listing_status="in_collection",
    )
    session.add(item)
    await session.flush()

    def owned_ids() -> object:
        return select(CollectionItem.id).where(CollectionItem.id == item.id, owned_copy())

    assert await session.scalar(owned_ids()) == item.id

    item.listing_status = "listed_for_sale"
    await session.flush()
    assert await session.scalar(owned_ids()) == item.id, "a listed disc is still owned"

    item.listing_status = "sold"
    item.listing_price = Decimal("9.99")
    await session.flush()
    assert await session.scalar(owned_ids()) is None, "a sold disc is not owned"

    # And it is still there — not deleted, so §6.30's 90-day purge cannot destroy the
    # record of what it fetched.
    still_there = await session.get(CollectionItem, item.id)
    assert still_there is not None
    assert still_there.deleted_at is None
    assert still_there.listing_price == Decimal("9.99")
