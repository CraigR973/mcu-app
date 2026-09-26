"""Fetching disc specs, within the bounds `DECISIONS.md` #110 sets — §3.7.

**This module is where the risk acceptance is enforced rather than described.** #110's
conditions map one-to-one onto code here:

| #110 says | Here |
|---|---|
| exact release URLs only, never the search routes | `require_in_bounds`, before every request |
| requests sequential and rate-limited | one at a time, `MIN_INTERVAL_SECONDS` apart |
| no images, scripts or advertising | one `GET` for the HTML; nothing else is requested |
| (a page that moved, Batch U1, #219) | followed once, only to the same release, spaced |
| a `403`/`429`/objection halts **the whole integration** | `halt`, persisted |
| resuming requires a new owner decision | nothing here clears the halt |
| results cached indefinitely, not refreshed | `refresh=False` skips a row that already has specs |
| every derived row records source URL and fetch time | written on the item, every time |

**The halt is deliberately total and deliberately sticky.** One `403` stops every future
fetch in the deployment, including the backfill, until a person clears it — and nothing in
this file can clear it. That is what "resuming after any of those requires a new owner
decision" has to mean if it is to mean anything.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import CollectionItem
from src.models.specs_state import SINGLETON_ID, SpecsIntegrationState
from src.services.specs.bluray_com import (
    OutOfBounds,
    canonical_release_url,
    extract,
    release_number,
    require_in_bounds,
)

logger = structlog.get_logger(__name__)

#: #110's "conservatively rate-limited". Five seconds between requests is slower than a
#: person clicking through the site, which is the standard worth meeting when the access is
#: a risk acceptance rather than a permission.
MIN_INTERVAL_SECONDS = 5.0

#: A single request's ceiling. A page is ~200 KB; anything far larger is not the page.
MAX_BYTES = 4 * 1024 * 1024

REQUEST_TIMEOUT = 20.0

#: Sent honestly. #110 forbids evasion, and a user agent that pretends to be a browser is
#: the first step of it — a site that wants to refuse this must be able to.
USER_AGENT = "MCU-App/1.0 (private film collection; contact via site owner)"

#: Statuses that halt everything, per #110. `403` is a refusal and `429` is being told to
#: stop; both mean the same thing here.
HALT_STATUSES = frozenset({401, 403, 429, 451})


class IntegrationHalted(Exception):
    """The integration is stopped and only an owner decision restarts it."""


class PageMoved(Exception):
    """Blu-ray.com sent a page somewhere this fetcher will not follow — Batch U1, #219.

    Only a move to the same release, under #110's predicate, is followed, and only once.
    ``reason`` is written for Craig, who is shown it with the disc.
    """

    def __init__(self, url: str, location: str, reason: str) -> None:
        super().__init__(reason)
        self.url = url
        self.location = location
        self.reason = reason


@dataclass(frozen=True)
class FetchedPage:
    """A release page, and the address it was read from.

    ``url`` differs from the address asked for only when Blu-ray.com had moved the page to a
    new address for the same release and the fetch followed it (Batch U1).
    """

    url: str
    html: str


@dataclass
class SpecsRunResult:
    """What one run did. Every URL fetched is listed — the ledger asks for that."""

    fetched: list[str] = field(default_factory=list)
    updated: int = 0
    skipped: int = 0
    failed: list[dict[str, str]] = field(default_factory=list)
    halted: bool = False
    halt_reason: str | None = None


async def get_state(db: AsyncSession) -> SpecsIntegrationState:
    """The one row. Created if a fresh database somehow lacks it."""
    state = (
        await db.execute(
            select(SpecsIntegrationState).where(SpecsIntegrationState.id == SINGLETON_ID)
        )
    ).scalar_one_or_none()
    if state is None:  # pragma: no cover - the migration inserts it
        state = SpecsIntegrationState(id=SINGLETON_ID, halted=False, fetch_count=0)
        db.add(state)
        await db.flush()
    return state


async def halt(db: AsyncSession, reason: str) -> SpecsIntegrationState:
    """Stop the integration. **Nothing in this module ever undoes this.**"""
    state = await get_state(db)
    if not state.halted:
        state.halted = True
        state.halted_reason = reason[:2000]
        state.halted_at_utc = utcnow()
        await db.flush()
        logger.error("specs_integration_halted", reason=reason[:300])
    return state


def _location(response: httpx.Response) -> str:
    """Where a redirect points, as an absolute address. A relative one is read against the
    address that answered."""
    location = str(response.headers.get("location", ""))
    try:
        return str(response.url.join(location))
    except (httpx.InvalidURL, ValueError):
        return location


def moved_to(url: str, response: httpx.Response) -> str:
    """The new address of a moved page, if the fetch may follow it — Batch U1, #219.

    Only when it passes #110's release-page predicate **for the same release number**:
    Blu-ray.com renames a release by changing its slug and keeping its number. Anywhere
    else — another release, a search route, a sign-in page, another site — raises
    :class:`PageMoved` and is never requested.
    """
    target = _location(response)
    number = release_number(url)
    if number is None or release_number(target) != number:
        raise PageMoved(
            url,
            target,
            f"Blu-ray.com sent this page to {target[:200]}, which is not the same release "
            "page, so it was not followed.",
        )
    return target


async def _request(client: httpx.AsyncClient, url: str, db: AsyncSession) -> httpx.Response:
    """One `GET`, and a halt if Blu-ray.com says stop."""
    require_in_bounds(url)
    response = await client.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=REQUEST_TIMEOUT,
        # #110 forbids evasion, and httpx would follow a redirect anywhere. A moved page is
        # judged by `moved_to` instead, before anything is requested from its new address.
        follow_redirects=False,
    )
    if response.status_code in HALT_STATUSES:
        await halt(db, f"Blu-ray.com answered {response.status_code} for {url}")
        raise IntegrationHalted(f"HTTP {response.status_code}")
    return response


async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    db: AsyncSession,
    *,
    pause: float = MIN_INTERVAL_SECONDS,
) -> FetchedPage:
    """One page, or a halt.

    Raises :class:`IntegrationHalted` for anything #110 treats as being told to stop, after
    recording it. Raises :class:`httpx.HTTPError` for an ordinary transport failure, which
    is not a refusal and does not halt anything.

    **A page that moved (Batch U1, #219)** is followed once, to the same release only, and
    the second request waits ``pause`` like any other: it is a request under #110's spacing,
    and a `403` or `429` to it halts everything too. A redirect anywhere else, or a second
    redirect, raises :class:`PageMoved`.
    """
    require_in_bounds(url)
    state = await get_state(db)
    if state.halted:
        raise IntegrationHalted(state.halted_reason or "halted")

    read_from = url
    response = await _request(client, url, db)
    if response.is_redirect:
        read_from = moved_to(url, response)
        if pause:
            await asyncio.sleep(pause)
        response = await _request(client, read_from, db)
        if response.is_redirect:
            raise PageMoved(
                url,
                _location(response),
                f"Blu-ray.com moved this page to {read_from[:200]} and then sent that "
                f"address to {_location(response)[:200]}, so it was not followed again.",
            )
    response.raise_for_status()

    body = response.text
    if len(body.encode("utf-8", "ignore")) > MAX_BYTES:  # pragma: no cover - guard
        raise httpx.HTTPError("response too large to be a release page")

    state.fetch_count += 1
    state.last_fetch_at_utc = utcnow()
    await db.flush()
    return FetchedPage(url=read_from, html=body)


async def apply_specs(
    db: AsyncSession, item: CollectionItem, html: str, *, url: str, now: datetime
) -> bool:
    """Parse and store. Returns whether anything was written.

    **The provenance columns are written on the same statement as the specs**, because #110
    makes them a condition rather than a nicety: a row whose source is unrecorded cannot be
    found again when the owner decides to remove everything derived from that site.
    """
    specs = extract(html)
    if specs.is_empty:
        return False

    if specs.video:
        item.video_specs = specs.video
    if specs.audio:
        item.audio_specs = specs.audio
    if specs.special_features is not None:
        item.special_features = specs.special_features
    if specs.region_code:
        item.region_code = specs.region_code
    if specs.release_label:
        item.release_label = specs.release_label

    item.specs_source_url = url
    item.specs_fetched_at_utc = now
    await db.flush()
    return True


async def run_specs_fetch(
    db: AsyncSession,
    pairs: list[tuple[uuid.UUID, str]],
    *,
    client: httpx.AsyncClient,
    refresh: bool = False,
    pause: float = MIN_INTERVAL_SECONDS,
) -> SpecsRunResult:
    """Fetch specs for `(collection_item_id, release_url)` pairs. **Makes live requests.**

    Sequential by construction — the loop is the rate limit, and there is no gather here to
    accidentally turn ten polite requests into ten simultaneous ones.
    """
    result = SpecsRunResult()
    now = utcnow()

    state = await get_state(db)
    if state.halted:
        result.halted = True
        result.halt_reason = state.halted_reason
        return result

    for index, (item_id, url) in enumerate(pairs):
        item = await db.get(CollectionItem, item_id)
        if item is None or item.deleted_at is not None:
            result.failed.append({"url": url, "reason": "no such collection item"})
            continue

        # #110: "successful results are cached indefinitely rather than refreshed
        # automatically". A row that already has specs is not fetched again unless asked.
        if item.specs_source_url and not refresh:
            result.skipped += 1
            continue

        try:
            require_in_bounds(url)
        except OutOfBounds as exc:
            result.failed.append({"url": url, "reason": str(exc)})
            continue

        if index and pause:
            await asyncio.sleep(pause)

        try:
            page = await fetch_page(client, url, db, pause=pause)
        except IntegrationHalted as exc:
            result.halted = True
            result.halt_reason = str(exc)
            # Everything stops, including whatever is left in `pairs`. That is what
            # "halts the whole integration" means.
            break
        except PageMoved as exc:
            result.failed.append({"url": url, "reason": exc.reason})
            continue
        except httpx.HTTPError as exc:
            result.failed.append({"url": url, "reason": str(exc)[:200]})
            continue

        result.fetched.append(page.url)
        # A page that moved is recorded at its new address (Batch U1).
        source = url if page.url == url else canonical_release_url(page.url)
        if await apply_specs(db, item, page.html, url=source, now=now):
            result.updated += 1
        else:
            result.failed.append({"url": url, "reason": "no specs found on the page"})

    logger.info(
        "specs_run",
        fetched=len(result.fetched),
        updated=result.updated,
        skipped=result.skipped,
        failed=len(result.failed),
        halted=result.halted,
    )
    return result
