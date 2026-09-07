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

    assert "https://*.supabase.co" in headers["Content-Security-Policy"]
    assert "https://*.up.railway.app" in headers["Content-Security-Policy"]
    assert "camera=(self)" in headers["Permissions-Policy"]
    assert "microphone=(self)" in headers["Permissions-Policy"]
