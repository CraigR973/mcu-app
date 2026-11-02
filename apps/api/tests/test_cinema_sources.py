"""Recorded public specimens and bounded anonymous transport; never contact providers."""

import asyncio
import copy
import hashlib
import json
from dataclasses import replace
from datetime import UTC, date
from pathlib import Path

import httpx
import pytest

from src.services.cinemas.collect import collect_venue
from src.services.cinemas.domain import (
    Showing,
    Snapshot,
    SourceError,
    local_start,
    release_category,
)
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
from src.services.cinemas.venues import BY_SLUG

FIXTURES = Path(__file__).parent / "fixtures" / "cinemas"


def body(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_real_specimen_provenance():
    provenance = json.loads(body("provenance.json"))
    assert len(provenance) == 12
    for name, record in provenance.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == record["fixtureSha256"]
        assert len(record["sourceSha256"]) == 64


@pytest.mark.parametrize(
    ("file", "slug", "count"),
    [
        ("kilmarnock", "odeon-kilmarnock", 137),
        ("quay", "odeon-glasgow-quay", 269),
        ("braehead", "odeon-braehead", 262),
        ("east-kilbride", "odeon-east-kilbride", 201),
    ],
)
def test_cinematimes_uses_full_html_beyond_fifty_structured_rows(file, slug, count):
    snapshot = parse_cinematimes(body(f"cinematimes-{file}.html"), BY_SLUG[slug])
    assert len(snapshot.rows) == count
    assert len(snapshot.observed_dates) == 7
    assert snapshot.complete_dates == set()
    assert snapshot.errors == []
    assert snapshot.upstream_utc is None
    assert all(r.booking and "www.odeon.co.uk" in r.booking for r in snapshot.rows)
    assert all(
        release_category(r.evidence, identity_verified=False) == "unclassified"
        for r in snapshot.rows
    )


def test_cinematimes_wrong_branch_and_disagreeing_timestamps_quarantined():
    source = body("cinematimes-braehead.html")
    with pytest.raises(SourceError, match="venue identity"):
        parse_cinematimes(source, BY_SLUG["odeon-kilmarnock"])
    # Corrupt one structured timestamp, retaining its opaque booking identity.
    source = source.replace('"startDate": "2026-', '"startDate": "2027-', 1)
    result = parse_cinematimes(source, BY_SLUG["odeon-braehead"])
    assert any("disagrees" in error for error in result.errors)
    assert len(result.rows) == 261


def test_vue_real_cinema_day_and_booking_identity():
    data = json.loads(body("vue.json"))
    result = parse_vue(data, date(2026, 10, 31), BY_SLUG["vue-st-enoch"])
    assert len(result.rows) == 19
    assert result.errors == []
    assert result.complete_dates == {date(2026, 10, 31)}
    assert all(r.start.tzinfo is not None for r in result.rows)
    corrupt = copy.deepcopy(data)
    corrupt["result"][0]["showingGroups"][0]["sessions"][0]["bookingUrl"] = (
        "/book-tickets/summary/WRONG/film/session"
    )
    rejected = parse_vue(corrupt, date(2026, 10, 31), BY_SLUG["vue-st-enoch"])
    assert rejected.errors and not rejected.complete_dates
    assert len(rejected.rows) == 18
    with pytest.raises(SourceError):
        parse_vue({"responseCode": 403, "result": []}, date(2026, 10, 31), BY_SLUG["vue-st-enoch"])


@pytest.mark.parametrize(
    ("source", "slug", "count"),
    [
        ("everyman", "everyman-glasgow", 6),
        ("cineworld", "cineworld-silverburn", 19),
    ],
)
def test_boxoffice_joins_real_ids_and_preserves_partial_horizon(source, slug, count):
    data = json.loads(body(source + "-schedule.json"))
    metadata = movie_metadata(json.loads(body(source + "-metadata.json")))
    result = parse_boxoffice(data, metadata, BY_SLUG[slug])
    assert len(result.rows) == count and result.errors == []
    assert result.observed_dates and not result.complete_dates
    # These real metadata records have null release dates. Do not infer a year/run
    # from a programme title, date of showing or current calendar year.
    assert all(r.source_release is None for r in result.rows)
    assert all(r.booking for r in result.rows)
    # IDs without matching metadata cannot become a nameless, apparently complete day.
    missing = parse_boxoffice(data, {}, BY_SLUG[slug])
    assert missing.rows == [] and missing.errors and not missing.complete_dates


def test_gft_and_imax_real_dates_no_title_merging_or_global_completeness():
    gft = parse_gft(body("gft.html"))
    assert len(gft.rows) == 20 and not gft.errors
    assert len({r.film_key for r in gft.rows}) == len(gft.rows)
    assert all(r.strength == "weak" for r in gft.rows)
    imax = parse_science(
        body("science-event.html"), "https://www.tickettailor.com/events/gscimax/2456601"
    )
    assert len(imax.rows) == 6 and not imax.errors
    assert not imax.complete_dates and not gft.complete_dates
    assert all(r.formats == ("IMAX",) for r in imax.rows)
    assert all(r.start.astimezone(UTC).hour == r.start.hour for r in imax.rows)


@pytest.mark.parametrize("stamp", ["2026-03-29T01:30:00", "2026-10-25T01:30:00"])
def test_dst_gaps_and_folds_require_corroboration(stamp):
    with pytest.raises(SourceError, match="Ambiguous or nonexistent"):
        local_start(stamp)


def test_dst_offset_and_structured_corroboration():
    summer = local_start("2026-07-01T20:00:00")
    assert summer.astimezone(UTC).hour == 19
    second_fold = local_start("2026-10-25T01:30:00", explicit_utc="2026-10-25T01:30:00Z")
    assert second_fold.fold == 1
    with pytest.raises(SourceError, match="disagrees"):
        local_start("2026-07-01T20:00:00", explicit_utc="2026-07-01T20:00:00Z")


def test_new_and_returning_need_evidence_and_identity_independent_of_age():
    evidence = {
        "run": "returning",
        "sourceUrl": BY_SLUG["gft"].programme_url,
        "quote": "Returning for another run",
    }
    assert release_category(evidence, identity_verified=True) == "olderFilm"
    assert release_category(evidence, identity_verified=False) == "unclassified"
    assert (
        release_category({**evidence, "run": "firstUkTheatrical"}, identity_verified=True)
        == "newRelease"
    )
    for change in [
        {"conflict": True},
        {"combinedProgramme": True},
        {"quote": ""},
        {"sourceUrl": "https://attacker.example/"},
        {"run": "2026"},
    ]:
        assert release_category({**evidence, **change}, identity_verified=True) == "unclassified"
    assert release_category({}, identity_verified=True) == "unclassified"


def test_conflicting_or_replayed_showings():
    row = Showing("1", "1", "Film", local_start("2026-11-04T20:00"), None, "2026-11-04T20:00")
    snapshot = Snapshot(rows=[row, row])
    snapshot.validate()
    assert snapshot.rows == [row]
    with pytest.raises(SourceError, match="conflicting source rows"):
        Snapshot(rows=[row, replace(row, start=local_start("2026-11-04T21:00"))]).validate()
    with pytest.raises(SourceError, match="conflicting identities"):
        Snapshot(rows=[row, replace(row, key="2", title="A remake")]).validate()


def test_science_discovery_never_follows_checkout_or_untrusted_hosts():
    links = science_links(
        """<a href="https://www.tickettailor.com/events/gscimax/123">one</a>
        <a href="https://www.tickettailor.com/checkout/view-event/id/123">checkout</a>
        <a href="https://evil.example/events/gscimax/123">evil</a>""",
        BY_SLUG["science-centre-imax"].programme_url,
    )
    assert links == ["https://www.tickettailor.com/events/gscimax/123"]


@pytest.mark.asyncio
async def test_transport_stops_refused_host_without_retry_or_other_branch():
    seen = []

    async def handler(request):
        seen.append(str(request.url))
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        first = await collect_venue(
            BY_SLUG["odeon-braehead"], date(2026, 11, 1), date(2026, 11, 7), fetch
        )
        second = await collect_venue(
            BY_SLUG["odeon-kilmarnock"], date(2026, 11, 1), date(2026, 11, 7), fetch
        )
        assert first.failed and second.failed
        assert first.refused_host == second.refused_host == "cinematimes.com"
        assert fetch.requests == len(seen) == 1


@pytest.mark.asyncio
async def test_transport_bounds_redirect_challenge_body_requests_and_hosts():
    async def handler(request):
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"Location": "https://evil.example"})
        if request.url.path == "/challenge":
            return httpx.Response(200, text="<title>Just a moment</title>")
        return httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        for url, message in [
            ("https://evil.example/", "Unexpected"),
            ("https://www.myvue.com/redirect", "302"),
            ("https://www.everymancinema.com/large", "body limit"),
        ]:
            with pytest.raises(SourceError, match=message):
                await fetch.get(url)
        with pytest.raises(Refused):
            await fetch.get("https://cinematimes.com/challenge")
        fetch.requests = 120
        with pytest.raises(SourceError, match="limit"):
            await fetch.get("https://www.glasgowfilm.org/")


@pytest.mark.asyncio
async def test_transport_host_spacing_and_global_concurrency():
    starts = []
    active = maximum = 0

    async def handler(request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        starts.append((request.url.host, asyncio.get_running_loop().time()))
        await asyncio.sleep(0.02)
        active -= 1
        return httpx.Response(200, text="programme")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetch = Budget(client)
        await asyncio.gather(
            *(
                fetch.get(url)
                for url in [
                    "https://www.myvue.com/one",
                    "https://www.myvue.com/two",
                    "https://cinematimes.com/",
                    "https://www.glasgowfilm.org/",
                ]
            )
        )
    vue = [t for host, t in starts if host == "www.myvue.com"]
    assert vue[1] - vue[0] >= 0.99
    assert maximum <= 2
