"""Authenticated brand artwork — Group AA, Batch AA8.

The MARKS photo collages contain film stills and portraits.  They belong in the
private archive, not Vercel's public asset directory: an image tag cannot attach the
app's bearer token, so the web client fetches these bytes and creates a local object URL.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from src.auth import CurrentUser

router = APIRouter(prefix="/api/v1", tags=["brand"])

_ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "brand"
_HEROES = {
    "five": "hero-photo-five-v3.png",
    "single": "hero-photo-v3.png",
}


@router.get("/brand/heroes/{hero}")
async def serve_hero(hero: str, _user: CurrentUser) -> FileResponse:
    """Serve one private photo hero to a signed-in person only."""
    filename = _HEROES.get(hero)
    if filename is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand artwork not found")

    return FileResponse(
        _ASSET_DIRECTORY / filename,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )
