"""Home's "Needs attention" row, for Craig — Batch X2 (DS44-01, UX48-02).

**It reads operational problems the daily check recorded**
(`services/health_checks.py`, run at 08:00 inside the reminders job), so it works when push
is what broke, and adds one problem of its own: the check itself not having run for more
than a day, which nothing else could say.

Identification warnings are reconciled against the current actionable lists on every read.
This does not record a check, change the daily heartbeat or queue a notification.

Admin only: the problems are operational, and Mark has nothing to act on.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from src.auth import AdminUser, CurrentUser
from src.clock import utcnow
from src.models.craig_note import CraigNote
from src.models.profile import Profile
from src.routers.movies import Database
from src.schemas.attention import AttentionItemResponse, AttentionResponse, NoteRequest
from src.services.health_checks import CHECK_STALE_AFTER, current_problems, day, last_checked

router = APIRouter(prefix="/api/v1", tags=["attention"])


@router.get("/attention", response_model=AttentionResponse)
async def attention(_user: AdminUser, db: Database) -> AttentionResponse:
    """The problems the last daily check found, oldest first, and whether it is running."""
    now = utcnow()
    checked = await last_checked(db)
    # What a person asked Craig, ahead of what the check found: someone is waiting on it.
    notes = (
        await db.execute(
            select(CraigNote, Profile.display_name)
            .outerjoin(Profile, Profile.id == CraigNote.from_user_id)
            .where(CraigNote.cleared_utc.is_(None))
            .order_by(CraigNote.created_utc)
        )
    ).all()
    items = [
        AttentionItemResponse(
            key=f"note:{note.id}",
            message=f"{name or 'Someone'} says: {note.body}",
            since=note.created_utc,
            noteId=note.id,
        )
        for note, name in notes
    ]
    items += [
        AttentionItemResponse(
            key=row.check_key, message=row.message or "", since=row.failing_since_utc
        )
        for row in await current_problems(db, now=now)
    ]
    if checked is None or checked < now - CHECK_STALE_AFTER:
        when = f"since {day(checked)}" if checked is not None else "yet"
        items.insert(
            0,
            AttentionItemResponse(key="check:stale", message=f"The daily check hasn't run {when}."),
        )
    return AttentionResponse(items=items, checkedAt=checked)


#: Open lines one person may have waiting at once. Enough to say a few things, too few for a
#: stuck finger to fill Craig's Home.
MAX_OPEN_NOTES = 5


@router.post("/attention/notes", status_code=status.HTTP_204_NO_CONTENT)
async def tell_craig(payload: NoteRequest, user: CurrentUser, db: Database) -> None:
    """A line from the person asking, for Craig's "Needs attention" (Batch X12a).

    Open to both people, so it works for Craig too; the You page offers it to Mark.
    """
    waiting = await db.scalar(
        select(func.count(CraigNote.id)).where(
            CraigNote.from_user_id == user.id, CraigNote.cleared_utc.is_(None)
        )
    )
    if (waiting or 0) >= MAX_OPEN_NOTES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Craig has not cleared your earlier notes yet.",
        )
    db.add(
        CraigNote(id=uuid.uuid4(), from_user_id=user.id, body=payload.message, created_utc=utcnow())
    )
    await db.commit()


@router.delete("/attention/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_note(note_id: uuid.UUID, _user: AdminUser, db: Database) -> None:
    """Craig has read it. The row stays in the table, cleared, as a record."""
    note = await db.get(CraigNote, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such note")
    if note.cleared_utc is None:
        note.cleared_utc = utcnow()
        await db.commit()
