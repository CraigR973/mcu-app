"""Parsers for the recorded public specimens; source dates are not original years."""

import json
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from src.services.cinemas.domain import Showing, Snapshot, SourceError, booking_url, local_start
from src.services.cinemas.venues import Venue

ODEON_CODES = {
    "odeon-kilmarnock": "019",
    "odeon-glasgow-quay": "530",
    "odeon-braehead": "615",
    "odeon-east-kilbride": "923",
}
_OPERATOR_HOSTS = {
    "cinematimes": {"www.odeon.co.uk"},
    "vue": {"www.myvue.com"},
    "everyman": {"purchase.everymancinema.com", "www.everymancinema.com"},
    "cineworld": {"web.cineworld.co.uk", "www.cineworld.co.uk"},
    "gft": {"www.glasgowfilm.org"},
    "science": {"www.tickettailor.com", "buytickets.at"},
}


def _booking(value: str | None, source: str) -> str | None:
    valid = booking_url(value)
    return valid if valid and urlsplit(valid).hostname in _OPERATOR_HOSTS[source] else None


def _jsonld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        value = json.loads(script.get_text())
        nodes = value if isinstance(value, list) else [value]
        for node in nodes:
            if isinstance(node, dict):
                blocks.append(node)
                blocks.extend(n for n in node.get("@graph", []) if isinstance(n, dict))
    return blocks


def parse_cinematimes(body: str, venue: Venue) -> Snapshot:
    soup = BeautifulSoup(body, "html.parser")
    structured = _jsonld(soup)
    theaters = [x for x in structured if x.get("@type") == "MovieTheater"]
    if len(theaters) != 1 or theaters[0].get("name") != venue.name:
        raise SourceError("CinemaTimes venue identity differs from the approved branch")
    times: dict[str, str] = {}
    for node in structured:
        if node.get("@type") == "ScreeningEvent":
            url = node.get("offers", {}).get("url", "")
            key = parse_qs(urlsplit(url).query).get("showtimeId", [""])[0]
            if key:
                times[key] = node["startDate"]
    result = Snapshot()
    for section in soup.select(".date-section[data-section-date]"):
        day = date.fromisoformat(str(section["data-section-date"]))
        result.observed_dates.add(day)
        for card in section.select(".movie-card"):
            title = card.select_one(".cp-film-title")
            if title is None:
                result.errors.append("Missing programme title")
                continue
            # This is the provider's film resource, not a key derived from a title.
            # It remains source-only/unverified until explicit identity evidence exists.
            resource = urlsplit(urljoin(venue.programme_url, str(title.get("href", ""))))
            film_key = (
                resource.path
                if resource.hostname == "cinematimes.com"
                and re.fullmatch(r"/uk/glasgow/movies/[^/]+/", resource.path)
                else None
            )
            for link in card.select("a.time-button[data-time][href]"):
                try:
                    url = _booking(str(link["href"]), venue.source)
                    if url is None:
                        raise SourceError("Unexpected ODEON booking destination")
                    keys = parse_qs(urlsplit(url).query).get("showtimeId", [])
                    if len(keys) != 1 or not re.fullmatch(
                        ODEON_CODES[venue.slug] + r"-\d+", keys[0]
                    ):
                        raise SourceError("ODEON showing belongs to another venue")
                    local = day.isoformat() + "T" + str(link["data-time"])
                    start = local_start(local, explicit_utc=times.get(keys[0]))
                    fmt = str(link.get("data-format", "standard"))
                    result.rows.append(
                        Showing(
                            keys[0],
                            film_key or "showing:" + keys[0],
                            title.get_text(" ", strip=True),
                            start,
                            url,
                            local,
                            formats=() if fmt == "standard" else (fmt,),
                        )
                    )
                except (ValueError, KeyError) as exc:
                    result.errors.append(str(exc))
    if not result.observed_dates:
        raise SourceError("No dated CinemaTimes programme sections")
    label = re.search(
        r"Times from ODEON, updated [A-Za-z]+ \d{2}:\d{2}", soup.get_text(" ", strip=True)
    )
    result.source_update_label = label.group(0) if label else None
    # A complete HTML parse is not proof of the operator's full schedule. In particular,
    # the seven-date specimen is narrower than the target and JSON-LD stops at 50 rows.
    result.validate()
    return result


def validate_vue_page(body: str, venue: Venue) -> None:
    page = BeautifulSoup(body, "html.parser")
    title = " ".join(page.title.get_text(" ", strip=True).split()) if page.title else ""
    if venue.name.casefold() not in title.casefold():
        raise SourceError("Vue public programme page identity unavailable; no date requests")


