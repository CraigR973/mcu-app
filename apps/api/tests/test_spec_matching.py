"""Finding a disc's Blu-ray.com page, the parts that need no database — Batch T7.

**What this proves:** a Blu-ray.com page title is read correctly for film, format, country
and edition; only exact release pages ever become candidates; one UK page is accepted and
anything less certain waits for Craig; the page year is read from a real captured page; the
Brave client sends the key, reads its results and fails by name.

**The titles are real.** Every one below was returned for Blu-ray.com by a web search on
24 Sep 2026, for Blade Runner 2049 and Fight Club, with the page addresses beside them.

**What it does not:** a live Brave call. The client is built from Brave's documentation
and is confirmed against a real response on the first live search, which needs Craig's key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from src.models.specs_backfill import SpecRun
from src.scripts.spec_backfill import report
from src.services.specs.backfill import Coverage, StartOutcome, same_page
from src.services.specs.bluray_com import OutOfBounds, canonical_release_url, extract_year
from src.services.specs.candidates import (
    Disc,
    decide,
    judge,
    parse_release_title,
    search_query,
)
from src.services.specs.search import (
    SEARCH_PATH,
    BraveError,
    BraveNotConfigured,
    BraveSearch,
    SearchHit,
    hits_from_payload,
)

FIXTURES = Path(__file__).parent / "fixtures"

#: Returned for "site:blu-ray.com Blade Runner 2049 4K Blu-ray United Kingdom", 24 Sep.
BLADE_RUNNER_HITS = [
    SearchHit(url, title, "")
    for title, url in [
        (
            "Blade Runner 2049 4K Blu-ray (4K Ultra HD + Blu-ray) (United Kingdom)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/248418/",
        ),
        (
            "Blade Runner 2049 4K Blu-ray (SteelBook) (United Kingdom)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/338923/",
        ),
        (
            "Blade Runner 2049 4K Blu-ray (HMV Exclusive DigiPack) (United Kingdom)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/217763/",
        ),
        (
            "Blade Runner 2049 4K Blu-ray (Zavvi Exclusive SteelBook) (United Kingdom)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/285308/",
        ),
        (
            "Blade Runner 2049 4K Blu-ray (Limited Edition with Whiskey Glasses Set) "
            "(United Kingdom)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/190525/",
        ),
        (
            "Blade Runner 2049 4K/3D Blu-ray (HMV Exclusive SteelBook) (United Kingdom)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-3D-Blu-ray/190503/",
        ),
        (
            "Blade Runner 2049 4K Blu-ray (4K Ultra HD + Blu-ray)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/189774/",
        ),
        (
            "Blade Runner 2049 Blu-ray (United Kingdom)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-Blu-ray/190522/",
        ),
        (
            "Blade Runner 2049 Blu-ray (Limited Edition | Bonus Disc | Art Cards) (United Kingdom)",
            "https://www.blu-ray.com/movies/Blade-Runner-2049-Blu-ray/194680/",
        ),
        (
            "Blade Runner 2049 DVD (United Kingdom)",
            "https://www.blu-ray.com/dvd/Blade-Runner-2049-DVD/146727/",
        ),
    ]
]

#: Returned for "blu-ray.com Fight Club Blu-ray United Kingdom release", 24 Sep.
FIGHT_CLUB_HITS = [
    SearchHit(url, title, "")
    for title, url in [
        (
            "Fight Club Blu-ray (MetalPak) (United Kingdom)",
            "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/114797/",
        ),
        (
            "Fight Club Blu-ray (10th Anniversary Edition) (United Kingdom)",
            "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/6715/",
        ),
        (
            "Fight Club Blu-ray (Play Exclusive SteelBook) (United Kingdom)",
            "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/41252/",
        ),
        (
            "Fight Club 4K Blu-ray (4K Ultra HD + Blu-ray) (United Kingdom)",
            "https://www.blu-ray.com/movies/Fight-Club-4K-Blu-ray/410066/",
        ),
        (
            "Fight Club 4K Blu-ray (SteelBook) (United Kingdom)",
            "https://www.blu-ray.com/movies/Fight-Club-4K-Blu-ray/407386/",
        ),
        (
            "Fight Club 4K Blu-ray (SteelBook)",
            "https://www.blu-ray.com/movies/Fight-Club-4K-Blu-ray/406956/",
        ),
        (
            "Fight Club Blu-ray (10th Anniversary Edition)",
            "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/5587/",
        ),
        (
            "Fight Club Blu-ray (SteelBook)",
            "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/213961/",
        ),
        (
            "Fight Club Blu-ray (Best Buy Exclusive)",
            "https://www.blu-ray.com/movies/Fight-Club-Blu-ray/207375/",
        ),
        ("Strippers vs Werewolves", "https://en.wikipedia.org/wiki/Strippers_vs_Werewolves"),
    ]
]


# ---------------------------------------------------------------------------
# Reading a page title
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "name", "label", "country", "editions"),
    [
        (
            "Blade Runner 2049 4K Blu-ray (4K Ultra HD + Blu-ray) (United Kingdom)",
            "Blade Runner 2049",
            "4K Blu-ray",
            "United Kingdom",
            (),
        ),
        (
            "Blade Runner 2049 4K Blu-ray (Zavvi Exclusive SteelBook) (United Kingdom)",
            "Blade Runner 2049",
            "4K Blu-ray",
            "United Kingdom",
            ("Zavvi Exclusive SteelBook",),
        ),
        (
            "Blade Runner 2049 4K/3D Blu-ray (HMV Exclusive SteelBook) (United Kingdom)",
            "Blade Runner 2049",
            "4K/3D Blu-ray",
            "United Kingdom",
            ("HMV Exclusive SteelBook",),
        ),
        (
            "Blade Runner 2049 4K Blu-ray (4K Ultra HD + Blu-ray)",
            "Blade Runner 2049",
            "4K Blu-ray",
            "United States",
            (),
        ),
        (
            "Fight Club Blu-ray (10th Anniversary Edition) (United Kingdom)",
            "Fight Club",
            "Blu-ray",
            "United Kingdom",
            ("10th Anniversary Edition",),
        ),
        (
            "Blade Runner 2049 Blu-ray (United Kingdom) - Blu-ray.com",
            "Blade Runner 2049",
            "Blu-ray",
            "United Kingdom",
            (),
        ),
    ],
)
def test_a_page_title_is_read_for_film_format_country_and_edition(
    title: str, name: str, label: str, country: str, editions: tuple[str, ...]
) -> None:
    release = parse_release_title(title)
    assert (release.name, release.format_label, release.country, release.editions) == (
        name,
        label,
        country,
        editions,
    )


def test_a_title_cut_short_has_no_country_and_no_format() -> None:
    """A search engine may truncate a long title. Then the country is unknown, not the US."""
    release = parse_release_title("Fight Club 4K Blu-ray (SteelBook) (United Kin...")
    assert release.country is None
    assert release.format_label is None


# ---------------------------------------------------------------------------
# Deciding
# ---------------------------------------------------------------------------

BLADE_RUNNER_4K = Disc(title="Blade Runner 2049", year=2017, format_code="4k_uhd")
BLADE_RUNNER_BD = Disc(title="Blade Runner 2049", year=2017, format_code="blu_ray")
FIGHT_CLUB_BD = Disc(title="Fight Club", year=1999, format_code="blu_ray")
FIGHT_CLUB_4K = Disc(title="Fight Club", year=1999, format_code="4k_uhd")


def test_the_one_plain_uk_4k_is_chosen_among_five_uk_4k_editions() -> None:
    verdict = decide(judge(BLADE_RUNNER_HITS, BLADE_RUNNER_4K), BLADE_RUNNER_4K)
    assert verdict.decision == "accepted"
    assert verdict.url == "https://www.blu-ray.com/movies/Blade-Runner-2049-4K-Blu-ray/248418/"


def test_the_one_plain_uk_blu_ray_is_chosen_for_a_blu_ray() -> None:
    verdict = decide(judge(BLADE_RUNNER_HITS, BLADE_RUNNER_BD), BLADE_RUNNER_BD)
    assert verdict.url == "https://www.blu-ray.com/movies/Blade-Runner-2049-Blu-ray/190522/"


def test_three_uk_editions_and_no_plain_one_wait_for_craig() -> None:
    """Fight Club's UK Blu-rays are a MetalPak, a steelbook and an anniversary edition."""
    candidates = judge(FIGHT_CLUB_HITS, FIGHT_CLUB_BD)
    verdict = decide(candidates, FIGHT_CLUB_BD)
    assert verdict.decision == "needs_you"
    assert verdict.url is None
    assert "3 UK editions" in verdict.note
    assert sum(candidate.matches for candidate in candidates) == 3


