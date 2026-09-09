"""RFC 5545 serialisation — roadmap §7.4.

No database and no HTTP: these are the three rules that actually break calendar feeds, and
each is pinned on its own. **A malformed feed is silently ignored** by Apple Calendar and
Google Calendar — no error reaches anyone, the subscription simply shows nothing or shows
stale events for ever — so these behaviours cannot be verified by looking at the app.
"""

from __future__ import annotations

from datetime import date, datetime

from src.services.ical import CalendarEvent, escape_text, fold, render_calendar

NOW = datetime(2026, 9, 9, 1, 2, 3)


def test_a_comma_in_a_title_does_not_end_the_property_early() -> None:
    """RFC 5545 §3.3.11. A film called *Fast, Cheap & Out of Control* is not hypothetical.

    Unescaped, the comma ends the value and every following field shifts by one — which a
    parser accepts, producing an event with the wrong description.
    """
    assert escape_text("Fast, Cheap & Out of Control") == "Fast\\, Cheap & Out of Control"


def test_semicolons_and_backslashes_are_escaped_in_the_right_order() -> None:
    """Backslash first, or the escapes added afterwards get escaped themselves."""
    assert escape_text("a;b") == "a\;b"
    assert escape_text("a\\b") == "a\\\\b"
    assert escape_text("a\\,b") == "a\\\\\\,b"


def test_newlines_become_literal_escapes_not_line_breaks() -> None:
    """A raw newline inside a value ends the content line and makes the rest garbage."""
    assert escape_text("one\ntwo") == "one\\ntwo"
    assert escape_text("one\r\ntwo") == "one\\ntwo"


def test_a_long_line_is_folded_to_75_octets_with_a_leading_space() -> None:
    folded = fold("SUMMARY:" + "X" * 200)
    lines = folded.split("\r\n")
    assert len(lines) > 1
    assert all(len(line.encode("utf-8")) <= 75 for line in lines)
    assert all(line.startswith(" ") for line in lines[1:])


def test_folding_counts_octets_not_characters() -> None:
    """The limit is 75 **octets**. An em dash is three bytes and one character.

    A fold computed on the string produces lines that are still over the limit — and a
    naive byte slice would split a character in half and make the file invalid UTF-8.
    """
    folded = fold("SUMMARY:" + "—" * 60)
    lines = folded.split("\r\n")
    assert all(len(line.encode("utf-8")) <= 75 for line in lines)
    # Nothing was cut mid-character: every piece still decodes.
    assert "".join(line.lstrip(" ") if i else line for i, line in enumerate(lines)).startswith(
        "SUMMARY:—"
    )


def test_an_all_day_event_ends_the_following_day() -> None:
    """A ``VALUE=DATE`` range is half-open.

    With ``DTEND`` equal to ``DTSTART`` the event is zero-length, and several clients drop
    it entirely — a feed that validates and shows nothing.
    """
    ics = render_calendar(
        [CalendarEvent(uid="x@mcu", summary="A Release", start=date(2026, 10, 1))],
        name="MCU",
        description="d",
        now=NOW,
    )
    assert "DTSTART;VALUE=DATE:20261001" in ics
    assert "DTEND;VALUE=DATE:20261002" in ics


def test_every_line_ends_crlf() -> None:
    """RFC 5545 §3.1. Parsers that accept a bare newline exist; phones tend not to."""
    ics = render_calendar(
        [CalendarEvent(uid="x@mcu", summary="A Release", start=date(2026, 10, 1))],
        name="MCU",
        description="d",
        now=NOW,
    )
    assert "\n" in ics
    assert ics.replace("\r\n", "").count("\n") == 0
    assert ics.endswith("\r\n")


def test_the_document_is_well_formed_and_carries_a_name() -> None:
    ics = render_calendar(
        [CalendarEvent(uid="x@mcu", summary="A Release", start=date(2026, 10, 1))],
        name="MCU — Release calendar",
        description="Upcoming releases.",
        now=NOW,
    )
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.rstrip("\r\n").endswith("END:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == ics.count("END:VEVENT") == 1
    # Apple's extension, honoured by Google. Without it the subscription is named after
    # its URL in the sidebar.
    assert "X-WR-CALNAME" in ics
    # Asks clients not to poll harder than daily — an unauthenticated endpoint fetched
    # every fifteen minutes by two phones is the cheapest denial of service there is.
    assert "REFRESH-INTERVAL;VALUE=DURATION:P1D" in ics


def test_an_empty_calendar_is_still_a_valid_document() -> None:
    """A subscription set up before the first ingestion must not break the client."""
    ics = render_calendar([], name="MCU", description="d", now=NOW)
    assert "BEGIN:VCALENDAR" in ics and "END:VCALENDAR" in ics
    assert "BEGIN:VEVENT" not in ics


def test_a_newline_in_a_url_cannot_inject_calendar_properties() -> None:
    """The hole this batch's security review found, before anything could write to it.

    A URI property is not TEXT and so is not escaped — so a newline inside one ends the
    content line and everything after it is parsed as further iCalendar properties. The
    probe below produced a real ``X-EVIL`` property and a hijacked ``DESCRIPTION`` in the
    served feed.

    Nothing writes ``release_calendar.url`` yet. **Batch 19's scrapers are what would arm
    it** — that column exists to hold links scraped from retailer pages, which is exactly
    the untrusted source this guards against.
    """
    ics = render_calendar(
        [
            CalendarEvent(
                uid="x@mcu",
                summary="A Release",
                start=date(2026, 10, 1),
                url="https://ok.test/\r\nX-EVIL:injected\r\nDESCRIPTION:hijacked",
            )
        ],
        name="MCU",
        description="d",
        now=NOW,
    )
    assert "X-EVIL" not in ics
    assert "hijacked" not in ics
    # Dropped entirely rather than silently truncated to a different link.
    assert "URL:" not in ics


def test_a_non_http_uri_never_reaches_a_calendar_client() -> None:
    for hostile in ("javascript:alert(1)", "data:text/html;base64,PHNjcmlwdD4="):
        ics = render_calendar(
            [CalendarEvent(uid="x@mcu", summary="A", start=date(2026, 10, 1), url=hostile)],
            name="MCU",
            description="d",
            now=NOW,
        )
        assert "URL:" not in ics, hostile


def test_an_ordinary_url_still_appears() -> None:
    ics = render_calendar(
        [
            CalendarEvent(
                uid="x@mcu",
                summary="A",
                start=date(2026, 10, 1),
                url="https://www.themoviedb.org/movie/949",
            )
        ],
        name="MCU",
        description="d",
        now=NOW,
    )
    assert "URL:https://www.themoviedb.org/movie/949" in ics
