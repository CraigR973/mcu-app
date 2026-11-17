"""Found for the film it is — AG4 (CR49-02, CR49-05, CT52-02).

**Every fact the app finds for a film is stamped with the film it was found for**, and a fact
whose stamp is not its film as it is now is forgotten and looked up again. One rule, one
column, one sweep, chosen at the owner's word on 17 Nov over an ``identity_changed`` hook
(``DECISIONS.md`` #388), which would be right only while every path that changes a film
remembered to call it.

Before AG4 three rules did this, each found after the fact: an IMDb rating carried the IMDb id
it was read for; a disc value was due again once priced before the film's last TMDB sync (a
time rule an undo defeated, since an undo puts the old sync time back); and reviews (#378) and
disc pages (#380) were forgotten when found before the film's latest audited correction, which
a moved copy never wrote. eBay's sold listings were in none of them. The time rule and the
audit rule are retired into this; the IMDb rating already worked this way and is left alone.

**The stamp** (:func:`identity`) is ``film:<TMDB id>``, ``tv:<TMDB series id>``, or ``none``
for a film not yet identified, so identifying a film makes everything found under its
spreadsheet title due again, as the time rule did. A copy's disc page is stamped with the film
the copy was on when the matcher chose it, so a move (CT52-02) forgets it like a correction.

**The sweep** (:func:`forget_found_for_another_film`) runs in four places, for what each touched:
identify, undo, merge and move call it in their own transaction, so no screen shows the old
film's facts; and the nightly disc spec and review job sweeps everything as it starts
(:func:`nightly_sweep`, before the 04:00 valuation job and the eBay scans of the day), which
catches any path that changed a film without calling it. That catch-all is capped: past
:data:`CATCH_ALL_LIMIT` rows it forgets nothing and counts a failure on the job's heartbeat,
which the daily check names, since a mistake in the rule would otherwise forget good rows that
take nights to look up again.

What every other table with a film id is, and what a merge does with it, is :data:`FILM_LINKS`;
CI fails on a foreign key to ``movies`` it does not name (`tests/test_found_for.py`).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog
from sqlalchemy import Text, case, cast, delete, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.clock import utcnow
from src.models.collection_item import CollectionItem
from src.models.ebay_sold import EbayUsedListing, EbayUsedScan
from src.models.ebay_watch import EbayPriceRef
from src.models.movie import Movie
from src.models.reviews import FilmReview
from src.models.specs_backfill import SpecLookup
from src.models.valuation import DiscValuation

logger = structlog.get_logger(__name__)

#: A film not yet identified: what was found for it was found under its own title.
NOT_IDENTIFIED = "none"

#: The nightly catch-all forgets nothing past this many rows, and says so (AG4). A correction
#: forgets one film's rows; a rule that suddenly disowns hundreds is a mistake to look at, not
#: to act on, since a forgotten disc page or review takes nights to look up again within the
#: Brave and Blu-ray.com caps.
CATCH_ALL_LIMIT = 50

#: The disc page lookups the matcher decided, in the statuses that answer a film. A page a
#: person chose, or a disc a person skipped, is their call about the disc in hand (#380).
_PAGE_STATUSES = ("accepted", "done", "needs_you", "no_match")


def identity(tmdb_id: int | None, tmdb_tv_id: int | None) -> str:
    """What a film is, as a stamp: its TMDB film id, else its TMDB series id, else ``none``."""
    if tmdb_id is not None:
        return f"film:{tmdb_id}"
    if tmdb_tv_id is not None:
        return f"tv:{tmdb_tv_id}"
    return NOT_IDENTIFIED


def stamp(movie: Movie) -> str:
    """The stamp for a fact found for ``movie`` now."""
    return identity(movie.tmdb_id, movie.tmdb_tv_id)


async def stamp_of(db: AsyncSession, movie_id: uuid.UUID) -> str:
    """The stamp for a fact found for the film ``movie_id`` now."""
    row = (
        await db.execute(select(Movie.tmdb_id, Movie.tmdb_tv_id).where(Movie.id == movie_id))
    ).one_or_none()
    if row is None:
        raise LookupError(f"No film {movie_id}")
    return identity(row.tmdb_id, row.tmdb_tv_id)


async def stamp_of_copy(db: AsyncSession, item_id: uuid.UUID) -> str:
    """The stamp for a fact found for the film the copy ``item_id`` is on now."""
    row = (
        await db.execute(
            select(Movie.tmdb_id, Movie.tmdb_tv_id)
            .join(CollectionItem, CollectionItem.movie_id == Movie.id)
            .where(CollectionItem.id == item_id)
        )
    ).one_or_none()
    if row is None:
        raise LookupError(f"No copy {item_id}")
    return identity(row.tmdb_id, row.tmdb_tv_id)


def identity_sql(movie: Any = Movie) -> ColumnElement[str]:
    """:func:`identity` in SQL, for ``movie`` (the table, or an alias of it)."""
    return case(
        (movie.tmdb_id.is_not(None), literal("film:") + cast(movie.tmdb_id, Text)),
        (movie.tmdb_tv_id.is_not(None), literal("tv:") + cast(movie.tmdb_tv_id, Text)),
        else_=literal(NOT_IDENTIFIED),
    )


# ---------------------------------------------------------------------------
# What each table with a film id is
# ---------------------------------------------------------------------------

LinkKind = Literal["found_for", "moved", "dropped"]


@dataclass(frozen=True)
class FilmLink:
    """One table's film id, what it is, and what a merge does with it."""

    table: str
    kind: LinkKind
    why: str


