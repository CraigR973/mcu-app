from typing import Any

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.types import Event, Hint

from src.config import Environment, docs_urls, settings
from src.logging_config import configure_logging
from src.middleware import CorrelationIdMiddleware, SecurityHeadersMiddleware
from src.routers import health

configure_logging(settings.log_level)


def _scrub_pii(event: Event, _hint: Hint) -> Event | None:
    """Remove account display identifiers before an event leaves the process."""
    user: Any = event.get("user")
    if isinstance(user, dict):
        user.pop("display_name", None)
        user.pop("username", None)
        user.pop("email", None)
    return event


if settings.sentry_dsn_backend:
    sentry_sdk.init(
        dsn=settings.sentry_dsn_backend,
        environment=settings.environment,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        send_default_pii=False,
        before_send=_scrub_pii,
        traces_sample_rate=0.05 if settings.environment == Environment.production else 0.0,
    )

_docs = docs_urls(settings.environment)
app = FastAPI(
    title="MCU API",
    description="Mark's Cinematic Universe API",
    version="0.1.0",
    docs_url=_docs["docs_url"],
    redoc_url=_docs["redoc_url"],
    openapi_url=_docs["openapi_url"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router)
