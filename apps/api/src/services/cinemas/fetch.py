"""One run's anonymous HTTP budget, with host refusal and deadline stops."""

import asyncio
import time
from collections import defaultdict
from urllib.parse import urlsplit

import httpx

from src.services.cinemas.domain import SOURCE_HOSTS, SourceError

ALLOWED_HOSTS = SOURCE_HOSTS


class Refused(SourceError):
    def __init__(self, host: str, status: int) -> None:
        self.host = host
        super().__init__(f"Source host refused HTTP {status}; no retry")


class Budget:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.requests = 0
        self.bytes_read = 0
        self.started = time.monotonic()
        self.refused: set[str] = set()
        self.host_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.last_start: dict[str, float] = {}
        self.slots = asyncio.Semaphore(2)

    async def get(self, url: str) -> str:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or host not in ALLOWED_HOSTS
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise SourceError("Unexpected source URL; no request sent")
        async with self.host_locks[host], self.slots:
            if host in self.refused:
                raise Refused(host, 0)
            delay = 1 - (time.monotonic() - self.last_start.get(host, 0))
            if delay > 0:
                await asyncio.sleep(delay)
            if (
                self.requests >= 120
                # Reserve one bounded response plus its final decoder chunk. This
                # stops before a request that could exceed the whole-pass byte cap.
                or self.bytes_read > 64 * 1024 * 1024 - (2 * 1024 * 1024 + 65536)
                or time.monotonic() - self.started >= 300
            ):
                raise SourceError("Programme run request/byte/time limit reached")
            self.last_start[host] = time.monotonic()
            self.requests += 1
            async with asyncio.timeout(min(15, 300 - (time.monotonic() - self.started))):
                async with self.client.stream("GET", url, follow_redirects=False) as response:
                    if response.status_code in (401, 403, 429):
                        self.refused.add(host)
                        raise Refused(host, response.status_code)
                    if response.status_code != 200:
                        raise SourceError(
                            f"Programme HTTP {response.status_code}; no retry/redirect"
                        )
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        self.bytes_read += len(chunk)
                        chunks.extend(chunk)
                        if len(chunks) > 2 * 1024 * 1024 or self.bytes_read > 64 * 1024 * 1024:
                            raise SourceError("Programme decoded-body limit reached")
                    body = chunks.decode("utf-8")
                    title = body[:3000].lower()
                    if any(
                        x in title
                        for x in (
                            "<title>access denied",
                            "<title>just a moment",
                            "<title>virtual waiting room",
                        )
                    ):
                        self.refused.add(host)
                        raise Refused(host, 200)
                    return body
