"""Unit tests for src/scripts/import_collection.py.

Re-authored in Batch 4 alongside the importer itself. The April version of this file
tested the April schema — a scalar ``format`` column, a TMDB integer primary key, and
``notes`` holding the raw location string. All three are gone; the assertions that
pinned them are replaced by ones that pin §3.4's shape, including the location columns
whose absence was the defect this batch exists to fix.
"""

from __future__ import annotations

import asyncio
import csv
import uuid
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from src.scripts.import_collection import (
    DEFAULT_CONDITION,
    REVIEW_FIELDNAMES,
    ImportRow,
    ImportStats,
    LiveFilmIndex,
    OrphanRisk,
    ReplacementBlocked,
    ReplacementPlan,
    ensure_replacement_allowed,
    insert_collection_item,
    insert_credits,
    lock_replacement_tables,
    replacement_plan,
    resolution_counts,
    run,
    soft_delete_live_items,
    upsert_movie,
    upsert_unmatched_movie,
    write_review_file,
)
from src.services.movie_metadata import (
    build_top_cast_summary,
    credit_rows,
    parse_year,
    pick_trailer_key,
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
    movie_id, inserted, kind = upsert_unmatched_movie(conn, LiveFilmIndex([]), "Some Obscure Disc")

    assert inserted is True
    assert kind == "new"
    assert isinstance(movie_id, uuid.UUID)
    insert_sql, params = cur.execute.call_args_list[0][0]
    assert "INSERT INTO movies" in insert_sql
    assert params[1] == "Some Obscure Disc"


def test_upsert_unmatched_movie_reuses_existing_row() -> None:
    existing = uuid.uuid4()
    conn, cur = _make_conn([(str(existing),)])
    index = LiveFilmIndex([(existing, "Some Obscure Disc")])
    movie_id, inserted, kind = upsert_unmatched_movie(conn, index, "Some Obscure Disc")

    assert inserted is False
    assert movie_id == existing
    assert kind == "title"
    # **No SQL at all now.** Batch 41 answers this from the index the run already holds,
    # where the old code issued one lookup per unsettled row.
    assert cur.execute.call_count == 0


def test_upsert_unmatched_movie_reuses_a_film_that_has_since_been_identified() -> None:
    """The 2026-09-18 defect, at its smallest (`DECISIONS.md` #198).

    The old lookup was `title = %s AND tmdb_id IS NULL`. Once `OWNER-ACTIONS.md` 1i step 2
    gave 395 films a `tmdb_id`, that clause stopped finding them — so a sheet row TMDB
    could not settle minted a duplicate, hung the new disc on it, and left the watch
    history on a film with no disc. Measured: 401 films, 587 watch rows, no error.
    """
    identified = uuid.uuid4()
    conn, cur = _make_conn()
    index = LiveFilmIndex([(identified, "Double Indemnity")])

    movie_id, inserted, kind = upsert_unmatched_movie(conn, index, "Double Indemnity")

    assert movie_id == identified
    assert inserted is False
    assert kind == "title"
    cur.execute.assert_not_called()


def test_upsert_unmatched_movie_matches_a_title_identification_tidied() -> None:
    """Identification rewrites `Thing, The` to `The Thing`; the sheet still says the old one.

    155 of the 395 films identified on 2026-09-17 were retitled this way, so exact
    matching alone would have recovered only part of the damage.
    """
    tidied = uuid.uuid4()
    conn, _ = _make_conn()
    index = LiveFilmIndex([(tidied, "The Thing")])

    movie_id, inserted, kind = upsert_unmatched_movie(conn, index, "Thing, The")

    assert movie_id == tidied
    assert inserted is False
    assert kind == "normalised"


def test_upsert_unmatched_movie_refuses_to_choose_between_two_live_films() -> None:
    """Two `Dunkirk`s, and nothing in a spreadsheet row says which.

    Seven titles in the real collection are like this. Offering rather than guessing is
    the rule the matcher already applies to TMDB candidates, applied to our own rows.
    """
    first, second = uuid.uuid4(), uuid.uuid4()
    conn, cur = _make_conn()
    index = LiveFilmIndex([(first, "Dunkirk"), (second, "Dunkirk")])

    movie_id, inserted, kind = upsert_unmatched_movie(conn, index, "Dunkirk")

    assert inserted is True, "a disc is never dropped on the floor"
    assert kind == "ambiguous"
    assert movie_id not in {first, second}
    assert "INSERT INTO movies" in cur.execute.call_args_list[0][0][0]


def test_an_exact_title_beats_a_normalised_collision() -> None:
    """`The Mummy` resolves exactly even though three `Mummy` rows normalise alike."""
    exact = uuid.uuid4()
    conn, _ = _make_conn()
    index = LiveFilmIndex(
        [
            (exact, "The Mummy"),
            (uuid.uuid4(), "Mummy, The (Original)"),
            (uuid.uuid4(), "Mummy, The (Tom Cruise)"),
        ]
    )

    movie_id, inserted, kind = upsert_unmatched_movie(conn, index, "The Mummy")

    assert movie_id == exact
    assert inserted is False
    assert kind == "title"


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


def test_insert_collection_item_live_source_row_still_blocks_a_duplicate() -> None:
    conn, cur = _make_conn([(1,)])
    assert insert_collection_item(conn, uuid.uuid4(), _make_candidate()) is False
    # Only the duplicate check ran.
    assert cur.execute.call_count == 1
    assert "deleted_at IS NULL" in cur.execute.call_args[0][0]


def test_insert_collection_item_soft_deleted_source_row_does_not_block_reinsert() -> None:
    # The SELECT contains the live-row predicate, so None is the database answer when a
    # row with this source number exists only in Trash.
    conn, cur = _make_conn([None])
    assert insert_collection_item(conn, uuid.uuid4(), _make_candidate()) is True
    assert "deleted_at IS NULL" in cur.execute.call_args_list[0][0][0]
    assert "INSERT INTO collection_items" in cur.execute.call_args_list[1][0][0]


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
# Batch 39 replacement planning and dry-run behaviour
# ---------------------------------------------------------------------------


def test_replacement_plan_counts_live_items_and_the_split_risk() -> None:
    conn, cur = _make_conn([(1857,), (397, 586)])
    plan = replacement_plan(conn)

    assert plan == ReplacementPlan(
        live_items=1857,
        unidentified_films_with_watches=397,
        watch_rows_at_risk=586,
    )
    assert "collection_items WHERE deleted_at IS NULL" in cur.execute.call_args_list[0][0][0]
    risk_sql = cur.execute.call_args_list[1][0][0]
    assert "m.tmdb_id IS NULL" in risk_sql
    assert "w.deleted_at IS NULL" in risk_sql


def test_replacement_guard_names_both_counts_and_the_identify_step() -> None:
    plan = ReplacementPlan(
        live_items=1857,
        unidentified_films_with_watches=397,
        watch_rows_at_risk=586,
    )

    with pytest.raises(ReplacementBlocked) as caught:
        ensure_replacement_allowed(plan, accept_split=False)

    message = str(caught.value)
    assert "397 unidentified films" in message
    assert "586 live watch rows" in message
    assert "--identify" in message


def test_accept_split_is_the_explicit_guard_override() -> None:
    plan = ReplacementPlan(
        live_items=1,
        unidentified_films_with_watches=1,
        watch_rows_at_risk=2,
    )
    ensure_replacement_allowed(plan, accept_split=True)


def test_soft_delete_reports_the_database_rowcount() -> None:
    conn, cur = _make_conn()
    cur.rowcount = 1857
    assert soft_delete_live_items(conn) == 1857
    sql = cur.execute.call_args[0][0]
    assert "UPDATE collection_items" in sql
    assert "SET deleted_at" in sql
    assert "WHERE deleted_at IS NULL" in sql


def test_replacement_locks_watched_movies_and_items_during_the_write_pass() -> None:
    conn, cur = _make_conn()
    lock_replacement_tables(conn)

    sql = cur.execute.call_args[0][0]
    assert "collection_items, movies, watch_log" in sql
    assert "SHARE ROW EXCLUSIVE" in sql


class _FakeTMDBClient:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


async def _prepared_rows(
    candidates: list[ImportCandidate], _tmdb: object, _stats: ImportStats
) -> tuple[list[ImportRow], list[dict[str, Any]]]:
    return [ImportRow(candidate=candidate) for candidate in candidates], []


def test_replace_dry_run_reports_the_count_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    conn, _ = _make_conn()
    plan = ReplacementPlan(
        live_items=1857,
        unidentified_films_with_watches=397,
        watch_rows_at_risk=586,
    )
    review_out = tmp_path / "review.csv"

    with (
        patch("src.scripts.import_collection.parse_xlsx", return_value=[_make_candidate()]),
        patch("src.scripts.import_collection.psycopg2.connect", return_value=conn),
        patch("src.scripts.import_collection.replacement_plan", return_value=plan),
        patch("src.scripts.import_collection.TMDBClient", return_value=_FakeTMDBClient()),
        patch("src.scripts.import_collection.match_and_enrich", side_effect=_prepared_rows),
        patch("src.scripts.import_collection.soft_delete_live_items") as soft_delete,
        patch("src.scripts.import_collection.orphan_risk", return_value=OrphanRisk(0, 0, [])),
    ):
        stats = asyncio.run(
            run(
                Path("catalogue.xlsx"),
                True,
                review_out,
                replace_items=True,
                accept_split=True,
            )
        )

    assert stats.items_to_replace == 1857
    assert stats.items_replaced == 0
    soft_delete.assert_not_called()
    # Two now: the preflight that proves the DSN before TMDB, and the read the history
    # guard needs *after* matching, since it depends on what matching produced.
    assert conn.close.call_count == 2
    assert (
        "Would soft-delete 1857 live collection items; removed nothing" in capsys.readouterr().out
    )


def test_replace_guard_stops_before_tmdb_or_any_write(tmp_path: Path) -> None:
    conn, _ = _make_conn()
    plan = ReplacementPlan(
        live_items=1857,
        unidentified_films_with_watches=397,
        watch_rows_at_risk=586,
    )

    with (
        patch("src.scripts.import_collection.parse_xlsx", return_value=[_make_candidate()]),
        patch("src.scripts.import_collection.psycopg2.connect", return_value=conn),
        patch("src.scripts.import_collection.replacement_plan", return_value=plan),
        patch("src.scripts.import_collection.TMDBClient") as tmdb_client,
        pytest.raises(ReplacementBlocked),
    ):
        asyncio.run(
            run(
                Path("catalogue.xlsx"),
                True,
                tmp_path / "review.csv",
                replace_items=True,
            )
        )

    tmdb_client.assert_not_called()
    conn.close.assert_called_once()


def test_plain_dry_run_keeps_the_existing_no_database_behaviour(tmp_path: Path) -> None:
    with (
        patch("src.scripts.import_collection.parse_xlsx", return_value=[_make_candidate()]),
        patch("src.scripts.import_collection.psycopg2.connect") as connect,
        patch("src.scripts.import_collection.TMDBClient", return_value=_FakeTMDBClient()),
        patch("src.scripts.import_collection.match_and_enrich", side_effect=_prepared_rows),
    ):
        stats = asyncio.run(run(Path("catalogue.xlsx"), True, tmp_path / "review.csv"))

    assert stats.items_to_replace == 0
    connect.assert_not_called()


def test_plain_import_keeps_per_item_transactions_and_never_replaces(tmp_path: Path) -> None:
    preflight_conn, _ = _make_conn()
    write_conn, _ = _make_conn()
    candidates = [_make_candidate(row_number=2), _make_candidate(row_number=3)]

    with (
        patch("src.scripts.import_collection.parse_xlsx", return_value=candidates),
        patch(
            "src.scripts.import_collection.psycopg2.connect",
            side_effect=[preflight_conn, write_conn],
        ),
        patch("src.scripts.import_collection.TMDBClient", return_value=_FakeTMDBClient()),
        patch("src.scripts.import_collection.match_and_enrich", side_effect=_prepared_rows),
        patch("src.scripts.import_collection.write_import_row") as write_row,
        patch("src.scripts.import_collection.replace_collection_items") as replace,
    ):
        stats = asyncio.run(run(Path("catalogue.xlsx"), False, tmp_path / "review.csv"))

    assert stats.items_to_replace == 0
    assert write_row.call_count == 2
    assert write_conn.__exit__.call_count == 2
    replace.assert_not_called()


def test_replace_write_failure_rolls_back_the_single_connection_context(tmp_path: Path) -> None:
    preflight_conn, _ = _make_conn()
    risk_conn, _ = _make_conn()
    write_conn, _ = _make_conn()
    plan = ReplacementPlan(1, 0, 0)

    def fail_replacement(
        _conn: Any,
        _rows: list[ImportRow],
        stats: ImportStats,
        *,
        accept_split: bool,
    ) -> ReplacementPlan:
        assert accept_split is False
        stats.items_replaced = 1
        stats.items_inserted = 1
        raise psycopg2.DatabaseError("forced failure")

    with (
        patch("src.scripts.import_collection.parse_xlsx", return_value=[_make_candidate()]),
        patch(
            "src.scripts.import_collection.psycopg2.connect",
            side_effect=[preflight_conn, risk_conn, write_conn],
        ),
        patch("src.scripts.import_collection.replacement_plan", return_value=plan),
        patch("src.scripts.import_collection.orphan_risk", return_value=OrphanRisk(0, 0, [])),
        patch("src.scripts.import_collection.TMDBClient", return_value=_FakeTMDBClient()),
        patch("src.scripts.import_collection.match_and_enrich", side_effect=_prepared_rows),
        patch(
            "src.scripts.import_collection.replace_collection_items", side_effect=fail_replacement
        ),
    ):
        stats = asyncio.run(
            run(
                Path("catalogue.xlsx"),
                False,
                tmp_path / "review.csv",
                replace_items=True,
            )
        )

    assert write_conn.__exit__.call_count == 1
    assert write_conn.__exit__.call_args.args[0] is psycopg2.DatabaseError
    assert isinstance(write_conn.__exit__.call_args.args[1], psycopg2.DatabaseError)
    assert stats.items_replaced == 0
    assert stats.items_inserted == 0
    assert stats.errors == ["replacement rolled back — forced failure"]


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


def _offered(tmdb_id: int, title: str, year: int | None, votes: int = 10) -> Any:
    from src.services.identify.matcher import Candidate

    return Candidate(
        tmdb_id=tmdb_id, title=title, original_title=title, year=year, vote_count=votes
    )


def test_review_row_lists_the_tied_alternatives() -> None:
    from src.scripts.import_collection import review_row
    from src.services.identify.matcher import Proposal
    from src.services.identify.titles import parse_title

    proposal = Proposal(
        "ask",
        reason="TMDB holds two films of this title.",
        candidates=[_offered(1, "Frankenstein", 2025), _offered(2, "Frankenstein", 1931)],
    )
    row = review_row(
        _make_candidate(title="Frankenstein"), parse_title("Frankenstein"), proposal, "ask"
    )

    assert row["reason"] == "ask: TMDB holds two films of this title."
    assert "1:Frankenstein (2025)" in row["alternatives"]
    assert "2:Frankenstein (1931)" in row["alternatives"]


def test_review_row_renders_a_missing_year_rather_than_omitting_it() -> None:
    from src.scripts.import_collection import review_row
    from src.services.identify.matcher import Proposal
    from src.services.identify.titles import parse_title

    proposal = Proposal("ask", candidates=[_offered(9, "Scapegoat", None)])
    row = review_row(_make_candidate(title="Scapegoat"), parse_title("Scapegoat"), proposal, "ask")
    assert row["alternatives"] == "9:Scapegoat (?)"


class _NamesakeTmdb:
    """TMDB answering by title for the review's namesake and article cases (CT46-01)."""

    FILMS: ClassVar[dict[str, list[tuple[int, str, str, int]]]] = {
        # The old engine took "French Connection" to the sequel (0.919 against 0.900).
        "french connection": [
            (10711, "French Connection II", "1975-05-18", 486),
            (1051, "The French Connection", "1971-10-09", 2400),
        ],
        # And "Good Fellas" to a 0-vote 2016 film, an exact hit without the space.
        "good fellas": [
            (626867, "Good Fellas", "2016-01-01", 0),
            (769, "GoodFellas", "1990-09-12", 12000),
        ],
    }

    def __init__(self) -> None:
        self.fetched: list[int] = []

    def _results(self, query: str) -> list[Any]:
        from src.tmdb.models import SearchResult

        rows = self.FILMS.get(query.lower().removeprefix("the ").strip(), [])
        return [
            SearchResult(
                id=tmdb_id,
                title=title,
                original_title=title,
                release_date=released,
                vote_count=votes,
            )
            for tmdb_id, title, released, votes in rows
        ]

    async def search_movie(
        self, query: str, year: int | None = None, page: int = 1, **_: Any
    ) -> Any:
        from src.tmdb.models import SearchResults

        results = self._results(query) if page == 1 else []
        return SearchResults(page=page, results=results, total_pages=1, total_results=len(results))

    async def get_movie(self, movie_id: int, append_to_response: Any = None, **_: Any) -> Any:
        from src.tmdb.models import Movie as TmdbMovie

        for rows in self.FILMS.values():
            for tmdb_id, title, released, votes in rows:
                if tmdb_id == movie_id:
                    return TmdbMovie(
                        id=tmdb_id,
                        title=title,
                        original_title=title,
                        overview="",
                        release_date=released,
                        vote_count=votes,
                    )
        raise KeyError(movie_id)

    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> Any:
        self.fetched.append(movie_id)
        return await self.get_movie(movie_id)

    async def search_tv(self, query: str, page: int = 1) -> Any:
        from src.tmdb.models import TvSearchResults

        return TvSearchResults()

    async def search_person(self, query: str, page: int = 1) -> Any:
        from src.tmdb.models import PersonSearchResults

        return PersonSearchResults()

    async def get_person_movie_credits(self, person_id: int) -> Any:
        from src.tmdb.models import PersonMovieCredits

        return PersonMovieCredits(id=person_id)


async def test_the_refresh_matches_with_t9_not_the_engine_namesake_and_article_cases() -> None:
    """X9's guard (CT46-01): the 8 Sep import's engine kept a leading article and scored an
    exact namesake above the real film. The refresh now matches with T9's identifier, which
    never takes the sequel and never settles on the 0-vote namesake."""
    from src.scripts.import_collection import ImportStats, match_and_enrich

    tmdb = _NamesakeTmdb()
    stats = ImportStats()
    rows, review = await match_and_enrich(
        [
            _make_candidate(title="French Connection"),
            _make_candidate(title="Good Fellas", row_number=3),
        ],
        tmdb,  # type: ignore[arg-type]
        stats,
    )

    # The sequel scored 0.919 against the real film's 0.900 in the old engine; T9 takes the
    # real film. The namesake was an exact hit at 1.000; T9 asks, as it did live on 12 Oct.
    assert [(row.candidate.title, row.tmdb_id) for row in rows] == [
        ("French Connection", 1051),
        ("Good Fellas", None),
    ]
    assert [(r["title"], r["reason"][:4]) for r in review] == [("Good Fellas", "ask:")]
    assert "626867:Good Fellas (2016)" in review[0]["alternatives"]
    assert "769:GoodFellas (1990)" in review[0]["alternatives"]
    assert tmdb.fetched == [1051]


def test_a_dry_run_can_count_resolutions_the_write_path_never_reaches() -> None:
    """`ImportStats` learns the reuse counts from the write path, which a dry run skips.

    So the rehearsal reported `Reused a live film: 0` whatever the real number was —
    a zero that could not be anything else. Reporting one of those is how the defect this
    batch fixes stayed invisible for a day, so the dry run computes them instead.
    """
    held = uuid.uuid4()
    index = LiveFilmIndex(
        [
            (held, "The Thing"),
            (uuid.uuid4(), "Dunkirk"),
            (uuid.uuid4(), "Dunkirk"),
            (uuid.uuid4(), "Double Indemnity"),
        ]
    )
    rows = [
        ImportRow(candidate=_make_candidate(title="Thing, The")),
        ImportRow(candidate=_make_candidate(title="Double Indemnity")),
        ImportRow(candidate=_make_candidate(title="Dunkirk")),
        ImportRow(candidate=_make_candidate(title="Never Heard Of It")),
    ]

    counts = resolution_counts(rows, index)

    assert counts == {"title": 1, "normalised": 1, "ambiguous": 1, "new": 1}