#: Every table with a film id (AG4). ``found_for``: a fact found for the film, stamped and
#: swept here; a merge drops it with the merged-away film, since it was found for that film's
#: identity, and an undo leaves it to be looked up again. ``moved``: a person's own record, or
#: a link, which a merge moves to the film merged into and an undo moves back
#: (`services/identification.py`). ``dropped``: the merged-away film's own, replaced by the
#: film merged into's. CI fails on a foreign key to ``movies`` not named here.
FILM_LINKS: tuple[FilmLink, ...] = (
    FilmLink("film_reviews", "found_for", "a review found for the film"),
    FilmLink("disc_valuations", "found_for", "an eBay value searched for the film"),
    FilmLink("ebay_used_listings", "found_for", "a used eBay listing found for the film"),
    FilmLink("ebay_used_scans", "found_for", "when the film's used listings were searched"),
    FilmLink("ebay_price_refs", "found_for", "what the film usually asks on eBay"),
    FilmLink("collection_items", "moved", "a copy on the shelf"),
    FilmLink("watch_log", "moved", "a person's viewing"),
    FilmLink("wanted_list", "moved", "a person's want"),
    FilmLink("movie_night_suggestions", "moved", "a person's suggestion"),
    FilmLink("movie_night_votes", "moved", "a person's vote"),
    FilmLink("release_calendar", "moved", "a release date, which carries its own TMDB id"),
    FilmLink("barcode_lookups", "moved", "a barcode scanned, which carries its own TMDB id"),
    FilmLink("deals", "moved", "a deal found, which carries its own TMDB id"),
    FilmLink("ebay_targets", "moved", "a person's saved eBay search"),
    FilmLink("movie_title_aliases", "moved", "a title the film answers to"),
    FilmLink("identify_doubts", "moved", "a doubt about the film's match"),
    FilmLink(
        "cinema_films",
        "moved",
        "a cinema listing agreed to be the film, which carries its own TMDB id (CR49-05)",
    ),
    FilmLink("movie_credits", "dropped", "TMDB's cast, written again for the film merged into"),
    FilmLink("identify_lookups", "dropped", "the merged-away film's own identification record"),
)

#: A copy's disc page is found for the film the copy is on: stamped on its lookup, reached
#: through ``collection_items`` rather than a film id of its own.
SPEC_LOOKUPS = "spec_lookups"

#: The stamped stores: each has a ``found_for`` column, not null, so a writer that forgets the
#: stamp fails loudly. CI checks every writer passes one.
STAMPED = (
    FilmReview,
    DiscValuation,
    EbayUsedListing,
    EbayUsedScan,
    EbayPriceRef,
    SpecLookup,
)


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------


@dataclass
class Forgotten:
    """What one sweep forgot, by table, or would have, had it not refused."""

    counts: dict[str, int] = field(default_factory=dict)
    refused: bool = False
    #: The most it would forget on its own: the catch-all's cap, or none.
    limit: int | None = None

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _film_scope(column: Any, films: Iterable[uuid.UUID] | None) -> list[ColumnElement[bool]]:
    return [] if films is None else [column.in_(list(films))]


def _disowned(model: Any, films: Iterable[uuid.UUID] | None) -> Any:
    """The ids of ``model``'s rows whose stamp is not their film's identity now."""
    return (
        select(model.id)
        .join(Movie, Movie.id == model.movie_id)
        .where(model.found_for != identity_sql(), *_film_scope(model.movie_id, films))
    )


