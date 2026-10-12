"""Fetching a page on the server's behalf, safely — Batch 19.

**This is the first thing in the application that fetches a URL a person supplied.** Every
other outbound request goes to a fixed host: TMDB, and nothing else. A retailer's
``base_url`` and §5.4's "test scraper" URL are both typed in by an admin, and the request is
made by the server — which is the definition of an SSRF surface.

The admin is trusted, so this is not primarily about them being malicious. It is about the
two things that go wrong anyway:

1. **A typo or a paste reaches somewhere it should not.** ``http://localhost:8000/api/v1/...``
   is a URL the *server* can reach and the admin's browser cannot, so the server would
   proxy it — including anything bound to the loopback interface of the container.
2. **A redirect goes somewhere the URL did not say.** A retailer that 302s to an internal
   address turns a safe-looking URL into an unsafe request, which is why redirects are
   followed manually and every hop is re-checked rather than handed to httpx.

Both are closed by resolving the host to its addresses and refusing anything that is not
publicly routable — checked **per hop**, after DNS, so a name that resolves to 127.0.0.1
is refused whatever it is called.
"""

from __future__ import annotations

import asyncio
import html
import ipaddress
import math
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger()

#: A retailer page is HTML. Anything much larger is a download, and reading it into memory
#: to run selectors over would be pointless as well as expensive.
MAX_BYTES = 3_000_000

#: Retailers are slow; a scrape that hangs holds a worker.
TIMEOUT_SECONDS = 20.0

#: Followed by hand, so each hop can be re-checked. Three is more than any real shop needs.
MAX_REDIRECTS = 3

#: Sent so a retailer can identify and contact us, which is the polite half of scraping and
#: the half that keeps a shop from blocking outright.
USER_AGENT = (
    "MCU-Collection/1.0 (private film collection price checker; contact via the site owner)"
)


class UnsafeUrlError(Exception):
    """The URL points somewhere the server must not fetch on someone's behalf."""


class FetchError(Exception):
    """The page could not be retrieved. Distinct from "retrieved and unparseable"."""


#: Answers that are the shop turning the request away, not the page being broken (20b).
REFUSAL_STATUSES = frozenset({429})

#: What a refusal keeps of the response: enough to tell a rate limit, which says when to
#: come back, from a block, which serves a challenge page (`docs/phase-batches.md`, 20b).
EVIDENCE_HEADERS = ("retry-after", "cf-mitigated", "server")

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


class RefusedError(FetchError):
    """The shop answered, and refused: ``429 Too Many Requests`` (Batch 20b).

    A refusal is not a broken scraper, so the runner keeps it out of auto-disable. It
    carries what the shop sent back, because whether a shop is limiting the rate or
    blocking the requester decides what would cure it.
    """

    def __init__(self, status: int, *, retry_after: str | None, evidence: str) -> None:
        self.status = status
        self.retry_after = retry_after
        self.evidence = evidence
        detail = f" ({evidence})" if evidence else ""
        super().__init__(f"The page answered {status}{detail}")


def _clip(value: str, limit: int = 80) -> str:
    flat = " ".join(value.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def refusal_from(response: httpx.Response) -> RefusedError:
    """What a refused response said, as one short line: headers first, then its title."""
    parts = [
        f"{name} {_clip(response.headers[name])}"
        for name in EVIDENCE_HEADERS
        if response.headers.get(name)
    ]
    # Only the head of the page: a challenge page names itself in its title, and the
    # rest of a refusal is of no use.
    title = _TITLE.search(response.content[:20_000].decode("utf-8", errors="replace"))
    if title and title.group(1).strip():
        parts.append(f'title "{_clip(html.unescape(title.group(1)))}"')
    retry_after = response.headers.get("retry-after")
    return RefusedError(
        response.status_code,
        retry_after=_clip(retry_after) if retry_after else None,
        evidence="; ".join(parts),
    )


#: The longest a refusal's ``Retry-After`` is waited for before the one retry (20b's second
#: half). Every refusal on 2 Oct asked for 60 seconds; a shop asking for more is not going to
#: be back within the night's run, and waiting would only make the run longer.
RETRY_AFTER_LIMIT_SECONDS = 90


@dataclass(frozen=True)
class RetryWait:
    """How long to wait before retrying a refused request, and why: the refusal's record."""

    seconds: float
    #: What the shop asked for, as it sent it, or ``None`` when it named no wait.
    asked: str | None
    note: str


def _asked_seconds(value: str, now: datetime) -> float | None:
    """``Retry-After`` in seconds: a number of seconds, or an HTTP date (RFC 9110 §10.2.3)."""
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, math.ceil((when - now).total_seconds()))


