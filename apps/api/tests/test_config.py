from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Environment, Settings, docs_urls

API_ROOT = Path(__file__).resolve().parents[1]


def _build_settings(**overrides: object) -> Settings:
    params: dict[str, object] = {
        "environment": Environment.production,
        "jwt_access_secret": "a" * 32,
        "jwt_refresh_secret": "b" * 32,
        "database_url": "postgresql+asyncpg://user:password@db.example.com:5432/mcu",
        "frontend_origin": "https://mcu.example.com",
    }
    params.update(overrides)
    return Settings(**params)


def test_valid_production_settings_construct() -> None:
    result = _build_settings()
    assert result.environment == Environment.production


@pytest.mark.parametrize("environment", [Environment.staging, Environment.production])
def test_non_development_rejects_empty_secret(environment: Environment) -> None:
    with pytest.raises(
        ValidationError,
        match="Refusing to start with weak/missing secrets: jwt_access_secret is empty",
    ):
        _build_settings(environment=environment, jwt_access_secret="")


def test_module_refuses_to_boot_with_empty_production_secret() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "ENVIRONMENT": "production",
            "JWT_ACCESS_SECRET": "",
            "JWT_REFRESH_SECRET": "b" * 32,
            "DATABASE_URL": "postgresql+asyncpg://user:password@db.example.com:5432/mcu",
            "FRONTEND_ORIGIN": "https://mcu.example.com",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", "import src.config"],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Refusing to start with weak/missing secrets" in result.stderr


def test_non_development_rejects_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="jwt_access_secret is a placeholder value"):
        _build_settings(jwt_access_secret="change-me-access")


def test_non_development_rejects_short_and_identical_secrets() -> None:
    with pytest.raises(ValidationError, match="must be at least 32 characters"):
        _build_settings(jwt_access_secret="short", jwt_refresh_secret="short")


def test_development_allows_empty_secrets() -> None:
    result = _build_settings(
        environment=Environment.development,
        jwt_access_secret="",
        jwt_refresh_secret="",
        frontend_origin="http://localhost:5173",
    )
    assert result.jwt_access_secret == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgres://user:password@host/db",
            "postgresql+asyncpg://user:password@host/db",
        ),
        (
            "postgresql://user:password@host/db",
            "postgresql+asyncpg://user:password@host/db",
        ),
    ],
)
def test_database_url_uses_asyncpg(raw: str, expected: str) -> None:
    assert _build_settings(database_url=raw).database_url == expected


def test_unknown_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _build_settings(environment="preview")


def test_docs_are_disabled_only_in_production() -> None:
    assert docs_urls(Environment.production) == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    assert docs_urls(Environment.staging)["docs_url"] == "/api/docs"
