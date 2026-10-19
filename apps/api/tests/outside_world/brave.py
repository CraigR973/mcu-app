"""api.search.brave.com — web search, used to find a disc's Blu-ray.com page and its reviews.

Answers no results unless a case says otherwise::

    {"brave": {"results": [{"contains": "dog soldiers", "web": [{"title": "...", "url": "...",
                                                                  "description": "..."}]}]}}
"""

from __future__ import annotations

from typing import Any

import httpx

HOSTS = ("api.search.brave.com",)


def handle(request: httpx.Request, world: Any) -> httpx.Response:
    query = request.url.params.get("q", "").lower()
    web: list[dict[str, str]] = []
    for rule in world.scenario().get("brave", {}).get("results", []):
        if rule["contains"].lower() in query:
            web = list(rule["web"])
            break
    return httpx.Response(200, json={"type": "search", "web": {"results": web}})