def test_a_us_page_never_matches_a_uk_disc() -> None:
    """The 10 Sep test used 189774, the US 4K, for Blade Runner 2049."""
    candidates = judge(BLADE_RUNNER_HITS, BLADE_RUNNER_4K)
    us = next(c for c in candidates if c.url.endswith("/189774/"))
    assert us.release.country == "United States"
    assert us.matches is False


def test_only_exact_release_pages_become_candidates() -> None:
    """#110's predicate, applied to every hit: no DVD path, no search route, no other site."""
    hits = [
        *FIGHT_CLUB_HITS,
        SearchHit("https://www.blu-ray.com/search/?quicksearch=1&q=fight+club", "Search", ""),
        SearchHit("https://www.blu-ray.com/dvd/Fight-Club-DVD/1/", "Fight Club DVD", ""),
        SearchHit("https://example.com/movies/Fight-Club-Blu-ray/1/", "Fight Club Blu-ray", ""),
    ]
    urls = [candidate.url for candidate in judge(hits, FIGHT_CLUB_BD)]
    assert all(url.startswith("https://www.blu-ray.com/movies/") for url in urls)
    assert len(urls) == 9


def test_a_4k_disc_takes_the_plain_uk_4k_not_the_steelbook_or_the_us_one() -> None:
    verdict = decide(judge(FIGHT_CLUB_HITS, FIGHT_CLUB_4K), FIGHT_CLUB_4K)
    assert verdict.url == "https://www.blu-ray.com/movies/Fight-Club-4K-Blu-ray/410066/"


