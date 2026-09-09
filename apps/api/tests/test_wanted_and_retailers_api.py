"""Batch 18's wanted list and retailer management — §5.1, §5.2.

**Four earlier batches deferred work to this table**, so a few of these tests are about
paying those debts rather than about §5.1 itself: the trash accepting `wanted_list`, and a
wanted entry being creatable from a bare TMDB id (which is what §11.2's "add missing to
wanted list" and §7.2's recommendation cards both start from).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.wanted import DEFAULT_RETAILERS, Retailer, WantedItem
from src.routers.movies import get_tmdb_client
from src.services.scraping.builtins import BUILT_IN_SCRAPERS
from src.services.scraping.runner import run_scrape
from src.tmdb.models import Credits, Genre
from src.tmdb.models import Movie as TmdbMovie

pytestmark = pytest.mark.asyncio

ACTOR_HEADER = "x-test-actor"
WANTED_TMDB_ID = 940_001


class FakeTmdb:
    async def get_movie_full(self, movie_id: int, language: str = "en-US") -> TmdbMovie:
        del language
        return TmdbMovie(
            id=movie_id,
            title="A Film Nobody Owns",
            original_title="A Film Nobody Owns",
            overview="Wanted, not owned.",
            release_date="2026-01-01",
            runtime=100,
            vote_average=7.0,
            vote_count=10,
            poster_path="/wanted.jpg",
            genres=[Genre(id=18, name="Drama")],
            credits=Credits(cast=[], crew=[]),
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


async def _profile(session: AsyncSession, role: UserRole) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Batch Eighteen {role.value.title()} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=role,
    )
    session.add(profile)
    await session.flush()
    return profile


@pytest_asyncio.fixture
async def admin(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, UserRole.admin)


@pytest_asyncio.fixture
async def viewer(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, UserRole.viewer)


@pytest_asyncio.fixture
async def overrides(
    api_session: AsyncSession, admin: Profile, viewer: Profile
) -> AsyncIterator[None]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user(request: Request) -> Profile:
        return admin if request.headers.get(ACTOR_HEADER) == "admin" else viewer

    async def override_tmdb() -> AsyncIterator[FakeTmdb]:
        yield FakeTmdb()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def _client_as(actor: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={ACTOR_HEADER: actor},
    )


@pytest_asyncio.fixture
async def client(overrides: None) -> AsyncIterator[AsyncClient]:
    del overrides
    async with _client_as("admin") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def viewer_client(overrides: None) -> AsyncIterator[AsyncClient]:
    del overrides
    async with _client_as("viewer") as http_client:
        yield http_client


async def _film(session: AsyncSession, title: str, *, owned: bool = False) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title=title,
        original_title=title,
        media_type="film",
        year=2087,
    )
    session.add(movie)
    await session.flush()
    if owned:
        session.add(CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["dvd"]))
        await session.flush()
    return movie


# ---------------------------------------------------------------------------
# §5.1 — the wanted list
# ---------------------------------------------------------------------------


async def test_adding_from_a_film_page_and_listing_it_works_both_ways(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§5.1's acceptance, word for word."""
    movie = await _film(api_session, "A Film To Buy")

    added = await client.post(
        "/api/v1/wanted",
        json={
            "movieId": str(movie.id),
            "preferredFormat": "4k_uhd",
            "maxPrice": "19.99",
            "currency": "GBP",
        },
    )
    assert added.status_code == 201, added.text
    assert added.json()["movieTitle"] == "A Film To Buy"
    assert added.json()["maxPrice"] == "19.99"

    listed = await client.get("/api/v1/wanted")
    mine = next(i for i in listed.json()["items"] if i["id"] == added.json()["id"])
    assert mine["preferredFormat"] == "4k_uhd"
    assert listed.json()["activeCount"] >= 1


