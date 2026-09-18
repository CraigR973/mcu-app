"""Postgres acceptance coverage for Batch 39's collection replacement.

This test is deliberately limited to CI's disposable localhost database. A replacement
touches every live ``collection_items`` row before this transaction rolls back, so it must
never be pointed at production merely to turn a local skip green.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from urllib.parse import urlsplit

import psycopg2
import psycopg2.extras
import pytest

from src.config import psycopg2_dsn
from src.scripts.import_collection import (
    HistoryWouldBeOrphaned,
    ImportRow,
    ImportStats,
    LiveFilmIndex,
    ReplacementBlocked,
    ensure_history_survives,
    ensure_replacement_allowed,
    orphan_risk,
    replace_collection_items,
    replacement_plan,
)
from src.spreadsheet.models import ImportCandidate
from src.tmdb.models import Genre, Movie

DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_HOST = urlsplit(DATABASE_URL).hostname if DATABASE_URL else None

pytestmark = pytest.mark.skipif(
    DATABASE_HOST not in {"localhost", "127.0.0.1", "::1"},
    reason="collection replacement acceptance requires disposable localhost Postgres",
)


@pytest.fixture()
def db():
    assert DATABASE_URL is not None
    conn = psycopg2.connect(psycopg2_dsn(DATABASE_URL))
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _insert_movie(
    conn,
    *,
    title: str,
    tmdb_id: int | None,
    year: int | None,
) -> uuid.UUID:
    movie_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO movies (id, tmdb_id, title, year, media_type) "
            "VALUES (%s, %s, %s, %s, 'film')",
            (str(movie_id), tmdb_id, title, year),
        )
    return movie_id


def _insert_item(
    conn,
    *,
    movie_id: uuid.UUID,
    source_row: int,
    formats: list[str],
) -> uuid.UUID:
    item_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO collection_items
                (id, movie_id, formats, condition, import_source_row)
            VALUES (%s, %s, %s, 'good', %s)
            """,
            (
                str(item_id),
                str(movie_id),
                psycopg2.extras.Json(formats),
                source_row,
            ),
        )
    return item_id


