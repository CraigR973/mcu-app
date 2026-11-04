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
#: The name, the file and its type. ``five`` and ``single`` stay for any web build still
#: installed from before AC2.
_HEROES = {
    "five": ("hero-photo-five-v3.png", "image/png"),
    "single": ("hero-photo-v3.png", "image/png"),
    # AC2 (#337): Home's banner T1, the photo letters alone, at a phone's 3x and a desktop's
    # 2x width. Built by `docs/brand/logo-system/build_letters_hero.py`.
    "letters-v1-1125": ("hero-letters-v1-1125.webp", "image/webp"),
    "letters-v1-1800": ("hero-letters-v1-1800.webp", "image/webp"),
}
#: A versioned name never changes its bytes, so a device may keep it; a new banner is a new
#: name. Still ``private``: shared caches never hold it (AA8).
_VERSIONED = "private, max-age=31536000, immutable"


@router.get("/brand/heroes/{hero}")
async def serve_hero(hero: str, _user: CurrentUser) -> FileResponse:
    """Serve one private photo hero to a signed-in person only."""
    found = _HEROES.get(hero)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand artwork not found")
    filename, media_type = found
    return FileResponse(
        _ASSET_DIRECTORY / filename,
        media_type=media_type,
        headers={"Cache-Control": _VERSIONED if "-v1-" in hero else "private, max-age=3600"},
    )