def test_a_film_with_no_year_is_never_accepted_automatically() -> None:
    undated = Disc(title="Blade Runner 2049", year=None, format_code="4k_uhd")
    verdict = decide(judge(BLADE_RUNNER_HITS, undated), undated)
    assert verdict.decision == "needs_you"
    assert "no year" in verdict.note


def test_a_disc_in_a_box_set_is_never_accepted_automatically() -> None:
    boxed = Disc(
        title="Blade Runner 2049",
        year=2017,
        format_code="4k_uhd",
        grouping="The James Bond Collection Box Set",
    )
    assert decide(judge(BLADE_RUNNER_HITS, boxed), boxed).decision == "needs_you"


def test_a_director_grouping_is_not_a_box_set() -> None:
    assert (
        Disc(title="Heat", year=1995, format_code="blu_ray", grouping="Clint Eastwood").in_box_set
        is False
    )
    assert Disc(
        title="Heat", year=1995, format_code="blu_ray", grouping="Universal Noir #2"
    ).in_box_set


def test_only_us_pages_leave_the_choice_to_craig() -> None:
    us_only = [hit for hit in FIGHT_CLUB_HITS if "United Kingdom" not in hit.title]
    verdict = decide(judge(us_only, FIGHT_CLUB_BD), FIGHT_CLUB_BD)
    assert verdict.decision == "needs_you"
    assert "No UK page" in verdict.note


