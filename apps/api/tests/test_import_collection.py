"""Unit tests for apps/api/scripts/import_collection.py."""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make scripts importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from import_collection import (  # noqa: E402
    DEFAULT_CONDITION,
    REVIEW_FIELDNAMES,
    insert_collection_item,
    insert_credits,
    insert_movie,
    map_format,
    parse_release_date,
    write_review_file,
)

from src.spreadsheet.models import ImportCandidate  # noqa: E402
from src.tmdb.models import CastMember, Credits, CrewMember, Genre, Movie  # noqa: E402

# ---------------------------------------------------------------------------
# map_format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "parser_fmt, expected",
    [
        ("4k_uhd", "4k_bluray"),
        ("blu_ray", "bluray"),
        ("dvd", "dvd"),
        ("download", "digital"),
    ],
)
def test_map_format_known(parser_fmt: str, expected: str) -> None:
    assert map_format(parser_fmt) == expected


def test_map_format_unknown_returns_none() -> None:
    assert map_format("laserdisc") is None
    assert map_format("") is None
    assert map_format("vhs") is None


# ---------------------------------------------------------------------------
# parse_release_date
# ---------------------------------------------------------------------------


def test_parse_release_date_valid() -> None:
    assert parse_release_date("2024-07-26") == date(2024, 7, 26)


def test_parse_release_date_none() -> None:
    assert parse_release_date(None) is None


def test_parse_release_date_empty() -> None:
    assert parse_release_date("") is None


def test_parse_release_date_invalid() -> None:
    assert parse_release_date("not-a-date") is None
    assert parse_release_date("26/07/2024") is None


# ---------------------------------------------------------------------------
# write_review_file
# ---------------------------------------------------------------------------


def test_write_review_file(tmp_path: Path) -> None:
    out = tmp_path / "review.csv"
    rows = [
        {
            "row": 5,
            "title": "Dune 2",
            "query": "Dune 2",
            "query_year": "",
            "top_tmdb_id": 693134,
            "top_title": "Dune: Part Two",
            "top_year": 2024,
            "confidence": "0.720",
            "reason": "low_confidence",
        },
        {
            "row": 17,
            "title": "???",
            "query": "???",
            "query_year": "",
            "top_tmdb_id": "",
            "top_title": "",
            "top_year": "",
            "confidence": "",
            "reason": "no_results",
        },
    ]
    write_review_file(rows, out)

    assert out.exists()
    with out.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == REVIEW_FIELDNAMES
        parsed = list(reader)

    assert len(parsed) == 2
    assert parsed[0]["title"] == "Dune 2"
    assert parsed[0]["reason"] == "low_confidence"
    assert parsed[1]["reason"] == "no_results"


def test_write_review_file_empty(tmp_path: Path) -> None:
    out = tmp_path / "review.csv"
    write_review_file([], out)
    assert out.exists()
    with out.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == REVIEW_FIELDNAMES
        assert list(reader) == []


# ---------------------------------------------------------------------------
# Helpers: fake DB connection/cursor
# ---------------------------------------------------------------------------


def _make_conn(fetchone_return=None, rowcount=1):
    """Return a mock psycopg2 connection whose cursor reports the given rowcount."""
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = fetchone_return
    cur.rowcount = rowcount

    conn = MagicMock()
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    return conn, cur


def _make_movie(**kwargs) -> Movie:
    defaults = dict(
        id=550,
        title="Fight Club",
        original_title="Fight Club",
        overview="An insomniac office worker…",
        release_date="1999-10-15",
        runtime=139,
        popularity=61.416,
        vote_average=8.4,
        vote_count=26280,
        poster_path="/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
        backdrop_path=None,
        genres=[Genre(id=18, name="Drama")],
        status="Released",
        tagline="Mischief. Mayhem. Soap.",
        budget=63000000,
        revenue=100853753,
        imdb_id="tt0137523",
        homepage=None,
        credits=None,
        videos=None,
        watch_providers=None,
    )
    defaults.update(kwargs)
    return Movie(**defaults)


def _make_candidate(**kwargs) -> ImportCandidate:
    defaults = dict(
        row_number=1,
        title="Fight Club",
        formats=["blu_ray"],
        location_raw="Front 2nd shelf",
        section="Front",
        shelf="2nd",
        category="Film",
        sub_category=None,
        item_type=None,
    )
    defaults.update(kwargs)
    return ImportCandidate(**defaults)


# ---------------------------------------------------------------------------
# insert_movie
# ---------------------------------------------------------------------------


def test_insert_movie_new_row() -> None:
    conn, cur = _make_conn(rowcount=1)
    movie = _make_movie()
    result = insert_movie(conn, movie)
    assert result is True
    cur.execute.assert_called_once()
    sql = cur.execute.call_args[0][0]
    assert "ON CONFLICT (id) DO NOTHING" in sql


def test_insert_movie_duplicate() -> None:
    conn, cur = _make_conn(rowcount=0)
    movie = _make_movie()
    result = insert_movie(conn, movie)
    assert result is False


def test_insert_movie_passes_correct_id() -> None:
    conn, cur = _make_conn(rowcount=1)
    movie = _make_movie(id=12345)
    insert_movie(conn, movie)
    params = cur.execute.call_args[0][1]
    assert params["id"] == 12345


