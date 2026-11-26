"""AH2 (#401): the admin closes a question, which is not deleting it.

On 25 Nov two questions stayed on both people's Needs you with nothing in the app to clear them:
Shetland Series 5, answered "keep separate", and Dead Man's Shoes, whose want had been removed.
Both were closed by hand with ``deleted_at``. A closed state of its own takes them off Needs
you, keeps them on record to be reopened, and leaves a closed want question hiding its other
film's listings.
"""

from collections.abc import Callable
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.assigned_review import AssignedReview
from src.models.profile import Profile
from src.services.scraping.another_film import wants_asked
from tests.test_assigned_reviews import assigned as assigned
from tests.test_assigned_reviews import review_world as review_world
from tests.test_needs_you_api import api_session as api_session
from tests.test_needs_you_api import client_as as client_as
from tests.test_needs_you_api import people as people

URL = "/api/v1/needs-you/reviews"


def _of(rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next(row for row in rows if row["kind"] == kind)


async def _answered_shetland(client_as: Callable[[str], AsyncClient]) -> dict[str, Any]:
    shetland = _of(await assigned(client_as), "shetland_series")
    answered = await client_as("mark").post(
        f"{URL}/{shetland['id']}/answer", json={"revision": 1, "answer": "keep_separate"}
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["status"] == "answered"
    return answered.json()


async def _needs_you_review_ids(client: AsyncClient) -> set[str]:
    return {review["id"] for review in (await client.get("/api/v1/needs-you")).json()["reviews"]}


async def test_the_admin_closes_an_answered_question_and_it_leaves_both_needs_you(
    review_world: dict[str, Any],
    client_as: Callable[[str], AsyncClient],
    api_session: AsyncSession,
    people: dict[str, Profile],
) -> None:
    craig_name, craig_id = people["craig"].display_name, people["craig"].id
    shetland = await _answered_shetland(client_as)
    craig, mark = client_as("craig"), client_as("mark")
    assert shetland["id"] in await _needs_you_review_ids(craig)
    offered = _of((await craig.get(URL)).json(), "shetland_series")
    assert (offered["canClose"], offered["canReopen"]) == (True, False)

    closed = await craig.post(f"{URL}/{shetland['id']}/close", json={"revision": 2})

    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert (body["status"], body["closedByName"], body["revision"]) == ("closed", craig_name, 3)
    assert body["closedAt"] is not None
    assert (body["canClose"], body["canReopen"], body["canAnswer"]) == (False, True, False)
    assert shetland["id"] not in await _needs_you_review_ids(craig)
    assert shetland["id"] not in await _needs_you_review_ids(mark)
    # On record, not deleted: both still read it on the reviews list.
    assert _of((await mark.get(URL)).json(), "shetland_series")["status"] == "closed"
    audits = (
        (
            await api_session.execute(
                select(AdminAction).where(AdminAction.target_id == shetland["id"])
            )
        )
        .scalars()
        .all()
    )
    assert any(
        a.user_id == craig_id and (a.changes or {}).get("closed") == {"from": None, "to": "closed"}
        for a in audits
    )


async def test_reopening_puts_it_back_as_it_was(
    review_world: dict[str, Any], client_as: Callable[[str], AsyncClient]
) -> None:
    shetland = await _answered_shetland(client_as)
    craig = client_as("craig")
    assert (await craig.post(f"{URL}/{shetland['id']}/close", json={"revision": 2})).is_success

    reopened = await craig.post(f"{URL}/{shetland['id']}/reopen", json={"revision": 3})

    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert (body["status"], body["closedAt"], body["closedByName"]) == ("answered", None, None)
    assert body["revision"] == 4
    assert shetland["id"] in await _needs_you_review_ids(craig)


async def test_closing_twice_is_closing_once(
    review_world: dict[str, Any], client_as: Callable[[str], AsyncClient]
) -> None:
    shetland = await _answered_shetland(client_as)
    craig = client_as("craig")
    first = await craig.post(f"{URL}/{shetland['id']}/close", json={"revision": 2})
    again = await craig.post(f"{URL}/{shetland['id']}/close", json={"revision": 2})

    assert first.status_code == again.status_code == 200
    assert again.json()["revision"] == first.json()["revision"] == 3


async def test_an_open_question_is_the_persons_and_cannot_be_closed(
    review_world: dict[str, Any], client_as: Callable[[str], AsyncClient]
) -> None:
    titanic = _of(await assigned(client_as), "titanic_disc")
    craig = client_as("craig")
    assert _of((await craig.get(URL)).json(), "titanic_disc")["canClose"] is False

    refused = await craig.post(f"{URL}/{titanic['id']}/close", json={"revision": 1})

    assert refused.status_code == 409
    assert _of((await craig.get(URL)).json(), "titanic_disc")["status"] == "open"


async def test_a_stale_revision_is_refused(
    review_world: dict[str, Any], client_as: Callable[[str], AsyncClient]
) -> None:
    shetland = await _answered_shetland(client_as)

    stale = await client_as("craig").post(f"{URL}/{shetland['id']}/close", json={"revision": 1})

    assert stale.status_code == 409


async def test_only_the_admin_closes_or_reopens(
    review_world: dict[str, Any], client_as: Callable[[str], AsyncClient]
) -> None:
    shetland = await _answered_shetland(client_as)
    mark = client_as("mark")
    assert _of((await mark.get(URL)).json(), "shetland_series")["canClose"] is False

    assert (
        await mark.post(f"{URL}/{shetland['id']}/close", json={"revision": 2})
    ).status_code == 403
    assert (
        await mark.post(f"{URL}/{shetland['id']}/reopen", json={"revision": 2})
    ).status_code == 403


async def test_a_closed_question_takes_no_answer(
    review_world: dict[str, Any], client_as: Callable[[str], AsyncClient]
) -> None:
    shetland = await _answered_shetland(client_as)
    assert (
        await client_as("craig").post(f"{URL}/{shetland['id']}/close", json={"revision": 2})
    ).is_success

    refused = await client_as("mark").post(
        f"{URL}/{shetland['id']}/answer", json={"revision": 3, "answer": "use_series"}
    )

    assert refused.status_code == 409
    assert "closed" in refused.json()["detail"]


async def test_a_closed_want_question_still_hides_its_other_films_listings(
    review_world: dict[str, Any],
    client_as: Callable[[str], AsyncClient],
    api_session: AsyncSession,
) -> None:
    """Closing is not deleting: ``wants_asked`` still counts the question, so a shop listing
    naming no year stays the other film's, as AG5 made it. The want's removal is what made the
    question "changed", as Dead Man's Shoes' was on 25 Nov."""
    want_question = _of(await assigned(client_as), "wanted_identity")
    want = review_world["wanted_identity"]
    want_id = want.id
    want.deleted_at = utcnow()
    await api_session.flush()
    craig = client_as("craig")
    assert _of((await craig.get(URL)).json(), "wanted_identity")["status"] == "changed"

    closed = await craig.post(f"{URL}/{want_question['id']}/close", json={"revision": 1})

    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert want_question["id"] not in await _needs_you_review_ids(craig)
    row = await api_session.get(AssignedReview, want_question["id"])
    assert row is not None and row.deleted_at is None
    assert want_id in await wants_asked(api_session)
