"""Batch AC1 (#335): Home's "Needs you" row, for each person.

The row is derived from loan rows on every read, so the tests set loans up directly and read
the row back as each audience: a shelf keeper (an admin, and Mark by his stable id), a
borrower, and a third active profile who keeps no shelves and sees no shelf jobs.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.clock import utc_today, utcnow
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.loan import Loan
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.routers import needs_you as needs_you_router

ACTOR_HEADER = "x-test-actor"
TODAY = utc_today()


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def _person(session: AsyncSession, role: UserRole, name: str) -> Profile:
    person = Profile(
        id=uuid.uuid4(),
        display_name=f"AC1 {name} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=role,
    )
    session.add(person)
    await session.flush()
    return person


@pytest_asyncio.fixture
async def people(api_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> dict[str, Profile]:
    craig = await _person(api_session, UserRole.admin, "Craig")
    mark = await _person(api_session, UserRole.viewer, "Mark")
    third = await _person(api_session, UserRole.viewer, "Third")
    # Mark keeps the shelves by his stable id, never by role (#306, #335). The test database's
    # Mark is someone else, so a stand-in takes the id for the test.
    monkeypatch.setattr(needs_you_router, "MARK_PROFILE_ID", mark.id)
    return {"craig": craig, "mark": mark, "third": third}


@pytest_asyncio.fixture
async def client_as(
    api_session: AsyncSession, people: dict[str, Profile]
) -> AsyncIterator[Callable[[str], AsyncClient]]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user(request: Request) -> Profile:
        return people[request.headers[ACTOR_HEADER]]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    opened: list[AsyncClient] = []

    def make(name: str) -> AsyncClient:
        client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={ACTOR_HEADER: name},
        )
        opened.append(client)
        return client

    try:
        yield make
    finally:
        for client in opened:
            await client.aclose()
        app.dependency_overrides.clear()


async def _disc(
    session: AsyncSession, title: str, *, section: str | None = "Front"
) -> CollectionItem:
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
    item = CollectionItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        formats=["blu_ray"],
        location=f"{section} 2nd shelf" if section else None,
        section=section,
        shelf="2nd" if section else None,
        condition="good",
    )
    session.add(item)
    await session.flush()
    return item


async def _loan(
    session: AsyncSession,
    item: CollectionItem,
    *,
    state: str | None,
    borrower: Profile | None = None,
    lent_days_ago: int | None = 3,
    due_in_days: int | None = None,
    returned_days_ago: int | None = None,
    needed_in_days: int | None = None,
) -> Loan:
    loan = Loan(
        id=uuid.uuid4(),
        collection_item_id=item.id,
        borrower_name=borrower.display_name if borrower else "Dave",
        borrower_profile_id=borrower.id if borrower else None,
        lent_date=None if lent_days_ago is None else TODAY - timedelta(days=lent_days_ago),
        due_date=None if due_in_days is None else TODAY + timedelta(days=due_in_days),
        returned_date=(
            None if returned_days_ago is None else TODAY - timedelta(days=returned_days_ago)
        ),
        needed_by_date=None if needed_in_days is None else TODAY + timedelta(days=needed_in_days),
        state=state,
    )
    session.add(loan)
    await session.flush()
    return loan


async def _row(client: AsyncClient, *loans: Loan) -> list[dict[str, Any]]:
    """The reader's row, kept to the loans this test made: the test database is shared."""
    response = await client.get("/api/v1/needs-you")
    assert response.status_code == 200, response.text
    ids = {str(loan.id) for loan in loans}
    return [item for item in response.json()["items"] if item["loanId"] in ids]