def _insert_watch(conn, *, movie_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    watch_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO watch_log (id, movie_id, user_id, watched_at, is_rewatch)
            VALUES (%s, %s, %s, %s, false)
            """,
            (str(watch_id), str(movie_id), str(user_id), date(2026, 9, 16)),
        )
    return watch_id


def _seed_profile(conn) -> uuid.UUID:
    user_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, display_name, role, is_active) "
            "VALUES (%s, %s, 'admin', true)",
            (str(user_id), f"Orphan Guard {uuid.uuid4().hex[:8]}"),
        )
    return user_id


def _replacement_movie(tmdb_id: int) -> Movie:
    return Movie(
        id=tmdb_id,
        title="TMDB Would Rename This",
        original_title="TMDB Would Rename This",
        overview="Fresh metadata which must not overwrite the existing movie row.",
        release_date="2001-01-01",
        runtime=100,
        popularity=1.0,
        vote_average=7.0,
        vote_count=100,
        poster_path=None,
        backdrop_path=None,
        genres=[Genre(id=18, name="Drama")],
        status="Released",
        tagline=None,
        budget=0,
        revenue=0,
        imdb_id=None,
        homepage=None,
        credits=None,
        videos=None,
        watch_providers=None,
    )


def test_guarded_replace_keeps_movies_and_watches_and_recalculates_ownership(db) -> None:
    unique = uuid.uuid4().int
    tmdb_id = 800_000_000 + unique % 100_000_000
    source_row = 2_000_000 + unique % 100_000_000
    user_id = uuid.uuid4()

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, display_name, role, is_active) "
            "VALUES (%s, %s, 'admin', true)",
            (str(user_id), f"Refresh Test {unique}"),
        )

    identified_id = _insert_movie(
        db,
        title="Existing Canonical Title",
        tmdb_id=tmdb_id,
        year=1999,
    )
    unidentified_id = _insert_movie(
        db,
        title="Messy Title, The",
        tmdb_id=None,
        year=None,
    )
    identified_old_item = _insert_item(
        db,
        movie_id=identified_id,
        source_row=source_row,
        formats=["4k_uhd"],
    )
    unidentified_old_item = _insert_item(
        db,
        movie_id=unidentified_id,
        source_row=source_row + 1,
        formats=["dvd"],
    )
    identified_watch = _insert_watch(db, movie_id=identified_id, user_id=user_id)
    unidentified_watch = _insert_watch(db, movie_id=unidentified_id, user_id=user_id)

    before = replacement_plan(db)
    assert before.live_items == 2
    assert before.unidentified_films_with_watches == 1
    assert before.watch_rows_at_risk == 1
    with pytest.raises(ReplacementBlocked):
        ensure_replacement_allowed(before, accept_split=False)

    candidate = ImportCandidate(
        row_number=source_row,
        title="Existing Canonical Title",
        formats=["blu_ray"],
        location_raw="Front 1st shelf",
        section="Front",
        shelf="1st",
        category="Film",
        sub_category=None,
        item_type=None,
    )
    stats = ImportStats()
    replace_collection_items(
        db,
        [ImportRow(candidate=candidate, movie=_replacement_movie(tmdb_id))],
        stats,
        accept_split=True,
    )

    assert stats.items_replaced == 2
    assert stats.items_inserted == 1
    assert stats.items_skipped == 0
    assert stats.movies_inserted == 0

    with db.cursor() as cur:
        cur.execute(
            "SELECT deleted_at IS NOT NULL FROM collection_items WHERE id IN (%s, %s) ORDER BY id",
            (str(identified_old_item), str(unidentified_old_item)),
        )
        assert [row[0] for row in cur.fetchall()] == [True, True]

        cur.execute(
            "SELECT count(*), min(movie_id::text) FROM collection_items WHERE deleted_at IS NULL"
        )
        live_count, live_movie_id = cur.fetchone()
        assert live_count == 1
        assert live_movie_id == str(identified_id)

        cur.execute(
            "SELECT count(*) FROM movies WHERE tmdb_id = %s",
            (tmdb_id,),
        )
        assert cur.fetchone()[0] == 1

        cur.execute(
            "SELECT title, year, best_format_owned FROM movies WHERE id = %s",
            (str(identified_id),),
        )
        assert cur.fetchone() == ("Existing Canonical Title", 1999, "blu_ray")

        cur.execute(
            "SELECT id, movie_id FROM watch_log WHERE id IN (%s, %s) ORDER BY id",
            (str(identified_watch), str(unidentified_watch)),
        )
        watches = {uuid.UUID(str(row[0])): uuid.UUID(str(row[1])) for row in cur.fetchall()}
        assert watches == {
            identified_watch: identified_id,
            unidentified_watch: unidentified_id,
        }

        # This is the exact state §13.5's already-covered restore-row route consumes:
        # the old row remains complete and differs only by its tombstone.
        cur.execute(
            "SELECT movie_id, formats, import_source_row, deleted_at IS NOT NULL "
            "FROM collection_items WHERE id = %s",
            (str(identified_old_item),),
        )
        old_movie_id, old_formats, old_source_row, is_deleted = cur.fetchone()
        assert uuid.UUID(str(old_movie_id)) == identified_id
        assert old_formats == ["4k_uhd"]
        assert old_source_row == source_row
        assert is_deleted is True


# ---------------------------------------------------------------------------
# Batch 41 — the history-orphan guard
#
# Batch 39's guard asks "is any *unidentified* film watched?". The 2026-09-18 dry run of
# the fresh sheet passed that guard with 1 and planned to strand **587 watch rows**
# anyway, because the films at risk had just been identified (`DECISIONS.md` #198). The
# question that actually protects the history is the one below: will every watched film
# still own a disc when this is over?
# ---------------------------------------------------------------------------


def _row_for(title: str, *, tmdb_id: int | None = None, source_row: int = 2) -> ImportRow:
    candidate = ImportCandidate(
        row=source_row,
        title=title,
        formats=["blu_ray"],
        location=None,
        category=None,
        sub_category=None,
        media_type="film",
    )
    return ImportRow(
        candidate=candidate,
        movie=_replacement_movie(tmdb_id) if tmdb_id is not None else None,
    )


def test_orphan_risk_sees_a_watched_identified_film_the_sheet_cannot_settle(db) -> None:
    """The exact shape of the 2026-09-18 defect, in Postgres.

    `Double Indemnity` is identified and watched. The sheet names it, but TMDB returns an
    ambiguous result so the row arrives with no `movie` — and before Batch 41 that meant a
    fresh title-only row and a stranded watch. The guard must see it coming.
    """
    user_id = _seed_profile(db)
    watched = _insert_movie(db, title="Double Indemnity", tmdb_id=996, year=1944)
    _insert_item(db, movie_id=watched, source_row=2, formats=["blu_ray"])
    _insert_watch(db, movie_id=watched, user_id=user_id)

    index = LiveFilmIndex.load(db)
    risk = orphan_risk(db, [_row_for("Double Indemnity")], index)

    assert risk.films == 0, "the index resolves it by title, so nothing is stranded"

    # And with the film absent from the index — the pre-Batch-41 behaviour — it is seen.
    risk_without = orphan_risk(db, [_row_for("Double Indemnity")], LiveFilmIndex([]))
    assert risk_without.films == 1
    assert risk_without.watch_rows == 1
    assert "Double Indemnity (1)" in risk_without.examples


def test_orphan_risk_counts_a_watched_film_the_sheet_no_longer_lists(db) -> None:
    """A disc genuinely sold or removed still strands its history, and should be named."""
    user_id = _seed_profile(db)
    gone = _insert_movie(db, title="Sold Last Year", tmdb_id=997, year=1999)
    _insert_item(db, movie_id=gone, source_row=3, formats=["dvd"])
    _insert_watch(db, movie_id=gone, user_id=user_id)

    risk = orphan_risk(db, [_row_for("Something Else Entirely")], LiveFilmIndex.load(db))

    assert risk.films == 1
    assert risk.watch_rows == 1
    assert risk.examples == ["Sold Last Year (1)"]


def test_orphan_risk_follows_a_matched_row_to_its_tmdb_id(db) -> None:
    """Resolution must mirror the write path, not second-guess it.

    A high-confidence row lands on its `tmdb_id`, so a film reached that way is safe even
    though its title in the sheet differs from the title we hold.
    """
    user_id = _seed_profile(db)
    watched = _insert_movie(db, title="Ben-Hur", tmdb_id=665, year=1959)
    _insert_item(db, movie_id=watched, source_row=4, formats=["blu_ray"])
    _insert_watch(db, movie_id=watched, user_id=user_id)

    risk = orphan_risk(db, [_row_for("Ben Hur", tmdb_id=665)], LiveFilmIndex.load(db))

    assert risk.films == 0


def test_a_film_with_no_watch_history_is_not_a_reason_to_refuse(db) -> None:
    """The guard protects history, not discs. Losing an unwatched film is ordinary."""
    unwatched = _insert_movie(db, title="Never Watched", tmdb_id=998, year=2001)
    _insert_item(db, movie_id=unwatched, source_row=5, formats=["dvd"])

    risk = orphan_risk(db, [_row_for("Something Else")], LiveFilmIndex.load(db))

    assert risk.films == 0


def test_the_replacement_refuses_rather_than_stranding_history(db) -> None:
    user_id = _seed_profile(db)
    watched = _insert_movie(db, title="Stranded", tmdb_id=999, year=1980)
    _insert_item(db, movie_id=watched, source_row=6, formats=["dvd"])
    _insert_watch(db, movie_id=watched, user_id=user_id)

    risk = orphan_risk(db, [_row_for("Nothing Like It")], LiveFilmIndex.load(db))

    with pytest.raises(HistoryWouldBeOrphaned) as caught:
        ensure_history_survives(risk, accept_split=False)
    assert "1 films holding 1 watch rows" in str(caught.value)
    assert "Stranded (1)" in str(caught.value)

    # Named and accepted, it proceeds — the same override Batch 39 established.
    ensure_history_survives(risk, accept_split=True)
