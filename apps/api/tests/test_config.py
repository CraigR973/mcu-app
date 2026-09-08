from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Environment, Settings, alembic_config_url, docs_urls

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
        (
            "postgresql://user:password@host/db?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://user:password@host/db?ssl=require",
        ),
        (
            "postgresql+asyncpg://user:password@host/db?application_name=mcu&ssl=require",
            "postgresql+asyncpg://user:password@host/db?application_name=mcu&ssl=require",
        ),
    ],
)
def test_database_url_uses_asyncpg(raw: str, expected: str) -> None:
    assert _build_settings(database_url=raw).database_url == expected


def test_alembic_url_escapes_config_parser_interpolation() -> None:
    url = "postgresql+asyncpg://postgres@/db?host=%2Ftmp%2Fpostgres"
    assert alembic_config_url(url) == ("postgresql+asyncpg://postgres@/db?host=%%2Ftmp%%2Fpostgres")


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


# ---------------------------------------------------------------------------
# psycopg2_dsn — one settings value, two drivers
# ---------------------------------------------------------------------------


def test_psycopg2_dsn_restores_libpq_scheme_and_sslmode() -> None:
    """The exact Neon URL shape that broke the Batch 4 import.

    `Settings` normalises for asyncpg on load, so what reaches a sync caller is
    `postgresql+asyncpg://…?ssl=require`. psycopg2 rejects both the scheme and the
    parameter name.
    """
    from src.config import psycopg2_dsn

    dsn = psycopg2_dsn("postgresql+asyncpg://u:p@host.neon.tech/neondb?ssl=require")
    assert dsn == "postgresql://u:p@host.neon.tech/neondb?sslmode=require"


def test_psycopg2_dsn_is_accepted_by_psycopg2() -> None:
    """Parse it with psycopg2 itself rather than asserting on a string we wrote.

    The original failure was psycopg2 refusing to parse the DSN, so the test that would
    have caught it has to be the parser, not an equality check.
    """
    import psycopg2.extensions

    from src.config import psycopg2_dsn

    parsed = psycopg2.extensions.parse_dsn(
        psycopg2_dsn("postgresql+asyncpg://u:p@host.neon.tech/neondb?ssl=require")
    )
    assert parsed["host"] == "host.neon.tech"
    assert parsed["dbname"] == "neondb"
    assert parsed["sslmode"] == "require"


def test_psycopg2_dsn_leaves_a_plain_url_alone() -> None:
    from src.config import psycopg2_dsn

    assert (
        psycopg2_dsn("postgresql://postgres:postgres@localhost:5432/mcu_test")
        == "postgresql://postgres:postgres@localhost:5432/mcu_test"
    )


def test_psycopg2_dsn_round_trips_the_settings_normaliser() -> None:
    """Whatever `Settings` does to a hosted URL, this must undo for psycopg2."""
    import psycopg2.extensions

    from src.config import Settings, psycopg2_dsn

    settings = Settings(
        database_url="postgresql://u:p@host.neon.tech/neondb?sslmode=require&channel_binding=require",
        jwt_access_secret="a" * 32,
        jwt_refresh_secret="b" * 32,
    )
    assert settings.database_url.startswith("postgresql+asyncpg://")
    parsed = psycopg2.extensions.parse_dsn(psycopg2_dsn(settings.database_url))
    assert parsed["sslmode"] == "require"
