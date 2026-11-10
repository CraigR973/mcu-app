"""AE9 (#355): a page for each person — read-only, on real Postgres.

Anyone signed in reads anyone active's page: their films watched this year and ever, their last
ten diary entries, the copies they added lately, their wants and the discs they have now.
Nothing from Settings is ever in it, and an inactive or unknown profile is not found.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utc_today
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.wanted import WantedItem
from src.models.watch_log import WatchLog
from tests.test_needs_you_api import _disc, _loan
from tests.test_needs_you_api import api_session as api_session
from tests.test_needs_you_api import client_as as client_as
from tests.test_needs_you_api import people as people

TODAY = utc_today()
#: Every field the page may carry; anything else, such as a PIN or a session, would fail this.
FIELDS = {
    "profileId",
    "displayName",
    "isYou",
    "watchedThisYear",
    "watchedTotal",
    "diary",
    "recentlyAdded",
    "wants",
    "wantsTotal",
    "loans",
}


async def _film(db: AsyncSession, title: str, year: int = 2001) -> Movie:
    movie = Movie(id=uuid.uuid4(), title=title, original_title=title, year=year, media_type="film")
    db.add(movie)
    await db.flush()
    return movie


async def _watch(
    db: AsyncSession,
    person: Profile,
    movie: Movie,
    on: date,
    *,
    rating: str | None = None,
    rewatch: bool = False,
) -> None:
    db.add(
        WatchLog(
            id=uuid.uuid4(),
            movie_id=movie.id,
            user_id=person.id,
            watched_at=on,
            personal_rating=Decimal(rating) if rating else None,
            is_rewatch=rewatch,
        )
    )
    await db.flush()


async def _page(client: AsyncClient, person: Profile) -> dict[str, Any]:
    response = await client.get(f"/api/v1/people/{person.id}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert set(body) == FIELDS
    return body


async def test_a_person_s_page_reads_their_diary_shelves_wants_and_loans(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    db, mark = api_session, people["mark"]
    alien = await _film(db, "AE9 Alien")
    heat = await _film(db, "AE9 Heat")
    old = await _film(db, "AE9 Old")
    await _watch(db, mark, alien, TODAY, rating="4.5")
    await _watch(db, mark, alien, TODAY - timedelta(days=1), rewatch=True)
    await _watch(db, mark, heat, TODAY - timedelta(days=2))
    await _watch(db, mark, old, date(TODAY.year - 1, 6, 1), rating="3")
    # Copies he added: one on the shelves, one sold since, which no longer counts.
    for title, status, minutes in (("AE9 Added", "in_collection", 5), ("AE9 Sold", "sold", 1)):
        movie = await _film(db, title)
        db.add(
            CollectionItem(
                id=uuid.uuid4(),
                movie_id=movie.id,
                formats=["4k_uhd"],
                condition="good",
                listing_status=status,
                added_by=mark.id,
                added_at_utc=datetime(2026, 11, 10, 9, 0) - timedelta(minutes=minutes),
            )
        )
    want = await _film(db, "AE9 Wanted")
    db.add(WantedItem(id=uuid.uuid4(), movie_id=want.id, is_active=True, added_by=mark.id))
    await db.flush()
    out = await _loan(db, await _disc(db, "AE9 Lent"), state="out", borrower=mark, lent_days_ago=3)
    asked = await _loan(
        db,
        await _disc(db, "AE9 Asked"),
        state="asked_for",
        borrower=mark,
        lent_days_ago=None,
        needed_in_days=2,
    )

    page = await _page(client_as("craig"), mark)
    assert page["displayName"] == mark.display_name and page["isYou"] is False
    assert (page["watchedThisYear"], page["watchedTotal"]) == (2, 3)
    assert [(e["title"], e["rating"], e["rewatch"]) for e in page["diary"]] == [
        ("AE9 Alien", 4.5, False),
        ("AE9 Alien", None, True),
        ("AE9 Heat", None, False),
        ("AE9 Old", 3.0, False),
    ]
    assert [c["title"] for c in page["recentlyAdded"]] == ["AE9 Added"]
    assert page["recentlyAdded"][0]["formats"] == ["4k_uhd"]
    assert [w["title"] for w in page["wants"]] == ["AE9 Wanted"] and page["wantsTotal"] == 1
    assert {(loan["loanId"], loan["state"]) for loan in page["loans"]} == {
        (str(out.id), "out"),
        (str(asked.id), "asked_for"),
    }


async def test_your_own_page_says_so_and_a_person_with_no_diary_reads_empty(
    people: dict[str, Profile], client_as: Callable[[str], AsyncClient]
) -> None:
    mine = await _page(client_as("third"), people["third"])
    assert mine["isYou"] is True
    assert (mine["watchedThisYear"], mine["watchedTotal"], mine["diary"]) == (0, 0, [])
    assert mine["recentlyAdded"] == [] and mine["wants"] == [] and mine["loans"] == []


async def test_an_inactive_or_unknown_profile_is_not_found(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    people["third"].is_active = False
    await api_session.flush()
    craig = client_as("craig")
    assert (await craig.get(f"/api/v1/people/{people['third'].id}")).status_code == 404
    assert (await craig.get(f"/api/v1/people/{uuid.uuid4()}")).status_code == 404
    assert (await craig.get("/api/v1/people/not-an-id")).status_code == 422
