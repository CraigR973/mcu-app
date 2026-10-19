"""Routing, the request log and the scenario file."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

#: Where the log and the scenario live; set by the launcher or the pytest fixture.
DIR_ENV = "OUTSIDE_WORLD_DIR"
_LOCK = threading.Lock()

Handler = Callable[[httpx.Request, "World"], httpx.Response]

#: Any public-looking address will do: the connection is never made, the mock answers first.
#: ``assert_fetchable`` (the shops' fetcher) resolves a host and refuses loopback/private ones.
_PUBLIC_ADDRESS = "93.184.216.34"


class World:
    """What a handler may read: the scenario, and a way to log."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def scenario(self) -> dict[str, Any]:
        path = self.directory / "scenario.json"
        try:
            data: dict[str, Any] = json.loads(path.read_text())
            return data
        except (OSError, ValueError):
            return {}

    def log(self, **entry: Any) -> None:
        entry.setdefault("t", time.time())
        line = json.dumps(entry, default=str)
        with _LOCK, (self.directory / "log.jsonl").open("a") as handle:
            handle.write(line + "\n")


def _directory() -> Path:
    value = os.environ.get(DIR_ENV)
    if not value:
        raise RuntimeError(f"{DIR_ENV} must name a directory for the fake world's log")
    path = Path(value)
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_log(directory: Path | None = None) -> list[dict[str, Any]]:
    path = (directory or _directory()) / "log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def set_scenario(values: dict[str, Any], directory: Path | None = None) -> None:
    path = (directory or _directory()) / "scenario.json"
    path.write_text(json.dumps(values))


def _routes() -> dict[str, Handler]:
    from . import anthropic, bluray, brave, ebay, letterboxd, push, shops, tmdb

    table: dict[str, Handler] = {}
    for module in (tmdb, ebay, brave, bluray, shops, letterboxd, anthropic, push):
        for host in module.HOSTS:
            table[host] = module.handle
    return table


def _refuse_database_not_throwaway() -> None:
    url = os.environ.get("DATABASE_URL", "")
    lowered = url.lower()
    if not url or any(word in lowered for word in ("neon", "railway", "supabase", "amazonaws")):
        raise RuntimeError("the fake outside world only runs against a throwaway database")
    parts = urlsplit(url.replace("+asyncpg", ""))
    host = parts.hostname or ""
    socket_dir = "host=" in (parts.query or "")
    if not socket_dir and host not in {"localhost", "127.0.0.1", "::1", ""}:
        raise RuntimeError(f"the fake outside world refuses database host {host!r}")


def install() -> None:
    _refuse_database_not_throwaway()
    world = World(_directory())
    routes = _routes()

    def answer(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        handler = routes.get(host)
        if handler is None:
            world.log(kind="unfaked", host=host, path=request.url.path, method=request.method)
            raise httpx.ConnectError(f"outside call to {host} is not faked", request=request)
        body = request.content[:2000].decode("utf-8", "replace") if request.content else ""
        world.log(
            kind="call",
            host=host,
            path=request.url.path,
            query=request.url.query.decode() if request.url.query else "",
            method=request.method,
            body=body,
        )
        return handler(request, world)

    original_async = httpx.AsyncClient.__init__
    original_sync = httpx.Client.__init__

    def async_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(answer)
        kwargs.pop("proxy", None)
        kwargs.pop("proxies", None)
        original_async(self, *args, **kwargs)

    def sync_init(self: httpx.Client, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(answer)
        kwargs.pop("proxy", None)
        kwargs.pop("proxies", None)
        original_sync(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = async_init  # type: ignore[method-assign]
    httpx.Client.__init__ = sync_init  # type: ignore[method-assign]

    real_getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(host, str) and host in routes:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_PUBLIC_ADDRESS, 443))]
        return real_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]
