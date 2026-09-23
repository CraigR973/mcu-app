"""The release calendar and its iCal feed — roadmap §7.3, §7.4, §6.33.

**`GET /api/v1/calendar.ics` is the first endpoint in this application that answers without
a bearer token**, and every unusual thing here follows from that.

A calendar app fetches a bare URL on a schedule. It cannot attach a header, cannot be
prompted, and will not surface an error — so the URL *is* the credential, and it is treated
with the same care as a refresh token:

- **256 bits of entropy**, from ``secrets.token_urlsafe(32)``.
- **Stored hashed** (SHA-256), so a database leak yields no working links. The plaintext is
  returned once and never again.
- **One live token per person, rotated on every subscribe**, because rotating is the only
  way to take back a link that has already been pasted somewhere.
- **A revoked token is indistinguishable from a wrong one** — both 404, with the same body.
  A 401 would confirm that a guessed token had once existed.
- **Rate-limited per IP**, because an endpoint that answers without credentials is the one
  worth hammering.
- **`X-Robots-Tag: noindex, nofollow`**, so a link pasted into anything that crawls does not
  end up in a search index.
- **No personal data in the feed at all.** It contains release dates for films — public
  facts, most of them from TMDB. Nothing says whose calendar it is, what they own, or what
  they have watched. That is what keeps a leaked URL a nuisance rather than a disclosure,
  and it is a property worth preserving if this feed is ever extended.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AdminUser, CurrentUser
from src.clock import utc_today, utcnow
from src.models.release_calendar import (
    RELEASE_TYPE_LABELS,
    ReleaseCalendarEntry,
)
from src.rate_limit import limiter
from src.routers.movies import Database, TmdbClient
from src.schemas.discovery import (
    CalendarEntryResponse,
    CalendarIngestResponse,
    CalendarListResponse,
    CalendarMonthResponse,
    CalendarSubscriptionResponse,
    ReleaseType,
)
from src.services.calendar import (
    REFRESH_AFTER,
    calendar_refreshed_at,
    issue_feed_token,
    refresh_calendar,
    refresh_calendar_if_stale,
    resolve_feed_token,
)
from src.services.ical import CalendarEvent, render_calendar

router = APIRouter(prefix="/api/v1", tags=["calendar"])

#: How far the `.ics` feed reaches back. A calendar that forgets last month's releases the
#: moment they happen is less useful than one that keeps them a little while.
FEED_LOOKBACK = timedelta(days=30)
FEED_HORIZON = timedelta(days=365)

#: An unauthenticated endpoint is the one worth hammering. Generous enough for a real
#: client — Apple polls at most hourly and this asks for daily — and far below what a
#: script would want.
ICS_LIMIT = "30/hour"


def _entry(entry: ReleaseCalendarEntry) -> CalendarEntryResponse:
    return CalendarEntryResponse(
        id=entry.id,
        title=entry.title,
        releaseType=cast(ReleaseType, entry.release_type),
        typeLabel=RELEASE_TYPE_LABELS.get(entry.release_type, entry.release_type),
        releaseDate=entry.release_date,
        label=entry.label,
        region=entry.region,
        url=entry.url,
        posterPath=entry.poster_path,
        overview=entry.overview,
        movieId=entry.movie_id,
    )


async def _entries_between(db: AsyncSession, start: date, end: date) -> list[ReleaseCalendarEntry]:
    return list(
        (
            await db.execute(
                select(ReleaseCalendarEntry)
                .where(
                    ReleaseCalendarEntry.release_date >= start,
                    ReleaseCalendarEntry.release_date <= end,
                )
                .order_by(ReleaseCalendarEntry.release_date, ReleaseCalendarEntry.title)
            )
        )
        .scalars()
        .all()
    )


async def _refresh_if_stale(db: AsyncSession, background_tasks: BackgroundTasks) -> None:
    """Batch T5: a read of a stale calendar refreshes it, after the response has gone.

    The reader gets today's rows at once; the next reader gets fresh ones. Staleness is
    checked here so a fresh calendar costs one indexed read, not a background task.
    """
    refreshed = await calendar_refreshed_at(db)
    if refreshed is None or refreshed < utcnow() - REFRESH_AFTER:
        background_tasks.add_task(refresh_calendar_if_stale)


@router.get("/calendar", response_model=CalendarListResponse)
async def list_calendar(
    _user: CurrentUser,
    db: Database,
    background_tasks: BackgroundTasks,
    days: Annotated[int, Query(ge=1, le=730)] = 120,
) -> CalendarListResponse:
    """Upcoming releases, soonest first — §6.5's `/calendar`."""
    today = utc_today()
    entries = await _entries_between(db, today, today + timedelta(days=days))
    await _refresh_if_stale(db, background_tasks)
    return CalendarListResponse(
        items=[_entry(entry) for entry in entries],
        total=len(entries),
        refreshedAt=await calendar_refreshed_at(db),
    )


