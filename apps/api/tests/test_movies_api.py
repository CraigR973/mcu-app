"""Integration tests for Phase 2.1 — GET /api/v1/movies and GET /api/v1/movies/{id}.

Requires a live DATABASE_URL; skipped automatically when unset (same pattern as
test_derived_field_triggers.py). Each test inserts rows in the 9_900_1xx ID
range, commits them, then deletes them in teardown so nothing persists.
"""

from __future__ import annotations

import os

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient

DATABASE_URL = os.environ.get("DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — skipping live-DB movie API tests",
)

# IDs in the 9_900_1xx range reserved for Phase 2.1 tests (9_900_001+ used by Phase 1.8)
_TEST_IDS = [9_900_101, 9_900_102, 9_900_103]


@pytest.fixture(autouse=True)
def seed_movies():
    """Insert test movies before each test; delete them after."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO movies (id, title, original_title, overview, tagline,
                                release_date, popularity, vote_average, vote_count,
                                genre_ids)
            VALUES
                (9900101, 'Alpha Film',   'Alpha Film',   'Overview A', 'Tag A',
                 '2020-06-15', 9.5, 8.1, 1000, ARRAY[28, 12]),
                (9900102, 'Beta Film',    'Beta Film',    'Overview B', 'Tag B',
                 '2021-03-01', 7.2, 7.5,  800, ARRAY[12, 35]),
                (9900103, 'Gamma Film',   'Gamma Film',   'Overview C', 'Tag C',
                 '2022-11-20', 5.0, 6.9,  500, ARRAY[18])
            ON CONFLICT (id) DO NOTHING
            """,
        )
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM movies WHERE id = ANY(%s)", (_TEST_IDS,))
    conn.close()


@pytest.fixture()
def app():
    from src.main import app as _app

    return _app


# ---------------------------------------------------------------------------
# GET /api/v1/movies — list
# ---------------------------------------------------------------------------


async def test_list_movies_returns_envelope(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/movies", params={"per_page": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    meta = body["meta"]
    assert {"total", "page", "per_page", "pages"} <= meta.keys()


async def test_list_movies_pagination(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/api/v1/movies", params={"page": 1, "per_page": 2})
        r2 = await client.get("/api/v1/movies", params={"page": 2, "per_page": 2})
    assert r1.status_code == 200
    assert r2.status_code == 200
    ids_p1 = {m["id"] for m in r1.json()["data"]}
    ids_p2 = {m["id"] for m in r2.json()["data"]}
    assert ids_p1.isdisjoint(ids_p2), "pages must not overlap"


async def test_list_movies_filter_by_genre(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/movies", params={"genre_id": 28, "per_page": 100})
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["data"]}
    assert 9_900_101 in ids  # only Alpha has genre 28
    assert 9_900_102 not in ids
    assert 9_900_103 not in ids


async def test_list_movies_filter_by_year(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/movies", params={"year": 2021, "per_page": 100})
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["data"]}
    assert 9_900_102 in ids  # Beta is 2021
    assert 9_900_101 not in ids
    assert 9_900_103 not in ids


async def test_list_movies_filter_by_format(app):
    # Set best_format_owned on Alpha directly so we can filter by it
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE movies SET best_format_owned = '4k_bluray' WHERE id = 9900101"
        )
    conn.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/movies", params={"format": "4k_bluray", "per_page": 100}
        )
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["data"]}
    assert 9_900_101 in ids
    assert 9_900_102 not in ids


async def test_list_movies_sort_by_popularity_desc(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/movies",
            params={"sort": "popularity", "order": "desc", "per_page": 100},
        )
    assert resp.status_code == 200
    pops = [m["popularity"] for m in resp.json()["data"] if m["id"] in set(_TEST_IDS)]
    assert pops == sorted(pops, reverse=True)


async def test_list_movies_sort_by_title_asc(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/movies",
            params={"sort": "title", "order": "asc", "per_page": 100},
        )
    assert resp.status_code == 200
    titles = [m["title"] for m in resp.json()["data"] if m["id"] in set(_TEST_IDS)]
    assert titles == sorted(titles)


async def test_list_movies_response_fields(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/movies", params={"per_page": 100})
    assert resp.status_code == 200
    movie = next(m for m in resp.json()["data"] if m["id"] == 9_900_101)
    expected_fields = {
        "id", "title", "original_title", "release_date", "runtime",
        "popularity", "vote_average", "vote_count",
        "poster_path", "backdrop_path", "genre_ids",
        "best_format_owned", "best_hdr_owned", "best_audio_owned",
    }
    assert expected_fields <= movie.keys()
    assert movie["title"] == "Alpha Film"
    assert movie["genre_ids"] == [28, 12]


# ---------------------------------------------------------------------------
# GET /api/v1/movies/{id} — detail
# ---------------------------------------------------------------------------


async def test_get_movie_returns_detail(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/movies/9900101")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    detail = body["data"]
    assert detail["id"] == 9_900_101
    assert detail["title"] == "Alpha Film"
    assert detail["overview"] == "Overview A"
    assert detail["tagline"] == "Tag A"
    assert "cast" in detail
    assert "crew" in detail
    assert isinstance(detail["cast"], list)
    assert isinstance(detail["crew"], list)


async def test_get_movie_includes_credits(app):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO movie_credits
                (movie_id, person_id, person_name, credit_type, character, credit_order)
            VALUES
                (9900101, 1001, 'Alice Actor', 'cast', 'Hero', 1),
                (9900101, 2001, 'Bob Director', 'crew', NULL, 1)
            ON CONFLICT DO NOTHING
            """,
        )
    conn.close()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/movies/9900101")
        assert resp.status_code == 200
        detail = resp.json()["data"]
        cast_names = [c["person_name"] for c in detail["cast"]]
        crew_names = [c["person_name"] for c in detail["crew"]]
        assert "Alice Actor" in cast_names
        assert "Bob Director" in crew_names
    finally:
        conn2 = psycopg2.connect(DATABASE_URL)
        conn2.autocommit = True
        with conn2.cursor() as cur:
            cur.execute(
                "DELETE FROM movie_credits WHERE movie_id = 9900101 AND person_id IN (1001, 2001)"
            )
        conn2.close()


async def test_get_movie_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/movies/9999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Movie not found"


async def test_get_movie_detail_fields(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/movies/9900102")
    assert resp.status_code == 200
    detail = resp.json()["data"]
    full_fields = {
        "id", "title", "original_title", "overview", "tagline",
        "release_date", "runtime", "popularity", "vote_average", "vote_count",
        "poster_path", "backdrop_path", "genre_ids", "status",
        "budget", "revenue", "imdb_id", "homepage",
        "best_format_owned", "best_hdr_owned", "best_audio_owned",
        "cast", "crew",
    }
    assert full_fields <= detail.keys()
