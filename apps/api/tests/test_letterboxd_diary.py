"""Batch S8's reader and matcher — snag 10b, `DECISIONS.md` #158, #160, #161.

**The collection titles here are real; the diary rows are not.** `'Death on the Nile
[1978]'`, `'Collector, The'`, `'Out of The past'`, `'Mummy, The (Tom Cruise)'` and the junk
row `'Test 15.04.26'` are rows live Neon actually holds, and they are the point — they are
what the normalisation has to survive.

**The diary fixture's dates, ratings and viewing ids are invented.** Those three together
*are* somebody's watch history, and the retrieved export is gitignored for exactly that
reason (`DECISIONS.md` #161); a six-line excerpt would still be six viewings. The column
shape is faithful, which is all a reader test needs.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from src.models.movie import Movie
from src.services.letterboxd.diary import (
    DiaryEntry,
    DiaryParseError,
    parse_diary,
    read_diary_csv,
)
from src.services.letterboxd.matcher import build_index, match_entry
from src.services.title_key import Strictness, title_key

FIXTURE = Path(__file__).parent / "fixtures" / "letterboxd_diary.csv"


def normalise_title(raw: str) -> str:
    """The collection index's key, the shared catalogue level since Batch X10 (#280)."""
    return title_key(raw, Strictness.TITLE)


HEADER = "WatchedDate,Slug,Name,Year,Rating,Rewatch,ViewingId\n"


def _film(title: str, year: int | None = None, tmdb_id: int | None = None) -> Movie:
    return Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
    )


def _entry(title: str, year: int | None = None, tmdb_id: int | None = None) -> DiaryEntry:
    return DiaryEntry(
        viewing_id="1",
        watched_at=date(2026, 9, 1),
        title=title,
        year=year,
        rating=None,
        is_rewatch=False,
        tmdb_id=tmdb_id,
    )


# ---------------------------------------------------------------------------
# Reading the file
# ---------------------------------------------------------------------------


class TestReadingADiary:
    def test_reads_the_shape_the_retrieved_diaries_actually_have(self) -> None:
        entries = read_diary_csv(FIXTURE)
        assert len(entries) == 6

        first = entries[0]
        assert first.viewing_id == "900000001"
        assert first.watched_at == date(2026, 9, 9)
        assert first.title == "Pressure"
        assert first.year == 2026
        assert first.rating == Decimal("4.0")
        assert first.is_rewatch is False
        assert first.slug == "pressure-2026"
        assert first.tmdb_id is None  # a CSV never carries one; the RSS feed does

    def test_a_rewatch_is_read_as_one(self) -> None:
        # `<letterboxd:rewatch>` in the feed, `Rewatch` in the file. A rewatch on a later
        # date is a different viewing and correctly becomes a second row.
        assert read_diary_csv(FIXTURE)[1].is_rewatch is True

    def test_a_blank_rating_is_data_rather_than_a_gap(self) -> None:
        """**Mark rates nothing — 0 of 1,149 entries** (`DECISIONS.md` #159).

        Treating blank as missing would produce 1,149 warnings describing normal
        behaviour, and a default rating would invent an opinion he never expressed.
        """
        nile = read_diary_csv(FIXTURE)[2]
        assert nile.rating is None
        assert nile.title == "Death on the Nile"

    def test_a_file_missing_a_column_is_refused_by_name(self) -> None:
        # Not "0 entries imported", which is what a tolerant reader would report and is
        # indistinguishable from an empty diary.
        with pytest.raises(DiaryParseError, match="ViewingId"):
            list(parse_diary(StringIO("WatchedDate,Slug,Name,Year,Rating,Rewatch\n")))

    def test_a_row_with_no_viewing_id_is_refused(self) -> None:
        """Without it the row cannot be idempotent, which is the one property that makes
        re-running safe. Importing it anyway would create a duplicate on every run."""
        with pytest.raises(DiaryParseError, match="idempotent"):
            list(parse_diary(StringIO(HEADER + "2026-09-09,x,A Film,2026,,No,\n")))

    def test_a_repeated_viewing_id_within_one_file_is_refused(self) -> None:
        # The two retrieved diaries have none — 2,322 rows, 2,322 distinct ids — but a
        # file assembled by hand could, and the unique index would reject the second row
        # mid-import after the first few hundred had been written.
        doubled = HEADER + (
            "2026-09-09,x,A Film,2026,,No,111\n2026-09-10,y,Another Film,2026,,No,111\n"
        )
        with pytest.raises(DiaryParseError, match="already appeared"):
            read_diary_csv_from(doubled)

    def test_an_impossible_rating_is_refused_rather_than_clamped(self) -> None:
        # `watch_log.personal_rating` has a CHECK for half-stars 0.5-5.0. Catching it here
        # names the line; letting it through names a constraint.
        with pytest.raises(DiaryParseError, match="half-star"):
            list(parse_diary(StringIO(HEADER + "2026-09-09,x,A Film,2026,4.3,No,111\n")))


