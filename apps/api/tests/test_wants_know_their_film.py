"""AG5 (MK53-03, CT52-04): a want's shop prices are its film's, and any want can ask which film.

The two live cases are the tests' own: 101 Films' "Bad Lieutenant (1992)" priced 27 times as
the 2009 film's want and pushed once, and the shops' *Dead Man's Shoes* (the 2004 film's disc,
naming no year) priced 53 times as the 1940 film's want, whose question confirmed its film.
"""

from __future__ import annotations

import ast
import importlib.util
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.assigned_review import AssignedReview
from src.models.movie import Movie
from src.models.price_check import ANOTHER_YEAR, SHARED_TITLE, PriceCheck
from src.models.price_history import PriceHistoryDaily
from src.models.profile import Profile, UserRole
from src.models.wanted import Retailer, WantedItem
from src.routers.wanted import _shop_prices
from src.services import assigned_reviews as service
from src.services.ebay_watch.usual import shop_prices
from src.services.health_checks import check_wants_naming_another_film
from src.services.scraping.aggregate import aggregate_old_checks
from src.services.scraping.alerts import AlertCandidate, _previously_alerted_below_threshold
from src.services.scraping.another_film import (
    other_film_label,
    other_films,
    rejudge_stored,
    wants_asked,
)
from src.services.scraping.extract import ScrapeCandidate, another_film, check_shape, extract
from src.services.scraping.runner import run_scrape, scrape_one
from tests.test_assigned_reviews import review_world as review_world
from tests.test_needs_you_api import api_session as api_session
from tests.test_needs_you_api import client_as as client_as
from tests.test_needs_you_api import people as people
from tests.test_price_alerts_and_history import CARD_CONFIG
from tests.test_price_alerts_and_history import db as db
from tests.test_scraping import _retailer as _unsaved_retailer
from tests.test_scraping import _zavvi_card

API = Path(__file__).parents[1]
SRC = API / "src"

BAD_LIEUTENANT_2009 = "Bad Lieutenant: Port of Call New Orleans"
#: 101 Films' two listings, as stored since 12 Oct.
LIEUTENANT_1992 = "Bad Lieutenant (1992) (Standard Edition) (4K-UHD)"
LIEUTENANT_1992_LE = "Bad Lieutenant (1992) (Limited Edition) (4K-UHD & Blu-ray)"
#: Second Sight's and Zavvi's, naming no year.
SHOES = "Dead Man's Shoes Limited Edition Blu-ray"
#: 101 Films' Castle Freak, a year from TMDB's: the same film.
CASTLE_FREAK = "Castle Freak (1995) (Standard Edition) (Blu-ray)"


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "film_year", "needs_year", "expected"),
    [
        (LIEUTENANT_1992, 2009, False, ANOTHER_YEAR),
        (LIEUTENANT_1992_LE, 2009, False, ANOTHER_YEAR),
        ("Bad Lieutenant [1992] 4K UHD", 2009, False, ANOTHER_YEAR),
        (LIEUTENANT_1992, 1992, False, None),
        (CASTLE_FREAK, 1996, False, None),
        ("Castle Freak (1994) Blu-ray", 1996, False, ANOTHER_YEAR),
        (SHOES, 1940, False, None),
        (SHOES, 1940, True, SHARED_TITLE),
        ("Dead Man's Shoes (2004) Blu-ray", 1940, True, ANOTHER_YEAR),
        ("Dead Man's Shoes (1940) Blu-ray", 1940, True, None),
        # A bare number is the title, never a year: "Blade Runner 2049", "1917".
        ("Blade Runner 2049 4K UHD", 2017, False, None),
        ("1917 4K UHD", 2019, False, None),
        # Two years, one of them the film's: it is the film.
        ("The Thing (1982) / The Thing (2011) Double Pack Blu-ray", 2011, False, None),
        (LIEUTENANT_1992, None, False, None),
        (None, 2009, True, None),
    ],
)
def test_a_listing_is_another_film_s_by_its_year(
    title: str | None, film_year: int | None, needs_year: bool, expected: str | None
) -> None:
    assert another_film(title, film_year, needs_year=needs_year) == expected


