"""Placeholder, filled in when its flow is built."""

from __future__ import annotations

import httpx

HOSTS: tuple[str, ...] = ()


def handle(request: httpx.Request, world: object) -> httpx.Response:
    return httpx.Response(404)
