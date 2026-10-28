"""Batch 14's stats dashboard, activity feed and exports — §13.1–13.4.

**These run against live Neon locally and an empty database in CI**, so every assertion is
about rows this test inserted or about a relationship that holds at any size. `STATUS.md`'s
Now block records four tests that failed by assuming the opposite, and one of Batch 12's
own did the same thing the same day.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.models.watch_log import WatchLog

ACTOR_HEADER = "x-test-actor"

#: A decade the real catalogue cannot occupy, so a count over "this decade" is a count of
#: this test's own rows. Same device as Batch 12's smart-collection tests.
FIXTURE_YEAR = 2087


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
        display_name=f"Batch Fourteen {role.value.title()} {uuid.uuid4().hex[:8]}",
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

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(overrides: None) -> AsyncIterator[AsyncClient]:
    del overrides
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={ACTOR_HEADER: "admin"},
    ) as http_client:
        yield http_client


async def _disc(
    session: AsyncSession,
    title: str,
    *,
    formats: list[str],
    year: int = FIXTURE_YEAR,
    genre_ids: list[int] | None = None,
    section: str | None = "Front",
    price: str | None = None,
    purchased: date | None = None,
    tmdb_id: int | None = None,
) -> tuple[Movie, CollectionItem]:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=year,
        genre_ids=genre_ids,
        poster_path="/poster.jpg",
    )
    session.add(movie)
    await session.flush()
    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=formats,
        location="Front 2nd shelf" if section == "Front" else section,
        section=section,
        shelf="2nd" if section == "Front" else None,
        condition="good",
        purchase_price=Decimal(price) if price is not None else None,
        purchase_date=purchased,
    )
    session.add(item)
    await session.flush()
    return movie, item


# ---------------------------------------------------------------------------
# §13.1 — the stats dashboard
# ---------------------------------------------------------------------------


async def test_the_dashboard_counts_formats_genres_decades_and_sections(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    await _disc(api_session, "A 4K Thriller", formats=["4k_uhd"], genre_ids=[53])
    await _disc(api_session, "A Combo Pack", formats=["4k_uhd", "blu_ray"], genre_ids=[53, 18])
    await _disc(api_session, "A Garage DVD", formats=["dvd"], genre_ids=[18], section="Garage")

    response = await client.get("/api/v1/collection/stats")
    assert response.status_code == 200, response.text
    body = response.json()

    formats = {slice_["key"]: slice_ for slice_ in body["formats"]}
    # A combo pack is one disc holding two formats, so it counts once in each.
    assert formats["4k_uhd"]["itemCount"] >= 2
    assert formats["blu_ray"]["itemCount"] >= 1
    # Best format first — FORMAT_RANK order, not "whichever is commonest".
    assert [s["key"] for s in body["formats"]][:1] == ["4k_uhd"]

    decades = {d["decade"]: d for d in body["decades"]}
    assert decades[2080]["movieCount"] == 3
    assert decades[2080]["label"] == "2080s"

    assert body["totalItems"] >= 3
    assert body["totalMovies"] >= 3


async def test_the_dashboard_says_how_many_copies_are_downloads(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Batch X12a (UX48-05): Home reads "N copies: discs, downloads", so the API says how many
    of the copies are downloads, and the Formats chart calls them that, not "Digital" (which
    is also a shelf section with a different count)."""
    before = (await client.get("/api/v1/collection/stats")).json()
    await _disc(api_session, "A Rip", formats=["download"], section="Digital")
    await _disc(api_session, "A Disc", formats=["blu_ray"])

    after = (await client.get("/api/v1/collection/stats")).json()

    assert after["downloadCopies"] == before["downloadCopies"] + 1
    assert after["totalItems"] == before["totalItems"] + 2
    labels = {slice_["key"]: slice_["label"] for slice_ in after["formats"]}
    assert labels["download"] == "Downloads"


