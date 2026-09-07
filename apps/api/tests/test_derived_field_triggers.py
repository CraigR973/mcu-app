"""Integration tests for migration 0015 — derived field triggers.

These tests exercise a live Postgres database after Batch 4 has restored the domain
schema. Each test runs
inside a transaction that is rolled back at teardown, so nothing persists.

Skipped automatically when ``DATABASE_URL`` is not set or the Batch 4 ``movies`` and
``collection_items`` tables do not exist. Batch 2 deliberately removes the legacy
domain schema before its replacement lands.
"""

from __future__ import annotations

import os

import psycopg2
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL")


def _domain_schema_exists() -> bool:
    if not DATABASE_URL:
        return False
    try:
        with (
            psycopg2.connect(DATABASE_URL) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT to_regclass('public.movies'), to_regclass('public.collection_items')"
            )
            return cursor.fetchone() == ("movies", "collection_items")
    except psycopg2.Error:
        return False


pytestmark = pytest.mark.skipif(
    not _domain_schema_exists(),
    reason="Batch 4 domain schema is not available — skipping derived-field tests",
)


# Reserve an unused TMDB-ID range for test fixtures so we never collide with
# real catalogue rows. TMDB IDs are <10M in 2026; 9_900_000+ is safe.
TEST_MOVIE_ID = 9_900_001