def parse_vue(data: dict[str, Any], day: date, venue: Venue) -> Snapshot:
    if (
        data.get("responseCode") != 0
        or data.get("errorMessage")
        or not isinstance(data.get("result"), list)
    ):
        raise SourceError("Vue did not report a successful cinema-day response")
    result = Snapshot(observed_dates={day}, complete_dates={day})
    for film in data["result"]:
        for group in film["showingGroups"]:
            if group.get("date") and _release_date(group["date"]) != day:
                result.errors.append("Vue group date differs from the requested civil date")
                continue
            for showing in group["sessions"]:
                try:
                    stamp = showing["showTimeWithTimeZone"]
                    if datetime.fromisoformat(stamp).tzinfo is None:
                        raise SourceError("Vue showing offset is missing")
                    start = local_start(stamp)
                    if start.date() != day:
                        raise SourceError("Vue showing differs from the requested civil date")
                    url = _booking(urljoin("https://www.myvue.com", showing["bookingUrl"]), "vue")
                    expected = (
                        f"/book-tickets/summary/{venue.source_id}/"
                        f"{film['filmId']}/{showing['sessionId']}"
                    )
                    if url is None or urlsplit(url).path.rstrip("/") != expected:
                        raise SourceError("Vue booking/session/venue identities disagree")
                    available = showing.get("isBookingAvailable") is True and not showing.get(
                        "isSoldOut", False
                    )
                    end = showing.get("endTime")
                    # The end field is local; never silently pick its DST fold.
                    parsed_end = local_start(end) if end else None
                    result.rows.append(
                        Showing(
                            str(showing["sessionId"]),
                            str(film["filmId"]),
                            film["filmTitle"],
                            start,
                            url if available else None,
                            stamp,
                            end=parsed_end,
                            screen=showing.get("screenName"),
                            source_release=_release_date(film.get("releaseDate")),
                            identity_facts={
                                **({"director": film["director"]} if film.get("director") else {}),
                                **(
                                    {"originalTitle": film["originalTitle"]}
                                    if film.get("originalTitle")
                                    else {}
                                ),
                                **(
                                    {"runtimeMinutes": film["runningTime"]}
                                    if film.get("runningTime")
                                    else {}
                                ),
                            },
                            evidence=_returning_label(film["filmTitle"], venue.programme_url),
                        )
                    )
                    result.observed_dates.add(start.date())
                except (ValueError, KeyError) as exc:
                    result.errors.append(str(exc))
    result.validate()
    return result


def _release_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _returning_label(title: str, url: str) -> dict[str, Any]:
    label = re.search(
        r"\b(?:\d+(?:st|nd|rd|th) anniversary(?:\)?\s+[248]K restoration)?"
        r"|[248]K restoration|re-release|reissue)\)?\s*$",
        title,
        re.I,
    )
    if len(title) <= 300 and label and title[: label.start()].strip(" ()-–:"):
        # A label is evidence about this programme, not yet a verified film/run.
        return {"returningLabel": True, "sourceUrl": url, "quote": title}
    return {}