def _disowned_pages(films: Iterable[uuid.UUID] | None, items: Iterable[uuid.UUID] | None) -> Any:
    """The matcher's page lookups whose stamp is not their copy's film now."""
    scope: list[ColumnElement[bool]] = []
    if films is not None or items is not None:
        scope.append(
            or_(
                CollectionItem.movie_id.in_(list(films or ())),
                CollectionItem.id.in_(list(items or ())),
            )
        )
    return (
        select(SpecLookup, CollectionItem)
        .join(CollectionItem, CollectionItem.id == SpecLookup.collection_item_id)
        .join(Movie, Movie.id == CollectionItem.movie_id)
        .where(
            SpecLookup.found_for != identity_sql(),
            SpecLookup.decided_by.is_(None),
            SpecLookup.status.in_(_PAGE_STATUSES),
            # A page's fields are taken only from a disc whose page it was (#380).
            or_(SpecLookup.status == "done", CollectionItem.specs_source_url.is_(None)),
            *scope,
        )
    )


_SIMPLE = (FilmReview, DiscValuation, EbayUsedScan, EbayPriceRef)


async def count_disowned(
    db: AsyncSession,
    *,
    films: Iterable[uuid.UUID] | None = None,
    items: Iterable[uuid.UUID] | None = None,
) -> dict[str, int]:
    """How many rows of each stamped store answer another film now. Writes nothing."""
    films = None if films is None else list(films)
    counts: dict[str, int] = {}
    if items is None or films is not None:
        for model in (*_SIMPLE, EbayUsedListing):
            disowned = _disowned(model, films).subquery()
            counts[model.__tablename__] = int(
                await db.scalar(select(func.count()).select_from(disowned)) or 0
            )
    pages = _disowned_pages(films, items).subquery()
    counts[SPEC_LOOKUPS] = int(await db.scalar(select(func.count()).select_from(pages)) or 0)
    return counts


async def forget_found_for_another_film(
    db: AsyncSession,
    *,
    films: Iterable[uuid.UUID] | None = None,
    items: Iterable[uuid.UUID] | None = None,
    limit: int | None = None,
) -> Forgotten:
    """Forget every fact whose stamp is not its film as it is now, so it is looked up again.

    ``films`` narrows the sweep to those films' facts (an identification and its undo);
    ``items`` to those copies' disc pages (a move and its undo). With neither, every stamped
    store is swept: the nightly catch-all, which passes ``limit`` and, past it, forgets nothing
    and returns ``refused``. Flushes; does not commit.

    What forgetting is, by store: a review, an eBay value, a used-listing search time and a
    usual eBay price are deleted, so each is due as if never looked up; a used listing is
    deleted and its film and format's sold figure worked out again from what is left; a disc
    page lookup goes with the fields its page gave the copy (:func:`forget_page_fields`), so
    the disc is searched again as never searched.
    """
    films = None if films is None else list(films)
    items = None if items is None else list(items)
    forgotten = Forgotten(counts=await count_disowned(db, films=films, items=items), limit=limit)
    if limit is not None and forgotten.total > limit:
        forgotten.refused = True
        logger.error("found_for_sweep_refused", counts=forgotten.counts, limit=limit)
        return forgotten
    if not forgotten.total:
        return forgotten

    # Lazy: the spec and sold-store modules import from modules that import this one.
    from src.services.ebay_sold import refresh_sales_value
    from src.services.specs.backfill import forget_page_fields

    if items is None or films is not None:
        for model in _SIMPLE:
            await db.execute(delete(model).where(model.id.in_(_disowned(model, films))))
        listings = (
            await db.execute(
                delete(EbayUsedListing)
                .where(EbayUsedListing.id.in_(_disowned(EbayUsedListing, films)))
                .returning(EbayUsedListing.movie_id, EbayUsedListing.format_code)
            )
        ).all()
        await db.flush()
        now = utcnow()
        for movie_id, format_code in sorted(
            set(listings), key=lambda pair: (str(pair[0]), pair[1])
        ):
            await refresh_sales_value(db, movie_id, format_code, now=now)

    pages = (await db.execute(_disowned_pages(films, items))).all()
    for lookup, item in pages:
        if lookup.status == "done" and item.specs_source_url:
            await forget_page_fields(db, item, lookup)
    if pages:
        await db.execute(
            delete(SpecLookup).where(SpecLookup.id.in_([lookup.id for lookup, _ in pages]))
        )
    await db.flush()
    logger.info("found_for_forgotten", counts=forgotten.counts)
    return forgotten


async def nightly_sweep(db: AsyncSession) -> Forgotten:
    """The catch-all: every stamped store, capped at :data:`CATCH_ALL_LIMIT`. Commits."""
    forgotten = await forget_found_for_another_film(db, limit=CATCH_ALL_LIMIT)
    await db.commit()
    return forgotten
