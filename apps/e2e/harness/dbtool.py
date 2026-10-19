"""Database housekeeping for the E2E harness. Throwaway servers only.

usage: dbtool.py <admin-url> <command> [args]
  fresh <db>               drop it if there, create it empty
  clone <template> <db>    drop <db> if there, copy <template> into it
  exists <db>              exit 0 if it exists, 1 if not
  url <db>                 print the URL for <db> on the same server
  sql <db> <statement>     run one statement (no result printed)
  scalar <db> <statement>  run one query and print its first column

The admin URL must name a local server: a socket directory, localhost or 127.0.0.1. Anything
that looks like Neon, Railway or another hosted database is refused before connecting.
"""

from __future__ import annotations

import sys
from urllib.parse import urlsplit, urlunsplit

import psycopg2
from psycopg2 import sql


def refuse_unless_local(url: str) -> None:
    lowered = url.lower()
    if any(word in lowered for word in ("neon", "railway", "supabase", "amazonaws", "azure")):
        raise SystemExit("refusing: that looks like a hosted database")
    parts = urlsplit(url)
    host = parts.hostname or ""
    if "host=" not in (parts.query or "") and host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit(f"refusing: host {host!r} is not local")


def with_database(url: str, database: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + database, parts.query, parts.fragment))


def connect(url: str, database: str):  # type: ignore[no-untyped-def]
    conn = psycopg2.connect(with_database(url, database))
    conn.autocommit = True
    return conn


def drop_if_there(cur, database: str) -> None:  # type: ignore[no-untyped-def]
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (database,),
    )
    cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


def main(argv: list[str]) -> int:
    admin, command, *args = argv
    refuse_unless_local(admin)
    if command == "url":
        print(with_database(admin, args[0]))
        return 0
    if command in {"sql", "scalar"}:
        conn = connect(admin, args[0])
        with conn.cursor() as cur:
            cur.execute(args[1])
            if command == "scalar":
                row = cur.fetchone()
                print("" if row is None else row[0])
        conn.close()
        return 0
    conn = connect(admin, "postgres")
    with conn.cursor() as cur:
        if command == "exists":
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (args[0],))
            return 0 if cur.fetchone() else 1
        if command == "fresh":
            drop_if_there(cur, args[0])
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(args[0])))
            return 0
        if command == "clone":
            template, database = args
            drop_if_there(cur, database)
            drop_conns = "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()"
            cur.execute(drop_conns, (template,))
            cur.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    sql.Identifier(database), sql.Identifier(template)
                )
            )
            return 0
    raise SystemExit(f"unknown command {command!r}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
