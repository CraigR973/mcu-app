"""AG4 — found for the film it is (CR49-02, CR49-05, CT52-02, CT52-03). Against Postgres in CI.

**What this proves.** Every table with a film id says what it is, and every foreign key to
``movies`` is moved by a merge or listed as dropped; every stamped store's writers stamp. A
correction, its undo and a move each forget what was found for the film (or the copy) as it
was, and only that: the French Connection copy (CT52-02) loses its sequel's page while the
sequel keeps its own review; a page a person chose stays. A merge carries the cinema link and
its undo brings it back (CR49-05). The nightly catch-all forgets what a path that changed a
film without asking left behind, and refuses past its limit. The migration's backfill stamps
rows with their film and marks what the retired rules judged stale. The daily check names two
owned copies with one disc page (CT52-03).
"""

from __future__ import annotations

import ast
import importlib.util
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

import src.models  # noqa: F401 - every model registered on the metadata
from src.models.admin_action import AdminAction
from src.models.base import Base
from src.models.cinema import CinemaFilm
from src.models.collection_item import CollectionItem
from src.models.ebay_sold import EbayUsedListing, EbayUsedScan
from src.models.ebay_watch import EbayPriceRef
from src.models.movie import Movie
from src.models.reviews import FilmReview
from src.models.specs_backfill import SpecLookup
from src.models.valuation import DiscValuation
from src.services import found_for
from src.services.found_for import (
    FILM_LINKS,
    STAMPED,
    count_disowned,
    identity,
    nightly_sweep,
    stamp,
)
from src.services.health_checks import check_copies_sharing_a_page
from src.services.identification import (
    MOVED_ON_MERGE,
    identify_film,
    undo_identification,
)
from src.services.identify.move_copy import move_copy, undo_move
from tests.test_identify_films import NOW, _disc, _film, _person, _record, _tmdb_ids

SRC = Path(__file__).parents[1] / "src"
SEQUEL_PAGE = "https://www.blu-ray.com/movies/French-Connection-II-Blu-ray/12345/"
FIRST_PAGE = "https://www.blu-ray.com/movies/The-French-Connection-Blu-ray/23456/"


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# The guards (no database)
# ---------------------------------------------------------------------------


def _film_keys() -> set[str]:
    return {
        column.table.name
        for table in Base.metadata.tables.values()
        for column in table.columns
        for key in column.foreign_keys
        if key.target_fullname == "movies.id"
    }


def test_every_table_with_a_film_id_says_what_it_is() -> None:
    """CR49-05: a table added with a film id and not listed fails here, before a merge drops
    it silently."""
    named = [link.table for link in FILM_LINKS]
    assert len(named) == len(set(named)), "a table is listed twice"
    assert set(named) == _film_keys()


def test_a_merge_moves_exactly_the_tables_listed_as_moved() -> None:
    moved = {link.table for link in FILM_LINKS if link.kind == "moved"}
    assert set(MOVED_ON_MERGE) == moved
    assert all(model.__tablename__ == table for table, model in MOVED_ON_MERGE.items())


def test_every_film_keyed_fact_is_stamped_and_not_null() -> None:
    found = {link.table for link in FILM_LINKS if link.kind == "found_for"}
    stamped = {model.__tablename__ for model in STAMPED}
    assert stamped == found | {found_for.SPEC_LOOKUPS}
    for model in STAMPED:
        column = model.__table__.columns["found_for"]
        assert column.nullable is False, model.__tablename__
        assert column.server_default is None and column.default is None, model.__tablename__


def _writers() -> list[tuple[str, str, ast.AST, str]]:
    """Each place in ``src`` that builds or inserts a stamped row: file, model, node, and the
    source of the function it is in."""
    names = {model.__name__ for model in STAMPED}
    found: list[tuple[str, str, ast.AST, str]] = []
    for path in SRC.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            body = ast.get_source_segment(source, function) or ""
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                func_node = node.func
                if isinstance(func_node, ast.Name) and func_node.id in names:
                    found.append((str(path), func_node.id, node, body))
                elif (
                    isinstance(func_node, ast.Name)
                    and func_node.id == "insert"
                    and node.args
                    and isinstance(node.args[0], ast.Name)
                    and node.args[0].id in names
                ):
                    found.append((str(path), f"insert({node.args[0].id})", node, body))
    return found


def test_every_writer_of_a_stamped_store_stamps() -> None:
    """A row built without ``found_for`` fails at the database; this says where, before CI's
    database does. An insert's upsert must stamp again too, so its function names the stamp."""
    writers = _writers()
    assert len(writers) >= 9, writers  # the reviews, specs, values, sold store and usual prices
    for path, what, node, body in writers:
        assert isinstance(node, ast.Call)
        if what.startswith("insert("):
            assert "found_for" in body, f"{path}: {what} without a stamp"
        else:
            keywords = {keyword.arg for keyword in node.keywords}
            assert "found_for" in keywords or None in keywords, f"{path}: {what} without a stamp"


def test_a_film_is_its_tmdb_id_its_series_id_or_not_identified() -> None:
    assert identity(603, None) == "film:603"
    assert identity(None, 1399) == "tv:1399"
    assert identity(None, None) == found_for.NOT_IDENTIFIED == "none"
    # A film's id wins, as a row identified as a film clears its series id anyway.
    assert identity(603, 1399) == "film:603"


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------


def _review(film: Movie, *, found_for_: str | None = None, site: str = "avforums") -> FilmReview:
    return FilmReview(
        id=uuid.uuid4(),
        movie_id=film.id,
        found_for=found_for_ or stamp(film),
        site=site,
        format_code="blu_ray",
        status="found",
        url=(
            f"https://www.blu-ray.com/movies/A-Film-Blu-ray/{uuid.uuid4().int % 900_000}/"
            if site == "bluray_com"
            else f"https://www.avforums.com/reviews/a-film-review.{uuid.uuid4().int % 90_000}/"
        ),
        found_via="brave",
        found_utc=NOW,
    )


def _value(film: Movie, *, found_for_: str | None = None, fmt: str = "blu_ray") -> DiscValuation:
    return DiscValuation(
        id=uuid.uuid4(),
        movie_id=film.id,
        found_for=found_for_ or stamp(film),
        format_code=fmt,
        status="priced",
        price=Decimal("9.00"),
        currency="GBP",
        sample_size=5,
        used_count=5,
        matched=5,
        considered=5,
        basis="current asking prices",
        search_query="a film blu-ray",
        checked_utc=NOW,
    )


def _sold(film: Movie, *, found_for_: str | None = None) -> EbayUsedListing:
    return EbayUsedListing(
        id=uuid.uuid4(),
        legacy_item_id=uuid.uuid4().hex,
        movie_id=film.id,
        found_for=found_for_ or stamp(film),
        format_code="blu_ray",
        price=Decimal("5.00"),
        postage=Decimal("1.00"),
        condition_code="3000",
        first_seen_utc=NOW,
        last_seen_utc=NOW,
        status="sold",
        ended_at_utc=NOW,
        sold_count=1,
    )


def _scan(film: Movie, *, found_for_: str | None = None) -> EbayUsedScan:
    return EbayUsedScan(
        id=uuid.uuid4(),
        movie_id=film.id,
        found_for=found_for_ or stamp(film),
        format_code="blu_ray",
        checked_utc=NOW,
    )


def _usual(film: Movie, *, found_for_: str | None = None) -> EbayPriceRef:
    return EbayPriceRef(
        id=uuid.uuid4(),
        movie_id=film.id,
        found_for=found_for_ or stamp(film),
        format_code="blu_ray",
        status="priced",
        median=Decimal("8.00"),
        sample_size=4,
        by_condition={},
        checked_utc=NOW,
    )


