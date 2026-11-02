"""Programme reads only: public sources never run in a person's request."""

import uuid
from datetime import UTC, date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from src.auth import CurrentUser
from src.clock import utcnow
from src.routers.movies import Database
from src.schemas.cinemas import CinemaProgrammeResponse, ReleaseFilter
from src.services.cinemas.domain import LONDON
from src.services.cinemas.programme import programme

router = APIRouter(prefix="/api/v1/cinemas", tags=["cinemas"])


@router.get("/programme", response_model=CinemaProgrammeResponse)
async def get_programme(
    user: CurrentUser,
    db: Database,
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    venue_ids: Annotated[list[uuid.UUID] | None, Query(alias="venueIds")] = None,
    release_category: Annotated[ReleaseFilter, Query(alias="releaseCategory")] = "all",
) -> CinemaProgrammeResponse:
    start = date_from or utcnow().replace(tzinfo=UTC).astimezone(LONDON).date()
    try:
        return await programme(db, user.id, start, date_to or start, venue_ids, release_category)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
