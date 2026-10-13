from typing import Any, Literal

import structlog
from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from src.config import settings
from src.database import AsyncSessionLocal
from src.services.webpush import load_vapid_private_key

router = APIRouter(prefix="/api/v1/health", tags=["health"])

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    commitSha: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    db: Literal["ok", "unreachable"]

    #: Whether Web Push is usable in **this deployment** — Batch 11.
    #:
    #: **This field exists because of the TMDB outage.** `TMDB_READ_TOKEN` had never been
    #: set in Railway, every TMDB-backed feature answered 502 for an unknown length of
    #: time, and the gate was green throughout — because a value that lives only in a
    #: hosting variable has nothing testing it (`STATUS.md`, "four things the next agent
    #: should know", item 4). Push has exactly that shape: with no key, subscriptions
    #: cannot be created and nothing anywhere says why.
    #:
    #: It reports the *result of loading the key*, not merely that a string is present —
    #: a malformed key is `invalid`, which is a different problem from `not_configured`
    #: and would otherwise surface only at the first send. No key material is exposed,
    #: and readiness is deliberately **not** failed by it: push being unconfigured is a
    #: missing feature, not an unhealthy container, and failing here would take the whole
    #: API out of rotation over a notification setting.
    push: Literal["configured", "not_configured", "invalid"]

    #: Whether the AI assistant can work in this deployment — Batch 30, and the same
    #: reasoning as `push`: `ANTHROPIC_API_KEY` lives only in a Railway variable, so
    #: without this nothing in the code could observe its absence.
    ai: Literal["configured", "not_configured"]

    #: Whether eBay Browse can be called in this deployment — Batch 28, and the third
    #: field here for the same reason as the first two. `EBAY_CLIENT_ID` and
    #: `EBAY_CLIENT_SECRET` are Railway variables, and until this field existed the only
    #: way to learn they were missing was to ask for a price and read a 503.
    ebay: Literal["configured", "not_configured"]

    #: TMDB and Brave, presence only — Batch X8 (DS44-04). TMDB's token is the variable whose
    #: absence on 9 Sep made every TMDB-backed feature answer 502 behind a green gate, the
    #: outage this endpoint names as its reason; Brave finds the reviews. Neither is called:
    #: a TMDB call costs a request and a Brave one costs credit.
    tmdb: Literal["configured", "not_configured"]
    brave: Literal["configured", "not_configured"]


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    log.info("health check")
    return HealthResponse(
        status="ok",
        commitSha=settings.railway_git_commit_sha or "unknown",
    )


def _ai_status() -> Literal["configured", "not_configured"]:
    """Is there a key for the assistant? Presence only — a call would cost money."""
    return "configured" if settings.anthropic_api_key else "not_configured"


def _ebay_status() -> Literal["configured", "not_configured"]:
    """Is there a keyset for Browse? Presence only — a call would spend the daily quota."""
    if settings.ebay_client_id and settings.ebay_client_secret:
        return "configured"
    return "not_configured"


def _push_status() -> Literal["configured", "not_configured", "invalid"]:
    """Can this deployment actually send a push?

    Loading the key is the check. A present-but-unreadable `VAPID_PRIVATE_KEY` passes any
    "is the variable set?" test and then fails at the first send, which is the worst of
    both worlds — so the question asked here is the same one the sender asks.
    """
    if not settings.vapid_private_key or not settings.vapid_subject:
        return "not_configured"
    try:
        load_vapid_private_key(settings.vapid_private_key)
    except ValueError:
        return "invalid"
    return "configured"


def _tmdb_status() -> Literal["configured", "not_configured"]:
    """Is there a TMDB credential? Presence only."""
    return "configured" if settings.tmdb_read_token or settings.tmdb_api_key else "not_configured"


def _brave_status() -> Literal["configured", "not_configured"]:
    """Is there a Brave Search key? Presence only — a search spends credit."""
    return "configured" if settings.brave_search_api_key else "not_configured"


def readiness_fields() -> dict[str, Any]:
    """Every outside service as this deployment sees it, for the boot heartbeat and /ready."""
    return {
        "push": _push_status(),
        "ai": _ai_status(),
        "ebay": _ebay_status(),
        "tmdb": _tmdb_status(),
        "brave": _brave_status(),
    }


@router.get("/ready", response_model=ReadinessResponse)
async def ready(response: Response) -> ReadinessResponse:
    fields = readiness_fields()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return ReadinessResponse(status="ready", db="ok", **fields)
    except Exception:
        log.warning("readiness check failed", db="unreachable")
        response.status_code = 503
        return ReadinessResponse(status="not_ready", db="unreachable", **fields)
