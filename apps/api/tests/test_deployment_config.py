"""Static checks for the deploy spine's failure-sensitive settings."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_container_migrates_before_starting_the_api() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    command = next(line for line in dockerfile.splitlines() if line.startswith("CMD "))
    assert "alembic upgrade head && exec uvicorn" in command


def test_railway_iac_waits_for_database_readiness() -> None:
    railway = (REPO_ROOT / ".railway" / "railway.ts").read_text(encoding="utf-8")
    assert "dockerfilePath: 'Dockerfile'" in railway
    assert "healthcheckPath: '/api/v1/health/ready'" in railway
    assert "restartPolicyType: 'ON_FAILURE'" in railway
    assert "DATABASE_URL: preserve()" in railway


def test_vercel_headers_preserve_future_browser_features() -> None:
    config = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    headers = {item["key"]: item["value"] for item in config["headers"][0]["headers"]}

    # Batch X8 (DS44-07) narrowed `connect-src` to the one API host and dropped Supabase,
    # which the app left (#17); this asserted the wildcards it replaced.
    csp = headers["Content-Security-Policy"]
    assert "https://api-production-a8fe.up.railway.app" in csp
    assert "*.up.railway.app" not in csp and "supabase" not in csp
    assert "camera=(self)" in headers["Permissions-Policy"]
    assert "microphone=(self)" in headers["Permissions-Policy"]


def test_the_container_can_run_the_cron_commands() -> None:
    """`OWNER-ACTIONS.md` gives Railway two start commands; this is what makes them work.

    CI never builds the image (`AGENTS.md`: "a Dockerfile regression surfaces at deploy
    time"), so the contract those commands depend on is asserted here instead — a moved
    `WORKDIR`, a dropped `PYTHONPATH` or a narrower `COPY` would break the two crons
    silently, and the first sign would be a scrape that never ran.
    """
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "WORKDIR /app" in dockerfile
    assert "PYTHONPATH=/app" in dockerfile
    # `src.scripts.*` has to be importable, which means the whole package is copied —
    # not just the modules uvicorn happens to reach.
    assert "COPY apps/api/src/ ./src/" in dockerfile

    for module in ("daily_scrape", "run_reminders", "spec_backfill", "value_collection"):
        assert (REPO_ROOT / "apps" / "api" / "src" / "scripts" / f"{module}.py").is_file()
        # The command in OWNER-ACTIONS.md, spelled out so the two cannot drift apart.
        assert f"python -m src.scripts.{module}" in (REPO_ROOT / "OWNER-ACTIONS.md").read_text(
            encoding="utf-8"
        )


def _service_block(railway: str, name: str) -> str:
    start = railway.index(f"service('{name}', {{")
    return railway[start : railway.index("\n  })\n", start)]


def test_the_collection_is_re_priced_every_fortnight() -> None:
    """Batch U4 — `DECISIONS.md` #222, #223.

    Craig chose every fortnight over every night. Two mornings each time, because the whole
    collection falls due together and a day's eBay share prices about half of it.
    """
    railway = (REPO_ROOT / ".railway" / "railway.ts").read_text(encoding="utf-8")
    values = _service_block(railway, "cron-values")

    assert "cronSchedule: '0 4 1,2,15,16 * *'" in values
    assert "startCommand: 'python -m src.scripts.value_collection'" in values
    assert "restartPolicyType: 'NEVER'" in values
    # The keyset by reference from `api`, as `cron-ebay` takes it: one copy of each secret.
    assert "EBAY_CLIENT_ID: api.env.EBAY_CLIENT_ID" in values
    assert "EBAY_CLIENT_SECRET: api.env.EBAY_CLIENT_SECRET" in values
    assert "...cronDefaults.env" in values
    # Declared is not deployed: a service left out of the project is never created.
    assert "resources: [api, scrape, reminders, specs, ebay, values]" in railway
