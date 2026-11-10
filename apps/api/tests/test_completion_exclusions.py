"""AE3 (#355, point 3): Closest to complete names what is missing; a film can be set not to count.

Eastwood's set will never be complete while Piano Blues, a TV documentary episode, counts
against it. Either person can say a missing film does not count, in that set only; each change
is audited; "Count it again" undoes it. A set whose only missing films do not count is complete,
so Home's row moves on. Every test runs inside a rolled-back transaction.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.admin_action import AdminAction
from src.models.completion_exclusion import CompletionExclusion
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.wanted import WantedItem
from tests.test_completion_sets import _a_set, _owned_film
from tests.test_completion_sets import admin as admin
from tests.test_completion_sets import api_session as api_session
from tests.test_completion_sets import client as client
from tests.test_completion_sets import overrides as overrides
from tests.test_completion_sets import viewer as viewer
from tests.test_completion_sets import viewer_client as viewer_client

#: Clint Eastwood's set as live data had it on 8 Nov: everything on the shelf but one.
OWNED = 9_300_001
PIANO_BLUES = 9_300_002


async def _eastwood(session: AsyncSession) -> uuid.UUID:
    await _owned_film(session, tmdb_id=OWNED, title="Unforgiven")
    row = await _a_set(session, "9300000", "Clint Eastwood", [OWNED, PIANO_BLUES])
    return row.id


async def _audits(session: AsyncSession, set_id: uuid.UUID, action: str) -> int:
    """This set's audit entries: ``create`` sets a film not to count, ``delete`` undoes it."""
    count = await session.scalar(
        select(func.count(AdminAction.id)).where(
            AdminAction.target_table == "completion_exclusions",
            AdminAction.changes["setId"].astext == str(set_id),
            AdminAction.action_type == action,
        )
    )
    return int(count or 0)


def _counts(body: dict[str, object]) -> tuple[object, ...]:
    return (
        body["ownedCount"],
        body["totalCount"],
        body["missingCount"],
        body["percentComplete"],
        body["excludedCount"],
    )


