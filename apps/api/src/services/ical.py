"""RFC 5545 serialisation for the calendar feed — roadmap §7.4.

**Written by hand rather than with a library, and the reason is the failure mode.** An
iCalendar file is fetched by Apple Calendar or Google Calendar on their schedule, parsed
without a person watching, and — when it is malformed — *silently ignored*. There is no
error message anywhere in the loop: the subscription simply shows nothing, or shows
yesterday's events for ever. So the three rules that actually break feeds are implemented
here explicitly, each with a test, instead of trusted to a dependency this app would then
have to keep current for one file.

The three:

1. **Escaping.** ``,``, ``;``, ``\\`` and newlines are structural in a property value. A
   film called *Fast, Cheap & Out of Control* ends the value early and shifts every
   following field by one. RFC 5545 §3.3.11.
2. **Folding.** Lines longer than 75 **octets** must be split, and continued with a leading
   space. Not 75 characters — an octet count, which is why the fold has to be done on
   encoded bytes and not on the string. RFC 5545 §3.1.
3. **CRLF.** Every line ends ``\\r\\n``. Parsers that accept bare ``\\n`` exist; the ones
   in phones tend not to.

``DTEND`` is the day *after* ``DTSTART`` for an all-day event: ``VALUE=DATE`` ranges are
half-open, so a release on the 9th with ``DTEND`` also on the 9th is a zero-length event and
several clients drop it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

#: RFC 5545 §3.1: "Lines of text SHOULD NOT be longer than 75 octets, excluding the line
#: break."
MAX_LINE_OCTETS = 75


@dataclass(frozen=True)
class CalendarEvent:
    """One VEVENT. All-day, because a release date has no time of day."""

    uid: str
    summary: str
    start: date
    description: str | None = None
    url: str | None = None
    #: Stamped so a client can tell an edited event from a new one.
    last_modified: datetime | None = None


def escape_text(value: str) -> str:
    """Escape a TEXT property value per RFC 5545 §3.3.11.

    Backslash first, or the escapes added below would themselves be escaped.
    """
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def safe_uri(value: str) -> str | None:
    """A URI fit to put in a property value, or ``None`` if it is not one.

    **A URI property is not TEXT, so it is not escaped** — which means a newline inside it
    ends the content line and everything after it is parsed as further iCalendar
    properties. Found by probing the serialiser during this batch's security review:

        url = "https://ok.test/\r\nX-EVIL:injected\r\nDESCRIPTION:hijacked"

    produced exactly those two lines in the output, overriding the event's real
    description. Nothing writes ``release_calendar.url`` today, so it was not yet
    reachable — but **Batch 19's scrapers exist to populate that column from scraped
    retailer pages**, which is precisely the untrusted source that would arm it.

    Rejecting rather than stripping: a URL containing a control character is not a URL
    that lost a character, it is one that should not be trusted, and dropping the property
    is a visible absence rather than a silently altered link. ``http``/``https`` only, so
    a ``javascript:`` or ``data:`` URI cannot reach a calendar client either.
    """
    candidate = value.strip()
    if not candidate or len(candidate) > 2000:
        return None
    # Any C0/C1 control character, not just CR and LF — a lone \x0b or \x85 is treated as
    # a line break by some parsers.
    if any(ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F for character in candidate):
        return None
    if not candidate.lower().startswith(("http://", "https://")):
        return None
    return candidate


def fold(line: str) -> str:
    """Fold a content line to 75 **octets**, continuing with a leading space.

    Counted in octets, not characters: a title with an em dash or an accented letter is
    more bytes than it looks, and a fold computed on the string can produce a line that is
    still over the limit — or, worse, split a multi-byte character in half and make the
    whole file invalid UTF-8. So the split is done on the encoded bytes, at a character
    boundary.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= MAX_LINE_OCTETS:
        return line

    pieces: list[str] = []
    remaining = line
    limit = MAX_LINE_OCTETS
    while len(remaining.encode("utf-8")) > limit:
        # Walk back to a character boundary that fits.
        cut = limit
        while cut > 0 and len(remaining[:cut].encode("utf-8")) > limit:
            cut -= 1
        if cut == 0:  # pragma: no cover - a single character over 74 octets cannot exist
            break
        pieces.append(remaining[:cut])
        remaining = remaining[cut:]
        # Continuation lines carry a leading space, which counts towards their own 75.
        limit = MAX_LINE_OCTETS - 1
    pieces.append(remaining)
    return "\r\n ".join(pieces)


def _line(name: str, value: str) -> str:
    return fold(f"{name}:{value}")


def _date(value: date) -> str:
    return value.strftime("%Y%m%d")


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def render_calendar(
    events: Sequence[CalendarEvent], *, name: str, description: str, now: datetime
) -> str:
    """A complete VCALENDAR, ready to serve.

    ``X-WR-CALNAME`` and ``X-WR-CALDESC`` are not in RFC 5545 — they are Apple extensions
    that Google honours too, and they are the only way the subscription gets a name in the
    sidebar rather than appearing as the URL. Harmless where unsupported.

    ``REFRESH-INTERVAL``/``X-PUBLISHED-TTL`` ask clients not to poll harder than daily. A
    release calendar changes at most once a day, and an unauthenticated endpoint being
    fetched every fifteen minutes by two phones is the cheapest denial of service there is.
    """
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Mark's Cinematic Universe//Release Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _line("X-WR-CALNAME", escape_text(name)),
        _line("X-WR-CALDESC", escape_text(description)),
        "REFRESH-INTERVAL;VALUE=DURATION:P1D",
        "X-PUBLISHED-TTL:P1D",
    ]

    for event in events:
        lines.extend(_render_event(event, now))

    lines.append("END:VCALENDAR")
    # CRLF throughout, including the trailing one. RFC 5545 §3.1.
    return "\r\n".join(lines) + "\r\n"


def _render_event(event: CalendarEvent, now: datetime) -> Iterable[str]:
    from datetime import timedelta

    yield "BEGIN:VEVENT"
    yield _line("UID", event.uid)
    yield _line("DTSTAMP", _timestamp(now))
    yield f"DTSTART;VALUE=DATE:{_date(event.start)}"
    # Half-open: a VALUE=DATE range ends the day *after* the last day it covers. With
    # DTEND equal to DTSTART the event is zero-length and several clients drop it.
    yield f"DTEND;VALUE=DATE:{_date(event.start + timedelta(days=1))}"
    yield _line("SUMMARY", escape_text(event.summary))
    if event.description:
        yield _line("DESCRIPTION", escape_text(event.description))
    if event.url:
        # A URL is not TEXT, so it is not escaped — which is exactly why it has to be
        # *validated*. See :func:`safe_uri`. A rejected URL drops the property rather
        # than emitting something a parser would read as further iCalendar lines.
        checked = safe_uri(event.url)
        if checked is not None:
            yield _line("URL", checked)
    if event.last_modified is not None:
        yield _line("LAST-MODIFIED", _timestamp(event.last_modified))
    yield "TRANSP:TRANSPARENT"
    yield "END:VEVENT"
