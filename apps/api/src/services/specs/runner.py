"""Fetching disc specs, within the bounds `DECISIONS.md` #110 sets — §3.7.

**This module is where the risk acceptance is enforced rather than described.** #110's
conditions map one-to-one onto code here:

| #110 says | Here |
|---|---|
| exact release URLs only, never the search routes | `require_in_bounds`, before every request |
| requests sequential and rate-limited | one at a time, `MIN_INTERVAL_SECONDS` apart |
| no images, scripts or advertising | one `GET` for the HTML; nothing follows |
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
from src.services.specs.bluray_com import OutOfBounds, extract, require_in_bounds

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


async def fetch_page(client: httpx.AsyncClient, url: str, db: AsyncSession) -> str:
    """One page, or a halt.

    Raises :class:`IntegrationHalted` for anything #110 treats as being told to stop, after
    recording it. Raises :class:`httpx.HTTPError` for an ordinary transport failure, which
    is not a refusal and does not halt anything.
    """
    require_in_bounds(url)
    state = await get_state(db)
    if state.halted:
        raise IntegrationHalted(state.halted_reason or "halted")

    response = await client.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=REQUEST_TIMEOUT,
        # #110 forbids evasion; following a redirect off the release path would also take
        # the fetch somewhere `require_in_bounds` never approved.
        follow_redirects=False,
    )

    if response.status_code in HALT_STATUSES:
        await halt(db, f"Blu-ray.com answered {response.status_code} for {url}")
        raise IntegrationHalted(f"HTTP {response.status_code}")
    response.raise_for_status()

    body = response.text
    if len(body.encode("utf-8", "ignore")) > MAX_BYTES:  # pragma: no cover - guard
        raise httpx.HTTPError("response too large to be a release page")

    state.fetch_count += 1
    state.last_fetch_at_utc = utcnow()
    await db.flush()
    return body


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
            html = await fetch_page(client, url, db)
        except IntegrationHalted as exc:
            result.halted = True
            result.halt_reason = str(exc)
            # Everything stops, including whatever is left in `pairs`. That is what
            # "halts the whole integration" means.
            break
        except httpx.HTTPError as exc:
            result.failed.append({"url": url, "reason": str(exc)[:200]})
            continue

        result.fetched.append(url)
        if await apply_specs(db, item, html, url=url, now=now):
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