def test_the_other_film_is_named_by_the_listing_s_words_before_its_year() -> None:
    assert other_film_label(LIEUTENANT_1992, 1992) == "Bad Lieutenant (1992)"
    assert other_film_label("Bad Lieutenant [1992] 4K", 1992) == "Bad Lieutenant (1992)"


def test_the_shape_check_refuses_another_film_s_listing_and_says_why() -> None:
    candidate = ScrapeCandidate(
        title=LIEUTENANT_1992,
        price=Decimal("22.00"),
        currency="GBP",
        url="https://101-films-store.com/products/bad-lieutenant-4k",
        raw_price_text="£22.00",
    )
    before = check_shape(candidate, expected_title=BAD_LIEUTENANT_2009)
    assert before.ok, "without the film's year the words alone still pass, as they did"

    verdict = check_shape(candidate, expected_title=BAD_LIEUTENANT_2009, film_year=2009)
    assert not verdict.ok
    assert verdict.another_film == ANOTHER_YEAR
    assert len(verdict.reasons) == 1 and "another film" in verdict.reasons[0]

    shoes = ScrapeCandidate(
        title=SHOES, price=Decimal("20"), currency="GBP", url=None, raw_price_text="£20"
    )
    asked = check_shape(shoes, expected_title="Dead Man's Shoes", film_year=1940, needs_year=True)
    assert not asked.ok and asked.another_film == SHARED_TITLE


def test_the_film_s_own_listing_wins_over_another_film_s_above_it() -> None:
    page = _zavvi_card("/p/1", LIEUTENANT_1992, "£22.00") + _zavvi_card(
        "/p/2", f"{BAD_LIEUTENANT_2009} (2009) (4K-UHD)", "£25.00"
    )
    candidate = extract(page, CARD_CONFIG, expected_title=BAD_LIEUTENANT_2009, film_year=2009)
    assert candidate.price == Decimal("25.00")

    only_other = extract(
        _zavvi_card("/p/1", LIEUTENANT_1992, "£22.00"),
        CARD_CONFIG,
        expected_title=BAD_LIEUTENANT_2009,
        film_year=2009,
    )
    assert only_other.title == LIEUTENANT_1992, "returned so the shape check can say whose"
    assert only_other.matching_cards == 0


def _shop(**kwargs: object) -> Retailer:
    return _unsaved_retailer(scraper_config=CARD_CONFIG, **kwargs)


async def _scrape(
    page: str, title: str, year: int, *, needs_year: bool = False
) -> tuple[ScrapeCandidate | None, Any]:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        return await scrape_one(
            _shop(), title, film_year=year, needs_year=needs_year, client=client
        )


async def test_the_shop_job_reads_another_film_s_listing_as_that_not_a_price() -> None:
    candidate, outcome = await _scrape(
        _zavvi_card("/p/1", LIEUTENANT_1992, "£22.00"), BAD_LIEUTENANT_2009, 2009
    )
    assert candidate is not None and candidate.title == LIEUTENANT_1992
    assert outcome.another_film == ANOTHER_YEAR
    assert not outcome.ok
    # Not stocked, so nothing counts it a failure or a success for the shop.
    assert outcome.not_stocked and not outcome.no_results
    assert "another film" in (outcome.error or "")


async def test_a_want_that_asked_needs_a_year_and_any_other_reads_as_before() -> None:
    page = _zavvi_card("/p/shoes", SHOES, "£20.00")
    _c, asked = await _scrape(page, "Dead Man's Shoes", 1940, needs_year=True)
    assert asked.another_film == SHARED_TITLE and not asked.ok

    priced, before = await _scrape(page, "Dead Man's Shoes", 1940)
    assert before.ok and before.another_film is None
    assert priced is not None and priced.price == Decimal("20.00")


