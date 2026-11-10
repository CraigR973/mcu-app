"""AE3's migration: guarded grants in one block, and a downgrade that keeps what people said."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.test_completion_exclusions import PIANO_BLUES, _eastwood
from tests.test_completion_sets import admin as admin
from tests.test_completion_sets import api_session as api_session
from tests.test_completion_sets import client as client
from tests.test_completion_sets import overrides as overrides
from tests.test_completion_sets import viewer as viewer


def statements(monkeypatch, method):
    path = Path(__file__).parents[1] / "migrations/versions/075_completion_exclusions.py"
    spec = importlib.util.spec_from_file_location("completion_exclusions_migration", path)
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


async def test_both_roles_are_granted_in_one_guarded_block(api_session, monkeypatch):
    db = api_session
    [guard] = [s for s in statements(monkeypatch, "upgrade") if "pg_roles" in s]
    assert "mcu_readonly" in guard and "mcu_backup" in guard
    await db.execute(text(guard))  # Safe when neither role exists.
    for role in ("mcu_readonly", "mcu_backup"):
        await db.execute(
            text(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') "
                f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$"
            )
        )
    await db.execute(text(guard))
    for role in ("mcu_readonly", "mcu_backup"):
        assert await db.scalar(
            text("SELECT has_table_privilege(:role,'completion_exclusions','SELECT')"),
            {"role": role},
        )
        assert not await db.scalar(
            text("SELECT has_table_privilege(:role,'completion_exclusions','INSERT')"),
            {"role": role},
        )


async def test_a_downgrade_with_rows_stops_instead_of_erasing_them(
    client, api_session, monkeypatch
):
    set_id = await _eastwood(api_session)
    response = await client.post(
        f"/api/v1/insights/completion/{set_id}/exclusions", json={"tmdbId": PIANO_BLUES}
    )
    assert response.status_code == 200, response.text
    [guard] = statements(monkeypatch, "downgrade")
    with pytest.raises(DBAPIError, match="downgrade 075 requires owner review"):
        async with api_session.begin_nested():
            await api_session.execute(text(guard))
    assert await api_session.scalar(text("SELECT count(*) FROM completion_exclusions")) == 1


async def test_the_clock_default_is_utc(api_session):
    default = await api_session.scalar(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'completion_exclusions' AND column_name = 'excluded_at_utc'"
        )
    )
    assert default is not None and "utc" in default
