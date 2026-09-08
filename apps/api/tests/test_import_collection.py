"""Unit tests for src/scripts/import_collection.py.

Re-authored in Batch 4 alongside the importer itself. The April version of this file
tested the April schema — a scalar ``format`` column, a TMDB integer primary key, and
``notes`` holding the raw location string. All three are gone; the assertions that
pinned them are replaced by ones that pin §3.4's shape, including the location columns
whose absence was the defect this batch exists to fix.
"""

from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.scripts.import_collection import (
    DEFAULT_CONDITION,
    REVIEW_FIELDNAMES,
    build_top_cast_summary,
    credit_rows,
    insert_collection_item,
    insert_credits,
    parse_year,
    pick_trailer_key,
    upsert_movie,
    upsert_unmatched_movie,
    write_review_file,
)
from src.spreadsheet.models import ImportCandidate
from src.tmdb.models import (
    CastMember,
    Credits,
    CrewMember,
    Genre,
    Movie,
    Video,
    Videos,
)

# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _make_conn(fetchone_returns: list[Any] | None = None):
    """Mock psycopg2 connection whose cursor replays ``fetchone_returns`` in order."""
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    if fetchone_returns is None:
        cur.fetchone.return_value = None
    else:
        cur.fetchone.side_effect = list(fetchone_returns)

    conn = MagicMock()
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    return conn, cur


def _make_movie(**kwargs) -> Movie:
    defaults: dict[str, Any] = dict(
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
    defaults: dict[str, Any] = dict(
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


def _cast(idx: int, name: str, order: int) -> CastMember:
    return CastMember(
        id=idx, name=name, character=f"{name}'s role", order=order, credit_id=f"c{idx}"
    )


def _crew(idx: int, name: str, job: str, department: str = "Directing") -> CrewMember:
    return CrewMember(id=idx, name=name, job=job, department=department, credit_id=f"w{idx}")


# ---------------------------------------------------------------------------
# parse_year
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1999-10-15", 1999),
        ("2024-01-01", 2024),
        ("1954", 1954),
        (None, None),
        ("", None),
        ("not-a-date", None),
    ],
)
def test_parse_year(raw: str | None, expected: int | None) -> None:
    assert parse_year(raw) == expected


# ---------------------------------------------------------------------------
# pick_trailer_key
# ---------------------------------------------------------------------------


def test_pick_trailer_key_prefers_official() -> None:
    movie = _make_movie(
        videos=Videos(
            results=[
                Video(id="1", key="unofficial", site="YouTube", type="Trailer", name="Fan cut"),
                Video(
                    id="2",
                    key="official",
                    site="YouTube",
                    type="Trailer",
                    name="Official",
                    official=True,
                ),
            ]
        )
    )
    assert pick_trailer_key(movie) == "official"


def test_pick_trailer_key_falls_back_to_first_youtube_trailer() -> None:
    movie = _make_movie(
        videos=Videos(
            results=[Video(id="1", key="only", site="YouTube", type="Trailer", name="Trailer")]
        )
    )
    assert pick_trailer_key(movie) == "only"


def test_pick_trailer_key_ignores_non_youtube_and_non_trailers() -> None:
    movie = _make_movie(
        videos=Videos(
            results=[
                Video(id="1", key="v", site="Vimeo", type="Trailer", name="Vimeo"),
                Video(id="2", key="c", site="YouTube", type="Clip", name="A clip"),
            ]
        )
    )
    assert pick_trailer_key(movie) is None


def test_pick_trailer_key_no_videos() -> None:
    assert pick_trailer_key(_make_movie()) is None


# ---------------------------------------------------------------------------
# build_top_cast_summary
# ---------------------------------------------------------------------------


def test_top_cast_summary_takes_five_in_billing_order() -> None:
    cast = [_cast(i, f"Actor {i}", order=i) for i in range(8)]
    # Shuffled input: the summary must sort by billing order, not by arrival.
    movie = _make_movie(credits=Credits(cast=list(reversed(cast)), crew=[]))
    summary = build_top_cast_summary(movie)
    assert summary is not None
    assert [entry["name"] for entry in summary] == [f"Actor {i}" for i in range(5)]
    assert summary[0]["tmdb_person_id"] == 0
    assert summary[0]["character_name"] == "Actor 0's role"


