"""AE4's migration: the Omniplex's frozen row matches the venue the code reads, and stays off."""

import importlib.util
from pathlib import Path

from sqlalchemy import text

from src.services.cinemas.venues import BY_SLUG
from tests.test_completion_sets import api_session as api_session


def _migration():
    path = Path(__file__).parents[1] / "migrations/versions/076_omniplex_venue.py"
    spec = importlib.util.spec_from_file_location("omniplex_venue_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_frozen_row_is_the_venue_the_code_reads():
    row = _migration().OMNIPLEX
    venue = BY_SLUG["omniplex-glasgow-renfrew-street"]
    assert row["id"] == venue.id
    assert (row["slug"], row["name"], row["source"], row["source_venue_id"]) == (
        venue.slug,
        venue.name,
        venue.source,
        venue.source_id,
    )
    assert (row["programme_url"], row["official_url"]) == (venue.programme_url, venue.official_url)


async def test_the_omniplex_is_in_the_database_and_switched_off(api_session):
    found = (
        await api_session.execute(
            text(
                "SELECT slug, collection_enabled FROM cinema_venues WHERE id = :id",
            ),
            {"id": str(BY_SLUG["omniplex-glasgow-renfrew-street"].id)},
        )
    ).one()
    assert tuple(found) == ("omniplex-glasgow-renfrew-street", False)
    assert await api_session.scalar(text("SELECT count(*) FROM cinema_venues")) == 10
