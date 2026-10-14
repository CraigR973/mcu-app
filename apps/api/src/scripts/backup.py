"""Take a copy of the database, or restore one and check it — Batch X4 (DS44-03, #257).

``.github/workflows/backup.yml`` runs both, weekly and in the monthly drill. By hand::

    BACKUP_DATABASE_URL=... PYTHONPATH=apps/api \\
      apps/api/.venv/bin/python3.12 -m src.scripts.backup dump --out /tmp/copy

    RESTORE_DATABASE_URL=... PYTHONPATH=apps/api \\
      apps/api/.venv/bin/python3.12 -m src.scripts.backup restore --from /tmp/copy

``dump`` reads through ``BACKUP_DATABASE_URL`` (the ``mcu_backup`` role), in one read-only
snapshot, and exits 1 when the role can read a credential or cannot read a table it should.
``restore`` migrates the database at ``RESTORE_DATABASE_URL`` to the copy's revision with
Alembic, loads it, and exits 1 when any table's rows differ from the manifest. Both
addresses come from the environment, never the command line, so a password reaches neither
``ps`` nor the shell history; neither is ever printed.

Restoring production is ``docs/restore-runbook.md``: into a new Neon branch first, never
over the live database.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg2

from src.services.backup import BackupPolicyError, Manifest, dump, restore, summary

API_DIR = Path(__file__).resolve().parents[2]


def _connect(url: str, *, readonly: bool) -> psycopg2.extensions.connection:
    connection = psycopg2.connect(url)
    if readonly:
        connection.set_session(isolation_level="REPEATABLE READ", readonly=True)
    return connection


def run_dump(out: Path) -> int:
    url = os.environ.get("BACKUP_DATABASE_URL", "")
    if not url:
        print("BACKUP_DATABASE_URL is not set.", file=sys.stderr)
        return 1
    connection = _connect(url, readonly=True)
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT current_user")
            row = cur.fetchone()
            role = str(row[0]) if row else ""
            manifest = dump(cur, out, role=role)
        connection.rollback()
    except BackupPolicyError as exc:
        print(f"Not copied: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()
    print(f"Copied {summary(manifest)}.")
    return 0


def migrate(url: str, revision: str) -> None:
    """``alembic upgrade <revision>`` against ``url``, as CI's migration job runs it."""
    env = {
        **os.environ,
        "DATABASE_URL": url,
        "PYTHONPATH": str(API_DIR),
        "JWT_ACCESS_SECRET": os.environ.get("JWT_ACCESS_SECRET", "restore-" + "x" * 32),
        "JWT_REFRESH_SECRET": os.environ.get("JWT_REFRESH_SECRET", "restore-" + "y" * 32),
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "--config",
            str(API_DIR / "alembic.ini"),
            "upgrade",
            revision,
        ],
        check=True,
        env=env,
        cwd=API_DIR,
        stdout=subprocess.DEVNULL,
    )


def code_head() -> str:
    """The newest migration in this checkout."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(Config(str(API_DIR / "alembic.ini"))).get_current_head()
    return str(head)


def run_restore(source: Path, *, expect_head: bool = False) -> int:
    url = os.environ.get("RESTORE_DATABASE_URL", "")
    if not url:
        print("RESTORE_DATABASE_URL is not set.", file=sys.stderr)
        return 1
    manifest = Manifest.read(source)
    if expect_head and manifest.revision != code_head():
        # The drill's check that production is migrated to the code it runs. A restore of an
        # older copy into a new branch (the runbook) expects no such thing.
        print(
            f"The copy is at migration {manifest.revision}; the code's newest is {code_head()}.",
            file=sys.stderr,
        )
        return 1
    migrate(url, manifest.revision)
    connection = _connect(url, readonly=False)
    try:
        with connection.cursor() as cur:
            differences = restore(cur, source)
        if differences:
            connection.rollback()
            print("Restored rows differ from the copy:", file=sys.stderr)
            for line in differences:
                print(f"  {line}", file=sys.stderr)
            return 1
        connection.commit()
    except BackupPolicyError as exc:
        connection.rollback()
        print(f"Not restored: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()
    print(f"Restored and checked {summary(manifest)}; every table's rows match the copy.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    take = commands.add_parser("dump", help="copy the database through BACKUP_DATABASE_URL")
    take.add_argument("--out", type=Path, required=True)
    back = commands.add_parser("restore", help="load a copy into RESTORE_DATABASE_URL, check it")
    back.add_argument("--from", dest="source", type=Path, required=True)
    back.add_argument(
        "--expect-head",
        action="store_true",
        help="fail unless the copy is at this checkout's newest migration (the drill)",
    )
    args = parser.parse_args(argv)
    if args.command == "dump":
        return run_dump(args.out)
    return run_restore(args.source, expect_head=args.expect_head)


if __name__ == "__main__":
    raise SystemExit(main())
