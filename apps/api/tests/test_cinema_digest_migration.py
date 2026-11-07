"""Run the frozen migration's real seed, grant and downgrade guard SQL on Postgres."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from src.models.cinema_digest import CinemaDigestDay, CinemaDigestFilm, CinemaDigestListing
from src.models.notification import Notification
from src.services.cinemas.venues import VENUES
from tests.test_cinema_digest import NOW, showing
from tests.test_collection_write_api import api_session as api_session


def statements(monkeypatch, method):
    path = Path(__file__).parents[1] / "migrations/versions/073_cinema_digest.py"
    spec = importlib.util.spec_from_file_location("digest_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql = []

    class Operations:
        def execute(self, value):
            sql.append(str(value))

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    monkeypatch.setattr(module, "op", Operations())
    getattr(module, method)()
    return sql


async def test_migration_seeds_current_verified_and_unmatched_listings_without_push(
    api_session, monkeypatch
):
    db = api_session
    await showing(db, VENUES[0], identity=1_950_006_001)
    await showing(db, VENUES[1], identity=1_950_006_002, status="unverified")
    for statement in statements(monkeypatch, "upgrade"):
        if "INSERT INTO cinema_digest_" in statement:
            await db.execute(text(statement))
    [film] = (await db.scalars(select(CinemaDigestFilm))).all()
    assert film.tmdb_id == 1_950_006_001 and film.baseline
    aliases = list((await db.scalars(select(CinemaDigestListing))).all())
    assert len(aliases) == 2 and all(alias.baseline for alias in aliases)
    assert sum(alias.film_id is None for alias in aliases) == 1
    assert (
        await db.scalar(
            select(func.count()).select_from(Notification).where(Notification.category == "cinemas")
        )
        == 0
    )


async def test_guarded_grants_present_and_absent_and_credentials_withheld(api_session, monkeypatch):
    db = api_session
    guards = [s for s in statements(monkeypatch, "upgrade") if "pg_roles" in s]
    for guard in guards:
        await db.execute(text(guard))
    for role in ("mcu_readonly", "mcu_backup"):
        if not await db.scalar(
            text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname=:role)"), {"role": role}
        ):
            # CREATE ROLE is transactional: other databases cannot see this test role.
            await db.execute(text(f"CREATE ROLE {role}"))
    for guard in guards:
        await db.execute(text(guard))
    for role in ("mcu_readonly", "mcu_backup"):
        assert await db.scalar(
            text("SELECT has_table_privilege(:role,'cinema_digest_deliveries','SELECT')"),
            {"role": role},
        )
        assert await db.scalar(
            text(
                "SELECT has_column_privilege(:role,'notification_preferences',"
                "'cinemas_enabled','SELECT')"
            ),
            {"role": role},
        )
        assert not await db.scalar(
            text("SELECT has_column_privilege(:role,'profiles','pin_hash','SELECT')"),
            {"role": role},
        )
        assert not await db.scalar(
            text("SELECT has_table_privilege(:role,'push_subscriptions','SELECT')"), {"role": role}
        )


async def test_populated_history_blocks_downgrade_without_deleting_it(api_session, monkeypatch):
    db = api_session
    db.add(CinemaDigestDay(local_date=NOW.date(), evaluated_at_utc=NOW, report={}))
    await db.flush()
    [guard] = statements(monkeypatch, "downgrade")
    with pytest.raises(DBAPIError, match="Retain cinema digest history"):
        async with db.begin_nested():
            await db.execute(text(guard))
    assert await db.scalar(select(func.count()).select_from(CinemaDigestDay)) == 1
