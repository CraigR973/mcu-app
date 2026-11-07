"""What a cinema trip's pushes say — the wording Craig approved (#345), in one place.

Times are the cinema's own, never the reader's: a showing at 20:10 is a fact about the cinema.
A format that is not plain digital follows the time ("20:00 IMAX"), as on the film page.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: The outbox's title column.
TITLE_LIMIT = 200

#: The film page's format words (`lib/cinemas.ts`), less the two that say nothing on a phone.
_FORMATS = {
    "2d": "2D",
    "3d": "3D",
    "4k": "4K",
    "imax": "IMAX",
    "isense": "iSense",
    "format.projection.3d": "3D",
    "format.projection.4k": "4K",
    "format.projection.imax": "IMAX",
}
_SILENT = {"format.projection.digital"}


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("Europe/London")


def _local(starts_utc: datetime, zone: str) -> datetime:
    return starts_utc.replace(tzinfo=UTC).astimezone(_zone(zone))


def format_words(formats: Sequence[str]) -> str:
    """ "IMAX", "IMAX 3D", or "" for plain digital and anything unrecognised."""
    words: list[str] = []
    for value in formats:
        key = str(value).lower()
        if key in _SILENT or (key.startswith("format.") and key not in _FORMATS):
            continue
        word = _FORMATS.get(key, str(value))
        if word not in words:
            words.append(word)
    return " ".join(words)


def clock(starts_utc: datetime, zone: str, formats: Sequence[str] = ()) -> str:
    """ "20:10", or "20:00 IMAX"."""
    words = format_words(formats)
    time = f"{_local(starts_utc, zone):%H:%M}"
    return f"{time} {words}" if words else time


def when(starts_utc: datetime, zone: str, formats: Sequence[str] = ()) -> str:
    """ "Mon 9 Nov at 20:10"."""
    local = _local(starts_utc, zone)
    return f"{local:%a} {local.day} {local:%b} at {clock(starts_utc, zone, formats)}"


def names(people: Sequence[str]) -> str:
    """Up to two names, then a count: "Mark", "Mark and Alex", "Mark, Alex and 2 others"."""
    if len(people) <= 2:
        return " and ".join(people)
    rest = len(people) - 2
    return f"{people[0]}, {people[1]} and {rest} other{'' if rest == 1 else 's'}"


def possessive(name: str) -> str:
    return f"{name}'s"


def title(text: str) -> str:
    return text if len(text) <= TITLE_LIMIT else text[: TITLE_LIMIT - 1] + "…"


def tally(going: int, people: int, *, invitees: int) -> str:
    """ " 2 of 3 going." on a trip with two or more invitees; nothing on a trip with one.

    ``going`` and ``people`` count the proposer, who always counts as going (#345 §5).
    """
    return f" {going} of {people} going." if invitees >= 2 else ""


def flag_sentence(flag: str | None) -> str:
    """What the reminder adds about a showing the programme no longer lists as it was."""
    if flag == "withdrawn":
        return " The cinema no longer lists this time; check before you go."
    if flag == "cancelled":
        return " The cinema has cancelled this showing."
    return ""
