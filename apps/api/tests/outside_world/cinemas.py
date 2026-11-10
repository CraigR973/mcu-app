"""One observed CinemaTimes HTML shape for the scheduled E2E flows; never a real GET.

AC6 reads an ODEON branch through it; AE4 (#355) the Omniplex, whose booking link carries the
showing's id in its path rather than an ODEON query.
"""

import html
from typing import Any

import httpx

from src.services.cinemas.parsers import ODEON_CODES, OMNIPLEX_BRANCHES
from src.services.cinemas.venues import BY_SLUG, VENUES

HOSTS = ("cinematimes.com",)


def handle(request: httpx.Request, world: Any) -> httpx.Response:
    scenario = world.scenario().get("cinemas", {})
    chosen = BY_SLUG.get(scenario.get("slug", ""))
    # Every approved CinemaTimes cinema has a page; only the scenario's lists its film. Since AE4
    # a morning run also reads a cinema awaiting its first enable beside the ODEONs (#355), so
    # the Omniplex is asked for whenever an ODEON is on, and answers with an empty day.
    venue = next(
        (v for v in VENUES if v.source == "cinematimes" and str(request.url) == v.programme_url),
        None,
    )
    if venue is None or chosen is None:
        world.log(kind="unknown", host=request.url.host, path=request.url.path)
        return httpx.Response(404)
    if venue.slug in ODEON_CODES:
        booking = (
            "https://www.odeon.co.uk/ticketing/seat-picker/"
            f"?showtimeId={ODEON_CODES[venue.slug]}-60606"
        )
    else:
        branch = OMNIPLEX_BRANCHES[venue.slug]
        booking = f"https://www.omniplexcinemas.co.uk/booking/seats/{branch}/60606"
    title = html.escape(scenario["title"])
    day = html.escape(scenario["day"])
    card = (
        '<div class="movie-card"><a class="cp-film-title" '
        f'href="/uk/glasgow/movies/ac6-e2e/">{title}</a>'
        '<a class="time-button" data-time="20:00" '
        f'href="{html.escape(booking)}">'
        "20:00</a></div>"
        if venue is chosen
        else ""
    )
    body = (
        '<script type="application/ld+json">'
        '{"@type":"MovieTheater","name":"' + html.escape(venue.name) + '"}</script>'
        f'<div class="date-section" data-section-date="{day}">{card}</div>'
    )
    return httpx.Response(200, text=body, headers={"content-type": "text/html"})
