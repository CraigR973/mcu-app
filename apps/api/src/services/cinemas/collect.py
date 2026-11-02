"""Collect the approved six source families without a browser or new provider."""

import json
import re
from datetime import UTC, date, timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from src.clock import utcnow
from src.services.cinemas.domain import LONDON, Snapshot, SourceError, days_between
from src.services.cinemas.fetch import Budget, Refused
from src.services.cinemas.parsers import (
    movie_metadata,
    parse_boxoffice,
    parse_cinematimes,
    parse_gft,
    parse_science,
    parse_vue,
    science_links,
)
from src.services.cinemas.venues import Venue

ADAPTER_VERSION = "ab6-2"


def _merge(into: Snapshot, other: Snapshot) -> None:
    into.rows.extend(other.rows)
    into.observed_dates.update(other.observed_dates)
    into.complete_dates.update(other.complete_dates)
    into.errors.extend(other.errors)


def _metadata_url(body: str, source: str) -> str:
    brand = "everyman" if source == "everyman" else "cineworld-cinemas"
    # The dated asset root is observed in each venue's HTML script URLs. We do not
    # execute/download JS or pin a stale site's build date. The query hash is the real
    # allMovie query recorded in both public specimens; a changed query fails honestly.
    match = re.search(
        r"https://cms-assets\.webediamovies\.pro/prod/" + brand + r"/[^/\s\"'<>]+/public/",
        body,
    )
    if match is None:
        raise SourceError("Current public movie-metadata asset root is unavailable")
    return match.group(0) + "page-data/sq/d/3836549025.json"


async def collect_venue(venue: Venue, start: date, end: date, fetch: Budget) -> Snapshot:
    days = days_between(start, end)
    checked_utc = utcnow()
    result = Snapshot()
    try:
        if venue.source == "cinematimes":
            result = parse_cinematimes(await fetch.get(venue.programme_url), venue)
        elif venue.source == "gft":
            result = parse_gft(await fetch.get(venue.programme_url))
        elif venue.source == "vue":
            # This approved adapter observes only today/tomorrow, even when the
            # caller selects later dates. Later coverage remains explicitly unchecked.
            today = checked_utc.replace(tzinfo=UTC).astimezone(LONDON).date()
            for day in (d for d in days if today <= d <= today + timedelta(days=1)):
                query = urlencode(
                    {
                        "showingDate": day.isoformat() + "T00:00:00",
                        "minEmbargoLevel": 3,
                        "includesSession": "true",
                        "includeSessionAttributes": "true",
                    },
                    safe=":",
                )
                url = "https://www.myvue.com/api/microservice/showings/cinemas/10097/films?" + query
                _merge(result, parse_vue(json.loads(await fetch.get(url)), day, venue))
        elif venue.source in ("everyman", "cineworld"):
            body = await fetch.get(venue.programme_url)
            metadata = movie_metadata(
                json.loads(await fetch.get(_metadata_url(body, venue.source)))
            )
            host = urlsplit(venue.programme_url).netloc
            # Business days run 03:00–03:00. Include the preceding business day to cover
            # a requested civil date's 00:00–03:00, then filter by actual local dates.
            for day in [start - timedelta(days=1), *days]:
                query = urlencode(
                    {
                        "from": day.isoformat() + "T03:00:00",
                        "theaters": json.dumps(
                            {"id": venue.source_id, "timeZone": "Europe/London"},
                            separators=(",", ":"),
                        ),
                        "to": (day + timedelta(days=1)).isoformat() + "T03:00:00",
                    }
                )
                data: dict[str, Any] = json.loads(
                    await fetch.get(
                        f"https://{host}/api/gatsby-source-boxofficeapi/schedule?" + query
                    )
                )
                _merge(result, parse_boxoffice(data, metadata, venue))
        elif venue.source == "science":
            body = await fetch.get(venue.programme_url)
            pending = science_links(body, venue.programme_url)
            visited: set[str] = set()
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                body = await fetch.get(url)
                if re.fullmatch(r"/events/gscimax/\d+/?", urlsplit(url).path):
                    _merge(result, parse_science(body, url))
                else:
                    pending.extend(x for x in science_links(body, url) if x not in visited)
            if not visited:
                result.errors.append("Science Centre public event discovery unavailable")
            # No proof yet that a box-office page has enumerated the entire future
            # horizon; known events update observations, never complete empty dates.
        else:
            raise SourceError("No approved adapter for this venue")
        result.validate()
        if len(result.rows) > 10000:
            raise SourceError("Programme normalised-row limit reached")
        result.rows = [x for x in result.rows if start <= x.start.date() <= end]
        result.observed_dates.intersection_update(days)
        result.complete_dates.intersection_update(days)
    except Refused as exc:
        result.failed = True
        result.refused_host = exc.host
        result.errors.append(str(exc))
        result.complete_dates.clear()
    except (SourceError, ValueError, KeyError, TypeError, httpx.HTTPError, TimeoutError) as exc:
        result.failed = True
        result.errors.append(type(exc).__name__ + ": " + str(exc)[:200])
        result.complete_dates.clear()
    # Conservative lower bound: the check's start, never the later import time.
    result.observed_utc = checked_utc
    return result