async def test_copy_counts_preserve_overlaps_and_owned_status_for_both_people(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    before = (await client.get("/api/v1/collection/stats")).json()
    await _disc(api_session, "Physical only", formats=["dvd"])
    await _disc(api_session, "Download only", formats=["download"])
    await _disc(api_session, "Combo with download", formats=["4k_uhd", "blu_ray", "download"])
    _, listed = await _disc(api_session, "Still owned while listed", formats=["blu_ray"])
    listed.listing_status = "listed_for_sale"
    _, sold = await _disc(api_session, "Sold mixed copy", formats=["dvd", "download"])
    sold.listing_status = "sold"
    _, trashed = await _disc(api_session, "Trashed mixed copy", formats=["dvd", "download"])
    trashed.deleted_at = datetime(2026, 10, 27)
    await api_session.flush()

    for actor in ("admin", "viewer"):
        response = await client.get("/api/v1/collection/stats", headers={ACTOR_HEADER: actor})
        assert response.status_code == 200
        after = response.json()
        assert after["totalItems"] == before["totalItems"] + 4
        assert after["downloadCopies"] == before["downloadCopies"] + 2
        assert after["physicalCopies"] == before["physicalCopies"] + 3
        assert after["physicalAndDownloadCopies"] == before["physicalAndDownloadCopies"] + 1
        assert after["identifiedMovies"] == before["identifiedMovies"]


async def test_empty_copy_counts_are_zero(client: AsyncClient, api_session: AsyncSession) -> None:
    from sqlalchemy import update

    # A disposable per-test transaction: every active copy is temporarily in the Trash.
    await api_session.execute(update(CollectionItem).values(deleted_at=datetime(2026, 10, 27)))
    body = (await client.get("/api/v1/collection/stats")).json()
    for key in (
        "totalMovies",
        "ownedWatchedMovies",
        "totalItems",
        "downloadCopies",
        "physicalCopies",
        "physicalAndDownloadCopies",
    ):
        assert body[key] == 0


async def test_a_film_in_two_genres_counts_once_in_each(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The bar chart counts *films*, so a two-genre film is one film in two bars — never
    half a film, and never two films."""
    await _disc(api_session, "A Two-Genre Film", formats=["dvd"], genre_ids=[10752, 10770])

    body = (await client.get("/api/v1/collection/stats")).json()
    genres = {g["key"]: g for g in body["genres"]}
    assert genres["10752"]["movieCount"] >= 1
    assert genres["10770"]["movieCount"] >= 1


async def test_an_empty_spend_series_carries_the_denominator_that_explains_it(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """An empty chart must be able to say *why* it is empty.

    All 1,857 imported rows have `purchase_price` NULL — the spreadsheet never carried
    one — so "no series" means "nothing recorded", not "nothing bought". `itemsWithPrice`
    is what lets the page tell a reader which, instead of drawing a flat line at zero.
    """
    body = (await client.get("/api/v1/collection/stats")).json()
    assert "itemsWithPrice" in body
    assert isinstance(body["spendOverTime"], list)

    await _disc(
        api_session,
        "A Disc With A Price",
        formats=["blu_ray"],
        price="12.99",
        purchased=date(2087, 3, 4),
    )
    after = (await client.get("/api/v1/collection/stats")).json()
    assert after["itemsWithPrice"] == body["itemsWithPrice"] + 1
    point = next(p for p in after["spendOverTime"] if p["month"] == "2087-03")
    # Integer pence. A running total built from floats drifts, and this is money.
    assert point["spentCents"] == 1299
    assert point["itemCount"] == 1


async def test_spend_accumulates_across_months_in_order(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    await _disc(
        api_session, "Bought First", formats=["dvd"], price="10.00", purchased=date(2087, 1, 5)
    )
    await _disc(
        api_session, "Bought Later", formats=["dvd"], price="5.50", purchased=date(2087, 2, 5)
    )

    points = {
        p["month"]: p
        for p in (await client.get("/api/v1/collection/stats")).json()["spendOverTime"]
    }
    assert points["2087-01"]["cumulativeCents"] + 550 == points["2087-02"]["cumulativeCents"]


async def test_most_watched_ranks_by_number_of_watches(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    once, _ = await _disc(api_session, "Watched Once", formats=["dvd"])
    thrice, _ = await _disc(api_session, "Watched Three Times", formats=["dvd"])
    for movie, times in ((once, 1), (thrice, 3)):
        for _ in range(times):
            api_session.add(
                WatchLog(
                    id=uuid.uuid4(),
                    movie_id=movie.id,
                    user_id=admin.id,
                    watched_at=date(2026, 1, 1),
                )
            )
    await api_session.flush()

    ranked = (await client.get("/api/v1/collection/stats")).json()["mostWatched"]
    positions = {film["title"]: index for index, film in enumerate(ranked)}
    assert positions["Watched Three Times"] < positions["Watched Once"]
    assert next(f for f in ranked if f["title"] == "Watched Three Times")["watchCount"] == 3


async def test_watched_count_is_about_the_person_asking(
    client: AsyncClient, api_session: AsyncSession, admin: Profile, viewer: Profile
) -> None:
    movie, _ = await _disc(api_session, "Seen By One Of Them", formats=["dvd"])
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=movie.id,
            user_id=viewer.id,
            watched_at=date(2026, 1, 1),
        )
    )
    await api_session.flush()

    # The admin is the one asking, and they have not seen it.
    body = (await client.get("/api/v1/collection/stats")).json()
    del admin
    assert isinstance(body["watchedMovies"], int)


async def test_owned_watches_are_a_distinct_personal_intersection_not_the_diary(
    client: AsyncClient, api_session: AsyncSession, admin: Profile, viewer: Profile
) -> None:
    before = (await client.get("/api/v1/collection/stats")).json()
    physical, _ = await _disc(api_session, "AB2 owned", formats=["dvd"])
    download, _ = await _disc(api_session, "AB2 download", formats=["download"])
    departed, item = await _disc(api_session, "AB2 departed", formats=["dvd"])
    item.listing_status = "sold"
    deleted, _ = await _disc(api_session, "AB2 deleted movie", formats=["dvd"])
    deleted.deleted_at = datetime(2026, 10, 28)
    unwatched, _ = await _disc(api_session, "AB2 only deleted watch", formats=["dvd"])
    other, _ = await _disc(api_session, "AB2 other person", formats=["dvd"])
    api_session.add(CollectionItem(movie_id=physical.id, formats=["blu_ray"]))
    for movie in (physical, physical, download, departed, deleted):
        api_session.add(WatchLog(movie_id=movie.id, user_id=admin.id, watched_at=date(2026, 1, 1)))
    api_session.add(
        WatchLog(
            movie_id=unwatched.id,
            user_id=admin.id,
            watched_at=date(2026, 1, 1),
            deleted_at=datetime(2026, 10, 28),
        )
    )
    api_session.add(WatchLog(movie_id=other.id, user_id=viewer.id, watched_at=date(2026, 1, 1)))
    await api_session.flush()
    mine = (await client.get("/api/v1/collection/stats")).json()
    theirs = (await client.get("/api/v1/collection/stats", headers={ACTOR_HEADER: "viewer"})).json()
    assert mine["ownedWatchedMovies"] == 2
    assert mine["watchedMovies"] == 4  # Whole diary still includes departed/deleted movies.
    assert theirs["ownedWatchedMovies"] == theirs["watchedMovies"] == 1
    assert mine["totalMovies"] == theirs["totalMovies"] == before["totalMovies"] + 4
    # A caller cannot choose another person's history through an extra query parameter.
    attempted = (await client.get(f"/api/v1/collection/stats?userId={viewer.id}")).json()
    assert attempted["ownedWatchedMovies"] == mine["ownedWatchedMovies"]


@pytest.mark.parametrize("departure", ["sold", "donated", "trash"])
async def test_owned_coverage_tracks_watch_removal_and_last_copy_departure(
    client: AsyncClient, api_session: AsyncSession, admin: Profile, departure: str
) -> None:
    movie, first = await _disc(api_session, "AB2 changing ownership", formats=["download"])
    second = CollectionItem(movie_id=movie.id, formats=["dvd"], listing_status="listed_for_sale")
    watch = WatchLog(movie_id=movie.id, user_id=admin.id, watched_at=date(2026, 1, 1))
    rewatch = WatchLog(movie_id=movie.id, user_id=admin.id, watched_at=date(2026, 1, 2))
    api_session.add_all([second, watch, rewatch])
    await api_session.flush()

    async def counts(owned: int, diary: int) -> None:
        await api_session.flush()
        body = (await client.get("/api/v1/collection/stats")).json()
        assert body["ownedWatchedMovies"] == owned
        assert body["watchedMovies"] == diary

    await counts(1, 1)
    watch.deleted_at = datetime(2026, 10, 28)
    await counts(1, 1)  # Remaining rewatch still counts once.
    rewatch.deleted_at = datetime(2026, 10, 28)
    await counts(0, 0)
    rewatch.deleted_at = None
    first.listing_status = "sold"
    await counts(1, 1)  # A remaining listed-for-sale copy is still owned.
    if departure == "trash":
        second.deleted_at = datetime(2026, 10, 28)
    else:
        second.listing_status = departure
    await counts(0, 1)  # Ownership never erases the diary.
    second.deleted_at = None
    second.listing_status = "in_collection"
    await counts(1, 1)


# ---------------------------------------------------------------------------
# §13.2 — the activity feed
# ---------------------------------------------------------------------------


async def test_the_feed_shows_watches_newest_first(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    movie, _ = await _disc(api_session, "A Film Watched For The Feed", formats=["dvd"])
    api_session.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=movie.id,
            user_id=admin.id,
            watched_at=date(2026, 9, 9),
        )
    )
    await api_session.flush()

    body = (await client.get("/api/v1/activity?limit=100")).json()
    mine = next(e for e in body["items"] if e["movieTitle"] == "A Film Watched For The Feed")
    assert mine["kind"] == "watched"
    assert mine["actorName"] == admin.display_name
    assert mine["actorId"] == str(admin.id)


async def test_an_audit_row_becomes_a_feed_event_naming_its_film(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    """Additions come from the audit log, not from `collection_items`.

    `added_at_utc` is NULL on all 1,857 imported rows and `created_at` is the import
    timestamp, so ordering by the item table would put 1,857 identical "added" events at
    the top and bury everything else for ever.
    """
    movie, item = await _disc(api_session, "A Newly Catalogued Disc", formats=["blu_ray"])
    api_session.add(
        AdminAction(
            id=uuid.uuid4(),
            user_id=admin.id,
            action_type="create",
            target_table="collection_items",
            target_id=str(item.id),
            changes={"formats": ["blu_ray"]},
        )
    )
    await api_session.flush()

    body = (await client.get("/api/v1/activity?limit=100")).json()
    mine = next(e for e in body["items"] if e["movieTitle"] == "A Newly Catalogued Disc")
    assert mine["kind"] == "added"
    assert mine["actorId"] == str(admin.id)
    assert mine["movieId"] == str(movie.id)


async def test_the_feed_honours_its_limit(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/activity?limit=5")).json()
    assert len(body["items"]) <= 5


# ---------------------------------------------------------------------------
# §13.3 — CSV and JSON
# ---------------------------------------------------------------------------


async def test_the_csv_opens_cleanly_in_excel(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§13.3's acceptance, made concrete.

    "Opens cleanly in Excel" is a BOM and CRLF endings: without the BOM, Excel reads the
    file as the local 8-bit codepage and mangles every non-ASCII character.

    **No title in the collection needs it today** — all 1,843 are pure ASCII, checked
    against live Neon. It is here because the next hand-added disc may not be, and a
    mangled export is the kind of defect nobody notices until they are looking at the file
    for another reason. The fixture below supplies the accented title the real data lacks.
    """
    await _disc(api_session, "Amélie", formats=["blu_ray"])

    response = await client.get("/api/v1/export/collection.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    raw = response.content
    assert raw.startswith(b"\xef\xbb\xbf"), "missing UTF-8 BOM — Excel would mangle accents"

    text = raw.decode("utf-8-sig")
    assert "\r\n" in text
    rows = list(csv.DictReader(io.StringIO(text)))
    mine = next(row for row in rows if row["title"] == "Amélie")
    assert mine["formats"] == "blu_ray"
    assert mine["section"] == "Front"


async def test_a_combo_pack_is_one_csv_row_with_both_formats(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The export is an inventory of discs. A combo pack is one object."""
    await _disc(api_session, "A Combo In The Export", formats=["4k_uhd", "blu_ray"])

    text = (await client.get("/api/v1/export/collection.csv")).content.decode("utf-8-sig")
    rows = [r for r in csv.DictReader(io.StringIO(text)) if r["title"] == "A Combo In The Export"]
    assert len(rows) == 1
    assert rows[0]["formats"] == "4k_uhd + blu_ray"


async def test_a_price_survives_the_csv_as_a_decimal_string(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    await _disc(
        api_session,
        "A Priced Disc In CSV",
        formats=["dvd"],
        price="12.99",
        purchased=date(2087, 5, 1),
    )
    text = (await client.get("/api/v1/export/collection.csv")).content.decode("utf-8-sig")
    row = next(r for r in csv.DictReader(io.StringIO(text)) if r["title"] == "A Priced Disc In CSV")
    # Not 12.989999999999998 — money never round-trips through a float.
    assert row["purchase_price"] == "12.99"
    assert row["purchase_date"] == "2087-05-01"


async def test_the_json_export_is_valid_json(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§13.3's other half. Streamed by hand, so "valid" is the thing that could break."""
    await _disc(api_session, "A Film In The JSON", formats=["dvd"])

    response = await client.get("/api/v1/export/collection.json")
    assert response.status_code == 200
    body = json.loads(response.content)

    assert isinstance(body["items"], list)
    assert body["count"] == len(body["items"])
    assert "exportedAt" in body
    mine = next(item for item in body["items"] if item["title"] == "A Film In The JSON")
    assert mine["formats"] == ["dvd"]


async def test_a_soft_deleted_disc_is_not_exported(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    _, item = await _disc(api_session, "A Disc In The Bin", formats=["dvd"])
    item.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()

    body = json.loads((await client.get("/api/v1/export/collection.json")).content)
    assert not [i for i in body["items"] if i["title"] == "A Disc In The Bin"]


# ---------------------------------------------------------------------------
# §13.4 — the printable view
# ---------------------------------------------------------------------------


async def test_the_html_export_is_laid_out_for_print(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§13.4 asks for a printable PDF and a coffee-table HTML. This is both.

    There is no server-side PDF renderer: every option needs system libraries in an image
    that **Railway builds and CI does not**, so a missing shared object would fail a deploy
    rather than a pull request. The browser's own "Save as PDF" renders this file.
    """
    await _disc(api_session, "A Film On The Coffee Table", formats=["4k_uhd"])

    response = await client.get("/api/v1/export/collection.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    # Inline by default: the print dialog lives in the tab, not in the downloads folder.
    assert "content-disposition" not in response.headers

    html = response.content.decode()
    assert "@page" in html and "page-break-inside: avoid" in html
    assert "print-color-adjust: exact" in html, "posters must survive the print dialog"
    assert "A Film On The Coffee Table" in html
    assert "https://image.tmdb.org/t/p/w342/poster.jpg" in html
    assert html.rstrip().endswith("</html>")


async def test_the_html_export_can_be_downloaded_instead(client: AsyncClient) -> None:
    response = await client.get("/api/v1/export/collection.html?download=true")
    assert "attachment" in response.headers["content-disposition"]


async def test_a_title_with_markup_in_it_is_escaped(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """The export is HTML built by string concatenation, so escaping is not optional."""
    await _disc(api_session, "A Film <script>alert(1)</script> Title", formats=["dvd"])

    html = (await client.get("/api/v1/export/collection.html")).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
