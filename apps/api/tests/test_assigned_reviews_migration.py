"""Real guarded grants and history-preserving downgrade, against disposable Postgres."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.test_assigned_reviews import assigned
from tests.test_assigned_reviews import review_world as review_world
from tests.test_needs_you_api import api_session as api_session
from tests.test_needs_you_api import client_as as client_as
from tests.test_needs_you_api import people as people


def statements(monkeypatch, method):
    path = Path(__file__).parents[1] / "migrations/versions/074_assigned_reviews.py"
    spec = importlib.util.spec_from_file_location("assigned_reviews_migration", path)
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


async def test_guarded_readonly_and_backup_grants_withhold_credentials(api_session, monkeypatch):
    db = api_session
    guards = [s for s in statements(monkeypatch, "upgrade") if "pg_roles" in s]
    assert len(guards) == 2
    for guard in guards:
        await db.execute(text(guard))  # Safe when a role does not exist.
    for role in ("mcu_readonly", "mcu_backup"):
        await db.execute(
            text(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') "
                f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$"
            )
        )
    for guard in guards:
        await db.execute(text(guard))
    for role in ("mcu_readonly", "mcu_backup"):
        assert await db.scalar(
            text("SELECT has_table_privilege(:role,'assigned_reviews','SELECT')"), {"role": role}
        )
        assert not await db.scalar(
            text("SELECT has_table_privilege(:role,'assigned_reviews','UPDATE')"), {"role": role}
        )
        assert not await db.scalar(
            text("SELECT has_column_privilege(:role,'profiles','pin_hash','SELECT')"),
            {"role": role},
        )


async def test_populated_downgrade_stops_instead_of_erasing_answers(
    review_world, client_as, api_session, monkeypatch
):
    await assigned(client_as)
    [guard] = statements(monkeypatch, "downgrade")
    with pytest.raises(DBAPIError, match="Assigned reviews exist"):
        async with api_session.begin_nested():
            await api_session.execute(text(guard))
    assert await api_session.scalar(text("SELECT count(*) FROM assigned_reviews")) == 3