def test_top_cast_summary_none_without_credits() -> None:
    assert build_top_cast_summary(_make_movie()) is None
    assert build_top_cast_summary(_make_movie(credits=Credits(cast=[], crew=[]))) is None


# ---------------------------------------------------------------------------
# credit_rows — §3.3's role vocabulary
# ---------------------------------------------------------------------------


def test_credit_rows_maps_crew_jobs_to_roles() -> None:
    movie = _make_movie(
        credits=Credits(
            cast=[_cast(1, "Edward Norton", 0)],
            crew=[
                _crew(10, "David Fincher", "Director"),
                _crew(11, "Jim Uhls", "Screenplay", "Writing"),
                _crew(12, "Art Linson", "Producer", "Production"),
                _crew(13, "Dust Brothers", "Original Music Composer", "Sound"),
            ],
        )
    )
    movie_id = uuid.uuid4()
    roles = sorted(row[4] for row in credit_rows(movie_id, movie))
    assert roles == ["cast", "composer", "director", "producer", "writer"]


def test_credit_rows_drops_jobs_outside_the_vocabulary() -> None:
    movie = _make_movie(
        credits=Credits(
            cast=[],
            crew=[
                _crew(20, "Someone", "Best Boy", "Lighting"),
                _crew(21, "Another", "Gaffer", "Lighting"),
            ],
        )
    )
    assert credit_rows(uuid.uuid4(), movie) == []


def test_credit_rows_caps_cast_and_keeps_billing_order() -> None:
    movie = _make_movie(
        credits=Credits(cast=[_cast(i, f"Actor {i}", order=i) for i in range(60)], crew=[])
    )
    rows = credit_rows(uuid.uuid4(), movie)
    assert len(rows) == 50
    assert rows[0][2] == "Actor 0"
    assert rows[-1][2] == "Actor 49"


def test_credit_rows_empty_without_credits() -> None:
    assert credit_rows(uuid.uuid4(), _make_movie()) == []


# ---------------------------------------------------------------------------
# upsert_movie
# ---------------------------------------------------------------------------


def test_upsert_movie_inserts_new_row() -> None:
    new_id = uuid.uuid4()
    conn, cur = _make_conn([(str(new_id),)])
    movie_id, inserted = upsert_movie(conn, _make_movie())

    assert inserted is True
    assert movie_id == new_id
    sql = cur.execute.call_args_list[0][0][0]
    assert "INSERT INTO movies" in sql
    assert "ON CONFLICT (tmdb_id) DO NOTHING" in sql


def test_upsert_movie_returns_existing_id_on_conflict() -> None:
    existing = uuid.uuid4()
    # First fetchone: the INSERT returned nothing (conflict). Second: the lookup.
    conn, cur = _make_conn([None, (str(existing),)])
    movie_id, inserted = upsert_movie(conn, _make_movie())

    assert inserted is False
    assert movie_id == existing
    assert "SELECT id FROM movies WHERE tmdb_id" in cur.execute.call_args_list[1][0][0]


def test_upsert_movie_maps_tmdb_fields_to_section_3_2_columns() -> None:
    conn, cur = _make_conn([(str(uuid.uuid4()),)])
    upsert_movie(conn, _make_movie())

    payload = cur.execute.call_args_list[0][0][1]
    # The TMDB id is a plain column, not the primary key.
    assert payload["tmdb_id"] == 550
    assert uuid.UUID(payload["id"]) != uuid.UUID(int=550)
    assert payload["year"] == 1999
    assert payload["runtime_minutes"] == 139
    assert payload["tmdb_rating"] == 8.4
    assert payload["tmdb_vote_count"] == 26280
    assert payload["genre_ids"] == [18]
    assert payload["media_type"] == "film"
    assert payload["last_tmdb_sync_utc"].tzinfo is None  # naive UTC, per AGENTS.md


def test_upsert_movie_handles_a_film_with_no_genres() -> None:
    conn, cur = _make_conn([(str(uuid.uuid4()),)])
    upsert_movie(conn, _make_movie(genres=[]))

    payload = cur.execute.call_args_list[0][0][1]
    assert payload["genres"] is None
    assert payload["genre_ids"] is None


