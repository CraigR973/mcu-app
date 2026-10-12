"""Home's "Needs attention" row, for Craig — Batch X2 (DS44-01, UX48-02).

**It reads what the daily check recorded** (`services/health_checks.py`, run at 08:00 inside
the reminders job), so it works when push is what broke, and adds one problem of its own: the
check itself not having run for more than a day, which nothing else could say.

Admin only: the problems are operational, and Mark has nothing to act on.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.auth import AdminUser
from src.clock import utcnow
from src.routers.movies import Database
from src.schemas.attention import AttentionItemResponse, AttentionResponse
from src.services.health_checks import CHECK_STALE_AFTER, current_problems, day, last_checked

router = APIRouter(prefix="/api/v1", tags=["attention"])


@router.get("/attention", response_model=AttentionResponse)
async def attention(_user: AdminUser, db: Database) -> AttentionResponse:
    """The problems the last daily check found, oldest first, and whether it is running."""
    now = utcnow()
    checked = await last_checked(db)
    items = [
        AttentionItemResponse(
            key=row.check_key, message=row.message or "", since=row.failing_since_utc
        )
        for row in await current_problems(db)
    ]
    if checked is None or checked < now - CHECK_STALE_AFTER:
        when = f"since {day(checked)}" if checked is not None else "yet"
        items.insert(
            0,
            AttentionItemResponse(key="check:stale", message=f"The daily check hasn't run {when}."),
        )
    return AttentionResponse(items=items, checkedAt=checked)