def test_nothing_in_bounds_is_no_match() -> None:
    wiki = [SearchHit("https://en.wikipedia.org/wiki/Fight_Club", "Fight Club - Wikipedia", "")]
    assert decide(judge(wiki, FIGHT_CLUB_BD), FIGHT_CLUB_BD).decision == "no_match"


def test_another_film_of_similar_name_does_not_match() -> None:
    hits = [
        SearchHit(
            "https://www.blu-ray.com/movies/Blade-Runner-Blu-ray/1/",
            "Blade Runner Blu-ray (The Final Cut) (United Kingdom)",
            "",
        )
    ]
    assert decide(judge(hits, BLADE_RUNNER_BD), BLADE_RUNNER_BD).decision == "needs_you"


def test_the_search_asks_for_uk_pages_on_the_site() -> None:
    assert search_query("Heat", "4k_uhd") == "site:blu-ray.com Heat 4K Blu-ray United Kingdom"
    assert search_query("Heat", "blu_ray") == "site:blu-ray.com Heat Blu-ray United Kingdom"


# ---------------------------------------------------------------------------
# Page addresses and years
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spelling",
    [
        "https://www.blu-ray.com/movies/Heat-Blu-ray/12345/",
        "https://blu-ray.com/movies/Heat-Blu-ray/12345",
        "http://WWW.Blu-ray.com/movies/Heat-Blu-ray/12345/",
    ],
)
def test_every_spelling_of_a_page_is_stored_as_one(spelling: str) -> None:
    assert canonical_release_url(spelling) == "https://www.blu-ray.com/movies/Heat-Blu-ray/12345/"
    assert same_page(spelling, "https://www.blu-ray.com/movies/Heat-Blu-ray/12345/")


def test_a_search_route_cannot_be_made_canonical() -> None:
    with pytest.raises(OutOfBounds):
        canonical_release_url("https://www.blu-ray.com/search/?q=heat")


def test_the_page_year_is_read_from_real_captured_pages() -> None:
    fight_club = (FIXTURES / "bluray_com_release_page.html").read_text()
    blade_runner = (FIXTURES / "bluray_com_release_page_4k.html").read_text()
    assert extract_year(fight_club) == 1999
    assert extract_year(blade_runner) == 2017
    assert extract_year("<html><body><p>No studio line</p></body></html>") is None


# ---------------------------------------------------------------------------
# The Brave client
# ---------------------------------------------------------------------------


class _Brave:
    def __init__(self, statuses: list[int | Exception] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self._statuses = statuses or []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == SEARCH_PATH
        self.requests.append(request)
        status = self._statuses.pop(0) if self._statuses else 200
        if isinstance(status, Exception):
            raise status
        if status != 200:
            return httpx.Response(status, json={"type": "ErrorResponse"})
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "url": "https://www.blu-ray.com/movies/Heat-Blu-ray/12345/",
                            "title": "<strong>Heat</strong> Blu-ray (United Kingdom)",
                            "description": "Heat Blu-ray Release Date &amp; specs",
                        },
                        {"title": "No address"},
                        {"url": "https://www.blu-ray.com/movies/Heat-Blu-ray/2/"},
                    ]
                }
            },
        )


def _brave(recorder: _Brave, **kwargs: Any) -> BraveSearch:
    brave = BraveSearch(api_key="test-key", rate=1000.0, **kwargs)
    brave._client = httpx.AsyncClient(  # noqa: SLF001 - injecting the transport is the point
        base_url="https://api.search.brave.com", transport=httpx.MockTransport(recorder.handler)
    )
    return brave


