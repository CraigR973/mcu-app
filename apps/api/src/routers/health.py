from typing import Literal

import structlog
from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from src.config import settings
from src.database import AsyncSessionLocal

router = APIRouter(prefix="/api/v1/health", tags=["health"])

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    commitSha: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    db: Literal["ok", "unreachable"]


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    log.info("health check")
    return HealthResponse(
        status="ok",
        commitSha=settings.railway_git_commit_sha or "unknown",
    )


@router.get("/ready", response_model=ReadinessResponse)
async def ready(response: Response) -> ReadinessResponse:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return ReadinessResponse(status="ready", db="ok")
    except Exception:
        log.warning("readiness check failed", db="unreachable")
        response.status_code = 503
        return ReadinessResponse(status="not_ready", db="unreachable")