# ---------------------------------------------------------------------------
# upsert_unmatched_movie — the rows April dropped entirely
# ---------------------------------------------------------------------------


def test_upsert_unmatched_movie_inserts_title_only_row() -> None:
    conn, cur = _make_conn([None])
    movie_id, inserted = upsert_unmatched_movie(conn, "Some Obscure Disc")

    assert inserted is True
    assert isinstance(movie_id, uuid.UUID)
    insert_sql, params = cur.execute.call_args_list[1][0]
    assert "INSERT INTO movies" in insert_sql
    assert params[1] == "Some Obscure Disc"


def test_upsert_unmatched_movie_reuses_existing_row() -> None:
    existing = uuid.uuid4()
    conn, cur = _make_conn([(str(existing),)])
    movie_id, inserted = upsert_unmatched_movie(conn, "Some Obscure Disc")

    assert inserted is False
    assert movie_id == existing
    # Only the lookup ran — nothing was inserted.
    assert cur.execute.call_count == 1


# ---------------------------------------------------------------------------
# insert_credits
# ---------------------------------------------------------------------------


def test_insert_credits_skipped_when_already_present() -> None:
    conn, cur = _make_conn([(1,)])
    movie = _make_movie(credits=Credits(cast=[_cast(1, "Edward Norton", 0)], crew=[]))
    assert insert_credits(conn, uuid.uuid4(), movie) == 0
    assert cur.execute.call_count == 1


def test_insert_credits_writes_rows_when_none_exist() -> None:
    conn, cur = _make_conn([None])
    movie = _make_movie(
        credits=Credits(
            cast=[_cast(1, "Edward Norton", 0)],
            crew=[_crew(10, "David Fincher", "Director")],
        )
    )
    # execute_values reaches into the real connection's encoding, which a MagicMock
    # cannot supply; the rows it is handed are what this test is about.
    with patch("psycopg2.extras.execute_values") as execute_values:
        assert insert_credits(conn, uuid.uuid4(), movie) == 2

    sent_rows = execute_values.call_args[0][2]
    assert sorted(row[4] for row in sent_rows) == ["cast", "director"]


def test_insert_credits_no_credits_object() -> None:
    conn, _ = _make_conn([None])
    assert insert_credits(conn, uuid.uuid4(), _make_movie()) == 0


# ---------------------------------------------------------------------------
# insert_collection_item — Batch 4's fix
# ---------------------------------------------------------------------------


def _item_params(cur) -> tuple[Any, ...]:
    """The parameter tuple from the INSERT (the second execute call)."""
    params = cur.execute.call_args_list[1][0][1]
    assert isinstance(params, tuple)
    return params


def test_insert_collection_item_writes_location_columns() -> None:
    """The whole point of the batch: location, section and shelf are columns.

    The April importer had nowhere to put them and wrote the raw string into `notes`
    instead, discarding the parsed structure for every row (`STATUS.md` gotcha 0b).
    """
    conn, cur = _make_conn([None])
    candidate = _make_candidate(location_raw="Front 2nd shelf", section="Front", shelf="2nd")
    assert insert_collection_item(conn, uuid.uuid4(), candidate) is True

    insert_sql = cur.execute.call_args_list[1][0][0]
    assert "location" in insert_sql
    assert "section" in insert_sql
    assert "shelf" in insert_sql
    # `notes` is not written at all — it means notes again.
    assert "notes" not in insert_sql

    params = _item_params(cur)
    assert params[3] == "Front 2nd shelf"
    assert params[4] == "Front"
    assert params[5] == "2nd"


def test_insert_collection_item_writes_formats_as_an_array() -> None:
    """A combo pack is one item holding two formats, not two items."""
    conn, cur = _make_conn([None])
    candidate = _make_candidate(formats=["blu_ray", "download"])
    insert_collection_item(conn, uuid.uuid4(), candidate)

    assert _item_params(cur)[2].adapted == ["blu_ray", "download"]


def test_insert_collection_item_keeps_unsectioned_location() -> None:
    """A cabinet has no §3.4 section. The raw text still survives in `location`."""
    conn, cur = _make_conn([None])
    candidate = _make_candidate(location_raw="Top Big Cabinet", section=None, shelf=None)
    insert_collection_item(conn, uuid.uuid4(), candidate)

    params = _item_params(cur)
    assert params[3] == "Top Big Cabinet"
    assert params[4] is None
    assert params[5] is None


