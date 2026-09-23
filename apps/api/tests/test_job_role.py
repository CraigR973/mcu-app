"""The scheduled jobs start without the web server's secrets — `DECISIONS.md` #204.

Both Railway crons fired on time every night from 10 Sep and crashed on import:
`Settings()` refused production without `JWT_ACCESS_SECRET`, `JWT_REFRESH_SECRET` and a
real `FRONTEND_ORIGIN`, which `.railway/railway.ts` never gives the job services and no job
reads. `scrape_runs` held a single manual row. These tests launch each job exactly the way
the cron does, with that environment, and prove the web server still refuses it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Environment, ProcessRole, Settings, launched_role

API_ROOT = Path(__file__).resolve().parents[1]

#: What a Railway job service actually has: production, a database, and nothing else of
#: the web server's. Empty strings rather than absent keys, because an empty environment
#: variable beats a value in a developer's `.env` file and absence would not.
JOB_ENVIRONMENT = {
    "ENVIRONMENT": "production",
    "DATABASE_URL": "postgresql+asyncpg://user:password@db.example.com:5432/mcu",
    "JWT_ACCESS_SECRET": "",
    "JWT_REFRESH_SECRET": "",
    "FRONTEND_ORIGIN": "",
}


def _launch(*args: str, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PROCESS_ROLE", None)
    environment.update(JOB_ENVIRONMENT)
    environment.update(extra or {})
    return subprocess.run(
        [sys.executable, *args],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


@pytest.mark.parametrize("script", ["daily_scrape", "run_reminders"])
def test_each_cron_job_starts_with_the_environment_railway_gives_it(script: str) -> None:
    # `--help` exits after the imports — the point every run crashed at — and before the
    # job does anything, so this makes no request and touches no database.
    result = _launch("-m", f"src.scripts.{script}", "--help")

    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()


def test_the_web_server_still_refuses_that_environment() -> None:
    result = _launch("-c", "import src.config")

    assert result.returncode != 0
    assert "jwt_access_secret is empty" in result.stderr


def test_the_web_server_refuses_to_start_as_a_job() -> None:
    result = _launch(
        "-c",
        "import src.main",
        extra={
            "PROCESS_ROLE": "job",
            "JWT_ACCESS_SECRET": "a" * 32,
            "JWT_REFRESH_SECRET": "b" * 32,
            "FRONTEND_ORIGIN": "https://mcu.example.com",
        },
    )

    assert result.returncode != 0
    assert "must run with PROCESS_ROLE=web" in result.stderr


@pytest.mark.parametrize(
    ("argv", "role"),
    [
        (["python", "-m", "src.scripts.daily_scrape"], ProcessRole.job),
        (["python", "-u", "-m", "src.scripts.run_reminders", "--no-deliver"], ProcessRole.job),
        (["/usr/local/bin/uvicorn", "src.main:app", "--port", "8000"], ProcessRole.web),
        (["python", "-m", "uvicorn", "src.main:app"], ProcessRole.web),
        (["/usr/local/bin/alembic", "upgrade", "head"], ProcessRole.web),
        (["python", "-m", "pytest", "-m", "slow"], ProcessRole.web),
        (["python", "-c", "import src.config"], ProcessRole.web),
        (["python", "-m"], ProcessRole.web),
    ],
)
def test_the_role_comes_from_how_the_process_was_launched(
    argv: list[str], role: ProcessRole
) -> None:
    assert launched_role(argv) == role


def _production(**overrides: object) -> Settings:
    params: dict[str, object] = {
        "environment": Environment.production,
        "database_url": "postgresql+asyncpg://user:password@db.example.com:5432/mcu",
    }
    params.update(overrides)
    return Settings(**params)


def test_a_job_needs_no_session_secrets_and_no_browser_origin() -> None:
    settings = _production(
        process_role=ProcessRole.job,
        jwt_access_secret="",
        jwt_refresh_secret="",
        frontend_origin="",
    )
    assert settings.process_role == ProcessRole.job


def test_a_job_still_needs_a_database() -> None:
    with pytest.raises(ValidationError, match="database_url is empty"):
        _production(process_role=ProcessRole.job, database_url="")


def test_the_web_server_still_needs_its_secrets() -> None:
    with pytest.raises(ValidationError, match="jwt_access_secret is empty"):
        _production(process_role=ProcessRole.web, frontend_origin="https://mcu.example.com")
