"""The sidebar's shape — Batch S3, snag 5.

One endpoint, one question: **which of the four self-hiding destinations have anything
behind them?** `DECISIONS.md` #154 hides Box sets, Collections, Deals and Loans while their
tables are empty, and that is a fact about the database rather than about the client, so
the client has to be told.

**Why not have the sidebar fetch the four lists it already has clients for?** Because it
would fetch four full result sets on every page load in order to learn they were empty —
on a phone, over a flaky connection, in a PWA whose whole point is being cheap to open.
Four `COUNT(*)`s in one round trip is the version that costs nothing.

**Why `CurrentUser` rather than admin.** Every one of these destinations is visible to a
viewer, and the menu is drawn for whoever is signed in. Smart collections are additionally
*per-user*, so the count is scoped to the caller — a shared count would show one person a
destination holding only the other's collections.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from src.auth import CurrentUser
from src.models.box_set import BoxSet
from src.models.deal import Deal
from src.models.loan import Loan
from src.models.smart_collection import SmartCollection
from src.routers.movies import Database
from src.schemas.navigation import NavSectionsResponse

router = APIRouter(prefix="/api/v1", tags=["navigation"])


@router.get("/nav/sections", response_model=NavSectionsResponse)
async def nav_sections(user: CurrentUser, db: Database) -> NavSectionsResponse:
    """Row counts for the destinations that hide themselves when empty.

    Each count matches what its page would actually list, which is the property that
    matters: a menu item that appears and then leads to an empty page is the bug this
    endpoint exists to prevent, and it would be a subtle one — the item would be *right*
    about the table and *wrong* about the page.
    """
    box_sets = await db.scalar(select(func.count(BoxSet.id)).where(BoxSet.deleted_at.is_(None)))
    collections = await db.scalar(
        select(func.count(SmartCollection.id)).where(SmartCollection.user_id == user.id)
    )
    # The same filter `GET /deals` applies, so the two cannot disagree.
    deals = await db.scalar(select(func.count(Deal.id)).where(Deal.dismissed_at_utc.is_(None)))
    # No filter: `GET /loans` lists returned loans alongside open ones.
    loans = await db.scalar(select(func.count(Loan.id)))

    return NavSectionsResponse(
        boxSets=int(box_sets or 0),
        collections=int(collections or 0),
        deals=int(deals or 0),
        loans=int(loans or 0),
    )