@pytest.fixture()
def db():
    """Yield a connection inside a transaction; ROLLBACK on teardown."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _insert_movie(conn, movie_id: int = TEST_MOVIE_ID, **overrides) -> None:
    cols = {
        "id": movie_id,
        "title": "The Test Movie",
        "original_title": "The Test Movie",
        "overview": "A film about testing.",
        "tagline": "Tested to the limit.",
    }
    cols.update(overrides)
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO movies ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
            list(cols.values()),
        )


def _insert_item(conn, movie_id: int = TEST_MOVIE_ID, **overrides) -> int:
    cols = {
        "movie_id": movie_id,
        "format": "dvd",
        "condition": "very_good",
    }
    cols.update(overrides)
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO collection_items ({', '.join(cols)}) "
            f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id",
            list(cols.values()),
        )
        return cur.fetchone()[0]


def _movie_row(conn, movie_id: int = TEST_MOVIE_ID) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT best_format_owned, best_hdr_owned, best_audio_owned, "
            "       search_vector::text "
            "FROM movies WHERE id = %s",
            (movie_id,),
        )
        row = cur.fetchone()
        return {
            "best_format_owned": row[0],
            "best_hdr_owned": row[1],
            "best_audio_owned": row[2],
            "search_vector": row[3],
        }


# ---------------------------------------------------------------------------
# search_vector trigger
# ---------------------------------------------------------------------------


def test_search_vector_populated_on_insert(db):
    # Postgres' English stemmer normalises lexemes ('fury' -> 'furi',
    # 'roads' -> 'road'), so we assert against stemmed forms.
    _insert_movie(db, title="Mad Max Fury Road")
    sv = _movie_row(db)["search_vector"]
    assert sv is not None
    assert "'mad':1A" in sv
    assert "'max':2A" in sv
    assert "'furi':3A" in sv
    assert "'road':4A" in sv


def test_search_vector_recomputed_on_title_change(db):
    _insert_movie(db, title="Original Title")
    with db.cursor() as cur:
        cur.execute(
            "UPDATE movies SET title = %s WHERE id = %s",
            ("Replacement Title", TEST_MOVIE_ID),
        )
    sv = _movie_row(db)["search_vector"]
    assert "'replac':1A" in sv
    assert "origin" not in sv


def test_search_vector_includes_overview_and_tagline(db):
    _insert_movie(
        db,
        title="X",
        overview="Spaceships explore distant galaxies.",
        tagline="Beyond the stars.",
    )
    sv = _movie_row(db)["search_vector"]
    assert "spaceship" in sv
    assert "galaxi" in sv  # English stemmer
    assert "star" in sv


# ---------------------------------------------------------------------------
# best_format_owned
# ---------------------------------------------------------------------------


def test_format_set_on_first_insert(db):
    _insert_movie(db)
    assert _movie_row(db)["best_format_owned"] is None
    _insert_item(db, format="dvd")
    assert _movie_row(db)["best_format_owned"] == "dvd"


def test_format_upgrades_to_higher_quality(db):
    _insert_movie(db)
    _insert_item(db, format="dvd")
    _insert_item(db, format="4k_bluray")
    assert _movie_row(db)["best_format_owned"] == "4k_bluray"


def test_format_unchanged_when_lower_added(db):
    _insert_movie(db)
    _insert_item(db, format="bluray")
    _insert_item(db, format="dvd")
    assert _movie_row(db)["best_format_owned"] == "bluray"


def test_format_downgrades_after_soft_delete(db):
    _insert_movie(db)
    _insert_item(db, format="dvd")
    uhd_id = _insert_item(db, format="4k_bluray")
    assert _movie_row(db)["best_format_owned"] == "4k_bluray"

    # DELETE on collection_items is converted to soft-delete by the existing
    # BEFORE trigger; the AFTER UPDATE on deleted_at fires the recalc.
    with db.cursor() as cur:
        cur.execute("DELETE FROM collection_items WHERE id = %s", (uhd_id,))
    assert _movie_row(db)["best_format_owned"] == "dvd"


def test_format_null_when_all_items_deleted(db):
    _insert_movie(db)
    item_id = _insert_item(db, format="bluray")
    with db.cursor() as cur:
        cur.execute("DELETE FROM collection_items WHERE id = %s", (item_id,))
    assert _movie_row(db)["best_format_owned"] is None


# ---------------------------------------------------------------------------
# best_hdr_owned
# ---------------------------------------------------------------------------


def test_hdr_picks_dolby_vision_over_hdr10(db):
    _insert_movie(db)
    _insert_item(db, format="4k_bluray", hdr_format="hdr10")
    _insert_item(db, format="4k_bluray", hdr_format="dolby_vision")
    assert _movie_row(db)["best_hdr_owned"] == "dolby_vision"


def test_hdr_ignores_null_and_empty(db):
    _insert_movie(db)
    _insert_item(db, format="bluray", hdr_format=None)
    assert _movie_row(db)["best_hdr_owned"] is None
    _insert_item(db, format="4k_bluray", hdr_format="hdr10")
    assert _movie_row(db)["best_hdr_owned"] == "hdr10"


# ---------------------------------------------------------------------------
# best_audio_owned
# ---------------------------------------------------------------------------


def test_audio_unnests_arrays_and_picks_atmos(db):
    _insert_movie(db)
    _insert_item(db, format="bluray", audio_formats=["dts", "dolby_digital"])
    _insert_item(db, format="4k_bluray", audio_formats=["dolby_atmos", "dts_hd_ma"])
    assert _movie_row(db)["best_audio_owned"] == "dolby_atmos"


def test_audio_returns_null_when_no_arrays(db):
    _insert_movie(db)
    _insert_item(db, format="dvd", audio_formats=None)
    assert _movie_row(db)["best_audio_owned"] is None


# ---------------------------------------------------------------------------
# transactional acceptance: a single statement updates derived fields atomically
# ---------------------------------------------------------------------------


def test_derived_fields_updated_in_same_transaction(db):
    """Adding a collection_item and reading the movie within the same
    transaction should see the new derived values — no commit needed."""
    _insert_movie(db)
    _insert_item(
        db,
        format="4k_bluray",
        hdr_format="dolby_vision",
        audio_formats=["dolby_atmos", "dts_hd_ma"],
    )
    # No commit — read the movie row back in this same transaction.
    row = _movie_row(db)
    assert row["best_format_owned"] == "4k_bluray"
    assert row["best_hdr_owned"] == "dolby_vision"
    assert row["best_audio_owned"] == "dolby_atmos"