# ---------------------------------------------------------------------------
# On Postgres: the run, the stored listings and every reader
# ---------------------------------------------------------------------------


async def _film(db: AsyncSession, title: str, year: int | None) -> Movie:
    movie = Movie(id=uuid.uuid4(), title=title, original_title=title, year=year, media_type="film")
    db.add(movie)
    await db.flush()
    return movie


async def _want(db: AsyncSession, movie: Movie, *, fmt: str | None = "4k_uhd") -> WantedItem:
    want = WantedItem(
        id=uuid.uuid4(), movie_id=movie.id, preferred_format=fmt, currency="GBP", is_active=True
    )
    db.add(want)
    await db.flush()
    return want


async def _saved_shop(db: AsyncSession, name: str = "101 Films") -> Retailer:
    shop = _shop(name=name, scrape_frequency="daily")
    db.add(shop)
    await db.flush()
    return shop


async def _listing(
    db: AsyncSession,
    want: WantedItem,
    shop: Retailer,
    title: str,
    *,
    price: str = "22.00",
    when: datetime | None = None,
    marked: str | None = None,
    notified: bool = False,
) -> PriceCheck:
    check = PriceCheck(
        id=uuid.uuid4(),
        wanted_id=want.id,
        retailer_id=shop.id,
        retailer_name_snapshot=shop.name,
        price=Decimal(price),
        currency="GBP",
        title_snapshot=title,
        url=f"https://93.184.216.34/p/{uuid.uuid4().hex}",
        checked_at=when or utcnow(),
        another_film=marked,
        notification_sent=notified,
    )
    db.add(check)
    await db.flush()
    return check


async def _ask(db: AsyncSession, want: WantedItem, person: Profile) -> AssignedReview:
    movie = await db.get(Movie, want.movie_id)
    assert movie is not None
    row = AssignedReview(
        id=uuid.uuid4(),
        kind="wanted_identity",
        target_id=want.id,
        assigned_to=person.id,
        snapshot={"movieId": str(movie.id), "title": movie.title, "year": movie.year},
        wording=service.as_wording(service.WORDS["wanted_identity"]),
    )
    db.add(row)
    await db.flush()
    return row


async def _person(db: AsyncSession) -> Profile:
    profile = Profile(
        id=uuid.uuid4(), display_name=f"viewer {uuid.uuid4().hex[:6]}", role=UserRole.viewer
    )
    db.add(profile)
    await db.flush()
    return profile


async def test_the_run_records_another_film_s_listing_marked_and_alerts_nothing(
    db: AsyncSession,
) -> None:
    shop = await _saved_shop(db)
    want = await _want(db, await _film(db, BAD_LIEUTENANT_2009, 2009))
    page = _zavvi_card("/products/bad-lieutenant-4k", LIEUTENANT_1992, "£22.00")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        result = await run_scrape(db, client=client, polite_pause=0.0)

    assert result.written == 0 and result.written_checks == []
    assert result.another_film == 1 and result.failed == 0
    [row] = (await db.scalars(select(PriceCheck).where(PriceCheck.wanted_id == want.id))).all()
    assert row.another_film == ANOTHER_YEAR and row.title_snapshot == LIEUTENANT_1992
    assert shop.consecutive_failures == 0, "another film's listing is the shop answering"


