"""AC3 (#335): Craig's review list for programme films the rule could not settle alone."""

from dataclasses import replace

import pytest
from sqlalchemy import select

from src.models.admin_action import AdminAction
from src.models.cinema import CinemaFilm, CinemaScreening
from src.routers import cinemas as cinemas_router
from src.services.cinemas import store
from tests.test_cinemas import DAY, NOW, VENUE, enable, looked_up, run, showing, snapshot
from tests.test_cinemas import clock as clock
from tests.test_collection_write_api import admin as admin
from tests.test_collection_write_api import api_session as api_session
from tests.test_collection_write_api import client as client
from tests.test_collection_write_api import overrides as overrides
from tests.test_collection_write_api import viewer as viewer
from tests.test_collection_write_api import viewer_client as viewer_client

assert run  # the fixture, imported for its name

URL = "/api/v1/cinemas/review"


@pytest.fixture(autouse=True)
def review_clock(monkeypatch):
    monkeypatch.setattr(cinemas_router, "utcnow", lambda: NOW)


async def _classic(api_session, run):
    """Rocky listed twice by a source that keys each showing, with nothing but its title: the
    1976 film and a 2025 namesake both fit, so the rule sends it to Craig."""
    first = showing("rocky-1", film_key="showing:1", title="Rocky")
    second = showing("rocky-2", film_key="showing:2", title="Rocky")
    lookups = {}
    for row in (first, second):
        record = looked_up(row, tmdb_id=1366, released="1976-11-21", uk=("1977-03-31",))
        ((key, value),) = record.items()
        namesake = value.candidates[0].model_copy(
            update={"tmdb_id": 9, "primary_release_date": None, "gb_theatrical": []}
        )
        lookups[key] = value.model_copy(update={"candidates": [*value.candidates, namesake]})
    await store.promote(api_session, VENUE, snapshot(first, second), DAY, DAY, run.id, lookups)
    await enable(api_session)
    return first, second, lookups


async def test_a_film_in_review_is_one_item_with_its_candidates_for_craig_only(
    api_session, run, client, viewer_client
):
    await _classic(api_session, run)
    response = await client.get(URL)
    assert response.status_code == 200, response.text
    [item] = [i for i in response.json()["items"] if i["title"] == "Rocky"]
    assert item["sourceTitles"] == ["Rocky"] and item["futureShowings"] == 2
    assert item["reason"] == "the title matches, but nothing else agrees"
    assert [c["tmdbId"] for c in item["candidates"]] == [1366, 9]
    assert item["candidates"][0]["year"] == 1976
    assert (await viewer_client.get(URL)).status_code == 403


async def test_choosing_a_film_links_every_row_relabels_and_is_audited(api_session, run, client):
    await _classic(api_session, run)
    [item] = [i for i in (await client.get(URL)).json()["items"] if i["title"] == "Rocky"]
    response = await client.post(f"{URL}/{item['key']}", json={"tmdbId": 1366})
    assert response.status_code == 200, response.text
    assert all(i["key"] != item["key"] for i in response.json()["items"])
    films = (await api_session.scalars(select(CinemaFilm).where(CinemaFilm.title == "Rocky"))).all()
    assert {f.identity_status for f in films} == {"verified"}
    assert {f.evidence["tmdbId"] for f in films} == {1366}
    showings = (
        await api_session.scalars(
            select(CinemaScreening).where(CinemaScreening.film_id.in_([f.id for f in films]))
        )
    ).all()
    assert {s.release_category for s in showings} == {"olderFilm"}
    assert {s.category_evidence["runReason"] for s in showings} == {"UK release 1977 · rerun"}
    audit = await api_session.scalar(
        select(AdminAction).where(AdminAction.target_table == "cinema_films")
    )
    assert audit is not None and audit.changes["decision"] == {"tmdbId": 1366}


async def test_the_decision_survives_the_daily_run_until_the_listing_changes(
    api_session, run, client
):
    first, second, lookups = await _classic(api_session, run)
    [item] = [i for i in (await client.get(URL)).json()["items"] if i["title"] == "Rocky"]
    await client.post(f"{URL}/{item['key']}", json={"tmdbId": 1366})
    await store.promote(api_session, VENUE, snapshot(first, second), DAY, DAY, run.id, lookups)
    film = await api_session.scalar(
        select(CinemaFilm).where(CinemaFilm.source_key == first.film_key)
    )
    assert film.identity_status == "verified" and film.evidence["identity"]["corroboration"] == [
        "Craig's review"
    ]
    # A new title is a new question.
    renamed = replace(first, title="Rocky (Director's Cut)")
    await store.promote(api_session, VENUE, snapshot(renamed, second), DAY, DAY, run.id)
    assert film.identity_status != "verified" and "reviewed" not in film.evidence


async def test_not_a_film_and_choices_it_was_never_offered(api_session, run, client):
    await _classic(api_session, run)
    [item] = [i for i in (await client.get(URL)).json()["items"] if i["title"] == "Rocky"]
    assert (await client.post(f"{URL}/{item['key']}", json={"tmdbId": 424242})).status_code == 422
    assert (await client.post(f"{URL}/{item['key']}", json={})).status_code == 422
    assert (
        await client.post(f"{URL}/{item['key']}", json={"tmdbId": 1366, "notAFilm": True})
    ).status_code == 422
    assert (
        await client.post(f"{URL}/0000000000000000", json={"notAFilm": True})
    ).status_code == 404
    response = await client.post(f"{URL}/{item['key']}", json={"notAFilm": True})
    assert response.status_code == 200
    films = (await api_session.scalars(select(CinemaFilm).where(CinemaFilm.title == "Rocky"))).all()
    assert {f.identity_status for f in films} == {"event"}
    showings = (
        await api_session.scalars(
            select(CinemaScreening).where(CinemaScreening.film_id.in_([f.id for f in films]))
        )
    ).all()
    assert {s.release_category for s in showings} == {"unclassified"}