def read_diary_csv_from(text: str) -> list[DiaryEntry]:
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = Path(fh.name)
    try:
        return read_diary_csv(path)
    finally:
        path.unlink()


# ---------------------------------------------------------------------------
# Normalisation — every case here is a real row in this collection
# ---------------------------------------------------------------------------


class TestNormalisation:
    @pytest.mark.parametrize(
        ("a", "b"),
        [
            # §-criterion: trailing articles. `'Collector, The'` is a real row.
            ("Collector, The", "The Collector"),
            # bracketed years. `'Death on the Nile [1978]'` is a real row.
            ("Death on the Nile [1978]", "Death on the Nile"),
            # `&` against `and`.
            ("Fast & Furious", "Fast and Furious"),
            # case. `'Out of The past'` and `'Murder on The Orient Express [2017]'` are real.
            ("Out of The past", "Out of the Past"),
            ("Murder on The Orient Express [2017]", "murder on the orient express"),
            # accents, because the collection has them and a diary spells them either way
            ("Amélie", "Amelie"),
        ],
    )
    def test_two_spellings_of_one_film_share_a_key(self, a: str, b: str) -> None:
        assert normalise_title(a) == normalise_title(b)

    def test_two_different_films_do_not(self) -> None:
        assert normalise_title("The Collector") != normalise_title("The Collection")

    def test_the_junk_row_normalises_without_crashing(self) -> None:
        # `'Test 15.04.26'` is a real row in `movies`, and a matcher that raised on it
        # would take the whole import down over one line of someone's typing.
        # Batch X10 (#280): the shared fold drops full stops ("U.S.", "Dr."), so the date's
        # parts join up; it was "test 15 04 26" under this module's own rule.
        assert normalise_title("Test 15.04.26") == "test 150426"


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