async def test_stored_listings_are_judged_by_the_want_s_film_as_it_is_now(
    db: AsyncSession,
) -> None:
    shop = await _saved_shop(db)
    lieutenant = await _film(db, BAD_LIEUTENANT_2009, 2009)
    bad = await _want(db, lieutenant)
    shoes = await _want(db, await _film(db, "Dead Man's Shoes", 1940), fmt=None)
    freak = await _want(db, await _film(db, "Castle Freak", 1996), fmt=None)
    second_sight = await _saved_shop(db, "Second Sight")
    for _ in range(2):
        await _listing(db, bad, shop, LIEUTENANT_1992)
        await _listing(db, shoes, second_sight, SHOES)
    await _listing(db, freak, shop, CASTLE_FREAK)
    await _ask(db, shoes, await _person(db))

    judged = await rejudge_stored(db)
    assert dict(judged.hidden) == {ANOTHER_YEAR: 2, SHARED_TITLE: 2}
    assert judged.by_want == {bad.id: 2, shoes.id: 2}
    marks = {
        check.wanted_id: check.another_film for check in (await db.scalars(select(PriceCheck)))
    }
    assert marks == {bad.id: ANOTHER_YEAR, shoes.id: SHARED_TITLE, freak.id: None}
    assert await wants_asked(db) == {shoes.id}

    again = await rejudge_stored(db)
    assert again.changed == 0, "a second pass changes nothing"

    # Correct the want to the film the shop lists, and its listings are its prices again.
    lieutenant.year = 1992
    shown = await rejudge_stored(db)
    assert shown.shown == 2 and not shown.hidden


async def test_no_reader_takes_another_film_s_listing_as_a_price(db: AsyncSession) -> None:
    shop = await _saved_shop(db)
    movie = await _film(db, BAD_LIEUTENANT_2009, 2009)
    want = await _want(db, movie)
    hidden = await _listing(db, want, shop, LIEUTENANT_1992, marked=ANOTHER_YEAR, notified=True)

    # The Wanted list.
    assert await _shop_prices(db, [want.id]) == {}
    # The eBay deal yardstick.
    assert await shop_prices(db, movie_id=movie.id, format_code="4k_uhd", now=utcnow()) == ()
    # A price drop is judged against the want's own last price, not another film's.
    own = await _listing(db, want, shop, f"{BAD_LIEUTENANT_2009} (2009) (4K-UHD)", price="20.00")
    candidate = AlertCandidate(check=own, wanted=want)
    assert not await _previously_alerted_below_threshold(db, candidate, Decimal("25.00"))
    hidden.another_film = None
    await db.flush()
    assert await _previously_alerted_below_threshold(db, candidate, Decimal("25.00"))


async def test_the_roll_up_leaves_another_film_s_listings_out_and_still_clears_them(
    db: AsyncSession,
) -> None:
    shop = await _saved_shop(db)
    want = await _want(db, await _film(db, BAD_LIEUTENANT_2009, 2009))
    old = datetime(2026, 1, 5, 3, 0)
    await _listing(db, want, shop, LIEUTENANT_1992, price="22.00", when=old, marked=ANOTHER_YEAR)
    await _listing(db, want, shop, f"{BAD_LIEUTENANT_2009} (2009)", price="30.00", when=old)

    await aggregate_old_checks(db, older_than_days=90, now=old + timedelta(days=100))

    [day] = (
        await db.scalars(select(PriceHistoryDaily).where(PriceHistoryDaily.wanted_id == want.id))
    ).all()
    assert (day.min_price, day.max_price, day.check_count) == (
        Decimal("30.00"),
        Decimal("30.00"),
        1,
    )
    left = await db.scalars(select(PriceCheck).where(PriceCheck.wanted_id == want.id))
    assert left.all() == []


def _selects_price_checks(node: ast.AST) -> bool:
    for call in ast.walk(node):
        if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "select":
            for arg in ast.walk(call):
                if isinstance(arg, ast.Name) and arg.id == "PriceCheck":
                    return True
    return False


