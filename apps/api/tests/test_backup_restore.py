"""A copy taken through the backup role restores whole and holds no credential — Batch X4.

Postgres-backed, so it runs in CI. Two scratch databases on the test server: a source,
migrated to head *after* the ``mcu_backup`` role exists so migration 053 grants it as
production's does, holding a PIN hash, a refresh token, a movie-night invite link and a box
set that refers to another; and an empty target. The copy is taken through the role with the
command the weekly run uses, then restored with the drill's command.

**What this proves:** the role reads every table it should and no credential; the copy holds
no PIN hash, token or invite link; the restore migrates the target, loads every row, keeps
the copy's own timestamps (triggers off), fills a fresh invite link, and its counts match;
and a role that can read a PIN hash stops the copy.

**What it does not:** production. The first live copy and drill are a run of
``.github/workflows/backup.yml`` after the deploy (X4's close-out).
"""

from __future__ import annotations

import contextlib
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest

from src.config import Settings, psycopg2_dsn
from src.scripts.backup import migrate, run_dump, run_restore
from src.services.backup import BackupPolicyError, Manifest, dump

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="DATABASE_URL not set — Postgres-backed tests skipped"
)
ROLE_PASSWORD = "x4-test-" + uuid.uuid4().hex


def _url(database: str, *, user: str | None = None) -> str:
    """The test server's address, for another database or as another role."""
    assert DATABASE_URL is not None
    parts = urlsplit(psycopg2_dsn(Settings(database_url=DATABASE_URL).database_url))
    assert parts.hostname is None or not any(
        name in parts.hostname for name in ("neon", "railway")
    ), "these tests create and drop databases; never point them at a hosted one"
    netloc = parts.netloc
    if user is not None:
        netloc = f"{user}:{ROLE_PASSWORD}@{netloc.rsplit('@', 1)[-1]}"
    return urlunsplit((parts.scheme, netloc, f"/{database}", parts.query, ""))


@pytest.fixture
def scratch() -> Iterator[tuple[str, str]]:
    """Two empty databases and the backup role; all dropped again afterwards."""
    assert DATABASE_URL is not None
    home = urlsplit(psycopg2_dsn(Settings(database_url=DATABASE_URL).database_url)).path[1:]
    admin = psycopg2.connect(_url(home))
    admin.autocommit = True
    suffix = uuid.uuid4().hex[:8]
    names = (f"x4_source_{suffix}", f"x4_target_{suffix}")
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'mcu_backup'")
        made_role = cur.fetchone() is None
        verb = "CREATE" if made_role else "ALTER"
        cur.execute(f"{verb} ROLE mcu_backup LOGIN PASSWORD %s", (ROLE_PASSWORD,))
        for name in names:
            cur.execute(f'CREATE DATABASE "{name}"')
    try:
        yield names
    finally:
        with admin.cursor() as cur:
            for name in names:
                cur.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            if made_role:
                # Granted in another database on this server: harmless to keep.
                with contextlib.suppress(psycopg2.Error):
                    cur.execute("DROP ROLE mcu_backup")
        admin.close()


def _seed(url: str) -> None:
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("UPDATE profiles SET pin_hash = 'pin-hash-secret' WHERE display_name = 'Craig'")
        cur.execute("SELECT id FROM profiles WHERE display_name = 'Craig'")
        row = cur.fetchone()
        assert row is not None
        craig = row[0]
        heat, alien = uuid.uuid4(), uuid.uuid4()
        cur.execute(
            "INSERT INTO movies (id, title) VALUES (%s, 'Heat'), (%s, 'Alien')",
            (str(heat), str(alien)),
        )
        cur.execute(
            "INSERT INTO collection_items (id, movie_id, formats) VALUES (%s, %s, '[\"blu_ray\"]')",
            (str(uuid.uuid4()), str(heat)),
        )
        cur.execute(
            "INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at_utc, created_at_utc)"
            " VALUES (%s, %s, 'refresh-token-secret', now() + interval '1 day', now())",
            (str(uuid.uuid4()), craig),
        )
        cur.execute(
            "INSERT INTO movie_night_sessions (id, created_by, invite_token)"
            " VALUES (%s, %s, 'invite-token-secret')",
            (str(uuid.uuid4()), craig),
        )
        series = uuid.uuid4()
        cur.execute(
            "INSERT INTO box_sets (id, name) VALUES (%s, 'Alien Anthology')", (str(series),)
        )
        cur.execute(
            "INSERT INTO box_sets (id, name, series_id) VALUES (%s, 'Alien 4K', %s)",
            (str(uuid.uuid4()), str(series)),
        )


def _one(url: str, query: str) -> object:
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()
        assert row is not None
        return row[0]


def test_a_copy_restores_whole_and_holds_no_credential(
    scratch: tuple[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_name, target_name = scratch
    source, target = _url(source_name), _url(target_name)
    migrate(source, "head")
    _seed(source)
    copy = tmp_path / "copy"

    monkeypatch.setenv("BACKUP_DATABASE_URL", _url(source_name, user="mcu_backup"))
    assert run_dump(copy) == 0

    manifest = Manifest.read(copy)
    assert manifest.tables["movies"]["rows"] == 2
    assert manifest.tables["profiles"]["withheld"] == ["pin_hash"]
    assert manifest.tables["movie_night_sessions"]["withheld"] == ["invite_token"]
    assert "refresh_tokens" in manifest.withheld_tables
    assert "refresh_tokens" not in manifest.tables
    written = "".join(path.read_text() for path in (copy / "data").iterdir())
    for secret in ("pin-hash-secret", "refresh-token-secret", "invite-token-secret"):
        assert secret not in written
    assert not (copy / "data" / "refresh_tokens.csv").exists()

    monkeypatch.setenv("RESTORE_DATABASE_URL", target)
    # The drill's form: the copy must also be at the code's newest migration.
    assert run_restore(copy, expect_head=True) == 0

    for table in ("movies", "collection_items", "box_sets", "profiles", "movie_night_sessions"):
        query = f"SELECT count(*) FROM {table}"
        assert _one(target, query) == _one(source, query), table
    assert _one(target, "SELECT count(*) FROM refresh_tokens") == 0
    assert _one(target, "SELECT count(*) FROM profiles WHERE pin_hash IS NOT NULL") == 0
    invite = _one(target, "SELECT invite_token FROM movie_night_sessions")
    assert isinstance(invite, str) and len(invite) == 64 and invite != "invite-token-secret"
    assert (
        _one(
            target,
            "SELECT column_default FROM information_schema.columns"
            " WHERE table_name = 'movie_night_sessions' AND column_name = 'invite_token'",
        )
        is None
    )
    assert _one(target, "SELECT count(*) FROM box_sets WHERE series_id IS NOT NULL") == 1
    # Triggers were off while it loaded, so the copy's timestamps are the source's.
    stamp = "SELECT updated_at FROM collection_items"
    assert _one(target, stamp) == _one(source, stamp)


def test_a_role_that_can_read_a_pin_hash_stops_the_copy(
    scratch: tuple[str, str], tmp_path: Path
) -> None:
    source_name, _ = scratch
    source = _url(source_name)
    migrate(source, "head")
    with psycopg2.connect(source) as conn, conn.cursor() as cur:
        cur.execute("GRANT SELECT (pin_hash) ON profiles TO mcu_backup")

    conn = psycopg2.connect(_url(source_name, user="mcu_backup"))
    conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
    try:
        with conn.cursor() as cur, pytest.raises(BackupPolicyError, match="profiles.pin_hash"):
            dump(cur, tmp_path / "copy", role="mcu_backup")
    finally:
        conn.close()