@pytest.mark.asyncio
async def test_a_search_sends_the_key_and_reads_the_results_as_plain_text() -> None:
    recorder = _Brave()
    hits = await _brave(recorder).search("site:blu-ray.com Heat Blu-ray United Kingdom")

    assert hits == [
        SearchHit(
            url="https://www.blu-ray.com/movies/Heat-Blu-ray/12345/",
            title="Heat Blu-ray (United Kingdom)",
            description="Heat Blu-ray Release Date & specs",
        )
    ]
    sent = recorder.requests[0]
    assert sent.headers["X-Subscription-Token"] == "test-key"
    assert sent.url.params["q"] == "site:blu-ray.com Heat Blu-ray United Kingdom"
    assert sent.url.params["count"] == "20"
    assert sent.url.params["country"] == "GB"


@pytest.mark.asyncio
async def test_no_key_refuses_before_sending_anything() -> None:
    async with BraveSearch(api_key="") as brave:
        assert brave.configured is False
        with pytest.raises(BraveNotConfigured):
            await brave.search("Heat")


@pytest.mark.asyncio
async def test_a_refused_key_is_not_retried() -> None:
    recorder = _Brave([401])
    brave = _brave(recorder)
    with pytest.raises(BraveError) as caught:
        await brave.search("Heat")
    assert caught.value.status_code == 401
    assert brave.search_calls == 1


@pytest.mark.asyncio
async def test_a_busy_server_and_a_dropped_connection_are_retried_and_counted() -> None:
    recorder = _Brave([503, httpx.ReadError("reset"), 200])
    brave = _brave(recorder, max_retries=2)
    hits = await brave.search("Heat")
    assert len(hits) == 1
    assert brave.search_calls == 3 == brave.attempts_per_search


@pytest.mark.asyncio
async def test_a_connection_that_keeps_dropping_is_a_brave_error() -> None:
    recorder = _Brave([httpx.ConnectTimeout("slow")] * 3)
    brave = _brave(recorder, max_retries=2)
    with pytest.raises(BraveError) as caught:
        await brave.search("Heat")
    assert caught.value.status_code is None


def test_a_payload_without_web_results_is_no_hits() -> None:
    assert hits_from_payload({"type": "search"}) == []
    assert hits_from_payload({"web": {"results": "not a list"}}) == []


# ---------------------------------------------------------------------------
# The command's exit code
# ---------------------------------------------------------------------------

COVERAGE = Coverage(
    discs=1250, with_specs=10, accepted=5, needs_you=20, no_match=3, skipped=0, not_searched=1212
)


def _run(**fields: Any) -> SpecRun:
    defaults: dict[str, Any] = {
        "trigger": "job",
        "status": "finished",
        "search_budget": 150,
        "searches": 0,
        "searched": 0,
        "accepted": 0,
        "queued": 0,
        "no_match": 0,
        "restored": 0,
        "fetch_budget": 150,
        "fetched": 0,
        "applied": 0,
        "sent_back": 0,
        "fetch_failed": 0,
        "last_error": None,
    }
    return SpecRun(**{**defaults, **fields})


def test_a_halted_batch_fails_the_command(capsys: pytest.CaptureFixture[str]) -> None:
    run = _run(status="halted", last_error="The Blu-ray.com integration is halted: HTTP 403")
    assert report(StartOutcome("started", run), run, COVERAGE) == 1
    assert "HTTP 403" in capsys.readouterr().out


def test_a_finished_batch_reports_coverage(capsys: pytest.CaptureFixture[str]) -> None:
    run = _run(searches=150, searched=150, accepted=90, queued=55, no_match=5)
    assert report(StartOutcome("started", run), run, COVERAGE) == 0
    out = capsys.readouterr().out
    assert "10 of 1250 Blu-ray and 4K discs have specs" in out
    assert "23 for Craig" in out


def test_a_halted_integration_refuses_to_start_and_says_so(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert report(StartOutcome("halted", None), None, COVERAGE) == 1
    assert "halted" in capsys.readouterr().out
