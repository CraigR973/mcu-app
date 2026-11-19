"""AG11 (#390): a want's question clears once the want is the film its answer names.

The live case is the tests' own: Dead Man's Shoes was answered 1940 on 15 Nov, and its want
already names the 1940 film, so nothing is left to apply. Bad Lieutenant is the rule's other side:
an answer of 1992 on the 2009 film's want waits for the admin until the want is the 1992 film.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.assigned_review import AssignedReview
from src.models.movie import Movie
from src.models.price_check import SHARED_TITLE, PriceCheck
from src.models.wanted import WantedItem
from src.services.health_checks import check_wants_naming_another_film
from src.services.scraping.another_film import rejudge_stored, wants_asked
from tests.test_assigned_reviews import review_world as review_world
from tests.test_needs_you_api import api_session as api_session
from tests.test_needs_you_api import client_as as client_as
from tests.test_needs_you_api import people as people
from tests.test_wants_know_their_film import (
    SHOES,
    _lieutenant_world,
    _listing,
    _saved_shop,
)


async def _ask_shoes(client_as: Callable[[str], AsyncClient]) -> dict[str, Any]:
    """The Dead Man's Shoes question, asked as on 15 Nov."""
    proposals = (await client_as("craig").get("/api/v1/needs-you/reviews/proposals")).json()
    [shoes] = [p for p in proposals if p["kind"] == "wanted_identity"]
    response = await client_as("craig").post("/api/v1/needs-you/reviews", json=shoes)
    assert response.status_code == 200, response.text
    return response.json()


async def _ask_lieutenant(
    api_session: AsyncSession, client_as: Callable[[str], AsyncClient]
) -> tuple[WantedItem, dict[str, Any]]:
    want = await _lieutenant_world(api_session)
    admin = client_as("craig")
    [proposal] = (await admin.get("/api/v1/needs-you/reviews/want-proposals")).json()
    response = await admin.post("/api/v1/needs-you/reviews", json=proposal)
    assert response.status_code == 200, response.text
    return want, response.json()


async def _answer(
    client_as: Callable[[str], AsyncClient], review: dict[str, Any], answer: str, revision: int = 1
) -> dict[str, Any]:
    path = f"/api/v1/needs-you/reviews/{review['id']}/answer"
    response = await client_as("mark").post(path, json={"revision": revision, "answer": answer})
    assert response.status_code == 200, response.text
    return response.json()


async def _on_needs_you(client_as: Callable[[str], AsyncClient], name: str) -> set[str]:
    return {r["id"] for r in (await client_as(name).get("/api/v1/needs-you")).json()["reviews"]}


async def _status(client_as: Callable[[str], AsyncClient], review: dict[str, Any]) -> str:
    response = await client_as("craig").get(f"/api/v1/needs-you/reviews/{review['id']}")
    assert response.status_code == 200, response.text
    status: str = response.json()["status"]
    return status


async def test_an_answer_naming_the_want_s_film_resolves_it_and_it_leaves_needs_you(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
) -> None:
    """Dead Man's Shoes: answered 1940, the want already the 1940 film. Nothing needed changing."""
    review = await _ask_shoes(client_as)
    assert review["id"] in await _on_needs_you(client_as, "craig")

    answered = await _answer(client_as, review, "1940")
    assert answered["status"] == "resolved" and answered["answer"] == "1940"
    assert not answered["canAnswer"]
    # It leaves Needs you for both people, the admin's "Apply …'s answer" with it.
    assert review["id"] not in await _on_needs_you(client_as, "craig")
    assert review["id"] not in await _on_needs_you(client_as, "mark")
    # The question and its answer are still there to read, the row kept as it was.
    listed = (await client_as("mark").get("/api/v1/needs-you/reviews")).json()
    [kept] = [r for r in listed if r["id"] == review["id"]]
    assert kept["status"] == "resolved" and kept["answer"] == "1940"
    row = await api_session.get(AssignedReview, uuid.UUID(review["id"]))
    assert row is not None and row.deleted_at is None and row.answer == "1940"


async def test_an_answer_naming_another_film_stays_the_admin_s_until_the_want_is_that_film(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
) -> None:
    """Bad Lieutenant: 1992 on the 2009 film's want waits; once the want is 1992, it clears."""
    want, review = await _ask_lieutenant(api_session, client_as)
    answered = await _answer(client_as, review, "1992")
    assert answered["status"] == "answered"
    assert review["id"] in await _on_needs_you(client_as, "craig")

    movie = await api_session.get(Movie, want.movie_id)
    assert movie is not None
    # A changed record that does not name the answer's film stays changed.
    movie.year = 2010
    await api_session.flush()
    assert await _status(client_as, review) == "changed"
    assert review["id"] in await _on_needs_you(client_as, "craig")

    # The want is now the film the answer names: resolved, though the record changed.
    movie.year = 1992
    await api_session.flush()
    assert await _status(client_as, review) == "resolved"
    assert review["id"] not in await _on_needs_you(client_as, "craig")

    # Back to the 2009 film, and the 1992 answer is the admin's to apply again.
    movie.year = 2009
    await api_session.flush()
    assert await _status(client_as, review) == "answered"


async def test_an_answer_naming_the_want_s_own_film_resolves_it(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
) -> None:
    _want, review = await _ask_lieutenant(api_session, client_as)
    assert (await _answer(client_as, review, "2009"))["status"] == "resolved"


async def test_unsure_or_no_answer_never_resolves(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
) -> None:
    review = await _ask_shoes(client_as)
    assert await _status(client_as, review) == "open"
    unsure = await _answer(client_as, review, "unsure")
    assert unsure["status"] == "open" and unsure["canAnswer"]
    assert review["id"] in await _on_needs_you(client_as, "mark")


async def test_a_resolved_question_still_hides_listings_that_name_no_year(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
) -> None:
    """The question row is what makes a want's title two films', so resolving it hides as before."""
    review = await _ask_shoes(client_as)
    assert (await _answer(client_as, review, "1940"))["status"] == "resolved"
    want_id = uuid.UUID(review["targetId"])
    want = await api_session.get(WantedItem, want_id)
    assert want is not None

    assert want_id in await wants_asked(api_session)
    listing = await _listing(
        api_session, want, await _saved_shop(api_session, "Second Sight"), SHOES
    )
    judged = await rejudge_stored(api_session)
    assert judged.by_want == {want_id: 1}
    await api_session.refresh(listing)
    assert listing.another_film == SHARED_TITLE
    stored = await api_session.get(PriceCheck, listing.id)
    assert stored is not None and stored.another_film == SHARED_TITLE
    # Asked, so the daily check does not raise it again.
    assert await check_wants_naming_another_film(api_session, utcnow()) == []
