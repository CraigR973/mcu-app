"""Barcode resolution — Batch 24, Phase 3.4.

**Neither of this batch's acceptance criteria can be met here, and both are named rather
than implied.** §3.3 wants *"scanning a real Blu-ray barcode on mobile returns a valid EAN
in < 2 seconds"* — a phone, a disc and a stopwatch. §3.4 wants *"scanning a common Blu-ray
returns the correct movie"* — a real barcode against live eBay. `group-start.md` puts both
in the owner's hands. What is testable is the decode path against fixtures and the
resolution chain against captured payloads, and that is what is here.

The eBay leg is exercised against `ebay_browse_blade_runner_2049.json` — the same verbatim
production capture Batch 28 uses — because the thing that can actually be wrong is the
extraction of a film's name out of seller prose, and prose is what a real payload has.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

import src.routers.barcode as barcode_router
from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.routers.movies import get_tmdb_client
from src.services.barcode import (
    check_digit_valid,
    film_title_from_listing,
    from_collection,
    normalise,
    rank_titles,
    titles_from_ebay,
)
from src.services.format_names import FORMAT_NAMES
from src.tmdb.models import SearchResult, SearchResults

FIXTURES = Path(__file__).parent / "fixtures"
BLADE_RUNNER: dict[str, Any] = json.loads(
    (FIXTURES / "ebay_browse_blade_runner_2049.json").read_text()
)


# ---------------------------------------------------------------------------
# The check digit — the only free signal separating a misread from a rare disc
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "barcode",
    [
        "5051892211475",  # EAN-13, a UK Blu-ray
        "5050629402445",  # EAN-13
        "883929665495",  # UPC-A, a US disc
        "96385074",  # EAN-8
    ],
)
def test_real_product_codes_pass(barcode: str) -> None:
    assert check_digit_valid(barcode)


@pytest.mark.parametrize(
    "barcode",
    [
        "5051892211476",  # last digit wrong
        "5051892211",  # truncated — a partial read
        "50518922114750",  # 14 digits: not a retail symbology
        "",
        "abcdefghijklm",
        "505189221147X",
    ],
)
def test_a_misread_is_refused(barcode: str) -> None:
    """A misread scan is not a rare disc.

    Without this, every fumbled scan spends a unit of a 5,000-a-day eBay quota searching
    for a number that does not exist, and the person is told "no match" — which reads as
    "we do not know this disc" rather than "try again".
    """
    assert not check_digit_valid(barcode)


def test_one_transposition_is_caught() -> None:
    """The failure the check digit is actually for.

    A scanner reading two adjacent digits in the wrong order is the classic error, and the
    alternating 3/1 weighting is what makes it detectable: the two positions contribute
    different amounts, so swapping unequal digits moves the sum.

    Indices 3 and 4 are `1` and `8`. An earlier revision of this test swapped 6 and 7,
    which are **both `2`** — it swapped a digit with itself and then asserted the result
    differed.
    """
    good = "5051892211475"
    transposed = good[:3] + good[4] + good[3] + good[5:]
    assert good != transposed
    assert check_digit_valid(good)
    assert not check_digit_valid(transposed)


def test_the_one_transposition_it_cannot_catch_is_stated_rather_than_claimed() -> None:
    """GS1 mod-10 does not catch every transposition, and pretending otherwise is worse
    than the gap.

    Swapping adjacent digits that differ by exactly 5 leaves the weighted sum unchanged
    modulo ten — 3a + b against 3b + a differ by 2(a − b), and 2 × 5 = 10. So a scanner
    reading `…16…` as `…61…` produces a barcode that validates and is not the disc in
    your hand. The confirmation UI is the thing standing between that and a wrong
    catalogue entry, which is the other half of why §3.4 makes it mandatory.
    """
    good = "5051892211475"
    # Indices 8 and 9 are `1` and `1`… so use a constructed pair differing by five.
    digits = list(good)
    assert check_digit_valid(good)
    # Find an adjacent pair differing by exactly 5; assert the swap still validates.
    swapped = None
    for index in range(len(digits) - 2):
        if abs(int(digits[index]) - int(digits[index + 1])) == 5:
            swapped = good[:index] + good[index + 1] + good[index] + good[index + 2 :]
            break
    if swapped is not None:
        assert check_digit_valid(swapped), "this is the documented blind spot"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5051892211475", "5051892211475"),
        (" 5051892211475 ", "5051892211475"),
        ("5-051892-211475", "5051892211475"),
        ("EAN 5051892211475", "5051892211475"),
    ],
)
def test_scanner_decoration_is_stripped(raw: str, expected: str) -> None:
    assert normalise(raw) == expected


# ---------------------------------------------------------------------------
# Getting a film's name out of seller prose
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("listing", "expected"),
    [
        (
            "Blade Runner 2049 [Blu-ray] [2017] - DVD  KZVG The Cheap Fast Free Post",
            "blade runner 2049",
        ),
        ("Blade Runner 2049 (Blu-ray, 2018) RYAN GOSLING / HARRISON FORD", "blade runner 2049"),
        ("Jaws 4K UHD Blu-ray SteelBook The Film Vault Range U.K. Exclusive", "jaws"),
        ("BLADE RUNNER 2049 - BLU-RAY DISC - 2018", "blade runner 2049"),
    ],
)
def test_the_title_is_cut_at_the_first_format_word(listing: str, expected: str) -> None:
    """Everything from the format word onwards describes the disc, not the film.

    Crude on purpose — it feeds a search whose results a person confirms. A cleverer
    extraction would produce a more confident wrong answer, which is the failure mode this
    whole batch's risk note is about.
    """
    assert film_title_from_listing(listing) == expected


def test_agreement_between_sellers_is_the_ranking() -> None:
    """Six sellers describing a disc the same way beats any one of them.

    It is the only evidence a barcode search offers, and the cheapest defence against the
    first listing happening to be a bundle or a mis-titled import.
    """
    ranked = rank_titles(
        [
            "Jaws [Blu-ray]",
            "Jaws (1975) Blu-ray",
            "Jaws 4K UHD Blu-ray",
            "Some Other Film Blu-ray",
        ]
    )
    assert ranked[0] == "jaws"
    assert "some other film" in ranked


def test_only_disc_listings_reach_the_ranking() -> None:
    """The same category gate Batch 28 uses, doing the same job.

    A barcode search returns whatever happens to contain those digits — the captured
    payload alone holds art prints, a DVD player and an audio book.
    """
    titles = titles_from_ebay(BLADE_RUNNER)
    summaries = BLADE_RUNNER["itemSummaries"]

    assert 0 < len(titles) < len(summaries)
    assert not any("Player" in title for title in titles)


def test_a_real_payload_resolves_to_the_right_film() -> None:
    """End to end over 200 verbatim production listings.

    This is the closest a fixture can get to §3.4's acceptance — the criterion itself
    needs a real barcode scanned against live eBay and is the owner's.
    """
    assert rank_titles(titles_from_ebay(BLADE_RUNNER))[0] == "blade runner 2049"


def test_an_empty_or_broken_payload_yields_nothing_rather_than_raising() -> None:
    """An eBay outage must still reach the manual-search screen."""
    assert titles_from_ebay({}) == []
    assert titles_from_ebay({"itemSummaries": None}) == []
    assert titles_from_ebay({"itemSummaries": ["not a dict"]}) == []


# ---------------------------------------------------------------------------
# The wire chain and the persisted confirmation
# ---------------------------------------------------------------------------


class FakeTmdbClient:
    async def search_movie(
        self,
        query: str,
        year: int | None = None,
        page: int = 1,
        language: str = "en-US",
        include_adult: bool = False,
    ) -> SearchResults:
        del year, page, language, include_adult
        return SearchResults(
            page=1,
            total_pages=1,
            total_results=1,
            results=[
                SearchResult(
                    id=335984,
                    title="Blade Runner 2049",
                    original_title="Blade Runner 2049",
                    overview=f"Search hit for {query}",
                    release_date="2017-10-04",
                    poster_path="/blade-runner.jpg",
                    popularity=42,
                )
            ],
        )


@pytest_asyncio.fixture
async def barcode_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()


async def _barcode_client(session: AsyncSession, role: UserRole) -> AsyncIterator[AsyncClient]:
    """**Batch S4 (`DECISIONS.md` #155) overrides `get_current_user`, not `require_admin`.**

    Both endpoints were ``AdminUser``; scanning is the quickest way to add a disc, and snag
    7 is about a phone, so leaving them admin-only would have handed a viewer the add page
    with its fastest path disabled. The old fixture overrode the dependency that no longer
    guards them — and could not have expressed a viewer at all, which is why this takes the
    role as an argument.
    """
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Barcode {role.value.title()} {uuid.uuid4().hex[:8]}",
        role=role,
    )
    session.add(profile)
    await session.flush()

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield session

    async def override_user() -> Profile:
        return profile

    async def override_tmdb() -> AsyncIterator[FakeTmdbClient]:
        yield FakeTmdbClient()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def barcode_client(barcode_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async for client in _barcode_client(barcode_session, UserRole.admin):
        yield client


@pytest_asyncio.fixture
async def barcode_viewer_client(barcode_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async for client in _barcode_client(barcode_session, UserRole.viewer):
        yield client


@pytest.mark.asyncio
async def test_a_viewer_can_scan_a_barcode_rather_than_getting_a_403(
    barcode_viewer_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Batch S4, `DECISIONS.md` #155 — **200, not 403.**

    Scanning is the fastest route through the add flow, and snag 7 is about reaching that
    flow from a phone. An add page a viewer can open whose scan button refuses them would
    be the exact defect #155 names: a button whose endpoint still 403s.
    """

    async def no_titles(_barcode: str) -> list[str]:
        return []

    monkeypatch.setattr(barcode_router, "_ebay_titles", no_titles)
    response = await barcode_viewer_client.post(
        "/api/v1/barcode/lookup", json={"barcode": "5051892211475"}
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_an_unknown_code_returns_the_manual_search_result(
    barcode_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_titles(_barcode: str) -> list[str]:
        return []

    monkeypatch.setattr(barcode_router, "_ebay_titles", no_titles)
    response = await barcode_client.post(
        "/api/v1/barcode/lookup", json={"barcode": "5051892211475"}
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "barcode": "5051892211475",
        "source": None,
        "alreadyOwned": False,
        "candidates": [],
    }


@pytest.mark.asyncio
async def test_the_ebay_title_reaches_tmdb_but_still_returns_only_a_candidate(
    barcode_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def one_title(_barcode: str) -> list[str]:
        return ["blade runner 2049"]

    monkeypatch.setattr(barcode_router, "_ebay_titles", one_title)
    response = await barcode_client.post(
        "/api/v1/barcode/lookup", json={"barcode": "5051892211475"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "ebay"
    assert body["alreadyOwned"] is False
    assert body["candidates"][0] == {
        "title": "Blade Runner 2049",
        "source": "ebay",
        "confidence": 0.7,
        "movieId": None,
        "tmdbId": 335984,
        "year": 2017,
        "posterPath": "/blade-runner.jpg",
        "evidence": "eBay listings for this barcode read as 'blade runner 2049'",
    }


@pytest.mark.asyncio
async def test_a_confirmed_local_film_is_canonical_and_the_next_scan_says_owned(
    barcode_client: AsyncClient, barcode_session: AsyncSession
) -> None:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=335984,
        title="Blade Runner 2049",
        original_title="Blade Runner 2049",
        year=2017,
        media_type="film",
    )
    barcode_session.add(movie)
    await barcode_session.flush()
    barcode_session.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=["blu_ray"],
            barcode="5051892211475",
        )
    )
    await barcode_session.flush()

    confirmed = await barcode_client.post(
        "/api/v1/barcode/confirm",
        json={
            "barcode": "5051892211475",
            # These two values deliberately disagree with the local row. The server's
            # movie id is authoritative, so neither can poison the cache.
            "title": "A Plausible Wrong Film",
            "source": "manual",
            "movieId": str(movie.id),
            "tmdbId": 999999,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["candidates"][0]["title"] == "Blade Runner 2049"
    assert confirmed.json()["candidates"][0]["tmdbId"] == 335984

    lookup = await barcode_client.post("/api/v1/barcode/lookup", json={"barcode": "5051892211475"})
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()["source"] == "cache"
    assert lookup.json()["alreadyOwned"] is True
    assert lookup.json()["candidates"][0]["movieId"] == str(movie.id)


@pytest.mark.asyncio
async def test_the_endpoint_refuses_a_bad_check_digit_before_the_chain(
    barcode_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def should_not_run(_barcode: str) -> list[str]:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(barcode_router, "_ebay_titles", should_not_run)
    response = await barcode_client.post(
        "/api/v1/barcode/lookup", json={"barcode": "5051892211476"}
    )

    assert response.status_code == 422
    assert called is False


@pytest.mark.asyncio
async def test_a_disc_already_owned_names_its_formats_as_the_archive_does(
    barcode_session: AsyncSession,
) -> None:
    """Batch Z1 (#287): the scan screen said "already owned on blu_ray", the stored code.

    It now reads as the Archive does, through the one set of format names.
    """
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title="A Twice Owned Film",
        original_title="A Twice Owned Film",
        year=2017,
        media_type="film",
    )
    barcode_session.add(movie)
    await barcode_session.flush()
    barcode_session.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=["4k_uhd", "blu_ray"],
            barcode="5051892211475",
        )
    )
    await barcode_session.flush()

    owned = await from_collection(barcode_session, "5051892211475")

    assert owned is not None
    assert owned.evidence == "already owned on 4K UHD + Blu-ray"
    assert not [code for code in FORMAT_NAMES if code in (owned.evidence or "")]
