"""Integration tests for migration 003's derived-field triggers (roadmap phase 1.8).

These exercise a live Postgres database. Each test runs inside a transaction that is
rolled back at teardown, so nothing persists — which also means they can be pointed at a
populated database without touching its rows.

Skipped only when ``DATABASE_URL`` is unset or unreachable, or the domain schema has not
been migrated. CI provides Postgres 17 and runs ``alembic upgrade head`` first, so a skip
there means a real failure, not a missing database.

**These tests were re-authored in Batch 4 and are not the April file.** They assert the
same thirteen behaviours against the §3.4 schema that replaced the April one: a UUID
primary key on ``movies`` instead of the TMDB id, a ``formats`` JSONB array instead of a
scalar ``format`` column, and ``video_specs``/``audio_specs`` JSONB instead of scalar
``hdr_format`` and ``audio_formats[]``. The behaviour under test is unchanged; only the
shape it is expressed in moved.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import psycopg2
import psycopg2.extras
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
    reason="domain schema is not available — set DATABASE_URL and run `alembic upgrade head`",
)


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


def _insert_movie(conn, **overrides: Any) -> uuid.UUID:
    """Insert a movie and return its id."""
    cols: dict[str, Any] = {
        "id": uuid.uuid4(),
        "title": "The Test Movie",
        "original_title": "The Test Movie",
        "overview": "A film about testing.",
        "tagline": "Tested to the limit.",
    }
    cols.update(overrides)
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO movies ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
            [str(v) if isinstance(v, uuid.UUID) else v for v in cols.values()],
        )
    movie_id = cols["id"]
    assert isinstance(movie_id, uuid.UUID)
    return movie_id


def _insert_item(
    conn,
    movie_id: uuid.UUID,
    formats: list[str] | None = None,
    hdr: list[str] | None = None,
    audio: list[str] | None = None,
    **overrides: Any,
) -> uuid.UUID:
    """Insert a collection item for ``movie_id`` and return its id.

    ``hdr`` and ``audio`` are the convenience shape the assertions care about; they are
    written into the ``video_specs``/``audio_specs`` JSONB documents §3.4 specifies.
    """
    cols: dict[str, Any] = {
        "id": uuid.uuid4(),
        "movie_id": str(movie_id),
        "formats": psycopg2.extras.Json(formats if formats is not None else ["dvd"]),
        "condition": "good",
    }
    if hdr is not None:
        cols["video_specs"] = psycopg2.extras.Json({"resolution": "2160p", "hdr": hdr})
    if audio is not None:
        cols["audio_specs"] = psycopg2.extras.Json(
            [{"language": "English", "format": fmt} for fmt in audio]
        )
    cols.update(overrides)
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO collection_items ({', '.join(cols)}) "
            f"VALUES ({', '.join(['%s'] * len(cols))})",
            [str(v) if isinstance(v, uuid.UUID) else v for v in cols.values()],
        )
    item_id = cols["id"]
    assert isinstance(item_id, uuid.UUID)
    return item_id


def _movie_row(conn, movie_id: uuid.UUID) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT best_format_owned, best_hdr_owned, best_audio_owned, "
            "       search_vector::text "
            "FROM movies WHERE id = %s",
            (str(movie_id),),
        )
        row = cur.fetchone()
        assert row is not None
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
    movie_id = _insert_movie(db, title="Mad Max Fury Road")
    sv = _movie_row(db, movie_id)["search_vector"]
    assert sv is not None
    assert "'mad':1A" in sv
    assert "'max':2A" in sv
    assert "'furi':3A" in sv
    assert "'road':4A" in sv


def test_search_vector_recomputed_on_title_change(db):
    movie_id = _insert_movie(db, title="Original Title")
    with db.cursor() as cur:
        cur.execute(
            "UPDATE movies SET title = %s WHERE id = %s",
            ("Replacement Title", str(movie_id)),
        )
    sv = _movie_row(db, movie_id)["search_vector"]
    assert "'replac':1A" in sv
    assert "origin" not in sv


def test_search_vector_includes_overview_and_tagline(db):
    movie_id = _insert_movie(
        db,
        title="X",
        overview="Spaceships explore distant galaxies.",
        tagline="Beyond the stars.",
    )
    sv = _movie_row(db, movie_id)["search_vector"]
    assert "spaceship" in sv
    assert "galaxi" in sv  # English stemmer
    assert "star" in sv


# ---------------------------------------------------------------------------
# best_format_owned
# ---------------------------------------------------------------------------


def test_format_set_on_first_insert(db):
    movie_id = _insert_movie(db)
    assert _movie_row(db, movie_id)["best_format_owned"] is None
    _insert_item(db, movie_id, formats=["dvd"])
    assert _movie_row(db, movie_id)["best_format_owned"] == "dvd"


def test_format_upgrades_to_higher_quality(db):
    movie_id = _insert_movie(db)
    _insert_item(db, movie_id, formats=["dvd"])
    _insert_item(db, movie_id, formats=["4k_uhd"])
    assert _movie_row(db, movie_id)["best_format_owned"] == "4k_uhd"


def test_format_unchanged_when_lower_added(db):
    movie_id = _insert_movie(db)
    _insert_item(db, movie_id, formats=["blu_ray"])
    _insert_item(db, movie_id, formats=["dvd"])
    assert _movie_row(db, movie_id)["best_format_owned"] == "blu_ray"


def test_format_picks_best_within_a_combo_pack(db):
    """A single item can hold several formats — the §3.4 shape the April scalar
    column could not express, so this behaviour had no test before."""
    movie_id = _insert_movie(db)
    _insert_item(db, movie_id, formats=["blu_ray", "download"])
    assert _movie_row(db, movie_id)["best_format_owned"] == "blu_ray"


def test_format_downgrades_after_soft_delete(db):
    movie_id = _insert_movie(db)
    _insert_item(db, movie_id, formats=["dvd"])
    uhd_id = _insert_item(db, movie_id, formats=["4k_uhd"])
    assert _movie_row(db, movie_id)["best_format_owned"] == "4k_uhd"

    # DELETE on collection_items is converted to soft-delete by the BEFORE trigger;
    # the AFTER UPDATE on deleted_at fires the recalc.
    with db.cursor() as cur:
        cur.execute("DELETE FROM collection_items WHERE id = %s", (str(uhd_id),))
    assert _movie_row(db, movie_id)["best_format_owned"] == "dvd"


def test_format_null_when_all_items_deleted(db):
    movie_id = _insert_movie(db)
    item_id = _insert_item(db, movie_id, formats=["blu_ray"])
    with db.cursor() as cur:
        cur.execute("DELETE FROM collection_items WHERE id = %s", (str(item_id),))
    assert _movie_row(db, movie_id)["best_format_owned"] is None


# ---------------------------------------------------------------------------
# best_hdr_owned
# ---------------------------------------------------------------------------


def test_hdr_picks_dolby_vision_over_hdr10(db):
    movie_id = _insert_movie(db)
    _insert_item(db, movie_id, formats=["4k_uhd"], hdr=["HDR10"])
    _insert_item(db, movie_id, formats=["4k_uhd"], hdr=["Dolby Vision"])
    assert _movie_row(db, movie_id)["best_hdr_owned"] == "Dolby Vision"


def test_hdr_ignores_null_and_empty(db):
    movie_id = _insert_movie(db)
    _insert_item(db, movie_id, formats=["blu_ray"])
    assert _movie_row(db, movie_id)["best_hdr_owned"] is None
    _insert_item(db, movie_id, formats=["4k_uhd"], hdr=["HDR10"])
    assert _movie_row(db, movie_id)["best_hdr_owned"] == "HDR10"


# ---------------------------------------------------------------------------
# best_audio_owned
# ---------------------------------------------------------------------------


def test_audio_unnests_arrays_and_picks_atmos(db):
    movie_id = _insert_movie(db)
    _insert_item(db, movie_id, formats=["blu_ray"], audio=["DTS", "Dolby Digital"])
    _insert_item(db, movie_id, formats=["4k_uhd"], audio=["Dolby Atmos", "DTS-HD MA"])
    assert _movie_row(db, movie_id)["best_audio_owned"] == "Dolby Atmos"


def test_audio_returns_null_when_no_arrays(db):
    movie_id = _insert_movie(db)
    _insert_item(db, movie_id, formats=["dvd"])
    assert _movie_row(db, movie_id)["best_audio_owned"] is None


# ---------------------------------------------------------------------------
# transactional acceptance: a single statement updates derived fields atomically
# ---------------------------------------------------------------------------


def test_derived_fields_updated_in_same_transaction(db):
    """Adding a collection_item and reading the movie within the same
    transaction should see the new derived values — no commit needed."""
    movie_id = _insert_movie(db)
    _insert_item(
        db,
        movie_id,
        formats=["4k_uhd"],
        hdr=["Dolby Vision"],
        audio=["Dolby Atmos", "DTS-HD MA"],
    )
    # No commit — read the movie row back in this same transaction.
    row = _movie_row(db, movie_id)
    assert row["best_format_owned"] == "4k_uhd"
    assert row["best_hdr_owned"] == "Dolby Vision"
    assert row["best_audio_owned"] == "Dolby Atmos"
