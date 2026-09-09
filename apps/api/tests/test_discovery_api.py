"""Batch 16's streaming availability and recommendations — §7.1 and §7.2.

TMDB is faked here and exercised live in the batch report. A suite that called a third
party would fail for reasons that have nothing to do with this code, and TMDB's answer for
any given film changes whenever a streaming deal does.

What is pinned here is everything *this* app decides: which region is asked about, how the
three offer kinds are ordered, and — the one that would be wrong silently — what counts as
"owned".
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import WantedItem
from src.routers.movies import get_tmdb_client
from src.tmdb.models import (
    SearchResult,
    SearchResults,
    WatchProvider,
    WatchProviderCountry,
    WatchProviders,
)

pytestmark = pytest.mark.asyncio


def _provider(provider_id: int, name: str) -> WatchProvider:
    return WatchProvider(
        provider_id=provider_id, provider_name=name, logo_path=f"/{provider_id}.jpg"
    )


def _result(tmdb_id: int, title: str, *, genres: list[int] | None = None) -> SearchResult:
    return SearchResult(
        id=tmdb_id,
        title=title,
        original_title=title,
        overview=f"About {title}.",
        release_date="2026-09-09",
        poster_path=f"/{tmdb_id}.jpg",
        genre_ids=genres or [],
    )


class FakeDiscoveryClient:
    """Stands in for TMDB, and records which region it was asked about."""

    def __init__(
        self,
        providers: WatchProviders | None = None,
        recommendations: list[SearchResult] | None = None,
        upcoming: list[SearchResult] | None = None,
        fail: bool = False,
    ) -> None:
        self._providers = providers or WatchProviders()
        self._recommendations = recommendations or []
        self._upcoming = upcoming or []
        self._fail = fail
        self.regions_asked: list[str] = []

    async def get_watch_providers(self, movie_id: int) -> WatchProviders:
        del movie_id
        if self._fail:
            raise httpx.ConnectError("TMDB is down")
        return self._providers

    async def get_recommendations(
        self, movie_id: int, language: str = "en-US", page: int = 1
    ) -> SearchResults:
        del movie_id, language, page
        if self._fail:
            raise httpx.ConnectError("TMDB is down")
        return SearchResults(
            page=1,
            total_pages=1,
            total_results=len(self._recommendations),
            results=self._recommendations,
        )

    async def get_upcoming(
        self, region: str = "GB", language: str = "en-US", page: int = 1
    ) -> SearchResults:
        del language, page
        self.regions_asked.append(region)
        return SearchResults(
            page=1, total_pages=1, total_results=len(self._upcoming), results=self._upcoming
        )


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def viewer(api_session: AsyncSession) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Batch Sixteen {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=UserRole.viewer,
        streaming_region="GB",
    )
    api_session.add(profile)
    await api_session.flush()
    return profile


def _install(api_session: AsyncSession, viewer: Profile, tmdb: FakeDiscoveryClient) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user() -> Profile:
        return viewer

    async def override_tmdb() -> AsyncIterator[FakeDiscoveryClient]:
        yield tmdb

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _owned_film(
    session: AsyncSession, title: str, tmdb_id: int | None, *, live_copy: bool = True
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=2087,
        genre_ids=[53],
    )
    session.add(movie)
    await session.flush()
    session.add(
        CollectionItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            formats=["blu_ray"],
            deleted_at=None if live_copy else datetime(2026, 9, 9),
        )
    )
    await session.flush()
    return movie


# ---------------------------------------------------------------------------
# §7.1 — streaming availability
# ---------------------------------------------------------------------------


async def test_streaming_reports_the_regions_offers_in_a_useful_order(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """Subscription first, then rent, then buy.

    "Included in what you already pay for" and "£13.99 to own" are not the same answer to
    "can I watch this tonight?", so they are separate kinds and the cheap one leads.
    """
    movie = await _owned_film(api_session, "A Streamable Film", 949)
    providers = WatchProviders(
        results={
            "GB": WatchProviderCountry(
                link="https://example.test/gb",
                flatrate=[_provider(337, "Disney Plus")],
                rent=[_provider(2, "Apple TV Store")],
                buy=[_provider(2, "Apple TV Store")],
            ),
            "US": WatchProviderCountry(link="https://example.test/us", flatrate=[]),
        }
    )
    _install(api_session, viewer, FakeDiscoveryClient(providers=providers))
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{movie.id}/streaming")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["region"] == "GB"
    assert body["link"] == "https://example.test/gb"
    assert [(o["providerName"], o["kind"]) for o in body["offers"]] == [
        ("Disney Plus", "flatrate"),
        ("Apple TV Store", "rent"),
        ("Apple TV Store", "buy"),
    ]


async def test_the_region_comes_from_the_profile_and_can_be_overridden(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """ "Is this on Netflix at my sister's in Ireland?" without changing a setting."""
    movie = await _owned_film(api_session, "A Film Abroad", 950)
    providers = WatchProviders(
        results={"IE": WatchProviderCountry(link="https://example.test/ie", flatrate=[])}
    )
    _install(api_session, viewer, FakeDiscoveryClient(providers=providers))
    try:
        async with _client() as client:
            default = await client.get(f"/api/v1/movies/{movie.id}/streaming")
            overridden = await client.get(f"/api/v1/movies/{movie.id}/streaming?region=IE")
    finally:
        app.dependency_overrides.clear()

    assert default.json()["region"] == "GB"
    assert default.json()["link"] is None
    assert overridden.json()["region"] == "IE"
    assert overridden.json()["link"] == "https://example.test/ie"


async def test_an_unidentified_film_says_so_rather_than_reporting_no_offers(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """ "We could not look" and "there is nothing" are different answers.

    757 of this collection's films had no TMDB id; rendering both as an empty list would
    tell someone a film is streaming nowhere when nobody ever asked.
    """
    movie = await _owned_film(api_session, "A Shelf Title Only", None)
    _install(api_session, viewer, FakeDiscoveryClient())
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{movie.id}/streaming")
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert body["unidentified"] is True
    # Not the same as an outage: nobody asked, so nothing failed.
    assert body["unavailable"] is False
    assert body["offers"] == []


async def test_a_tmdb_outage_is_an_answer_with_a_flag_not_a_502(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """Three failure modes, three different sentences — and none of them a 5xx.

    A bare empty list would be indistinguishable from "not streaming anywhere". But a
    **502 is worse**: the web client classifies any 5xx as a network failure
    (`DECISIONS.md` #43, correctly — a gateway, a proxy or a booting container all produce
    one), so the page would tell the reader to check their connection while the connection
    is fine and TMDB is the thing that is down. Seen in the browser during this batch, with
    the local API missing its TMDB token.
    """
    movie = await _owned_film(api_session, "A Film TMDB Cannot Reach", 951)
    _install(api_session, viewer, FakeDiscoveryClient(fail=True))
    try:
        async with _client() as client:
            streaming = await client.get(f"/api/v1/movies/{movie.id}/streaming")
            recommendations = await client.get(f"/api/v1/movies/{movie.id}/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert streaming.status_code == 200
    assert streaming.json()["unavailable"] is True
    assert streaming.json()["unidentified"] is False
    assert streaming.json()["offers"] == []

    assert recommendations.status_code == 200
    assert recommendations.json()["unavailable"] is True
    assert recommendations.json()["items"] == []


# ---------------------------------------------------------------------------
# §7.2 — recommendations
# ---------------------------------------------------------------------------


async def test_recommendations_are_flagged_against_what_is_on_the_shelf(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """§7.2's acceptance: "correct ownership flags"."""
    source = await _owned_film(api_session, "The Film Being Viewed", 949)
    already = await _owned_film(api_session, "One We Already Have", 111_111)

    _install(
        api_session,
        viewer,
        FakeDiscoveryClient(
            recommendations=[
                _result(111_111, "One We Already Have"),
                _result(222_222, "One We Do Not"),
            ]
        ),
    )
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{source.id}/recommendations")
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    by_id = {item["tmdbId"]: item for item in body["items"]}
    assert by_id[111_111]["ownership"] == "owned"
    assert by_id[111_111]["movieId"] == str(already.id)
    assert by_id[222_222]["ownership"] == "unowned"
    assert by_id[222_222]["movieId"] is None
    assert body["ownedCount"] == 1


