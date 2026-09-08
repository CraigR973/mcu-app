from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {
    "change-me-access",
    "change-me-refresh",
    "change-me-to-a-random-secret-at-least-32-chars",
    "change-me-to-another-random-secret-at-least-32-chars",
}
_MIN_SECRET_LENGTH = 32


def alembic_config_url(database_url: str) -> str:
    """Escape ConfigParser interpolation tokens in an Alembic database URL."""
    return database_url.replace("%", "%%")


def psycopg2_dsn(database_url: str) -> str:
    """Convert the app's SQLAlchemy URL into a libpq DSN psycopg2 can parse.

    :attr:`Settings.database_url` is normalised for asyncpg at load time — the scheme
    becomes ``postgresql+asyncpg`` and libpq's ``sslmode`` is renamed to asyncpg's
    ``ssl``. psycopg2 speaks libpq and rejects both, with an error naming the whole URL as
    an "invalid connection option", which reads like a malformed URL rather than the
    driver mismatch it is.

    This matters because the batch importer is sync psycopg2 while the API is async
    asyncpg, so one settings value has to serve two drivers. Handing
    ``settings.database_url`` straight to ``psycopg2.connect`` fails against every hosted
    database and succeeds against a bare local one, which is exactly the shape of bug that
    reaches production.
    """
    parts = urlsplit(database_url)
    scheme = "postgresql" if parts.scheme.startswith("postgresql") else parts.scheme

    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append(("sslmode", value) if key == "ssl" else (key, value))

    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Environment(StrEnum):
    development = "development"
    staging = "staging"
    production = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mcu_app"

    # Auth secrets are consumed when Batch 3 lands PIN + JWT auth. Keeping them in
    # the foundation means a non-development deployment can never start weakly.
    jwt_access_secret: str = ""
    jwt_refresh_secret: str = ""

    # TMDB (optional at API boot; used by the Batch 4 import pipeline)
    tmdb_api_key: str = ""
    tmdb_read_token: str = ""

    # App
    frontend_origin: str = "http://localhost:5173"
    #: How many proxy hops in front of the app are ours. Exactly one on Railway, which
    #: is the default. Used to read ``X-Forwarded-For`` from the right-hand end — see
    #: :func:`src.rate_limit.client_address`, where reading the leftmost entry would let
    #: any caller forge a fresh rate-limit bucket per request.
    trusted_proxy_count: int = 1
    sentry_dsn_backend: str = ""
    log_level: str = "INFO"
    environment: Environment = Environment.development
    # Railway injects this for Git-backed deployments. The health endpoint
    # exposes it so deployment verification can prove which commit is running.
    railway_git_commit_sha: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def _use_asyncpg_driver(cls, value: object) -> object:
        """Normalise hosted Postgres URLs for SQLAlchemy's asyncpg dialect.

        Neon emits libpq-style ``sslmode`` and ``channel_binding`` query
        parameters. asyncpg calls the first option ``ssl`` and does not support
        the second, so passing Neon's URL through unchanged raises ``TypeError``
        before a connection is attempted.
        """
        if not isinstance(value, str):
            return value

        parts = urlsplit(value)
        scheme = parts.scheme
        if scheme in {"postgres", "postgresql"}:
            scheme = "postgresql+asyncpg"

        sslmode: str | None = None
        has_asyncpg_ssl = False
        query: list[tuple[str, str]] = []
        for key, query_value in parse_qsl(parts.query, keep_blank_values=True):
            if key == "sslmode":
                sslmode = query_value
            elif key == "channel_binding":
                continue
            else:
                query.append((key, query_value))
                has_asyncpg_ssl = has_asyncpg_ssl or key == "ssl"

        if sslmode and not has_asyncpg_ssl:
            query.append(("ssl", sslmode))

        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @model_validator(mode="after")
    def _reject_weak_secrets_outside_development(self) -> "Settings":
        if self.environment == Environment.development:
            return self

        errors: list[str] = []
        for field_name, secret in (
            ("jwt_access_secret", self.jwt_access_secret),
            ("jwt_refresh_secret", self.jwt_refresh_secret),
        ):
            if not secret:
                errors.append(f"{field_name} is empty")
            elif secret in _PLACEHOLDER_SECRETS:
                errors.append(f"{field_name} is a placeholder value")
            elif len(secret) < _MIN_SECRET_LENGTH:
                errors.append(f"{field_name} must be at least {_MIN_SECRET_LENGTH} characters")

        if self.jwt_access_secret == self.jwt_refresh_secret:
            errors.append("jwt_access_secret and jwt_refresh_secret must be different")
        if not self.database_url:
            errors.append("database_url is empty")
        if not self.frontend_origin or self.frontend_origin.startswith("http://localhost"):
            errors.append("frontend_origin must not be empty or localhost outside development")

        if errors:
            raise ValueError("Refusing to start with weak/missing secrets: " + "; ".join(errors))
        return self


settings = Settings()


def docs_urls(environment: Environment) -> dict[str, str | None]:
    """Disable API discovery routes in production for this private application."""
    if environment == Environment.production:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {
        "docs_url": "/api/docs",
        "redoc_url": "/api/redoc",
        "openapi_url": "/api/openapi.json",
    }