def test_insert_collection_item_empty_location_is_null() -> None:
    conn, cur = _make_conn([None])
    candidate = _make_candidate(location_raw="", section=None, shelf=None)
    insert_collection_item(conn, uuid.uuid4(), candidate)

    assert _item_params(cur)[3] is None


def test_insert_collection_item_uses_default_condition() -> None:
    conn, cur = _make_conn([None])
    insert_collection_item(conn, uuid.uuid4(), _make_candidate())
    assert _item_params(cur)[7] == DEFAULT_CONDITION


def test_insert_collection_item_skips_an_exact_duplicate() -> None:
    conn, cur = _make_conn([(1,)])
    assert insert_collection_item(conn, uuid.uuid4(), _make_candidate()) is False
    # Only the duplicate check ran.
    assert cur.execute.call_count == 1


def test_insert_collection_item_keys_re_runs_on_the_spreadsheet_line() -> None:
    """Not on the item's contents. Two source rows resolving to the same film, shelf and
    format are still two discs — keying on contents collapsed "French Connection" and
    "French Connection 2" into one and lost a disc (`DECISIONS.md` #32)."""
    conn, cur = _make_conn([None])
    insert_collection_item(conn, uuid.uuid4(), _make_candidate(row_number=1430))

    check_sql, check_params = cur.execute.call_args_list[0][0]
    assert "import_source_row = %s" in check_sql
    assert check_params == (1430,)
    assert "formats" not in check_sql
    assert "location" not in check_sql


def test_insert_collection_item_records_its_source_row() -> None:
    conn, cur = _make_conn([None])
    insert_collection_item(conn, uuid.uuid4(), _make_candidate(row_number=550))
    assert _item_params(cur)[8] == 550


def test_insert_collection_item_does_not_collapse_two_titles_on_one_film() -> None:
    """The French Connection case: same movie_id, same shelf, same format, two lines."""
    movie_id = uuid.uuid4()
    first, cur_first = _make_conn([None])
    second, cur_second = _make_conn([None])

    a = _make_candidate(row_number=550, title="French Connection")
    b = _make_candidate(row_number=551, title="French Connection 2")
    assert insert_collection_item(first, movie_id, a) is True
    assert insert_collection_item(second, movie_id, b) is True

    assert _item_params(cur_first)[8] == 550
    assert _item_params(cur_second)[8] == 551


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
# review_row — the ambiguous queue has to be answerable from the file
# ---------------------------------------------------------------------------


def test_review_row_lists_the_tied_alternatives() -> None:
    from src.matching import MatchCandidate, MatchResult
    from src.scripts.import_collection import review_row

    def _cand(id_: int, title: str, year: int | None) -> MatchCandidate:
        return MatchCandidate(
            tmdb_id=id_,
            title=title,
            year=year,
            confidence=1.0,
            title_similarity=1.0,
            year_match="unknown",
            title_exact=True,
        )

    result = MatchResult(
        raw_query="Frankenstein",
        query="Frankenstein",
        candidates=[_cand(1, "Frankenstein", 2025), _cand(2, "Frankenstein", 1931)],
        matched=True,
        ambiguous=True,
    )
    row = review_row(_make_candidate(title="Frankenstein"), result, "ambiguous_match")

    assert row["reason"] == "ambiguous_match"
    assert "1:Frankenstein (2025)" in row["alternatives"]
    assert "2:Frankenstein (1931)" in row["alternatives"]


def test_review_row_renders_a_missing_year_rather_than_omitting_it() -> None:
    from src.matching import MatchCandidate, MatchResult
    from src.scripts.import_collection import review_row

    result = MatchResult(
        raw_query="Scapegoat",
        query="Scapegoat",
        candidates=[
            MatchCandidate(
                tmdb_id=9,
                title="Scapegoat",
                year=None,
                confidence=1.0,
                title_similarity=1.0,
                year_match="unknown",
            )
        ],
        matched=True,
    )
    row = review_row(_make_candidate(title="Scapegoat"), result, "ambiguous_match")
    assert row["alternatives"] == "9:Scapegoat (?)"
