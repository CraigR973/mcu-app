"""Source observations with explicit uncertainty; no date/year/title guessing."""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
SOURCE_HOSTS = frozenset(
    {
        "cinematimes.com",
        "www.cineworld.co.uk",
        "www.myvue.com",
        "www.everymancinema.com",
        "www.glasgowfilm.org",
        "www.glasgowsciencecentre.org",
        "www.tickettailor.com",
        "cms-assets.webediamovies.pro",
    }
)
Category = Literal["newRelease", "olderFilm", "unclassified"]
BOOKING_PATHS = {
    "www.odeon.co.uk": ("/ticketing/seat-picker/", "/cinemas/"),
    "www.myvue.com": ("/book-tickets/", "/cinema/"),
    "www.everymancinema.com": ("/booking/", "/venues-list/", "/film-listing/"),
    "purchase.everymancinema.com": ("/launch/ticketing/",),
    "web.cineworld.co.uk": ("/order/showtimes/",),
    "www.cineworld.co.uk": ("/cinemas/",),
    "www.glasgowfilm.org": ("/checkout/showing/", "/movie/", "/all-listings/"),
    "www.tickettailor.com": ("/events/gscimax/",),
    "buytickets.at": ("/gscimax/",),
}


class SourceError(ValueError):
    """A specimen cannot establish a safe, complete observation."""


def booking_url(value: str | None) -> str | None:
    if not value or len(value) > 2048 or any(ord(c) < 32 for c in value):
        return None
    try:
        url = urlsplit(value)
        if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
            return None
        paths = BOOKING_PATHS.get(url.hostname or "", ())
        return value if any(url.path.startswith(p) for p in paths) else None
    except ValueError:
        return None


def local_start(value: str, *, explicit_utc: str | None = None) -> datetime:
    """Return aware local time; quarantine folds/gaps instead of choosing fold=0."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return parsed.astimezone(LONDON)
    if explicit_utc:
        exact = datetime.fromisoformat(explicit_utc.replace("Z", "+00:00"))
        if exact.tzinfo is None:
            raise SourceError("Offset missing from corroborating timestamp")
        local = exact.astimezone(LONDON)
        if local.replace(tzinfo=None) != parsed:
            raise SourceError("HTML date/time disagrees with structured timestamp")
        return local
    possible = {
        parsed.replace(tzinfo=LONDON, fold=fold).astimezone(UTC)
        for fold in (0, 1)
        if parsed.replace(tzinfo=LONDON, fold=fold)
        .astimezone(UTC)
        .astimezone(LONDON)
        .replace(tzinfo=None)
        == parsed
    }
    if len(possible) != 1:
        raise SourceError("Ambiguous or nonexistent Europe/London local time")
    return next(iter(possible)).astimezone(LONDON)


def days_between(start: date, end: date) -> list[date]:
    if not 0 <= (end - start).days < 14:
        raise SourceError("Select between one and fourteen local dates")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def release_category(evidence: dict[str, Any], *, identity_verified: bool) -> Category:
    """Explicit run evidence only: dates/years/titles are not a first-run classifier."""
    if not identity_verified or evidence.get("conflict") or evidence.get("combinedProgramme"):
        return "unclassified"
    source = evidence.get("sourceUrl")
    quote = evidence.get("quote")
    if (
        not isinstance(source, str)
        or not isinstance(quote, str)
        or not quote.strip()
        or len(quote) > 300
    ):
        return "unclassified"
    try:
        url = urlsplit(source)
        if (
            url.scheme != "https"
            or url.hostname not in SOURCE_HOSTS
            or url.username
            or url.password
            or url.port not in (None, 443)
        ):
            return "unclassified"
    except ValueError:
        return "unclassified"
    if evidence.get("run") == "firstUkTheatrical":
        return "newRelease"
    if evidence.get("run") == "returning":
        return "olderFilm"
    return "unclassified"


@dataclass(frozen=True)
class Showing:
    key: str
    film_key: str
    title: str
    start: datetime
    booking: str | None
    source_local: str
    strength: str = "opaque"
    end: datetime | None = None
    screen: str | None = None
    formats: tuple[str, ...] = ()
    cancelled: bool = False
    expired: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)
    tmdb_id: int | None = None
    imdb_id: str | None = None
    source_release: date | None = None
    identity_facts: dict[str, str | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or (self.end is not None and self.end.tzinfo is None):
            raise SourceError("Showing timestamps require an evidenced offset")
        if self.end is not None and self.end <= self.start:
            raise SourceError("Showing end must follow its start")
        if not self.key or len(self.key) > 500 or not self.film_key or len(self.film_key) > 300:
            raise SourceError("Missing or oversized showing/film identity")
        if not self.title.strip() or len(self.title) > 500:
            raise SourceError("Missing or oversized programme title")
        if len(self.source_local) > 50 or (self.screen is not None and len(self.screen) > 200):
            raise SourceError("Oversized showing timestamp or screen")
        if self.booking is not None and booking_url(self.booking) != self.booking:
            raise SourceError("Unapproved booking URL")
        if self.tmdb_id is not None and (
            type(self.tmdb_id) is not int or not 0 < self.tmdb_id < 2**31
        ):
            raise SourceError("Invalid explicit TMDB identity")
        if self.imdb_id is not None and not re.fullmatch(r"tt\d{7,10}", self.imdb_id):
            raise SourceError("Invalid explicit IMDb identity")
        if set(self.identity_facts) - {"director", "originalTitle", "runtimeMinutes"}:
            raise SourceError("Unexpected source identity fact")
        for key, value in self.identity_facts.items():
            if key == "runtimeMinutes":
                if type(value) is not int or not 0 < value <= 1000:
                    raise SourceError("Invalid source runtime")
            elif not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise SourceError("Invalid source identity text")
        if set(self.evidence) - {
            "run",
            "sourceUrl",
            "quote",
            "conflict",
            "combinedProgramme",
            "reissue",
            "returningLabel",
        }:
            raise SourceError("Unexpected programme evidence fields; no raw payload storage")


@dataclass
class Snapshot:
    rows: list[Showing] = field(default_factory=list)
    observed_dates: set[date] = field(default_factory=set)
    complete_dates: set[date] = field(default_factory=set)
    source_update_label: str | None = None
    upstream_utc: datetime | None = None
    errors: list[str] = field(default_factory=list)
    failed: bool = False
    refused_host: str | None = None
    observed_utc: datetime | None = None

    def validate(self) -> None:
        keyed: dict[str, Showing] = {}
        films: dict[str, Showing] = {}
        for row in self.rows:
            if row.key in keyed and keyed[row.key] != row:
                raise SourceError("One showing identity has conflicting source rows")
            keyed[row.key] = row
            previous = films.get(row.film_key)
            if previous and (
                previous.title != row.title
                or previous.identity_facts != row.identity_facts
                or previous.source_release != row.source_release
                or (previous.tmdb_id and row.tmdb_id and previous.tmdb_id != row.tmdb_id)
                or (previous.imdb_id and row.imdb_id and previous.imdb_id != row.imdb_id)
            ):
                raise SourceError("One source film key has conflicting identities")
            films[row.film_key] = row
        self.rows = list(keyed.values())
        if self.errors:
            self.complete_dates.clear()