async def test_a_film_this_collection_has_never_seen_can_be_wanted(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """**The whole point of wanting a film is that you do not own it.**

    Requiring a `movies` row first would exclude every realistic case — and would make
    §11.2's "add missing to wanted list" and §7.2's recommendation cards impossible, since
    both start from a bare TMDB id and nothing else.
    """
    added = await client.post(
        "/api/v1/wanted", json={"tmdbId": WANTED_TMDB_ID, "preferredFormat": "blu_ray"}
    )
    assert added.status_code == 201, added.text
    assert added.json()["movieTitle"] == "A Film Nobody Owns"

    created = (
        await api_session.execute(select(Movie).where(Movie.tmdb_id == WANTED_TMDB_ID))
    ).scalar_one()
    assert created.poster_path == "/wanted.jpg"
    # And it is *not* in the collection — a wanted film has no disc.
    copies = (
        (
            await api_session.execute(
                select(CollectionItem).where(CollectionItem.movie_id == created.id)
            )
        )
        .scalars()
        .all()
    )
    assert copies == []


async def test_a_body_naming_neither_film_is_a_422_not_a_500(
    client: AsyncClient,
) -> None:
    """`STATUS.md` gotcha 20: a `field_validator` does not run for a field the request
    omits, so "exactly one of" has to be checked where absence is visible."""
    assert (await client.post("/api/v1/wanted", json={})).status_code == 422


async def test_a_body_naming_both_is_also_refused(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    movie = await _film(api_session, "Ambiguous")
    response = await client.post(
        "/api/v1/wanted", json={"movieId": str(movie.id), "tmdbId": WANTED_TMDB_ID}
    )
    assert response.status_code == 422


async def test_the_same_film_cannot_be_wanted_twice(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Batch 20's alerts would fire twice for it."""
    movie = await _film(api_session, "Wanted Once")
    first = await client.post("/api/v1/wanted", json={"movieId": str(movie.id)})
    assert first.status_code == 201
    second = await client.post("/api/v1/wanted", json={"movieId": str(movie.id)})
    assert second.status_code == 409


async def test_wanting_a_film_you_already_own_is_allowed_and_flagged(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Upgrading a DVD to 4K is exactly this, so it is surfaced rather than refused."""
    movie = await _film(api_session, "Owned On DVD, Wanted On 4K", owned=True)
    added = await client.post(
        "/api/v1/wanted", json={"movieId": str(movie.id), "preferredFormat": "4k_uhd"}
    )
    assert added.status_code == 201
    assert added.json()["ownedAlready"] is True


async def test_a_price_survives_as_a_decimal_string(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Money never round-trips through a float — this value is the threshold Batch 20's
    alerts compare against, and a float compares wrongly at exactly the boundary."""
    movie = await _film(api_session, "A Priced Want")
    added = await client.post(
        "/api/v1/wanted", json={"movieId": str(movie.id), "maxPrice": "12.99"}
    )
    assert added.json()["maxPrice"] == "12.99"

    row = await api_session.get(WantedItem, uuid.UUID(added.json()["id"]))
    assert row is not None and str(row.max_price) == "12.99"


async def test_a_nonsense_or_negative_price_is_refused(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    movie = await _film(api_session, "A Badly Priced Want")
    for bad in ("not a number", "-5", "0", "9999999"):
        response = await client.post(
            "/api/v1/wanted", json={"movieId": str(movie.id), "maxPrice": bad}
        )
        assert response.status_code == 422, bad


async def test_marking_inactive_is_not_the_same_as_removing(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """ "I stopped looking" is a decision worth keeping; "I removed it by mistake" is an
    accident worth undoing. Only the second belongs in a bin."""
    movie = await _film(api_session, "No Longer Looking")
    added = await client.post("/api/v1/wanted", json={"movieId": str(movie.id)})
    item_id = added.json()["id"]

    updated = await client.put(
        f"/api/v1/wanted/{item_id}", json={"isActive": False, "currency": "GBP"}
    )
    assert updated.status_code == 200
    assert updated.json()["isActive"] is False

    # Still listed by default, and still not deleted.
    listed = await client.get("/api/v1/wanted")
    assert any(i["id"] == item_id for i in listed.json()["items"])
    active_only = await client.get("/api/v1/wanted?activeOnly=true")
    assert not any(i["id"] == item_id for i in active_only.json()["items"])

    row = await api_session.get(WantedItem, uuid.UUID(item_id))
    assert row is not None and row.deleted_at is None


async def test_a_removed_entry_appears_in_the_trash_tab_batch_15_could_not_fill(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Batch 15 made the trash **refuse** the name `wanted_list` rather than answer an
    empty page for a table that did not exist. This is the payoff for having done that
    instead of quietly returning nothing."""
    movie = await _film(api_session, "A Want Thrown Away")
    added = await client.post("/api/v1/wanted", json={"movieId": str(movie.id)})
    item_id = added.json()["id"]

    removed = await client.request("DELETE", f"/api/v1/wanted/{item_id}")
    assert removed.status_code == 204

    trash = await client.get("/api/v1/trash/all?table=wanted_list")
    assert trash.status_code == 200, trash.text
    assert any(row["id"] == item_id for row in trash.json()["items"])
    assert any(c["table"] == "wanted_list" for c in trash.json()["counts"])

    restored = await client.post(f"/api/v1/trash/wanted_list/{item_id}/restore-row")
    assert restored.status_code == 204
    assert any(i["id"] == item_id for i in (await client.get("/api/v1/wanted")).json()["items"])


async def test_a_viewer_can_read_the_wanted_list_but_not_change_it(
    viewer_client: AsyncClient, api_session: AsyncSession
) -> None:
    movie = await _film(api_session, "Mark Can Look")
    assert (await viewer_client.get("/api/v1/wanted")).status_code == 200
    refused = await viewer_client.post("/api/v1/wanted", json={"movieId": str(movie.id)})
    assert refused.status_code == 403


# ---------------------------------------------------------------------------
# §5.2 — retailers
# ---------------------------------------------------------------------------


def _retailer_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": f"A Shop {uuid.uuid4().hex[:6]}",
        "baseUrl": "https://shop.example",
        "dealsUrl": "https://shop.example/sale",
        "scraperType": "generic_css",
        "scraperConfig": {"price": ".price"},
        "scrapeFrequency": "weekly",
        "enabled": True,
        "currency": "GBP",
        "region": "GB",
    }
    body.update(overrides)
    return body


async def test_an_admin_adds_a_retailer_and_it_is_saved_and_enabled(
    client: AsyncClient,
) -> None:
    """§5.2's acceptance, word for word."""
    response = await client.post("/api/v1/retailers", json=_retailer_body(name="Test Shop"))
    assert response.status_code == 201, response.text
    assert response.json()["enabled"] is True
    assert response.json()["isConfigured"] is True

    listed = await client.get("/api/v1/retailers")
    assert any(r["name"] == "Test Shop" for r in listed.json()["items"])
    assert listed.json()["enabledCount"] >= 1


async def test_a_retailer_url_must_be_http_or_https(client: AsyncClient) -> None:
    """`base_url` is fetched by a background job, so a `file:` value would be a request the
    server makes on someone else's behalf. Refused at the API *and* by a CHECK."""
    for hostile in ("file:///etc/passwd", "gopher://x", "javascript:alert(1)", "//evil.test"):
        response = await client.post("/api/v1/retailers", json=_retailer_body(baseUrl=hostile))
        assert response.status_code == 422, hostile


async def test_two_retailers_cannot_share_a_name(client: AsyncClient) -> None:
    await client.post("/api/v1/retailers", json=_retailer_body(name="Duplicated Shop"))
    again = await client.post("/api/v1/retailers", json=_retailer_body(name="Duplicated Shop"))
    assert again.status_code == 409


async def test_seeding_is_idempotent_and_leaves_selectors_empty(
    client: AsyncClient,
) -> None:
    """§5.2's "seeded default retailers".

    **Every seeded row has an empty `scraper_config`.** The CSS a real page needs is
    Batch 19's, and inventing selectors here would be worse than none: that batch's own
    risk note says a wrong selector *"does not error — it selects the wrong node and
    persists a plausible wrong number"*. An empty config is visibly unconfigured, and the
    list endpoint reports `configuredCount` so the settings page can say so.

    The emptiness is asserted against `DEFAULT_RETAILERS` rather than against whatever the
    rows currently hold. Live Neon's six defaults have since had Batch 19's built-in
    selectors applied to them — a separate, deliberate action — so a test reading the rows
    would be asserting the state of one database rather than the behaviour of the seed.
    """
    assert all(
        "scraper_config" not in default and "selectors" not in default
        for default in DEFAULT_RETAILERS
    ), "the seed data itself must carry no selectors"

    first = await client.post("/api/v1/retailers/seed")
    assert first.status_code == 200, first.text

    second = await client.post("/api/v1/retailers/seed")
    # Idempotent: whatever the first call did, the second adds nothing.
    assert second.json()["created"] == 0

    # And every default is present afterwards, however it got there.
    listed = (await client.get("/api/v1/retailers")).json()
    by_name = {r["name"] for r in listed["items"]}
    for default in DEFAULT_RETAILERS:
        assert default["name"] in by_name, default["name"]


async def test_a_removed_retailer_goes_to_the_trash(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    created = await client.post("/api/v1/retailers", json=_retailer_body(name="Doomed Shop"))
    retailer_id = created.json()["id"]

    assert (await client.request("DELETE", f"/api/v1/retailers/{retailer_id}")).status_code == 204
    assert not any(
        r["id"] == retailer_id for r in (await client.get("/api/v1/retailers")).json()["items"]
    )

    trash = await client.get("/api/v1/trash/all?table=retailers")
    assert any(row["id"] == retailer_id for row in trash.json()["items"])

    row = await api_session.get(Retailer, uuid.UUID(retailer_id))
    assert row is not None and row.deleted_at is not None


async def test_a_viewer_can_see_retailers_but_not_add_one(
    viewer_client: AsyncClient,
) -> None:
    assert (await viewer_client.get("/api/v1/retailers")).status_code == 200
    assert (await viewer_client.post("/api/v1/retailers", json=_retailer_body())).status_code == 403


async def test_a_scraper_config_that_is_not_an_object_is_refused(
    client: AsyncClient,
) -> None:
    """A wrong shape here would fail inside Batch 19's unattended job rather than when an
    admin saved it."""
    response = await client.post(
        "/api/v1/retailers", json=_retailer_body(scraperConfig=["not", "an", "object"])
    )
    assert response.status_code == 422


async def test_a_non_finite_price_is_refused_rather_than_raising(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """`Decimal("NaN")` **parses**, and then every comparison against it raises.

    So the `<= 0` guard was the thing that would have 500'd, not the parse — the `try`
    around `Decimal(value)` never saw it. Found by Batch 27's security review; admin-only
    input, so never reachable by a visitor, but a 422 is the right answer to a price of
    "NaN".
    """
    movie = await _film(api_session, "A Film With An Unreal Price")
    for unreal in ("NaN", "nan", "Infinity", "-Infinity", "sNaN"):
        response = await client.post(
            "/api/v1/wanted", json={"movieId": str(movie.id), "maxPrice": unreal}
        )
        assert response.status_code == 422, unreal


async def test_the_test_endpoint_fills_placeholders_and_prices_the_film_asked_for(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§5.4's tool must build its request the way a real run does, and pick the same card.

    Both halves of the *Sheriff of Fractured Jaw* defect are covered here. The browser used
    to fill `{query}` alone and send the literal text `{format}` to the shop; and the
    endpoint used to run `extract` with no expected title, so it priced whichever card came
    first rather than the one that is actually the film (`DECISIONS.md` #99).
    """
    requested: list[str] = []

    async def fake_fetch(url: str, **_kwargs: object) -> SimpleNamespace:
        requested.append(url)
        html = """
        <div data-testid="product-item">
          <a href="/p/blu-ray/the-sheriff-of-fractured-jaw/1/"
             data-testid="product-title">The Sheriff of Fractured Jaw (Dual Format Edition)</a>
          <div data-testid="product-price"><span class="product-variant-price">£18.99</span></div>
        </div>
        <div data-testid="product-item">
          <a href="/p/4k/jaws-4k-ultra-hd/2/"
             data-testid="product-title">Jaws - 4K Ultra HD (Includes 2D Blu-ray)</a>
          <div data-testid="product-price"><span class="product-variant-price">£19.99</span></div>
        </div>
        """
        return SimpleNamespace(html=html, final_url=url, status_code=200)

    monkeypatch.setattr("src.routers.scraping.fetch_page", fake_fetch)

    response = await client.post(
        "/api/v1/scrapers/test",
        json={
            "url": "https://www.zavvi.com/search?q={query}%20{format}",
            "scraperConfig": BUILT_IN_SCRAPERS["Zavvi"]["config"],
            "expectedTitle": "Jaws",
            "preferredFormat": "4k_uhd",
            "expectedHost": "https://www.zavvi.com",
        },
    )
    body = response.json()

    assert response.status_code == 200, body
    # No placeholder ever reaches the shop.
    assert requested == ["https://www.zavvi.com/search?q=Jaws%204K"]
    # And the card priced is the film, not whichever one happened to be first.
    assert body["title"] == "Jaws - 4K Ultra HD (Includes 2D Blu-ray)"
    assert body["price"] == "19.99"
    assert body["ok"] is True, body["reasons"]


async def test_a_run_of_only_digital_wants_does_not_switch_every_shop_off(
    api_session: AsyncSession, admin: Profile
) -> None:
    """A digital want is skipped, and a shop that was never asked has not failed.

    Auto-disable counts three consecutive failures. Attributing a skip to the retailer
    would have switched off every enabled shop in the app after three runs of a wanted list
    the shops simply cannot serve (`DECISIONS.md` #101).
    """
    movie = await _film(api_session, "A Digital Only Film")
    retailer = Retailer(
        id=uuid.uuid4(),
        name=f"Skip Test {uuid.uuid4().hex[:8]}",
        base_url="https://shop.test",
        scraper_type="generic_css",
        search_url_template="https://shop.test/s?q={query}",
        scraper_config={"title": ".t", "price": ".p", "url": ".t"},
        enabled=True,
        currency="GBP",
    )
    api_session.add(retailer)
    api_session.add(
        WantedItem(
            id=uuid.uuid4(),
            movie_id=movie.id,
            preferred_format="download",
            is_active=True,
            added_by=admin.id,
        )
    )
    await api_session.flush()

    def explode(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("a digital want must not reach a shop")

    async with httpx.AsyncClient(transport=httpx.MockTransport(explode)) as client:
        result = await run_scrape(api_session, client=client, dry_run=False, polite_pause=0.0)

    assert result.skipped >= 1
    assert result.failed == 0
    assert result.disabled == []
    assert retailer.enabled is True
    assert retailer.consecutive_failures == 0


async def test_three_films_a_shop_does_not_carry_do_not_switch_it_off(
    api_session: AsyncSession, admin: Profile
) -> None:
    """The 2026-09-09 regression, end to end.

    A wanted list of *Misery*, *Nope* and *Project Hail Mary* took 101 Films, Powerhouse
    and Second Sight offline: each returned a real page of real listings, the title guard
    correctly refused all of them, and three refusals in one run read as three failures.
    A shop that answered honestly must survive being asked for stock it never had.
    """
    for title in ("Misery", "Nope", "Project Hail Mary"):
        movie = await _film(api_session, title)
        api_session.add(
            WantedItem(
                id=uuid.uuid4(),
                movie_id=movie.id,
                preferred_format="4k_uhd",
                is_active=True,
                added_by=admin.id,
            )
        )
    retailer = Retailer(
        id=uuid.uuid4(),
        name=f"Boutique {uuid.uuid4().hex[:8]}",
        base_url="https://shop.test",
        scraper_type="generic_css",
        search_url_template="https://shop.test/s?q={query}",
        scraper_config={
            "item": ".card",
            "title": ".card a",
            "price": ".price",
            "url": ".card a",
        },
        enabled=True,
        currency="GBP",
    )
    api_session.add(retailer)
    await api_session.flush()

    #: A real catalogue page: parsed perfectly, and about none of the three films.
    catalogue = """
    <div class="card"><a href="https://shop.test/p/1">Cold Prey Trilogy Blu-ray Boxset</a>
      <div class="price">£45.00</div></div>
    <div class="card"><a href="https://shop.test/p/2">BRUISER - 4K UHD LE</a>
      <div class="price">£30.00</div></div>
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=catalogue))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        result = await run_scrape(api_session, client=client, dry_run=False, polite_pause=0.0)

    assert result.not_stocked == 3
    assert result.failed == 0
    assert result.disabled == []
    assert retailer.enabled is True
    assert retailer.consecutive_failures == 0


async def test_a_wanted_edition_round_trips_through_the_api(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Free text, stored and returned. A want that names no edition stays null rather than
    acquiring an empty string, because "" and "no preference" must not both mean the same
    thing to `edition_matches`."""
    movie = await _film(api_session, "Deep Red")

    created = await client.post(
        "/api/v1/wanted",
        json={
            "movieId": str(movie.id),
            "preferredFormat": "4k_uhd",
            "preferredEdition": "Arte Originale Slipcover",
        },
    )
    assert created.status_code == 201, created.json()
    assert created.json()["preferredEdition"] == "Arte Originale Slipcover"

    listed = await client.get("/api/v1/wanted")
    row = next(i for i in listed.json()["items"] if i["id"] == created.json()["id"])
    assert row["preferredEdition"] == "Arte Originale Slipcover"

    cleared = await client.put(
        f"/api/v1/wanted/{created.json()['id']}",
        json={"preferredFormat": "4k_uhd", "isActive": True},
    )
    assert cleared.status_code == 200, cleared.json()
    assert cleared.json()["preferredEdition"] is None