def test_every_reader_of_stored_shop_prices_decides_about_another_film() -> None:
    """A function that selects from ``price_checks`` names ``PRICED`` or ``another_film``.

    ``PRICED`` for a reader of prices; ``another_film`` for the shop job's own upsert and the
    judging of stored listings. A new reader that names neither fails here.
    """
    readers: dict[str, str] = {}
    undecided: list[str] = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _selects_price_checks(function):
                continue
            names = {n.id for n in ast.walk(function) if isinstance(n, ast.Name)}
            attrs = {n.attr for n in ast.walk(function) if isinstance(n, ast.Attribute)}
            where = f"{path.relative_to(SRC)}:{function.name}"
            if "PRICED" in names:
                readers[where] = "priced"
            elif "another_film" in attrs or "another_film" in names:
                readers[where] = "another_film"
            else:
                undecided.append(where)
    assert undecided == []
    priced = {where for where, how in readers.items() if how == "priced"}
    assert {
        "routers/wanted.py:_shop_prices",
        "services/scraping/alerts.py:_previously_alerted_below_threshold",
        "services/scraping/aggregate.py:aggregate_old_checks",
        "services/ebay_watch/usual.py:shop_prices",
    } <= priced


# ---------------------------------------------------------------------------
# Any want can ask "which film?"
# ---------------------------------------------------------------------------


async def test_the_daily_check_raises_a_want_whose_shops_name_another_film(
    db: AsyncSession,
) -> None:
    shop = await _saved_shop(db)
    want = await _want(db, await _film(db, BAD_LIEUTENANT_2009, 2009))
    await _listing(db, want, shop, LIEUTENANT_1992, marked=ANOTHER_YEAR)
    await _listing(db, want, shop, LIEUTENANT_1992_LE, marked=ANOTHER_YEAR)

    [(key, message)] = await check_wants_naming_another_film(db, utcnow())
    assert key == f"wanted:another-film:{want.id}"
    assert "101 Films: Bad Lieutenant (1992)" in message
    assert f"{BAD_LIEUTENANT_2009} (2009)" in message and "Administration" in message

    await _ask(db, want, await _person(db))
    assert await check_wants_naming_another_film(db, utcnow()) == []


async def _lieutenant_world(api_session: AsyncSession) -> WantedItem:
    shop = await _saved_shop(api_session)
    want = await _want(api_session, await _film(api_session, BAD_LIEUTENANT_2009, 2009))
    await _listing(api_session, want, shop, LIEUTENANT_1992, marked=ANOTHER_YEAR)
    await _listing(api_session, want, shop, LIEUTENANT_1992_LE, marked=ANOTHER_YEAR)
    return want


async def test_the_admin_asks_any_want_which_film_and_the_viewer_answers_in_its_years(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
) -> None:
    want = await _lieutenant_world(api_session)
    admin, mark = client_as("craig"), client_as("mark")

    assert (await mark.get("/api/v1/needs-you/reviews/want-proposals")).status_code == 403
    response = await admin.get("/api/v1/needs-you/reviews/want-proposals")
    assert response.status_code == 200, response.text
    [proposal] = response.json()
    assert proposal["targetId"] == str(want.id) and proposal["kind"] == "wanted_identity"
    assert proposal["question"] == (
        f"Is the wanted film {BAD_LIEUTENANT_2009} (2009) or Bad Lieutenant (1992)?"
    )
    assert [c["value"] for c in proposal["choices"]] == ["2009", "1992"]

    assigned = await admin.post("/api/v1/needs-you/reviews", json=proposal)
    assert assigned.status_code == 200, assigned.text
    review = assigned.json()
    assert review["title"] == f"Check {BAD_LIEUTENANT_2009} on Wanted"
    assert "101 Films lists Bad Lieutenant (1992)" in review["evidence"]
    assert [c["value"] for c in review["choices"]] == ["2009", "1992", "unsure"]
    # Asked, so it is proposed no more.
    assert (await admin.get("/api/v1/needs-you/reviews/want-proposals")).json() == []

    [shown] = [
        r for r in (await mark.get("/api/v1/needs-you/reviews")).json() if r["id"] == review["id"]
    ]
    assert shown["canAnswer"]
    path = f"/api/v1/needs-you/reviews/{review['id']}/answer"
    refused = await mark.post(path, json={"revision": 1, "answer": "1940"})
    assert refused.status_code == 422, "a year the question does not offer"
    answered = await mark.post(path, json={"revision": 1, "answer": "1992"})
    assert answered.status_code == 200, answered.text
    assert answered.json()["answer"] == "1992" and answered.json()["status"] == "answered"
    # Recording an answer moves nothing: the want is still the 2009 film's.
    await api_session.refresh(want)
    assert (await api_session.get(Movie, want.movie_id)).year == 2009  # type: ignore[union-attr]


