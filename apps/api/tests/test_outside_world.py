"""The fake outside world's own guarantees — Batch 38.

The end-to-end suite and the cron-job cases are only worth running if nothing in them can
reach a real service or a real database. These cases start a Python process the way the suite
does (``apps/e2e/fakes`` on the path, ``MCU_OUTSIDE_WORLD=1``) and try to leave it.

They need no database: the code that arms the fake only reads the *name* of the database URL.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FAKES = REPO / "apps" / "e2e" / "fakes"
API = REPO / "apps" / "api"


def run(code: str, tmp_path: Path, database_url: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": f"{API}:{FAKES}",
        "MCU_OUTSIDE_WORLD": "1",
        "OUTSIDE_WORLD_DIR": str(tmp_path),
        "DATABASE_URL": database_url,
    }
    return subprocess.run(  # noqa: S603 - fixed interpreter, code from this file
        [sys.executable, "-c", textwrap.dedent(code)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def logged(tmp_path: Path) -> list[dict[str, object]]:
    path = tmp_path / "log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


LOCAL = "postgresql://postgres:postgres@localhost:5432/mcu_test"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@ep-cool-name-123.eu-west-2.aws.neon.tech/neondb?sslmode=require",
        "postgresql://postgres:p@containers-us-west-1.railway.app:5432/railway",
        "postgresql://u:p@db.example.com:5432/app",
    ],
)
def test_it_refuses_to_arm_against_a_database_that_is_not_a_throwaway(
    tmp_path: Path, url: str
) -> None:
    done = run("print('started')", tmp_path, url)
    assert done.returncode != 0
    assert "started" not in done.stdout
    assert "throwaway" in done.stderr or "refuses database host" in done.stderr


def test_it_arms_against_a_local_database(tmp_path: Path) -> None:
    done = run("print('started')", tmp_path, LOCAL)
    assert done.returncode == 0, done.stderr
    assert "started" in done.stdout


def test_a_call_to_a_host_nobody_faked_fails_and_is_written_down(tmp_path: Path) -> None:
    done = run(
        """
        import asyncio, httpx
        async def go():
            async with httpx.AsyncClient() as client:
                try:
                    await client.get("https://example.invalid/anything")
                except httpx.ConnectError as exc:
                    print("blocked:", exc)
        asyncio.run(go())
        """,
        tmp_path,
        LOCAL,
    )
    assert done.returncode == 0, done.stderr
    assert "blocked" in done.stdout
    assert [e["host"] for e in logged(tmp_path) if e["kind"] == "unfaked"] == ["example.invalid"]


def test_the_model_sdks_own_http_library_is_covered_too(tmp_path: Path) -> None:
    """The ``anthropic`` SDK brings its own ``httpx2``. Patching ``httpx`` alone let a real
    request out to api.anthropic.com during Batch 38's first chat case, so this is pinned."""
    done = run(
        """
        import asyncio, anthropic
        async def go():
            client = anthropic.AsyncAnthropic(api_key="not-a-key")
            reply = await client.messages.create(
                model="claude-sonnet-5", max_tokens=20,
                messages=[{"role": "user", "content": "hello"}],
            )
            print("answer:", reply.content[0].text)
        asyncio.run(go())
        """,
        tmp_path,
        LOCAL,
    )
    assert done.returncode == 0, done.stderr
    assert "answer: You asked: hello" in done.stdout
    hosts = {e["host"] for e in logged(tmp_path) if e["kind"] in {"call", "unfaked"}}
    assert hosts == {"api.anthropic.com"}
    assert not [e for e in logged(tmp_path) if e["kind"] == "unfaked"]


def test_a_second_message_carrying_an_sdk_only_field_is_refused_as_the_api_refuses_it(
    tmp_path: Path,
) -> None:
    """AI45-01: every follow-up failed with a 400 because a replayed text block carried
    ``parsed_output``. The recorded model says the same, so the e2e chat case can fail."""
    done = run(
        """
        import asyncio, anthropic
        async def go():
            client = anthropic.AsyncAnthropic(api_key="not-a-key")
            try:
                await client.messages.create(
                    model="claude-sonnet-5", max_tokens=20,
                    messages=[
                        {"role": "user", "content": "one"},
                        {"role": "assistant", "content": [
                            {"type": "text", "text": "answer", "parsed_output": None}]},
                        {"role": "user", "content": "two"},
                    ],
                )
            except anthropic.BadRequestError as exc:
                print("refused:", exc.status_code)
        asyncio.run(go())
        """,
        tmp_path,
        LOCAL,
    )
    assert done.returncode == 0, done.stderr
    assert "refused: 400" in done.stdout


def test_nothing_gets_out_by_a_raw_socket_or_a_name_lookup(tmp_path: Path) -> None:
    done = run(
        """
        import socket
        for attempt in (
            lambda: socket.create_connection(("192.0.2.1", 80), timeout=1),
            lambda: socket.getaddrinfo("example.invalid", 80),
        ):
            try:
                attempt()
            except OSError as exc:
                print("blocked:", type(exc).__name__)
        """,
        tmp_path,
        LOCAL,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.count("blocked:") == 2
    assert len([e for e in logged(tmp_path) if e["kind"] == "unfaked"]) >= 2


def test_recorded_model_tool_ids_are_unique_across_requests(tmp_path: Path) -> None:
    """Two chats must not collide on the real database's unique tool-use constraint."""
    (tmp_path / "scenario.json").write_text(
        json.dumps(
            {
                "anthropic": {
                    "rules": [
                        {
                            "lastUserContains": "tool fixture",
                            "toolUse": {
                                "name": "log_watch",
                                "input": {"title": "The Quiet Engine"},
                            },
                        }
                    ]
                }
            }
        )
    )
    done = run(
        """
        import asyncio, anthropic
        async def go():
            client = anthropic.AsyncAnthropic(api_key="not-a-key")
            ids = []
            for streaming in (False, True):
                for _ in range(2):
                    args = dict(model="claude-sonnet-5", max_tokens=100,
                                messages=[{"role": "user", "content": "tool fixture"}])
                    if streaming:
                        async with client.messages.stream(**args) as stream:
                            message = await stream.get_final_message()
                    else:
                        message = await client.messages.create(**args)
                    ids.extend(block.id for block in message.content if block.type == "tool_use")
            assert len(ids) == 4, ids
            assert len(set(ids)) == 4, ids
            assert all(value.startswith("toolu_e2e_") for value in ids)
            print("four unique tool uses")
        asyncio.run(go())
        """,
        tmp_path,
        LOCAL,
    )
    assert done.returncode == 0, done.stderr
    assert "four unique tool uses" in done.stdout