async def _every_fact(db: AsyncSession, film: Movie, *, found_for_: str | None = None) -> None:
    for row in (
        _review(film, found_for_=found_for_),
        _value(film, found_for_=found_for_),
        _sold(film, found_for_=found_for_),
        _scan(film, found_for_=found_for_),
        _usual(film, found_for_=found_for_),
    ):
        db.add(row)
    await db.flush()


async def _paged(
    db: AsyncSession,
    film: Movie,
    *,
    page: str = SEQUEL_PAGE,
    decided_by: uuid.UUID | None = None,
    found_for_: str | None = None,
) -> tuple[CollectionItem, SpecLookup]:
    """A copy the matcher (or a person) gave ``page``, read, with the specs it gave."""
    disc = await _disc(
        db,
        film,
        "blu_ray",
        specs_source_url=page,
        specs_fetched_at_utc=NOW,
        video_specs={"codec": "MPEG-4 AVC"},
        release_label="Sequel Pictures",
        region_code="B",
    )
    lookup = SpecLookup(
        id=uuid.uuid4(),
        collection_item_id=disc.id,
        found_for=found_for_ or stamp(film),
        status="done",
        accepted_url=page,
        how="confirmed" if decided_by else "auto",
        decided_by=decided_by,
        decided_utc=NOW,
        searched_utc=NOW,
        fetched_utc=NOW,
        attempts=0,
    )
    db.add(lookup)
    await db.flush()
    return disc, lookup


async def _counts(db: AsyncSession, film: Movie) -> dict[str, int]:
    counts = {}
    for model in (FilmReview, DiscValuation, EbayUsedListing, EbayUsedScan, EbayPriceRef):
        counts[model.__tablename__] = int(
            await db.scalar(
                select(func.count()).select_from(model).where(model.movie_id == film.id)
            )
            or 0
        )
    return counts


ALL_FIVE = {
    "film_reviews": 1,
    "disc_valuations": 1,
    "ebay_used_listings": 1,
    "ebay_used_scans": 1,
    "ebay_price_refs": 1,
}
NONE_OF_THEM = dict.fromkeys(ALL_FIVE, 0)


# ---------------------------------------------------------------------------
# Corrections and undos
# ---------------------------------------------------------------------------


async def test_a_correction_forgets_what_was_found_for_the_film_as_it_was(
    db: AsyncSession,
) -> None:
    """Bad Lieutenant, 16 Oct: corrected from the 1992 film to the 2009 one, its eBay value,
    usual price, used listings and review were all the 1992 film's. Nothing else goes."""
    wrong, right, other_id = _tmdb_ids()
    film = await _film(db, "Bad Lieutenant", tmdb_id=wrong, year=1992)
    other = await _film(db, "Heat", tmdb_id=other_id, year=1995)
    await _every_fact(db, film)
    await _every_fact(db, other)
    disc, lookup = await _paged(db, film)
    assert await _counts(db, film) == ALL_FIVE

    done = await identify_film(
        db,
        film,
        _record(right, "Bad Lieutenant: Port of Call New Orleans", 2009),
        by=None,
        how="film_page",
    )

    assert stamp(done.film) == f"film:{right}"
    assert await _counts(db, film) == NONE_OF_THEM
    assert await _counts(db, other) == ALL_FIVE
    assert await db.get(SpecLookup, lookup.id) is None
    await db.refresh(disc)
    assert (disc.specs_source_url, disc.video_specs, disc.release_label) == (None, None, None)


async def test_identifying_a_film_forgets_what_its_spreadsheet_title_found(
    db: AsyncSession,
) -> None:
    """Batch T9's reason for the values' time rule: a film priced as "Captain Ameica" was
    searched under that title. Not identified is a film too, so identifying it forgets that."""
    film = await _film(db, "Captain Ameica - Civil War", year=None)
    await _every_fact(db, film)
    assert {row.found_for for row in await db.scalars(select(DiscValuation))} >= {"none"}

    tmdb_id, _, _ = _tmdb_ids()
    await identify_film(
        db, film, _record(tmdb_id, "Captain America: Civil War", 2016), by=None, how="picked"
    )

    assert await _counts(db, film) == NONE_OF_THEM