async def test_a_want_whose_shops_name_no_other_film_cannot_be_asked(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    want = await _want(api_session, await _film(api_session, "Misery", 1990))
    current, _ = await service.context(api_session, "wanted_identity", want.id)
    response = await client_as("craig").post(
        "/api/v1/needs-you/reviews",
        json={
            "kind": "wanted_identity",
            "targetId": str(want.id),
            "assignedTo": str(people["mark"].id),
            "expectedFingerprint": service.fingerprint(current),
        },
    )
    assert response.status_code == 422, response.text
    assert "name no other film" in response.text


async def test_the_dead_man_s_shoes_question_keeps_the_words_it_was_asked_with(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
) -> None:
    proposals = (await client_as("craig").get("/api/v1/needs-you/reviews/proposals")).json()
    [shoes] = [p for p in proposals if p["kind"] == "wanted_identity"]
    response = await client_as("craig").post("/api/v1/needs-you/reviews", json=shoes)
    assert response.status_code == 200, response.text
    assert response.json()["question"] == service.WORDS["wanted_identity"][1]
    row = await api_session.get(AssignedReview, uuid.UUID(response.json()["id"]))
    assert row is not None and row.wording == service.as_wording(service.WORDS["wanted_identity"])

    path = "/api/v1/needs-you/reviews/" + response.json()["id"] + "/answer"
    answered = await client_as("mark").post(path, json={"revision": 1, "answer": "1940"})
    assert answered.status_code == 200, answered.text


async def test_the_database_keeps_a_want_question_s_words_and_years(
    db: AsyncSession,
) -> None:
    person = await _person(db)
    want = await _want(db, await _film(db, BAD_LIEUTENANT_2009, 2009))
    row = await _ask(db, want, person)
    listing = await _listing(db, want, await _saved_shop(db), LIEUTENANT_1992)

    row.answer = "1992"
    await db.flush()

    for column, value in [("answer", "a year"), ("wording", None)]:
        with pytest.raises(IntegrityError):
            async with db.begin_nested():
                await db.execute(
                    text(f"UPDATE assigned_reviews SET {column} = :value WHERE id = :id"),
                    {"value": value, "id": row.id},
                )
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add(
                AssignedReview(
                    id=uuid.uuid4(),
                    kind="titanic_disc",
                    target_id=uuid.uuid4(),
                    assigned_to=person.id,
                    snapshot={},
                    answer="2009",
                )
            )
            await db.flush()
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            await db.execute(
                text("UPDATE price_checks SET another_film = 'maybe' WHERE id = :id"),
                {"id": listing.id},
            )


def test_the_migration_gives_dead_man_s_shoes_the_words_it_was_asked_with() -> None:
    path = API / "migrations/versions/081_wants_know_their_film.py"
    spec = importlib.util.spec_from_file_location("wants_know_their_film", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert service.as_wording(service.WORDS["wanted_identity"]) == module.DEAD_MANS_SHOES


async def test_other_films_are_each_year_a_want_s_shops_name(db: AsyncSession) -> None:
    want = await _want(db, await _film(db, BAD_LIEUTENANT_2009, 2009))
    await _listing(db, want, await _saved_shop(db), LIEUTENANT_1992, marked=ANOTHER_YEAR)
    await _listing(
        db, want, await _saved_shop(db, "Zavvi"), "Bad Lieutenant [1992] 4K", marked=ANOTHER_YEAR
    )
    [other] = await other_films(db, want.id)
    assert (other.year, other.label, other.shops) == (
        1992,
        "Bad Lieutenant (1992)",
        ("101 Films", "Zavvi"),
    )
