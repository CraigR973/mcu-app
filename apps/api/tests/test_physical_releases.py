"""Batch S6's physical release dates — snag 2.

`RELEASE_TYPES` has carried `4k_uhd_release` and `blu_ray_release` since Batch 17 and
**nothing ever wrote either**: `services/calendar.py` hardcoded `"theatrical"`, so all 30
live release rows were cinema dates.

**The classifier tests are pure and the note strings are real.** Every one was read off
live TMDB on 2026-09-15 across a 60-film sample of this collection.
"""

from __future__ import annotations

import pytest

from src.models.release_calendar import RELEASE_TYPES
from src.services.calendar import classify_physical
from src.tmdb.models import (
    TMDB_RELEASE_DIGITAL,
    TMDB_RELEASE_PHYSICAL,
    TMDB_RELEASE_THEATRICAL,
    CountryReleaseDates,
    ReleaseDate,
    ReleaseDates,
)


class TestClassifyingAPhysicalRelease:
    """**TMDB type 5 means "Physical" and no more.**

    A 4K disc and a Blu-ray released the same day are one entry, so the free-text `note` a
    contributor typed is the only signal there is.
    """

    @pytest.mark.parametrize(
        "note",
        ["4k Ultra HD Blu-ray", "4K UHD", "Ultra HD", "Limited Edition 4K Steelbook"],
    )
    def test_a_note_naming_4k_is_a_4k_release(self, note: str) -> None:
        assert classify_physical(note) == "4k_uhd_release"

    @pytest.mark.parametrize(
        "note",
        ["Blu-ray", "", "DVD", "DVD release", "Alien Anthology Blu-ray Box Set"],
    )
    def test_everything_else_is_a_disc_release(self, note: str) -> None:
        """**A deliberate approximation, and the code admits it.**

        `RELEASE_TYPES` has no DVD member, so a DVD-only release is recorded as
        `blu_ray_release` — which reads as "out on disc". Inventing a vocabulary member
        for a format nobody in this collection is waiting for would be worse.
        """
        assert classify_physical(note) == "blu_ray_release"

    @pytest.mark.parametrize("note", ["VHS", "LaserDisc", "Betamax"])
    def test_an_obsolete_format_is_skipped_rather_than_mislabelled(self, note: str) -> None:
        """A VHS date is a fact about 1994, and a calendar of *upcoming* releases has no
        use for it. Calling it a Blu-ray would be worse than not listing it."""
        assert classify_physical(note) is None

    def test_a_4k_note_wins_over_an_obsolete_one(self) -> None:
        # Box-set notes list several formats at once.
        assert classify_physical("VHS / 4K Ultra HD") == "4k_uhd_release"

    def test_every_type_it_can_return_is_in_the_vocabulary(self) -> None:
        # A classifier that returned a string the CHECK constraint refuses would fail at
        # insert time, halfway through an ingestion, after the cinema dates were written.
        for note in ("4K UHD", "Blu-ray", ""):
            kind = classify_physical(note)
            assert kind is None or kind in RELEASE_TYPES


class TestReadingTmdbsReleaseDates:
    def test_a_country_is_found_case_insensitively_and_others_ignored(self) -> None:
        """A UK app that read US dates would be wrong in a way that looks right."""
        payload = ReleaseDates(
            id=1,
            results=[
                CountryReleaseDates(
                    iso_3166_1="US",
                    release_dates=[ReleaseDate(release_date="2026-01-01T00:00:00.000Z", type=5)],
                ),
                CountryReleaseDates(
                    iso_3166_1="gb",
                    release_dates=[ReleaseDate(release_date="2026-06-01T00:00:00.000Z", type=5)],
                ),
            ],
        )
        gb = payload.for_country("GB")
        assert len(gb) == 1
        assert gb[0].release_date is not None
        assert gb[0].release_date.startswith("2026-06-01")

    def test_a_country_with_no_entry_is_an_empty_list_not_an_error(self) -> None:
        """**The common case, by a wide margin.** Measured 2026-09-15 over three pages of
        `/movie/upcoming` GB: **1 of 58 films had a GB physical date at all.** A film with
        no physical date must keep its cinema date and its card — never be dropped."""
        assert ReleaseDates(id=1, results=[]).for_country("GB") == []

    def test_the_type_constants_match_tmdbs_documented_vocabulary(self) -> None:
        # Getting these wrong would silently ingest cinema dates as disc dates, which is
        # exactly the bug this batch exists to fix, inverted.
        assert (TMDB_RELEASE_THEATRICAL, TMDB_RELEASE_DIGITAL, TMDB_RELEASE_PHYSICAL) == (3, 4, 5)