async def test_a_disc_back_but_not_shelved_goes_to_the_shelf_keepers_only(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    item = await _disc(api_session, "Pulp Fiction")
    back = await _loan(
        api_session,
        item,
        state="back",
        borrower=people["third"],
        lent_days_ago=7,
        returned_days_ago=2,
    )

    for keeper in ("craig", "mark"):
        [entry] = await _row(client_as(keeper), back)
        assert entry["kind"] == "putBack"
        assert entry["movieTitle"] == "Pulp Fiction"
        assert entry["locationLabel"] == "Front 2nd"
        assert entry["returnedDate"] == (TODAY - timedelta(days=2)).isoformat()
    # The third person borrowed it, but putting it back is the shelf keepers' job (#335).
    assert await _row(client_as("third"), back) == []


async def test_a_request_goes_to_the_shelf_keepers_but_not_to_whoever_asked(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    asked_by_mark = await _loan(
        api_session,
        await _disc(api_session, "The Thing"),
        state="asked_for",
        borrower=people["mark"],
        lent_days_ago=None,
        needed_in_days=2,
    )
    asked_by_third = await _loan(
        api_session,
        await _disc(api_session, "Alien"),
        state="asked_for",
        borrower=people["third"],
        lent_days_ago=None,
        needed_in_days=5,
    )

    craig = await _row(client_as("craig"), asked_by_mark, asked_by_third)
    assert [(entry["kind"], entry["movieTitle"]) for entry in craig] == [
        ("handOver", "The Thing"),
        ("handOver", "Alien"),
    ]
    # Mark asked for The Thing: he is waiting for it, not handing it over.
    mark = await _row(client_as("mark"), asked_by_mark, asked_by_third)
    assert [entry["movieTitle"] for entry in mark] == ["Alien"]
    assert mark[0]["borrowerName"] == people["third"].display_name
    assert mark[0]["neededBy"] == (TODAY + timedelta(days=5)).isoformat()
    assert await _row(client_as("third"), asked_by_mark, asked_by_third) == []


async def test_an_overdue_loan_goes_to_its_borrower_and_the_shelf_keepers(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    to_third = await _loan(
        api_session,
        await _disc(api_session, "Heat"),
        state="out",
        borrower=people["third"],
        lent_days_ago=10,
        due_in_days=-3,
    )

    [mine] = await _row(client_as("third"), to_third)
    assert mine["kind"] == "overdue"
    assert mine["borrowerIsYou"] is True
    assert mine["daysOverdue"] == 3
    assert mine["daysOut"] == 10
    for keeper in ("craig", "mark"):
        [theirs] = await _row(client_as(keeper), to_third)
        assert theirs["kind"] == "overdue"
        assert theirs["borrowerIsYou"] is False
        assert theirs["borrowerName"] == people["third"].display_name


async def test_an_open_ended_loan_joins_the_row_on_its_fourteenth_day(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    thirteen = await _loan(
        api_session,
        await _disc(api_session, "Halloween"),
        state="out",
        borrower=people["craig"],
        lent_days_ago=13,
    )
    fourteen = await _loan(
        api_session,
        await _disc(api_session, "The Silence of the Lambs"),
        state="out",
        borrower=people["craig"],
        lent_days_ago=14,
    )

    [craig] = await _row(client_as("craig"), thirteen, fourteen)
    assert craig["movieTitle"] == "The Silence of the Lambs"
    assert craig["borrowerIsYou"] is True
    assert craig["daysOverdue"] is None
    assert craig["daysOut"] == 14
    [mark] = await _row(client_as("mark"), thirteen, fourteen)
    assert mark["borrowerIsYou"] is False
    assert await _row(client_as("third"), thirteen, fourteen) == []


async def test_a_loan_not_yet_due_and_a_friend_s_loan_follow_the_same_rule(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    due_today = await _loan(
        api_session,
        await _disc(api_session, "Thief"),
        state="out",
        borrower=people["third"],
        lent_days_ago=20,
        due_in_days=0,
    )
    friend_late = await _loan(
        api_session,
        await _disc(api_session, "Collateral"),
        state="out",
        borrower=None,
        lent_days_ago=9,
        due_in_days=-1,
    )

    # Due today is not overdue; a friend has no profile, so only the keepers are told.
    assert await _row(client_as("third"), due_today, friend_late) == []
    [entry] = await _row(client_as("mark"), due_today, friend_late)
    assert entry["movieTitle"] == "Collateral"
    assert entry["borrowerName"] == "Dave"
    assert entry["daysOverdue"] == 1


async def test_a_legacy_open_loan_with_no_state_still_reads_as_out(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    legacy = await _loan(
        api_session,
        await _disc(api_session, "Manhunter"),
        state=None,
        borrower=people["craig"],
        lent_days_ago=17,
    )
    legacy_closed = await _loan(
        api_session,
        await _disc(api_session, "Ronin"),
        state=None,
        borrower=None,
        lent_days_ago=40,
        returned_days_ago=30,
    )

    [entry] = await _row(client_as("mark"), legacy, legacy_closed)
    assert entry["kind"] == "overdue"
    assert entry["movieTitle"] == "Manhunter"
    assert entry["daysOut"] == 17


async def test_only_each_copy_s_current_loan_makes_a_task(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    item = await _disc(api_session, "Blood Simple")
    older = await _loan(
        api_session,
        item,
        state="back",
        borrower=people["third"],
        lent_days_ago=30,
        returned_days_ago=20,
    )
    newer = await _loan(
        api_session,
        item,
        state="out",
        borrower=people["mark"],
        lent_days_ago=2,
    )

    # Reborrowed before it was shelved: the old return is history, not a job.
    assert await _row(client_as("craig"), older, newer) == []


async def test_a_binned_or_sold_copy_drops_out_of_the_row(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    binned = await _disc(api_session, "Miller's Crossing")
    back = await _loan(
        api_session,
        binned,
        state="back",
        borrower=people["craig"],
        lent_days_ago=5,
        returned_days_ago=1,
    )
    sold = await _disc(api_session, "Barton Fink")
    late = await _loan(
        api_session,
        sold,
        state="out",
        borrower=people["third"],
        lent_days_ago=30,
    )
    assert len(await _row(client_as("craig"), back, late)) == 2
    binned.deleted_at = utcnow()
    sold.listing_status = "sold"
    await api_session.flush()

    # Owned means owned_copy(): nothing to shelve, and nothing to chase, for a copy we no
    # longer have.
    assert await _row(client_as("craig"), back, late) == []
    assert await _row(client_as("third"), back, late) == []


async def test_confirming_a_disc_shelved_clears_it_for_everyone(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    back = await _loan(
        api_session,
        await _disc(api_session, "Rosemary's Baby"),
        state="back",
        borrower=people["craig"],
        lent_days_ago=17,
        returned_days_ago=7,
    )
    assert len(await _row(client_as("craig"), back)) == 1
    assert len(await _row(client_as("mark"), back)) == 1

    # Loans' own confirm flow, choosing another shelf on the way: no second write path.
    confirmed = await client_as("mark").patch(
        f"/api/v1/loans/{back.id}", json={"state": "shelved", "section": "Back", "shelf": "3rd"}
    )
    assert confirmed.status_code == 200, confirmed.text

    assert await _row(client_as("craig"), back) == []
    assert await _row(client_as("mark"), back) == []


async def test_most_pressing_first(
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    put_back = await _loan(
        api_session,
        await _disc(api_session, "A Put Back"),
        state="back",
        borrower=people["third"],
        lent_days_ago=9,
        returned_days_ago=4,
    )
    overdue = await _loan(
        api_session,
        await _disc(api_session, "B Overdue"),
        state="out",
        borrower=people["third"],
        lent_days_ago=9,
        due_in_days=-2,
    )
    hand_over = await _loan(
        api_session,
        await _disc(api_session, "C Hand Over"),
        state="asked_for",
        borrower=people["third"],
        lent_days_ago=None,
        needed_in_days=1,
    )

    row = await _row(client_as("craig"), put_back, overdue, hand_over)
    assert [entry["kind"] for entry in row] == ["handOver", "overdue", "putBack"]


async def test_nothing_to_do_is_an_empty_row_for_anyone(
    client_as: Callable[[str], AsyncClient],
) -> None:
    response = await client_as("third").get("/api/v1/needs-you")
    assert response.status_code == 200
    assert response.json() == {"items": []}