def retry_wait(
    refusal: RefusedError,
    *,
    usual_pause: float,
    limit: float = RETRY_AFTER_LIMIT_SECONDS,
    now: datetime | None = None,
) -> RetryWait:
    """The wait before a refused request's one retry (Batch 20b, second half).

    The shop's ``Retry-After`` when it is within ``limit``, and never less than the usual
    pause; otherwise the usual pause, and the note says why. A ``limit`` of 0 waits for
    nothing a shop asks: "Run now" in the app passes it, because a run from the phone
    cannot hold a request open for half an hour.
    """
    return bounded_wait(refusal.retry_after, usual_pause=usual_pause, limit=limit, now=now)


def bounded_wait(
    asked: str | None,
    *,
    usual_pause: float,
    limit: float = RETRY_AFTER_LIMIT_SECONDS,
    now: datetime | None = None,
) -> RetryWait:
    """:func:`retry_wait`'s rule on a bare ``Retry-After`` value — shared since Batch X1 with
    the TMDB client, which waited however long TMDB asked, doubled each retry (CR43-06)."""
    if asked is None:
        return RetryWait(usual_pause, None, f"waited {usual_pause:g} s: no Retry-After")
    seconds = _asked_seconds(asked, now or datetime.now(UTC))
    if seconds is None:
        return RetryWait(
            usual_pause, asked, f"waited {usual_pause:g} s: Retry-After {asked!r} not understood"
        )
    if limit <= 0:
        return RetryWait(
            usual_pause,
            asked,
            f"waited {usual_pause:g} s: asked for {seconds:g} s, not waited for in a run "
            "from the app",
        )
    if seconds > limit:
        return RetryWait(
            usual_pause,
            asked,
            f"waited {usual_pause:g} s: asked for {seconds:g} s, over the {limit:g} s limit",
        )
    waited = max(seconds, usual_pause)
    return RetryWait(waited, asked, f"waited {waited:g} s, as asked")


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status: int
    html: str
    #: Where it ended up, which may differ from where it started.
    final_url: str


def _is_public_address(raw: str) -> bool:
    address = ipaddress.ip_address(raw)
    # `is_global` is the single question worth asking; the rest are spelled out because
    # `is_global` alone is False for some addresses that are fine and True for none that
    # are not, and being explicit documents what is being refused.
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


async def assert_fetchable(url: str) -> None:
    """Refuse a URL the server must not fetch. Raises :class:`UnsafeUrlError`.

    Resolution happens here, and the check is on the **resolved addresses**, not the
    hostname — a name under the caller's control can point at 127.0.0.1, and a blocklist of
    hostnames would never catch it. Every address the name resolves to must be public,
    because which one is used is the resolver's choice, not ours.
    """
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrlError("Only http and https URLs can be fetched")
    host = parts.hostname
    if not host:
        raise UnsafeUrlError("That URL has no host")

    # A literal address skips DNS and is checked directly.
    try:
        if not _is_public_address(host):
            raise UnsafeUrlError("That address is not publicly routable")
        return
    except ValueError:
        pass  # Not a literal; resolve it below.

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"That host could not be resolved: {host}") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UnsafeUrlError(f"That host resolved to nothing: {host}")
    for address in addresses:
        if not _is_public_address(str(address)):
            # **Every** address, not any: a name resolving to both a public and a private
            # address would otherwise be fetchable, and which one is used is the
            # resolver's choice rather than ours.
            raise UnsafeUrlError("That host resolves to a non-public address")


async def fetch_page(url: str, *, client: httpx.AsyncClient | None = None) -> FetchedPage:
    """Fetch one page, re-checking safety at every redirect.

    ``follow_redirects`` is **off**. httpx would follow a 302 to anywhere, including an
    internal address, without this code seeing it — turning a URL that passed the check
    into a request that never did.
    """
    owned = client is None
    http = client or httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await assert_fetchable(current)
            response = await http.get(current)

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise FetchError("Redirect with no destination")
                current = str(httpx.URL(current).join(location))
                continue

            if response.status_code in REFUSAL_STATUSES:
                raise refusal_from(response)
            if response.status_code >= 400:
                raise FetchError(f"The page answered {response.status_code}")

            body = response.content[:MAX_BYTES]
            return FetchedPage(
                url=url,
                status=response.status_code,
                # `errors="replace"` rather than strict: a retailer serving one bad byte
                # should cost that byte, not the whole scrape.
                html=body.decode(response.encoding or "utf-8", errors="replace"),
                final_url=current,
            )
        raise FetchError("Too many redirects")
    except httpx.HTTPError as exc:
        raise FetchError(f"The page could not be reached: {exc}") from exc
    finally:
        if owned:
            await http.aclose()
