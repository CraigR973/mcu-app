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


def _is_local(host: object) -> bool:
    if not isinstance(host, str):
        return True  # a unix-socket path or bytes address: nothing leaves the machine
    return host in {"", "localhost", "127.0.0.1", "::1", "0.0.0.0", "::"}  # noqa: S104


def install() -> None:
    _refuse_database_not_throwaway()
    world = World(_directory())
    routes = _routes()

    def answer(request: Any) -> httpx.Response:
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

    # Two HTTP libraries are in this process: ``httpx`` (the app's own clients) and ``httpx2``
    # (the one the ``anthropic`` SDK brings). Both get a mock transport.
    libraries: list[Any] = [httpx]
    try:
        import httpx2

        libraries.append(httpx2)
    except ImportError:  # pragma: no cover - the SDK is a dependency
        pass

    for library in libraries:

        def make(library: Any) -> Any:
            def handler(request: Any) -> Any:
                response = answer(request)
                if library is httpx:
                    return response
                return library.Response(
                    response.status_code, headers=response.headers, content=response.content
                )

            return handler

        mock = make(library)
        for client in (library.AsyncClient, library.Client):
            original = client.__init__

            def patched(
                self: Any, *args: Any, __original: Any = original, __mock: Any = mock, **kwargs: Any
            ) -> None:
                kwargs["transport"] = library_for(self).MockTransport(__mock)
                kwargs.pop("proxy", None)
                kwargs.pop("proxies", None)
                __original(self, *args, **kwargs)

            client.__init__ = patched

    # Backstop for anything that does not go through either library: nothing may resolve or
    # connect to a machine that is not this one.
    real_getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(host, str) and host in routes:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_PUBLIC_ADDRESS, 443))]
        if not _is_local(host):
            world.log(kind="unfaked", host=host, path="(name lookup)", method="DNS")
            raise socket.gaierror(f"name lookup for {host} is blocked by the fake outside world")
        return real_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def refuse_remote(address: Any) -> None:
        if isinstance(address, tuple) and address and not _is_local(address[0]):
            world.log(kind="unfaked", host=str(address[0]), path="(connect)", method="TCP")
            raise OSError(f"connecting to {address[0]} is blocked by the fake outside world")

    def connect(self: socket.socket, address: Any) -> None:
        refuse_remote(address)
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        refuse_remote(address)
        return real_connect_ex(self, address)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]


def library_for(client: Any) -> Any:
    """The HTTP library a client class belongs to, for its own ``MockTransport``."""
    module = type(client).__module__.split(".")[0]
    if module == "httpx2" or any(
        c.__module__.split(".")[0] == "httpx2" for c in type(client).__mro__
    ):
        import httpx2

        return httpx2
    return httpx