def test_insert_movie_genre_ids_extracted() -> None:
    conn, cur = _make_conn(rowcount=1)
    movie = _make_movie(genres=[Genre(id=28, name="Action"), Genre(id=18, name="Drama")])
    insert_movie(conn, movie)
    params = cur.execute.call_args[0][1]
    assert params["genre_ids"] == [28, 18]


def test_insert_movie_no_genres() -> None:
    conn, cur = _make_conn(rowcount=1)
    movie = _make_movie(genres=[])
    insert_movie(conn, movie)
    params = cur.execute.call_args[0][1]
    assert params["genre_ids"] == []


# ---------------------------------------------------------------------------
# insert_credits
# ---------------------------------------------------------------------------


def test_insert_credits_skipped_when_already_exist() -> None:
    conn, cur = _make_conn(fetchone_return=(3,))  # 3 existing credits
    movie = _make_movie(
        credits=Credits(
            cast=[
                CastMember(
                    id=1,
                    name="Brad Pitt",
                    character="Tyler Durden",
                    order=0,
                    profile_path=None,
                    credit_id="abc",
                )
            ],
            crew=[],
        )
    )
    with patch("import_collection.psycopg2.extras.execute_values") as mock_ev:
        insert_credits(conn, movie)
    mock_ev.assert_not_called()


def test_insert_credits_inserts_when_none_exist() -> None:
    conn, cur = _make_conn(fetchone_return=(0,))
    movie = _make_movie(
        credits=Credits(
            cast=[
                CastMember(
                    id=819,
                    name="Edward Norton",
                    character="The Narrator",
                    order=0,
                    profile_path=None,
                    credit_id="xyz",
                )
            ],
            crew=[
                CrewMember(
                    id=7467,
                    name="David Fincher",
                    job="Director",
                    department="Directing",
                    profile_path=None,
                    credit_id="def",
                )
            ],
        )
    )
    with patch("import_collection.psycopg2.extras.execute_values") as mock_ev:
        insert_credits(conn, movie)
    mock_ev.assert_called_once()
    rows = mock_ev.call_args[0][2]
    assert any(r[3] == "cast" for r in rows)
    assert any(r[3] == "crew" for r in rows)


def test_insert_credits_no_credits_object() -> None:
    conn, cur = _make_conn()
    movie = _make_movie(credits=None)
    with patch("import_collection.psycopg2.extras.execute_values") as mock_ev:
        insert_credits(conn, movie)
    mock_ev.assert_not_called()
    cur.execute.assert_not_called()


def test_insert_credits_filters_key_jobs_only() -> None:
    conn, cur = _make_conn(fetchone_return=(0,))
    movie = _make_movie(
        credits=Credits(
            cast=[],
            crew=[
                CrewMember(
                    id=1,
                    name="Joe A",
                    job="Director",
                    department="Directing",
                    profile_path=None,
                    credit_id="a",
                ),
                CrewMember(
                    id=2,
                    name="Joe B",
                    job="Gaffer",
                    department="Lighting",
                    profile_path=None,
                    credit_id="b",
                ),
                CrewMember(
                    id=3,
                    name="Joe C",
                    job="Screenplay",
                    department="Writing",
                    profile_path=None,
                    credit_id="c",
                ),
            ],
        )
    )
    with patch("import_collection.psycopg2.extras.execute_values") as mock_ev:
        insert_credits(conn, movie)
    rows = mock_ev.call_args[0][2]
    jobs = [r[6] for r in rows]
    assert "Director" in jobs
    assert "Screenplay" in jobs
    assert "Gaffer" not in jobs


# ---------------------------------------------------------------------------
# insert_collection_item
# ---------------------------------------------------------------------------


def test_insert_collection_item_new() -> None:
    conn, cur = _make_conn(fetchone_return=None)
    cand = _make_candidate(location_raw="Front 2nd shelf")
    result = insert_collection_item(conn, 550, cand, "bluray")
    assert result is True
    insert_call = [c for c in cur.execute.call_args_list if "INSERT" in str(c)]
    assert insert_call


def test_insert_collection_item_duplicate() -> None:
    conn, cur = _make_conn(fetchone_return=(1,))
    cand = _make_candidate()
    result = insert_collection_item(conn, 550, cand, "bluray")
    assert result is False
    # No INSERT should have been called
    for c in cur.execute.call_args_list:
        assert "INSERT" not in str(c)


def test_insert_collection_item_uses_default_condition() -> None:
    conn, cur = _make_conn(fetchone_return=None)
    cand = _make_candidate()
    insert_collection_item(conn, 550, cand, "dvd")
    insert_call = [c for c in cur.execute.call_args_list if "INSERT" in str(c)]
    assert insert_call
    params = insert_call[0][0][1]
    assert params[2] == DEFAULT_CONDITION


def test_insert_collection_item_stores_location_in_notes() -> None:
    conn, cur = _make_conn(fetchone_return=None)
    cand = _make_candidate(location_raw="Garage shelf 3")
    insert_collection_item(conn, 550, cand, "4k_bluray")
    insert_call = [c for c in cur.execute.call_args_list if "INSERT" in str(c)]
    params = insert_call[0][0][1]
    assert params[3] == "Garage shelf 3"


def test_insert_collection_item_empty_location_stored_as_none() -> None:
    conn, cur = _make_conn(fetchone_return=None)
    cand = _make_candidate(location_raw="")
    insert_collection_item(conn, 550, cand, "dvd")
    insert_call = [c for c in cur.execute.call_args_list if "INSERT" in str(c)]
    params = insert_call[0][0][1]
    assert params[3] is None