async def test_an_undo_is_a_correction_too(db: AsyncSession) -> None:
    """The time rule an undo defeated: an undo put the old sync time back, so a value priced
    between the correction and its undo stood for 30 days as the wrong film's."""
    first, second, _ = _tmdb_ids()
    film = await _film(db, "Salem's Lot", tmdb_id=first, year=1979)
    done = await identify_film(
        db, film, _record(second, "Salem's Lot", 2024), by=None, how="picked"
    )
    # Priced and looked up as the 2024 film, after the correction.
    await _every_fact(db, film)
    assert await _counts(db, film) == ALL_FIVE

    restored = await undo_identification(db, done.audit.id, by=None)

    assert stamp(restored) == f"film:{first}"
    assert await _counts(db, film) == NONE_OF_THEM


# ---------------------------------------------------------------------------
# Moves (CT52-02)
# ---------------------------------------------------------------------------


async def test_a_moved_copy_forgets_its_old_films_page_and_the_old_film_keeps_its_review(
    db: AsyncSession,
) -> None:
    """The French Connection, 17 Oct: the 1971 film's Blu-ray was accepted on the 1975 sequel's
    page while it sat on the sequel, and moved; the page and its specs stayed until AG4."""
    sequel_id, first_id, _ = _tmdb_ids()
    sequel = await _film(db, "French Connection II", tmdb_id=sequel_id, year=1975)
    first = await _film(db, "The French Connection", tmdb_id=first_id, year=1971)
    disc, lookup = await _paged(db, sequel)
    # The sequel's page seeded the sequel's own review, and is the sequel's.
    seeded = _review(sequel, site="bluray_com")
    db.add(seeded)
    await db.flush()

    moved = await move_copy(db, disc.id, _record(first_id, "The French Connection", 1971), by=None)

    assert moved.film.id == first.id
    await db.refresh(disc)
    assert disc.movie_id == first.id
    assert (disc.specs_source_url, disc.video_specs, disc.release_label) == (None, None, None)
    assert await db.get(SpecLookup, lookup.id) is None
    assert await db.get(FilmReview, seeded.id) is not None


async def test_a_page_a_person_chose_stays_with_the_copy_through_a_move(db: AsyncSession) -> None:
    """A person's page is their call about the disc in their hand (#380)."""
    craig = await _person(db)
    sequel_id, first_id, _ = _tmdb_ids()
    sequel = await _film(db, "French Connection II", tmdb_id=sequel_id, year=1975)
    disc, lookup = await _paged(db, sequel, page=FIRST_PAGE, decided_by=craig.id)

    await move_copy(db, disc.id, _record(first_id, "The French Connection", 1971), by=craig.id)

    await db.refresh(disc)
    assert disc.specs_source_url == FIRST_PAGE
    assert await db.get(SpecLookup, lookup.id) is not None


async def test_undoing_a_move_forgets_a_page_found_after_it(db: AsyncSession) -> None:
    sequel_id, first_id, _ = _tmdb_ids()
    sequel = await _film(db, "French Connection II", tmdb_id=sequel_id, year=1975)
    plain = await _disc(db, sequel, "blu_ray")
    moved = await move_copy(db, plain.id, _record(first_id, "The French Connection", 1971), by=None)
    # Searched and read as the 1971 film, on its new film.
    lookup = SpecLookup(
        id=uuid.uuid4(),
        collection_item_id=plain.id,
        found_for=stamp(moved.film),
        status="done",
        accepted_url=FIRST_PAGE,
        how="auto",
        decided_utc=NOW,
        attempts=0,
    )
    db.add(lookup)
    plain.specs_source_url = FIRST_PAGE
    await db.flush()

    await undo_move(db, moved.audit.id, by=None)

    await db.refresh(plain)
    assert (plain.movie_id, plain.specs_source_url) == (sequel.id, None)
    assert await db.get(SpecLookup, lookup.id) is None


