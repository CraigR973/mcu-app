from enum import StrEnum

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {
    "change-me-access",
    "change-me-refresh",
    "change-me-to-a-random-secret-at-least-32-chars",
    "change-me-to-another-random-secret-at-least-32-chars",
}
_MIN_SECRET_LENGTH = 32


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
    sentry_dsn_backend: str = ""
    log_level: str = "INFO"
    environment: Environment = Environment.development

    @field_validator("database_url", mode="before")
    @classmethod
    def _use_asyncpg_driver(cls, value: object) -> object:
        """Accept common hosted-Postgres URLs but always select the async driver."""
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

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
