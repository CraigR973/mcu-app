"""www.blu-ray.com — a release page for a disc's specs, and the shop-list search page.

A page is served only when a case names it; any other path is a plain "no results" page.
Release pages come from the captured fixtures::

    {"bluray": {"pages": {"/movies/Some-Film-4K-Blu-ray/1/": "bluray_com_release_page_4k.html"}}}
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

HOSTS = ("www.blu-ray.com",)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def handle(request: httpx.Request, world: Any) -> httpx.Response:
    pages = world.scenario().get("bluray", {}).get("pages", {})
    name = pages.get(request.url.path)
    if name:
        return httpx.Response(
            200, text=(_FIXTURES / name).read_text(), headers={"content-type": "text/html; charset=utf-8"}
        )
    return httpx.Response(
        200,
        text="<html><body><main><p>No results found.</p></main></body></html>",
        headers={"content-type": "text/html; charset=utf-8"},
    )