# ---------------------------------------------------------------------------
# Merges (CR49-05)
# ---------------------------------------------------------------------------


async def test_a_merge_carries_the_cinema_link_and_its_undo_brings_it_back(
    db: AsyncSession,
) -> None:
    tmdb_id, _, _ = _tmdb_ids()
    kept = await _film(db, "Misery", tmdb_id=tmdb_id, year=1990)
    merged = await _film(db, "Misery (1990)", year=None)
    listing = CinemaFilm(
        id=uuid.uuid4(),
        source="test",
        source_key=uuid.uuid4().hex,
        title="Misery",
        movie_id=merged.id,
        evidence={},
    )
    db.add(listing)
    await db.flush()

    done = await identify_film(
        db, merged, _record(tmdb_id, "Misery", 1990), by=None, how="picked", allow_merge=True
    )

    assert done.merged and done.film.id == kept.id
    await db.refresh(listing)
    assert listing.movie_id == kept.id
    assert done.audit.changes["merge"]["moved"]["cinema_films"] == [str(listing.id)]

    restored = await undo_identification(db, done.audit.id, by=None)

    await db.refresh(listing)
    assert listing.movie_id == restored.id == merged.id


# ---------------------------------------------------------------------------
# The nightly catch-all
# ---------------------------------------------------------------------------


async def test_the_catch_all_forgets_what_a_path_that_did_not_ask_left_behind(
    db: AsyncSession,
) -> None:
    """A film changed by a path that does not call the sweep: its facts are the old film's
    until the nightly job's catch-all, which forgets them, and only them."""
    old, new, other_id = _tmdb_ids()
    film = await _film(db, "Dead Man's Shoes", tmdb_id=new, year=1940)
    other = await _film(db, "Heat", tmdb_id=other_id, year=1995)
    await _every_fact(db, film, found_for_=f"film:{old}")
    await _every_fact(db, other)
    disc, lookup = await _paged(db, film, found_for_=f"film:{old}")
    await db.commit()

    assert (await count_disowned(db, films=[film.id]))["film_reviews"] == 1
    forgotten = await nightly_sweep(db)

    assert not forgotten.refused
    assert forgotten.counts == {**ALL_FIVE, "spec_lookups": 1}
    assert await _counts(db, film) == NONE_OF_THEM
    assert await _counts(db, other) == ALL_FIVE
    await db.refresh(disc)
    assert disc.specs_source_url is None
    assert await nightly_sweep(db) == found_for.Forgotten(
        counts={**NONE_OF_THEM, "spec_lookups": 0}, limit=found_for.CATCH_ALL_LIMIT
    )