async def test_a_missing_film_set_not_to_count_completes_the_set_and_is_audited(
    client: AsyncClient, api_session: AsyncSession, admin: Profile
) -> None:
    set_id = await _eastwood(api_session)

    response = await client.post(
        f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": PIANO_BLUES}
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    assert _counts(detail) == (1, 1, 0, 100, 1)
    films = {film["tmdbId"]: film for film in detail["films"]}
    assert films[PIANO_BLUES]["counts"] is False
    assert films[OWNED]["counts"] is True
    assert detail["missingFilms"] == []

    listed = await client.get("/api/v1/insights/completion")
    mine = next(item for item in listed.json()["items"] if item["id"] == str(set_id))
    assert _counts(mine) == (1, 1, 0, 100, 1)

    stored = await api_session.scalar(
        select(CompletionExclusion).where(CompletionExclusion.set_id == set_id)
    )
    assert stored is not None and stored.excluded_by == admin.id
    assert await _audits(api_session, set_id, "create") == 1


async def test_count_it_again_restores_the_set_and_is_audited(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    set_id = await _eastwood(api_session)
    await client.post(
        f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": PIANO_BLUES}
    )

    response = await client.delete(f"/api/v1/insights/completion/{set_id}/exclusions/{PIANO_BLUES}")
    assert response.status_code == 200, response.text
    assert _counts(response.json()) == (1, 2, 1, 50, 0)
    assert [film["tmdbId"] for film in response.json()["missingFilms"]] == [PIANO_BLUES]
    assert await _audits(api_session, set_id, "delete") == 1
    # Undoing what is already undone changes nothing and logs nothing.
    again = await client.delete(f"/api/v1/insights/completion/{set_id}/exclusions/{PIANO_BLUES}")
    assert again.status_code == 200
    assert await _audits(api_session, set_id, "delete") == 1


async def test_either_person_can_say_so_and_both_see_the_same(
    client: AsyncClient, viewer_client: AsyncClient, api_session: AsyncSession, viewer: Profile
) -> None:
    set_id = await _eastwood(api_session)

    response = await viewer_client.post(
        f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": PIANO_BLUES}
    )
    assert response.status_code == 200, response.text
    seen = await client.get(f"/api/v1/insights/completion/{set_id}")
    assert _counts(seen.json()) == (1, 1, 0, 100, 1)
    stored = await api_session.scalar(
        select(CompletionExclusion).where(CompletionExclusion.set_id == set_id)
    )
    assert stored is not None and stored.excluded_by == viewer.id


async def test_saying_it_twice_is_one_row_and_one_audit(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    set_id = await _eastwood(api_session)
    for _ in range(2):
        response = await client.post(
            f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": PIANO_BLUES}
        )
        assert response.status_code == 200, response.text

    rows = await api_session.scalar(
        select(func.count(CompletionExclusion.id)).where(CompletionExclusion.set_id == set_id)
    )
    assert rows == 1
    assert await _audits(api_session, set_id, "create") == 1


async def test_it_does_not_count_in_that_set_only(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    set_id = await _eastwood(api_session)
    other = await _a_set(api_session, "9300100", "An Actor In It", [OWNED, PIANO_BLUES])
    await client.post(
        f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": PIANO_BLUES}
    )

    response = await client.get(f"/api/v1/insights/completion/{other.id}")
    assert _counts(response.json()) == (1, 2, 1, 50, 0)


async def test_a_film_on_the_shelf_always_counts(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    set_id = await _eastwood(api_session)
    refused = await client.post(
        f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": OWNED}
    )
    assert refused.status_code == 409

    # Set not to count while missing, then bought: it counts, as owned.
    await client.post(
        f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": PIANO_BLUES}
    )
    await _owned_film(api_session, tmdb_id=PIANO_BLUES, title="Piano Blues")
    response = await client.get(f"/api/v1/insights/completion/{set_id}")
    assert _counts(response.json()) == (2, 2, 0, 100, 0)
    films = {film["tmdbId"]: film for film in response.json()["films"]}
    assert films[PIANO_BLUES]["owned"] is True and films[PIANO_BLUES]["counts"] is True


async def test_only_a_member_of_a_known_set(client: AsyncClient, api_session: AsyncSession) -> None:
    set_id = await _eastwood(api_session)
    outsider = await client.post(
        f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": 9_399_999}
    )
    assert outsider.status_code == 422
    unknown = await client.post(
        f"/api/v1/insights/completion/{uuid.uuid4()}/exclusions", json={"tmdbId": PIANO_BLUES}
    )
    assert unknown.status_code == 404


async def test_homes_row_names_up_to_three_missing_films_oldest_first_and_which_are_wanted(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    members = [9_300_201, 9_300_202, 9_300_203, 9_300_204, 9_300_205]
    await _owned_film(api_session, tmdb_id=members[0], title="On The Shelf")
    row = await _a_set(api_session, "9300200", "Alfred Hitchcock", members)
    years = {9_300_202: 1927, 9_300_203: 1925, 9_300_204: 1929, 9_300_205: 1926}
    row.set_metadata = {
        "members": [
            {"tmdbId": m, "title": f"Film {m}", "year": years.get(m, 1958), "posterPath": None}
            for m in members
        ]
    }
    # The Mountain Eagle, lost, does not count; a film already wanted reads as wanted.
    wanted_film = Movie(
        id=uuid.uuid4(), tmdb_id=9_300_204, title="Film 9300204", original_title="x", year=1929
    )
    api_session.add(wanted_film)
    await api_session.flush()
    api_session.add(WantedItem(id=uuid.uuid4(), movie_id=wanted_film.id, is_active=True))
    await api_session.flush()
    await client.post(
        f"/api/v1/insights/completion/{row.id}/exclusions", json={"tmdbId": 9_300_203}
    )

    listed = await client.get("/api/v1/insights/completion")
    mine = next(item for item in listed.json()["items"] if item["id"] == str(row.id))
    assert _counts(mine) == (1, 4, 3, 25, 1)
    named = [(film["tmdbId"], film["wanted"]) for film in mine["missingFilms"]]
    assert named == [(9_300_205, False), (9_300_202, False), (9_300_204, True)]
