"""AD1: exact private questions, honest observations and stale-target protection on Postgres."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.assigned_review import AssignedReview
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.wanted import WantedItem
from src.services import assigned_reviews as service
from tests.test_needs_you_api import api_session as api_session
from tests.test_needs_you_api import client_as as client_as
from tests.test_needs_you_api import people as people


@pytest_asyncio.fixture
async def review_world(
    api_session: AsyncSession, people: dict[str, Profile], monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    movies = {}
    for kind, title, year in [
        ("titanic_disc", "Titanic", 1953),
        ("wanted_identity", "Dead Man's Shoes", 1940),
        ("shetland_series", "Shetland - Series 5", None),
    ]:
        movie = Movie(
            id=uuid.uuid4(), title=title, original_title=title, year=year, media_type="film"
        )
        api_session.add(movie)
        await api_session.flush()
        movie.tmdb_id = {"titanic_disc": 16535, "wanted_identity": 416920}.get(kind)
        movies[kind] = movie.id
        if kind == "wanted_identity":
            target = WantedItem(movie_id=movie.id, is_active=True)
        else:
            item = CollectionItem(
                id=uuid.uuid4(),
                movie_id=movie.id,
                formats=["blu_ray"],
                condition="good",
                listing_status="in_collection",
            )
            api_session.add(item)
            await api_session.flush()
            target = (
                item
                if kind == "shetland_series"
                else IdentifyDoubt(
                    movie_id=movie.id,
                    collection_item_id=item.id,
                    source="specs",
                    status="open",
                    identified_as=16535,
                    proposed_tmdb_id=597,
                    note="Disc page names 1997",
                )
            )
        api_session.add(target)
        await api_session.flush()
        targets[kind] = target
    monkeypatch.setattr(service, "MARK_REVIEW_MOVIES", movies)
    monkeypatch.setattr(service, "MARK_PROFILE_ID", people["mark"].id)
    return targets


async def assigned(client_as: Callable[[str], AsyncClient]) -> list[dict[str, Any]]:
    admin = client_as("craig")
    response = await admin.get("/api/v1/needs-you/reviews/proposals")
    assert response.status_code == 200, response.text
    assert len(response.json()) == 3
    rows = []
    for proposal in response.json():
        response = await admin.post("/api/v1/needs-you/reviews", json=proposal)
        assert response.status_code == 200, response.text
        rows.append(response.json())
    return rows


async def test_three_private_reviews_and_no_cross_profile_access(
    review_world: dict[str, Any], client_as: Callable[[str], AsyncClient]
) -> None:
    rows = await assigned(client_as)
    mark, admin, third = [client_as(name) for name in ("mark", "craig", "third")]
    mark_home = (await mark.get("/api/v1/needs-you")).json()
    assert {r["id"] for r in mark_home["reviews"]} == {r["id"] for r in rows}
    assert (await third.get("/api/v1/needs-you")).json()["reviews"] == []
    assert (await third.get("/api/v1/needs-you/reviews")).json() == []
    assert (
        (await admin.get("/api/v1/needs-you/reviews?allAssignees=true"))
        .json()[0]["assigneeName"]
        .startswith("AC1 Mark")
    )
    for viewer in (mark, third):
        assert (await viewer.get("/api/v1/needs-you/reviews/proposals")).status_code == 403
        assert (await viewer.get("/api/v1/needs-you/reviews?allAssignees=true")).status_code == 403
    path = f"/api/v1/needs-you/reviews/{rows[0]['id']}"
    assert (await third.get(path)).status_code == 404
    assert (
        await third.post(path + "/answer", json={"revision": 1, "answer": "1953"})
    ).status_code == 404
    assert (
        await admin.post(path + "/answer", json={"revision": 1, "answer": "1953"})
    ).status_code == 403
    assert (
        await third.patch(
            path + "/assignee", json={"revision": 1, "assignedTo": rows[0]["assignedTo"]}
        )
    ).status_code == 403


async def test_observations_leave_uncertainty_open_without_identity_writes(
    review_world: dict[str, Any], api_session: AsyncSession, client_as: Callable[[str], AsyncClient]
) -> None:
    [titanic, wanted, shetland] = await assigned(client_as)
    mark = client_as("mark")
    path = f"/api/v1/needs-you/reviews/{titanic['id']}/answer"
    unsure = await mark.post(path, json={"revision": 1, "answer": "unsure"})
    assert unsure.status_code == 200
    assert unsure.json()["status"] == "open"
    assert unsure.json()["revision"] == 2
    answer = await mark.post(path, json={"revision": 2, "answer": "1997"})
    assert answer.json()["status"] == "answered"
    assert answer.json()["revision"] == 3
    assert (await mark.post(path, json={"revision": 2, "answer": "1997"})).json()["revision"] == 3
    assert (await mark.post(path, json={"revision": 2, "answer": "1953"})).status_code == 409
    assert (await mark.post(path, json={"revision": 3, "answer": "2004"})).status_code == 422
    assert review_world["titanic_disc"].status == "open"
    disc = await api_session.get(CollectionItem, review_world["titanic_disc"].collection_item_id)
    assert disc is not None
    movie = await api_session.get(Movie, disc.movie_id)
    assert movie is not None and movie.year == 1953
    history = (
        await api_session.scalars(
            select(AdminAction)
            .where(AdminAction.target_id == titanic["id"])
            .order_by(AdminAction.created_at)
        )
    ).all()
    assert len(history) == 3  # Create, unsure, 1997; lost-response retry adds no event.
    assert history[-1].changes is not None and history[-1].changes["answer"]["to"] == "1997"
    assert len((await mark.get("/api/v1/needs-you")).json()["reviews"]) == 3


async def test_assignment_retry_does_not_duplicate_or_reset_answer(
    review_world: dict[str, Any], api_session: AsyncSession, client_as: Callable[[str], AsyncClient]
) -> None:
    await assigned(client_as)
    rows = await assigned(client_as)
    assert await api_session.scalar(select(func.count()).select_from(AssignedReview)) == 3
    mark = client_as("mark")
    await mark.post(
        f"/api/v1/needs-you/reviews/{rows[0]['id']}/answer", json={"revision": 1, "answer": "1953"}
    )
    repeated = await assigned(client_as)
    assert repeated[0]["answer"] == "1953"
    assert repeated[0]["revision"] == 2


@pytest.mark.parametrize("kind", ["titanic_disc", "wanted_identity", "shetland_series"])
async def test_changed_targets_refuse_new_answers(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
    kind: str,
) -> None:
    rows = await assigned(client_as)
    row = next(row for row in rows if row["kind"] == kind)
    movie = await api_session.get(Movie, uuid.UUID(row["movieId"]))
    assert movie is not None
    movie.title = "Someone corrected this identity"
    await api_session.flush()
    response = await client_as("mark").post(
        f"/api/v1/needs-you/reviews/{row['id']}/answer", json={"revision": 1, "answer": "unsure"}
    )
    assert response.status_code == 409
    current = (await client_as("mark").get(f"/api/v1/needs-you/reviews/{row['id']}")).json()
    assert current["status"] == "changed" and not current["canAnswer"]
    assert current["answer"] is None


async def test_domain_resolution_clears_home_but_preserves_review_history(
    review_world: dict[str, Any], api_session: AsyncSession, client_as: Callable[[str], AsyncClient]
) -> None:
    rows = await assigned(client_as)
    doubt = review_world["titanic_disc"]
    doubt.status = "kept"
    doubt.decided_utc = utcnow()
    series_copy = review_world["shetland_series"]
    series = Movie(title="Shetland", tmdb_tv_id=46923, media_type="tv")
    api_session.add(series)
    await api_session.flush()
    series_copy.movie_id = series.id
    await api_session.flush()
    mark = client_as("mark")
    assert len((await mark.get("/api/v1/needs-you")).json()["reviews"]) == 1
    all_rows = (await mark.get("/api/v1/needs-you/reviews")).json()
    assert len(all_rows) == 3
    assert [r["status"] for r in all_rows].count("resolved") == 2
    response = await mark.post(
        f"/api/v1/needs-you/reviews/{rows[0]['id']}/answer", json={"revision": 1, "answer": "1953"}
    )
    assert response.status_code == 409


async def test_reassignment_preserves_old_observation_in_audit_and_revokes_access(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    [row, *_] = await assigned(client_as)
    path = f"/api/v1/needs-you/reviews/{row['id']}"
    await client_as("mark").post(path + "/answer", json={"revision": 1, "answer": "1997"})
    request = {"revision": 2, "assignedTo": str(people["third"].id)}
    result = await client_as("craig").patch(path + "/assignee", json=request)
    assert result.status_code == 200, result.text
    assert result.json()["revision"] == 3 and result.json()["answer"] is None
    assert (await client_as("mark").get(path)).status_code == 404
    assert (await client_as("third").get(path)).json()["canAnswer"]
    assert (await client_as("craig").patch(path + "/assignee", json=request)).json()[
        "revision"
    ] == 3
    audits = (
        await api_session.scalars(select(AdminAction).where(AdminAction.target_id == row["id"]))
    ).all()
    assert any(a.changes and a.changes.get("previousAnswer") == "1997" for a in audits)


async def test_ambiguous_manifest_is_not_guessed(
    review_world: dict[str, Any], api_session: AsyncSession, client_as: Callable[[str], AsyncClient]
) -> None:
    copy = review_world["shetland_series"]
    api_session.add(CollectionItem(movie_id=copy.movie_id, formats=["dvd"], condition="good"))
    await api_session.flush()
    response = await client_as("craig").get("/api/v1/needs-you/reviews/proposals")
    assert response.status_code == 409
    assert await api_session.scalar(select(func.count()).select_from(AssignedReview)) == 0


async def test_deleted_film_preserves_question_without_a_broken_inspection_link(
    review_world: dict[str, Any],
    api_session: AsyncSession,
    client_as: Callable[[str], AsyncClient],
) -> None:
    rows = await assigned(client_as)
    row = next(row for row in rows if row["kind"] == "wanted_identity")
    movie = await api_session.get(Movie, uuid.UUID(row["movieId"]))
    assert movie is not None
    movie.deleted_at = utcnow()
    await api_session.flush()
    response = await client_as("mark").get(f"/api/v1/needs-you/reviews/{row['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "changed"
    assert response.json()["movieId"] is None
    assert not response.json()["canAnswer"]


async def test_the_shelf_keepers_read_each_other_s_reviews_but_answer_only_their_own(
    review_world: dict[str, Any],
    people: dict[str, Profile],
    client_as: Callable[[str], AsyncClient],
) -> None:
    """AE8 (#355): Craig and Mark read each other's open reviews, labelled by assignee, their
    own first; only the assignee answers; someone who keeps no shelves reads only their own."""
    rows = await assigned(client_as)
    mark, admin, third = [client_as(name) for name in ("mark", "craig", "third")]
    craig_home = (await admin.get("/api/v1/needs-you")).json()["reviews"]
    assert {r["id"] for r in craig_home} == {r["id"] for r in rows}
    assert all(r["canAnswer"] is False for r in craig_home)
    # One review moves to Craig: Mark still reads it, after his own, and cannot answer it.
    moved = rows[0]
    path = f"/api/v1/needs-you/reviews/{moved['id']}"
    response = await admin.patch(
        path + "/assignee",
        json={"revision": moved["revision"], "assignedTo": str(people["craig"].id)},
    )
    assert response.status_code == 200, response.text
    marks = (await mark.get("/api/v1/needs-you")).json()["reviews"]
    assert [r["id"] for r in marks][-1] == moved["id"]
    assert [r["canAnswer"] for r in marks] == [True] * (len(rows) - 1) + [False]
    detail = await mark.get(path)
    assert detail.status_code == 200, detail.text
    assert detail.json()["canAnswer"] is False
    answer = {"revision": detail.json()["revision"], "answer": "1953"}
    assert (await mark.post(path + "/answer", json=answer)).status_code == 404
    assert (await third.get(path)).status_code == 404
    assert (await third.get("/api/v1/needs-you")).json()["reviews"] == []
