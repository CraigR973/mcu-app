"""Read the live database from a cloud session, over HTTPS — read-only (`DECISIONS.md` #236).

A cloud container's proxy carries HTTPS only, so no Postgres connection leaves it, and
asyncpg cannot reach Neon from there. Neon also answers SQL over HTTPS, which this uses with
the read-only role's connection string in ``NEON_READONLY_URL``. The role and the variable
are made once on Craig's Mac: `docs/mac-cloud-setup.md`.

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.live_sql \\
        "SELECT count(*) FROM movies"
    … -m src.scripts.live_sql --explain "SELECT …"     # EXPLAIN (ANALYZE, BUFFERS)
    … -m src.scripts.live_sql --json "SELECT …"

**The role is what keeps it read-only.** It is set read-only, holds no write grant, and
cannot see the columns that hold credentials. The check here that a statement only reads is
a courtesy that fails before anything is sent, not the safeguard.

It never prints the connection string, and Neon's error messages are shown with the
password masked.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx

ENV_VAR = "NEON_READONLY_URL"
TIMEOUT = httpx.Timeout(60.0, connect=15.0)

_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
_READS = re.compile(r"(select|with|table|values|show)\b", re.IGNORECASE)
#: ``EXPLAIN``, its options, and ``ANALYZE``/``VERBOSE``: what it explains must read too,
#: because ``EXPLAIN ANALYZE`` runs the statement.
_EXPLAIN = re.compile(r"explain\b\s*(\([^)]*\)\s*)?((analy[sz]e|verbose)\b\s*)*", re.IGNORECASE)


class LiveSqlError(Exception):
    """What the person running it should read: Neon's refusal, or no endpoint answering."""


def reads_only(sql: str) -> bool:
    """One statement that only reads: ``SELECT``, ``WITH``, ``TABLE``, ``VALUES``, ``SHOW``,
    or an ``EXPLAIN`` of one of those."""
    body = _COMMENTS.sub(" ", sql).strip().rstrip(";").strip()
    if not body or ";" in body:
        return False
    explained = _EXPLAIN.match(body)
    if explained:
        body = body[explained.end() :]
    return bool(_READS.match(body))


def endpoints(url: str) -> list[str]:
    """Where Neon answers SQL over HTTPS for this connection string, in the order to try.

    The endpoint's own host first; then the regional ``api.`` host the serverless driver
    moved to. `docs/mac-cloud-setup.md` records which one answered from the Mac.
    """
    host = urlsplit(url).hostname
    if not host:
        raise LiveSqlError(f"{ENV_VAR} holds no host.")
    candidates = [f"https://{host}/sql"]
    _, _, region = host.partition(".")
    if region:
        candidates.append(f"https://api.{region}/sql")
    return candidates


def _masked(text: str, url: str) -> str:
    password = urlsplit(url).password
    return text.replace(password, "***") if password else text


def _refusal(response: httpx.Response, url: str) -> str:
    try:
        body = response.json()
        message = body.get("message") if isinstance(body, dict) else None
    except ValueError:
        message = None
    detail = message if isinstance(message, str) and message else response.text[:300]
    return _masked(f"Neon refused it (HTTP {response.status_code}): {detail}", url)


def run_query(
    sql: str, *, url: str, client: httpx.Client, params: Sequence[Any] = ()
) -> dict[str, Any]:
    """Send one statement and return Neon's answer: ``fields``, ``rows`` and ``command``."""
    headers = {
        "Neon-Connection-String": url,
        # Every value as Postgres prints it, so nothing is reinterpreted on the way.
        "Neon-Raw-Text-Output": "true",
        "Neon-Array-Mode": "false",
    }
    tried: list[str] = []
    for endpoint in endpoints(url):
        host = urlsplit(endpoint).hostname
        try:
            response = client.post(
                endpoint, headers=headers, json={"query": sql, "params": list(params)}
            )
        except httpx.TransportError as exc:
            tried.append(f"{host}: {type(exc).__name__}")
            continue
        if response.status_code == 404:
            tried.append(f"{host}: HTTP 404")
            continue
        if response.status_code != 200:
            raise LiveSqlError(_refusal(response, url))
        answer: dict[str, Any] = response.json()
        return answer
    raise LiveSqlError("No Neon SQL endpoint answered (" + "; ".join(tried) + ").")


def render(answer: Mapping[str, Any]) -> str:
    """Neon's answer as a plain table, or a plan's lines as Postgres prints them."""
    names = [str(field.get("name")) for field in answer.get("fields") or []]
    rows = answer.get("rows") or []
    if not names:
        return f"{answer.get('command') or 'OK'} {answer.get('rowCount') or 0}"
    cells = [
        ["" if row.get(name) is None else str(row.get(name)) for name in names] for row in rows
    ]
    if names == ["QUERY PLAN"]:
        return "\n".join(line for (line,) in cells)
    widths = [
        max([len(name), *(len(row[index]) for row in cells)]) for index, name in enumerate(names)
    ]
    lines = [
        " | ".join(name.ljust(width) for name, width in zip(names, widths, strict=True)),
        "-+-".join("-" * width for width in widths),
        *(
            " | ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True))
            for row in cells
        ),
        f"({len(rows)} row{'' if len(rows) == 1 else 's'})",
    ]
    return "\n".join(line.rstrip() for line in lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Read the live database over HTTPS with the read-only role (NEON_READONLY_URL)."
    )
    parser.add_argument("sql", help="one statement that only reads")
    parser.add_argument(
        "--explain", action="store_true", help="run it as EXPLAIN (ANALYZE, BUFFERS)"
    )
    parser.add_argument("--json", action="store_true", help="print Neon's rows as JSON")
    args = parser.parse_args(argv)

    url = (environ if environ is not None else os.environ).get(ENV_VAR, "")
    if not url:
        print(
            f"{ENV_VAR} is not set. docs/mac-cloud-setup.md makes it, once, on the Mac.",
            file=sys.stderr,
        )
        return 2
    if not reads_only(args.sql):
        print("Refused before sending: one statement that only reads, please.", file=sys.stderr)
        return 2
    sql = f"EXPLAIN (ANALYZE, BUFFERS) {args.sql}" if args.explain else args.sql

    try:
        with httpx.Client(timeout=TIMEOUT, transport=transport) as client:
            answer = run_query(sql, url=url, client=client)
    except LiveSqlError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(answer.get("rows") or [], indent=1) if args.json else render(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
