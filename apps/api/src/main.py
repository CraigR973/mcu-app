from typing import Any

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.types import Event, Hint
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.config import Environment, docs_urls, settings
from src.logging_config import configure_logging
from src.middleware import CorrelationIdMiddleware, SecurityHeadersMiddleware
from src.rate_limit import limiter
from src.routers import auth, health, movies

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

# slowapi reads the limiter off app.state, and its handler reads
# request.state.view_rate_limit — which src.rate_limit.enforce_durable_limit sets by
# hand so a durably-refused login answers with the same body a decorated route would.
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    """Adapter around slowapi's handler.

    slowapi types its handler as taking ``RateLimitExceeded``; Starlette's registry is
    typed as taking ``Exception``. Narrowing here rather than silencing the mismatch with
    an ignore keeps the check real — and the ``raise`` is not dead defensiveness, it is
    what makes the narrowing sound if the handler is ever registered for another type.
    """
    if not isinstance(exc, RateLimitExceeded):  # pragma: no cover - registered for one type
        raise exc
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

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
app.include_router(auth.router)
app.include_router(movies.router)
