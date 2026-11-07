"""One observed CinemaTimes HTML shape for the scheduled AC6 E2E flow; never a real GET."""

import html
from typing import Any

import httpx

from src.services.cinemas.parsers import ODEON_CODES
from src.services.cinemas.venues import BY_SLUG

HOSTS = ("cinematimes.com",)


def handle(request: httpx.Request, world: Any) -> httpx.Response:
    scenario = world.scenario().get("cinemas", {})
    venue = BY_SLUG.get(scenario.get("slug", ""))
    if venue is None or venue.source != "cinematimes" or str(request.url) != venue.programme_url:
        world.log(kind="unknown", host=request.url.host, path=request.url.path)
        return httpx.Response(404)
    code = ODEON_CODES[venue.slug]
    title = html.escape(scenario["title"])
    day = html.escape(scenario["day"])
    body = (
        '<script type="application/ld+json">'
        '{"@type":"MovieTheater","name":"' + html.escape(venue.name) + '"}</script>'
        f'<div class="date-section" data-section-date="{day}">'
        '<div class="movie-card"><a class="cp-film-title" '
        f'href="/uk/glasgow/movies/ac6-e2e/">{title}</a>'
        '<a class="time-button" data-time="20:00" '
        f'href="https://www.odeon.co.uk/ticketing/seat-picker/?showtimeId={code}-60606">'
        "20:00</a></div></div>"
    )
    return httpx.Response(200, text=body, headers={"content-type": "text/html"})