@router.get("/calendar/month", response_model=CalendarMonthResponse)
async def calendar_month(
    _user: CurrentUser,
    db: Database,
    background_tasks: BackgroundTasks,
    month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> CalendarMonthResponse:
    """§7.4's monthly view, bucketed by day server-side.

    Grouping here rather than in the browser keeps the grid a rendering problem, and makes
    an empty month an explicit empty map rather than something the client infers.
    """
    year, month_number = (int(part) for part in month.split("-"))
    # The year is bounded as well as the month. ``\d{4}`` matches "0000", and
    # ``date(0, 1, 1)`` raises ValueError — an unhandled 500 from a query string, found by
    # reading the pattern rather than by hitting it.
    if not 1 <= month_number <= 12 or not 1900 <= year <= 2200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Not a real month"
        )
    start = date(year, month_number, 1)
    end = date(year + (month_number == 12), (month_number % 12) + 1, 1) - timedelta(days=1)

    grouped: dict[str, list[CalendarEntryResponse]] = defaultdict(list)
    entries = await _entries_between(db, start, end)
    await _refresh_if_stale(db, background_tasks)
    for entry in entries:
        grouped[entry.release_date.isoformat()].append(_entry(entry))

    return CalendarMonthResponse(month=month, days=dict(grouped), total=len(entries))


@router.post("/calendar/subscribe", response_model=CalendarSubscriptionResponse)
async def subscribe_to_calendar(user: CurrentUser, db: Database) -> CalendarSubscriptionResponse:
    """Issue this person's feed URL — §7.4's "subscribe button with copy-link".

    **Calling this again rotates the link**, revoking the previous one. That is the whole
    recovery story for a URL pasted somewhere it should not have been, and the response
    says so, so nobody is left believing two links work.
    """
    from src.models.release_calendar import CalendarFeedToken

    had_previous = (
        await db.execute(
            select(CalendarFeedToken.id).where(
                CalendarFeedToken.user_id == user.id,
                CalendarFeedToken.revoked_at_utc.is_(None),
            )
        )
    ).first() is not None

    token = await issue_feed_token(db, user.id)
    # A path, not an absolute URL. The `Host` header is attacker-controlled, so reflecting
    # it would let someone induce a subscription link pointing at their own server; and
    # configuring an origin would mean a new Railway variable, which is a hosting change
    # this project keeps explicit. The web app holds `VITE_API_URL` and composes it there.
    return CalendarSubscriptionResponse(
        path=f"/api/v1/calendar.ics?token={token}",
        createdAt=utcnow(),
        replacedPrevious=had_previous,
    )


@router.get("/calendar.ics", include_in_schema=True)
@limiter.limit(ICS_LIMIT)
async def calendar_feed(
    request: Request,
    db: Database,
    background_tasks: BackgroundTasks,
    token: Annotated[str, Query(min_length=16, max_length=200)],
) -> Response:
    """The unauthenticated iCal feed — §7.4.

    ``request`` is unused by the body and required by slowapi's decorator, which reads the
    client address off it.

    **A wrong token and a revoked token get the same 404**, with the same body. A 401, or a
    different message for "this used to work", would confirm to someone guessing that a
    token had once existed — and there is no user to tell apart from an attacker here,
    because the whole point is that nobody signs in.
    """
    del request
    feed_token = await resolve_feed_token(db, token)
    if feed_token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    today = utc_today()
    entries = await _entries_between(db, today - FEED_LOOKBACK, today + FEED_HORIZON)
    # A subscribed calendar app polls even when nobody opens the app, so its reads keep
    # the calendar fresh too (Batch T5).
    await _refresh_if_stale(db, background_tasks)

    events = [
        CalendarEvent(
            # Stable across regenerations, so a client updates an event rather than
            # creating a duplicate every time it polls. RFC 5545 requires global
            # uniqueness, hence the domain-ish suffix.
            uid=f"{entry.id}@mcu-app",
            summary=f"{RELEASE_TYPE_LABELS.get(entry.release_type, 'Release')}: {entry.title}",
            start=entry.release_date,
            description=entry.overview,
            url=entry.url,
            last_modified=entry.updated_at,
        )
        for entry in entries
    ]

    body = render_calendar(
        events,
        name="MCU — Release calendar",
        description="Upcoming releases from Mark's Cinematic Universe.",
        now=utcnow(),
    )
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            # Named so a client that downloads rather than subscribes gets a sensible file.
            "Content-Disposition": 'inline; filename="mcu-release-calendar.ics"',
            # A URL that is its own credential must never be indexed.
            "X-Robots-Tag": "noindex, nofollow",
            # Nor cached by anything between here and the subscriber.
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/calendar/ingest", response_model=CalendarIngestResponse)
async def ingest_calendar(
    user: AdminUser,
    db: Database,
    tmdb: TmdbClient,
) -> CalendarIngestResponse:
    """§7.3's ingestion, on demand — the same refresh a stale read starts, now.

    Admin-only: it spends a shared TMDB budget and writes a table both people read. Since
    Batch T5 the calendar also refreshes itself when read and more than a day old, so this
    is the "now, please" button rather than the only way it ever updates.
    """
    del user
    result = await refresh_calendar(db, tmdb, force=True)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The calendar is already refreshing. Try again in a few minutes.",
        )
    return CalendarIngestResponse(
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        skipped=result.skipped,
        total=result.total,
        errors=result.errors,
        dryRun=False,
    )