async def test_the_catch_all_refuses_past_its_limit_and_forgets_nothing(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mistake in the rule would disown hundreds of good rows that take nights to look up
    again: past the limit the job forgets nothing and counts a failure instead."""
    monkeypatch.setattr(found_for, "CATCH_ALL_LIMIT", 3)
    old, new, _ = _tmdb_ids()
    film = await _film(db, "Dead Man's Shoes", tmdb_id=new, year=1940)
    await _every_fact(db, film, found_for_=f"film:{old}")
    await db.commit()

    forgotten = await nightly_sweep(db)

    assert forgotten.refused and forgotten.total == 5
    assert await _counts(db, film) == ALL_FIVE


async def test_the_nightly_job_counts_a_refusal_as_a_failure(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.scripts import spec_backfill

    monkeypatch.setattr(found_for, "CATCH_ALL_LIMIT", 0)
    old, new, _ = _tmdb_ids()
    film = await _film(db, "Dead Man's Shoes", tmdb_id=new, year=1940)
    db.add(_review(film, found_for_=f"film:{old}"))
    await db.commit()

    code, error = await spec_backfill.sweep(db)

    assert code == 1
    assert error is not None and "over the 0" in error
    assert (await _counts(db, film))["film_reviews"] == 1


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


async def test_a_value_priced_again_is_stamped_again(db: AsyncSession) -> None:
    from src.ebay.pricing import PriceEstimate
    from src.models.valuation import ValuationRun
    from src.services.valuation import DueFilm, Valuation, _store

    old, new, _ = _tmdb_ids()
    film = await _film(db, "Heat", tmdb_id=new, year=1995)
    db.add(_value(film, found_for_=f"film:{old}"))
    await db.flush()
    due = DueFilm(film.id, "blu_ray", "Heat", True, stamp(film))
    estimate = PriceEstimate(
        film_title="Heat", format_code="blu_ray", marketplace_id="EBAY_GB", considered=10, matched=3
    )
    valuation = Valuation(status="not_priced", price=None, sample_size=0, condition_label=None)

    run = ValuationRun(
        id=uuid.uuid4(),
        trigger="job",
        status="running",
        started_utc=NOW,
        heartbeat_utc=NOW,
        budget=10,
    )
    db.add(run)
    await db.flush()

    await _store(db, due, estimate, valuation, run_id=run.id, checked=NOW)

    value = await db.scalar(
        select(DiscValuation)
        .where(DiscValuation.movie_id == film.id)
        .execution_options(populate_existing=True)
    )
    assert value is not None and value.found_for == f"film:{new}"


async def test_a_used_listing_seen_again_and_its_search_are_stamped_as_the_film_is_now(
    db: AsyncSession,
) -> None:
    from src.services.ebay_sold import ObservedListing, TrackedDisc, _record_search

    old, new, _ = _tmdb_ids()
    film = await _film(db, "Heat", tmdb_id=new, year=1995)
    seen = _sold(film, found_for_=f"film:{old}")
    seen.status = "active"
    db.add(seen)
    db.add(_scan(film, found_for_=f"film:{old}"))
    await db.flush()
    disc = TrackedDisc(film.id, "blu_ray", "Heat", True, 1995, False, stamp(film))
    items = [
        ObservedListing(seen.legacy_item_id, Decimal("6.00"), Decimal("1.00"), "3000"),
        ObservedListing("new-listing", Decimal("7.00"), Decimal("1.00"), "3000"),
    ]

    await _record_search(db, disc, items, now=NOW)

    stamps = {
        row.legacy_item_id: row.found_for
        for row in await db.scalars(
            select(EbayUsedListing)
            .where(EbayUsedListing.movie_id == film.id)
            .execution_options(populate_existing=True)
        )
    }
    assert stamps == {seen.legacy_item_id: f"film:{new}", "new-listing": f"film:{new}"}
    scan = await db.scalar(select(EbayUsedScan.found_for).where(EbayUsedScan.movie_id == film.id))
    assert scan == f"film:{new}"


# ---------------------------------------------------------------------------
# The migration's backfill
# ---------------------------------------------------------------------------


def _backfill(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    path = Path(__file__).parents[1] / "migrations/versions/080_found_for_the_film_it_is.py"
    spec = importlib.util.spec_from_file_location("found_for_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql: list[str] = []

    class Operations:
        def execute(self, value: Any) -> None:
            sql.append(str(value))

        def __getattr__(self, name: str) -> Any:
            return lambda *args, **kwargs: None

    monkeypatch.setattr(module, "op", Operations())
    module.upgrade()
    return sql


async def test_the_backfill_stamps_each_row_with_its_film_and_marks_the_old_rules_stale(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bad Lieutenant's usual price, measured 12 Oct before the 16 Oct correction, is stale;
    its review found after it is the 2009 film's; the French Connection's page, chosen before
    the copy moved, is stale; a page a person chose stays as it stands."""
    craig = await _person(db)
    corrected_id, moved_from_id, other_id = _tmdb_ids()
    film = await _film(db, "Bad Lieutenant", tmdb_id=corrected_id, year=2009)
    usual = _usual(film, found_for_="x")
    usual.checked_utc = NOW - timedelta(days=4)
    review = _review(film, found_for_="x")
    review.found_utc = NOW + timedelta(days=1)
    db.add_all([usual, review])
    db.add(
        AdminAction(
            id=uuid.uuid4(),
            action_type="update",
            target_table="movies",
            target_id=str(film.id),
            changes={"kind": "identify", "tmdbId": corrected_id},
            created_at=NOW,
        )
    )
    # A merge is not a correction.
    merged_into = await _film(db, "Misery", tmdb_id=other_id, year=1990)
    merged_value = _value(merged_into, found_for_="x")
    merged_value.checked_utc = NOW - timedelta(days=4)
    db.add(merged_value)
    db.add(
        AdminAction(
            id=uuid.uuid4(),
            action_type="update",
            target_table="movies",
            target_id=str(merged_into.id),
            changes={"kind": "identify", "merge": {"sourceId": str(uuid.uuid4())}},
            created_at=NOW,
        )
    )
    first = await _film(db, "The French Connection", tmdb_id=moved_from_id, year=1971)
    disc, moved_lookup = await _paged(db, first, found_for_="x")
    chosen, chosen_lookup = await _paged(db, first, found_for_="x", decided_by=craig.id)
    for copy in (disc, chosen):
        db.add(
            AdminAction(
                id=uuid.uuid4(),
                action_type="update",
                target_table="collection_items",
                target_id=str(copy.id),
                changes={"kind": "move_copy"},
                created_at=NOW + timedelta(hours=1),
            )
        )
    await db.flush()

    for statement in _backfill(monkeypatch):
        await db.execute(text(statement))

    for row in (usual, review, merged_value, moved_lookup, chosen_lookup):
        await db.refresh(row)
    assert usual.found_for == "stale"
    assert review.found_for == f"film:{corrected_id}"
    assert merged_value.found_for == f"film:{other_id}"
    assert moved_lookup.found_for == "stale"
    assert chosen_lookup.found_for == f"film:{moved_from_id}"


# ---------------------------------------------------------------------------
# Two copies, one disc page (CT52-03)
# ---------------------------------------------------------------------------


async def test_two_owned_copies_with_one_disc_page_are_named_once_each(db: AsyncSession) -> None:
    """King Kong, 16 Nov: import row 878, the 1976 disc counted twice on the 2005 film."""
    tmdb_id, other_id, _ = _tmdb_ids()
    kong = await _film(db, "King Kong", tmdb_id=tmdb_id, year=2005)
    page = "https://www.blu-ray.com/movies/King-Kong-4K-Blu-ray/306836/"
    first = await _disc(db, kong, "4k_uhd", specs_source_url=page)
    await _disc(db, kong, "4k_uhd", specs_source_url=page)
    # Another format, another page, a copy in the Trash: none is the same disc twice.
    await _disc(db, kong, "blu_ray", specs_source_url=page)
    lone = await _film(db, "Hitchcock", tmdb_id=other_id, year=2012)
    await _disc(db, lone, "blu_ray", specs_source_url="https://www.blu-ray.com/movies/H/1/")
    await _disc(db, lone, "blu_ray", specs_source_url="https://www.blu-ray.com/movies/H/2/")

    results = dict(await check_copies_sharing_a_page(db, NOW))
    ours = {key: message for key, message in results.items() if str(kong.id) in key}
    assert list(ours.values()) == [
        "2 4K UHD copies of King Kong (2005) have the same disc page: is one disc counted "
        "twice? Check the shelf, and delete the extra copy in the app."
    ]
    assert not any(str(lone.id) in key for key in results)

    first.deleted_at = NOW
    await db.flush()
    results = dict(await check_copies_sharing_a_page(db, NOW))
    assert not any(str(kong.id) in key for key in results)