class TestMatching:
    def test_an_exact_tmdb_id_wins(self) -> None:
        """The path S5 takes: every RSS entry carries `tmdb:movieId`, 100 of 100 measured."""
        owned = _film("Heat", year=1995, tmdb_id=949)
        index = build_index([owned])
        outcome = match_entry(_entry("Heat", 1995, tmdb_id=949), index)
        assert outcome.movie is owned
        assert outcome.via == "tmdb_id"

    def test_a_title_match_finds_a_row_the_april_import_never_identified(self) -> None:
        """**580 of 2,322 entries, 396 distinct films** (`DECISIONS.md` #160).

        These rows have `tmdb_id IS NULL` *and* `year IS NULL`, so nothing but the title
        can find them — and `identifies` is what tells the importer it can fill them in.
        """
        unidentified = _film("Collector, The")
        index = build_index([unidentified])
        outcome = match_entry(_entry("The Collector", 1965), index)
        assert outcome.movie is unidentified
        assert outcome.via == "title"
        assert outcome.identifies is True

    def test_a_year_that_disagrees_does_not_veto_a_title_match(self) -> None:
        """**The mistake `DECISIONS.md` #158 records, guarded against.**

        An earlier pass filtered candidates on `abs(year - filmYear) <= 1` and reported
        *zero* owned-but-unidentified matches — an artifact, because every unidentified
        row has `year IS NULL` and was excluded by the test itself. Taken at face value it
        would have shipped S5 with neither an identification nor a confirmation step.
        """
        unidentified = _film("Out of The past")  # year is NULL, as it is in the database
        index = build_index([unidentified])
        outcome = match_entry(_entry("Out of the Past", 1947), index)
        assert outcome.movie is unidentified

    def test_death_on_the_nile_is_offered_rather_than_guessed(self) -> None:
        """The criterion's named fixture, and one of **15 real ambiguous titles** — 28
        entries — measured by running this matcher over both diaries against live Neon.

        Both rows are genuinely in the collection and both have `year IS NULL`, so nothing
        distinguishes them. A matcher that picked one would be right half the time and
        silent about it.

        *`DECISIONS.md` #160 recorded 6, and #174 records why this finds more: that pass
        did not collapse parenthetical disambiguators or rotate trailing articles, so it
        scored the other nine titles as "not in the collection" — a silent miss rather than
        a question.*
        """
        a = _film("Death on the Nile")
        b = _film("Death on the Nile [1978]")
        index = build_index([a, b])

        outcome = match_entry(_entry("Death on the Nile", 2022), index)
        assert outcome.movie is None
        assert outcome.ambiguity is not None
        assert {m.title for m in outcome.ambiguity.candidates} == {
            "Death on the Nile",
            "Death on the Nile [1978]",
        }
        assert "Death on the Nile" in outcome.ambiguity.describe()

    def test_murder_on_the_orient_express_is_the_other_one(self) -> None:
        index = build_index(
            [
                _film("Murder on The Orient Express [2017]"),
                _film("Murder on the Orient Express [1974]"),
            ]
        )
        assert (
            match_entry(_entry("Murder on the Orient Express", 1974), index).ambiguity is not None
        )

    def test_a_year_breaks_a_tie_when_both_rows_know_theirs(self) -> None:
        """The year is a tie-breaker, never a filter — so it settles an ambiguity it can
        settle, and stays out of the way when it cannot."""
        index = build_index([_film("Death on the Nile", 1978), _film("Death on the Nile", 2022)])
        outcome = match_entry(_entry("Death on the Nile", 2022), index)
        assert outcome.movie is not None
        assert outcome.movie.year == 2022

    def test_a_film_they_do_not_own_is_not_an_error(self) -> None:
        """**739 of 2,322 entries**, roughly a third. They watched it; it is not on the
        shelf. Reporting each as a failure would bury the 28 that need a person."""
        index = build_index([_film("Heat", 1995, tmdb_id=949)])
        outcome = match_entry(_entry("A Film Nobody Owns", 1999), index)
        assert outcome.movie is None
        assert outcome.ambiguity is None

    def test_a_soft_deleted_film_is_not_a_candidate(self) -> None:
        from datetime import datetime

        deleted = _film("Heat", 1995, tmdb_id=949)
        deleted.deleted_at = datetime(2026, 9, 9)
        index = build_index([deleted])
        assert index.total == 0
        assert match_entry(_entry("Heat", 1995, tmdb_id=949), index).movie is None

    def test_an_rss_entry_never_falls_back_to_a_title(self) -> None:
        """Batch X5 reverses S5's fall-through (CT46-02, #269).

        The feed names its film. Falling back to the title put a *Psycho* (1998) watch on
        the owned 1960 film; now a film the catalogue lacks is "not in the collection", and
        the sync gives it a row of its own. An unidentified owned row is left for T9.
        """
        unidentified = _film("Collector, The")
        index = build_index([unidentified])
        outcome = match_entry(_entry("The Collector", 1965, tmdb_id=12345), index)
        assert outcome.movie is None
        assert outcome.ambiguity is None

    def test_a_known_year_more_than_one_apart_excludes_a_candidate(self) -> None:
        """**X5's guard (#158 amended).** The diary's *Psycho* (1998) is not the owned 1960
        film, and *The Heat* (2013) is not Michael Mann's *Heat* (1995), though the leading
        article goes and the titles meet: the September import put both on the wrong film.
        """
        index = build_index([_film("Psycho", 1960), _film("Heat", 1995)])
        assert match_entry(_entry("Psycho", 1998), index).movie is None
        assert match_entry(_entry("The Heat", 2013), index).movie is None

    def test_a_year_one_apart_still_matches(self) -> None:
        """A UK release date or a festival premiere can put a film's year one either side."""
        owned = _film("Dunkirk", 2017)
        index = build_index([owned])
        assert match_entry(_entry("Dunkirk", 2016), index).movie is owned
        assert match_entry(_entry("Dunkirk", 2018), index).movie is owned

    def test_an_entry_without_a_year_is_never_excluded_by_one(self) -> None:
        """The other side of #158: an unknown year on either side never excludes."""
        owned = _film("Psycho", 1960)
        index = build_index([owned])
        assert match_entry(_entry("Psycho", None), index).movie is owned
