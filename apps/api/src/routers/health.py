import structlog
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/health", tags=["health"])

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get("")
async def health() -> dict[str, str]:
    log.info("health check")
    return {"status": "ok"}
