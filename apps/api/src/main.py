import os

import sentry_sdk
import structlog
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_current_user, require_admin
from .config import settings  # noqa: F401  — validates env on startup
from .logging_config import configure_logging
from .middleware import CorrelationIdMiddleware
from .routers.movies import router as movies_router
from .routers.search import router as search_router
from .routers.users import router as users_router

load_dotenv()
configure_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN") or None,
    environment=os.getenv("APP_ENV", "development"),
    traces_sample_rate=1.0,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

app = FastAPI(
    title="MCU API",
    description="Mark's Cinematic Universe API",
    version="0.0.1",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(movies_router)
app.include_router(search_router)
app.include_router(users_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    logger.info("health_check")
    return {"status": "ok"}


@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)) -> dict:  # type: ignore[type-arg]
    return user


@app.get("/api/admin/ping")
async def admin_ping(user: dict = Depends(require_admin)) -> dict:  # type: ignore[type-arg]
    return {"status": "ok", "user": user}


@app.get("/debug/error")
async def debug_error() -> None:
    """Endpoint used to verify Sentry captures errors and logs include correlation IDs."""
    logger.info("triggering_test_error")
    raise ValueError("Test error for Sentry verification")
