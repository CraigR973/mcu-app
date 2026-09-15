"""Batch S5's feed reader — snag 10a, `DECISIONS.md` #156, #158, #159.

Pure parsing, so these run everywhere. **The first *live* fetch is an owner action**
(`OWNER-ACTIONS.md` 1j): `docs/agent-commands/group-start.md` keeps live third-party
requests out of unattended runs, so the fixture is built from the element names recorded
from both real feeds rather than captured from the wire — and the parser is written not to
care about the parts that were not measured.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.services.letterboxd.diary import DiaryParseError
from src.services.letterboxd.feed import FEED_ENTRY_CAP, feed_url, parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "letterboxd_diary_rss.xml"


def _entries():
    return parse_feed(FIXTURE.read_text(encoding="utf-8"))


class TestTheFeedUrl:
    def test_builds_the_public_diary_url(self) -> None:
        assert feed_url("CraigR973") == "https://letterboxd.com/CraigR973/rss/"

    @pytest.mark.parametrize(
        "bad",
        ["", "craig/../mark", "craig?x=1", "https://letterboxd.com/craig", "craig r", "a" * 65],
    )
    def test_refuses_anything_that_is_not_a_username(self, bad: str) -> None:
        """Refused rather than escaped.

        A username is chosen from a list of two by the people who use this app; a value
        needing escaping is a mistake upstream, and quietly encoding it would hide that.
        """
        with pytest.raises(DiaryParseError):
            feed_url(bad)


class TestParsingTheFeed:
    def test_reads_every_field_the_criterion_names(self) -> None:
        first = _entries()[0]
        assert first.viewing_id == "900000001"  # from `<guid>letterboxd-watch-…`
        assert first.watched_at == date(2026, 9, 9)  # letterboxd:watchedDate
        assert first.is_rewatch is False  # letterboxd:rewatch
        assert first.rating == Decimal("4.0")  # letterboxd:memberRating
        assert first.tmdb_id == 111111  # tmdb:movieId
        assert first.title == "Pressure"
        assert first.year == 2026

    def test_the_watched_date_is_used_and_not_the_publication_date(self) -> None:
        """`<pubDate>` is when the entry was *posted*; `<letterboxd:watchedDate>` is when
        the film was watched, and they differ on real entries — the second one is logged
        the morning after. `watch_log.watched_at` wants the viewing."""
        entry = _entries()[1]
        assert entry.watched_at == date(2026, 9, 5)  # pubDate is the 6th

    def test_a_rewatch_is_read_as_one(self) -> None:
        assert _entries()[1].is_rewatch is True

    def test_a_missing_rating_is_none_rather_than_an_error(self) -> None:
        """**Mark rates nothing — 0 of 50** (`DECISIONS.md` #159). A null rating is correct
        data, so an entry without one is an ordinary entry."""
        collector = _entries()[2]
        assert collector.rating is None
        assert collector.title == "The Collector"
        assert collector.tmdb_id == 29259

    def test_the_title_falls_back_to_the_rss_title_when_the_namespaced_one_is_absent(
        self,
    ) -> None:
        """The exact XML was never captured, so the parser does not depend on any one
        element being present. `<title>` reads "Film Name, Year"."""
        fallback = _entries()[3]
        assert fallback.title == "Fast & Furious"
        assert fallback.year == 2009
        assert fallback.tmdb_id is None

    def test_an_item_that_is_not_a_viewing_is_skipped_rather_than_failing(self) -> None:
        """Letterboxd puts list publications in the same channel. They carry no
        `letterboxd-watch-` guid, and treating one as a parse failure would take down a
        sync over an entry that was never a viewing."""
        assert len(_entries()) == 4  # five items, one of them a list

    def test_the_namespace_prefix_does_not_matter(self) -> None:
        """Matched on local name.

        The fixture's namespace URIs are a guess — the measurement recorded element
        *names* — so the parser must survive being wrong about them, which is exactly what
        the first live fetch will confirm.
        """
        xml = FIXTURE.read_text(encoding="utf-8")
        # Declarations first, then the element prefixes — renaming a prefix without
        # renaming its `xmlns:` declaration leaves it undeclared and the document invalid,
        # which would test the wrong thing.
        renamed = (
            xml.replace(
                'xmlns:letterboxd="https://letterboxd.com"',
                'xmlns:lb="https://example.invalid/not-the-real-namespace"',
            )
            .replace(
                'xmlns:tmdb="https://themoviedb.org"',
                'xmlns:themoviedb="https://example.invalid/nor-this-one"',
            )
            .replace("letterboxd:", "lb:")
            .replace("<tmdb:", "<themoviedb:")
            .replace("</tmdb:", "</themoviedb:")
        )
        assert [e.viewing_id for e in parse_feed(renamed)] == [e.viewing_id for e in _entries()]

    def test_a_repeated_guid_yields_one_entry(self) -> None:
        doubled = FIXTURE.read_text(encoding="utf-8").replace(
            "letterboxd-watch-900000002", "letterboxd-watch-900000001"
        )
        assert len(parse_feed(doubled)) == 3

    def test_something_that_is_not_xml_is_refused_by_name(self) -> None:
        with pytest.raises(DiaryParseError, match="not XML"):
            parse_feed("<html>we are down for maintenance")

    def test_the_cap_is_recorded_as_fifty(self) -> None:
        """Not a page size to raise — it is Letterboxd's, and it is **why the sync
        interval is a correctness property**. Mark's feed reaches back about eight weeks;
        a sync running less often than roughly monthly loses his entries silently."""
        assert FEED_ENTRY_CAP == 50


class TestTheGuidIsS8sViewingId:
    def test_the_guid_wraps_the_same_number_the_csv_calls_viewing_id(self) -> None:
        """**The reason S8 runs first** (`DECISIONS.md` #176).

        `watch_log.letterboxd_viewing_id` stores the bare number, so a viewing present in
        both the file and the feed is one row rather than two. This asserts the half of
        that contract the feed owns; `test_letterboxd_import.py` asserts the other half
        end to end.
        """
        assert _entries()[0].viewing_id == "900000001"
        assert not _entries()[0].viewing_id.startswith("letterboxd-watch-")