def movie_metadata(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = data.get("data", {}).get("allMovie", {}).get("nodes")
    if not isinstance(nodes, list):
        raise SourceError("Public movie metadata has changed shape")
    return {str(m["id"]): m for m in nodes}


def parse_boxoffice(
    data: dict[str, Any], metadata: dict[str, dict[str, Any]], venue: Venue
) -> Snapshot:
    node = data.get(venue.source_id)
    if not isinstance(node, dict) or not isinstance(node.get("schedule"), dict):
        raise SourceError("Schedule is missing the approved venue identity")
    result = Snapshot()
    for film_id, dates in node["schedule"].items():
        film = metadata.get(str(film_id))
        if film is None or not film.get("title"):
            result.errors.append("Movie metadata is missing for a scheduled identity")
            continue
        for showings in dates.values():
            for showing in showings:
                try:
                    urls = [
                        u
                        for t in showing.get("data", {}).get("ticketing", [])
                        if t.get("provider") == "default"
                        for u in t.get("urls", [])
                    ]
                    url = next(
                        (_booking(u, venue.source) for u in urls if _booking(u, venue.source)), None
                    )
                    key = str(showing["id"])
                    strength = "weak"
                    if url and venue.source == "cineworld":
                        match = re.fullmatch(
                            r"/order/showtimes/(088-\d+)/seats/?", urlsplit(url).path
                        )
                        if not match:
                            raise SourceError("Cineworld booking belongs to another branch")
                        key, strength = match.group(1), "opaque"
                    # Everyman's purchase UUID is opaque but its reschedule stability is
                    # unproved; retain that uncertainty instead of merging moved times.
                    start = local_start(showing["startsAt"])
                    result.rows.append(
                        Showing(
                            key,
                            str(film_id),
                            film["title"],
                            start,
                            url,
                            showing["startsAt"],
                            strength=strength,
                            screen=showing.get("screen", {}).get("name"),
                            formats=tuple(
                                str(x)
                                for x in showing.get("tags", [])
                                if str(x).startswith("Format.")
                            ),
                            expired=showing.get("isExpired") is True,
                            source_release=_release_date(film.get("release")),
                            evidence=_returning_label(film["title"], venue.programme_url),
                        )
                    )
                    result.observed_dates.add(start.date())
                except (ValueError, KeyError) as exc:
                    result.errors.append(str(exc))
    result.validate()
    return result


def parse_gft(body: str) -> Snapshot:
    soup = BeautifulSoup(body, "html.parser")
    result = Snapshot()
    day: date | None = None
    title: str | None = None
    for tag in soup.find_all(["h4", "h5", "a"]):
        if tag.name == "h4":
            try:
                day = datetime.strptime(tag.get_text(strip=True), "%A, %B %d, %Y").date()
            except ValueError:
                day = None
        elif tag.name == "h5":
            title = tag.get_text(" ", strip=True)
        elif "/checkout/showing/" in str(tag.get("href", "")) and day and title:
            try:
                local = (
                    day.isoformat()
                    + "T"
                    + datetime.strptime(tag.get_text(strip=True), "%I:%M %p").time().isoformat()
                )
                url = _booking(urljoin("https://www.glasgowfilm.org", str(tag["href"])), "gft")
                if not url:
                    raise SourceError("Unexpected GFT booking destination")
                # No verified film ID in the SEO HTML: identical titles/slugs can
                # represent remakes. Keep showing-scoped identities until verified.
                key = urlsplit(url).path.rstrip("/").split("/")[-1]
                result.rows.append(
                    Showing(
                        key,
                        "showing:" + key,
                        title,
                        local_start(local),
                        url,
                        local,
                        strength="weak",
                    )
                )
                result.observed_dates.add(day)
            except (ValueError, KeyError) as exc:
                result.errors.append(str(exc))
    if not result.observed_dates:
        raise SourceError("GFT listing has no dated showing references; coverage unknown")
    result.validate()
    return result


def science_links(body: str, base: str) -> list[str]:
    soup = BeautifulSoup(body, "html.parser")
    result = set()
    for link in soup.select("a[href]"):
        url = urljoin(base, str(link["href"]))
        parsed = urlsplit(url)
        if (
            parsed.scheme == "https"
            and parsed.hostname == "www.tickettailor.com"
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
            and re.fullmatch(r"/events/gscimax(?:/\d+)?/?", parsed.path)
        ):
            result.add("https://www.tickettailor.com" + parsed.path)
    return sorted(result)


def parse_science(body: str, url: str) -> Snapshot:
    result = Snapshot()
    events = [x for x in _jsonld(BeautifulSoup(body, "html.parser")) if x.get("@type") == "Event"]
    event_id = urlsplit(url).path.rstrip("/").split("/")[-1]
    if not event_id.isdigit():
        raise SourceError("Unrecognised Science Centre event identity")
    for event in events:
        try:
            location = event.get("location", {}).get("name", "")
            if "imax" not in location.lower():
                raise SourceError("Event location does not identify Science Centre IMAX")
            stamp = event["startDate"]
            if datetime.fromisoformat(stamp).tzinfo is None:
                raise SourceError("Event offset missing")
            start = local_start(stamp)
            end = local_start(event["endDate"]) if event.get("endDate") else None
            result.rows.append(
                Showing(
                    event_id + ":" + start.isoformat(),
                    event_id,
                    event["name"],
                    start,
                    _booking(url, "science"),
                    stamp,
                    strength="weak",
                    end=end,
                    formats=("IMAX",),
                    cancelled=event.get("eventStatus") == "https://schema.org/EventCancelled",
                )
            )
            result.observed_dates.add(start.date())
        except (ValueError, KeyError) as exc:
            result.errors.append(str(exc))
    if not events:
        result.errors.append("Event structured dates unavailable; not a complete empty programme")
    result.validate()
    return result