async def test_a_film_whose_only_copy_is_in_the_trash_is_not_owned(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """ "Owned" answers "can I watch this tonight?", and a disc in the bin cannot.

    The row is still in `movies`, so a join that only checked the film table would call it
    owned — and the recommendation would quietly stop being a recommendation.
    """
    source = await _owned_film(api_session, "The Source Film", 949)
    await _owned_film(api_session, "Deleted Copy", 333_333, live_copy=False)

    _install(
        api_session, viewer, FakeDiscoveryClient(recommendations=[_result(333_333, "Deleted Copy")])
    )
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{source.id}/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["items"][0]["ownership"] == "unowned"
    assert response.json()["ownedCount"] == 0


async def test_an_unidentified_film_has_no_recommendations_and_does_not_error(
    api_session: AsyncSession, viewer: Profile
) -> None:
    movie = await _owned_film(api_session, "Nothing To Recommend From", None)
    _install(api_session, viewer, FakeDiscoveryClient())
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{movie.id}/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_nothing_is_padded_to_reach_ten(api_session: AsyncSession, viewer: Profile) -> None:
    """§7.2 asks for "10+ recommendations", which TMDB supplies for a well-known film and
    not for an obscure one. Padding would make the ownership flag meaningless."""
    source = await _owned_film(api_session, "An Obscure Film", 949)
    _install(api_session, viewer, FakeDiscoveryClient(recommendations=[_result(1, "The Only One")]))
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{source.id}/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert len(response.json()["items"]) == 1


# ---------------------------------------------------------------------------
# §7.2 — the new-releases feed
# ---------------------------------------------------------------------------


async def test_new_releases_are_filtered_by_the_collections_own_genres(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """And each result says which genre put it there.

    A suggestion that cannot explain itself is indistinguishable from a random one.
    """
    await _owned_film(api_session, "A Thriller On The Shelf", 949)
    upcoming = [
        _result(1, "An Upcoming Thriller", genres=[53]),
        _result(2, "An Upcoming Documentary", genres=[99]),
    ]
    fake = FakeDiscoveryClient(upcoming=upcoming)
    _install(api_session, viewer, fake)
    try:
        async with _client() as client:
            response = await client.get("/api/v1/discover/new-releases?genreLimit=3")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    titles = [item["title"] for item in body["items"]]
    assert "An Upcoming Thriller" in titles
    thriller = next(i for i in body["items"] if i["title"] == "An Upcoming Thriller")
    assert "Thriller" in thriller["matchedGenres"]
    assert body["basedOnGenres"], "the feed has to say what it filtered by"


async def test_the_upcoming_feed_asks_about_the_readers_region(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """Cinema release dates differ by country. A UK app listing US dates would be wrong in
    a way that looks right."""
    viewer.streaming_region = "IE"
    await api_session.flush()
    fake = FakeDiscoveryClient(upcoming=[])
    _install(api_session, viewer, fake)
    try:
        async with _client() as client:
            await client.get("/api/v1/discover/new-releases")
    finally:
        app.dependency_overrides.clear()

    assert fake.regions_asked == ["IE"]


async def test_a_wanted_film_gets_the_third_ownership_state(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """Batch 18's payoff for Batch 16's two-state enum.

    Batch 16 shipped "owned" and "unowned" only, because §3.5's `wanted_list` did not
    exist and a badge that could never appear is a legend entry pointing at nothing. The
    table exists now.
    """
    source = await _owned_film(api_session, "The Source", 949)
    wanted_film = await _owned_film(api_session, "On The Wanted List", 444_444, live_copy=False)
    api_session.add(
        WantedItem(id=uuid.uuid4(), movie_id=wanted_film.id, currency="GBP", is_active=True)
    )
    await api_session.flush()

    _install(
        api_session,
        viewer,
        FakeDiscoveryClient(recommendations=[_result(444_444, "On The Wanted List")]),
    )
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{source.id}/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["items"][0]["ownership"] == "wanted"


async def test_an_inactive_wanted_entry_is_not_shown_as_wanted(
    api_session: AsyncSession, viewer: Profile
) -> None:
    """ "No longer looking" is a decision, and calling it *wanted* would contradict it."""
    source = await _owned_film(api_session, "The Source Again", 949)
    film = await _owned_film(api_session, "No Longer Wanted", 555_555, live_copy=False)
    api_session.add(WantedItem(id=uuid.uuid4(), movie_id=film.id, currency="GBP", is_active=False))
    await api_session.flush()

    _install(
        api_session,
        viewer,
        FakeDiscoveryClient(recommendations=[_result(555_555, "No Longer Wanted")]),
    )
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{source.id}/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["items"][0]["ownership"] == "unowned"


async def test_owning_a_film_beats_wanting_it(api_session: AsyncSession, viewer: Profile) -> None:
    """Both can be true — a DVD-to-4K upgrade is exactly that — and "you already have
    this" is the more useful thing to say on a card suggesting what to watch."""
    source = await _owned_film(api_session, "Yet Another Source", 949)
    both = await _owned_film(api_session, "Owned And Wanted", 666_666)
    api_session.add(WantedItem(id=uuid.uuid4(), movie_id=both.id, currency="GBP", is_active=True))
    await api_session.flush()

    _install(
        api_session,
        viewer,
        FakeDiscoveryClient(recommendations=[_result(666_666, "Owned And Wanted")]),
    )
    try:
        async with _client() as client:
            response = await client.get(f"/api/v1/movies/{source.id}/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["items"][0]["ownership"] == "owned"
