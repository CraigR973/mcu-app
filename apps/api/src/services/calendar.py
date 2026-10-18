"""Ingesting upcoming releases, and issuing feed tokens — §7.3, §7.4.

**What "curated sources" turned into.** §7.3 says "TMDB upcoming + curated sources", and
§6.33 lists what it means by curated: Criterion and boutique-label announcements, award
ceremonies, and known sale events. Only two of those have a source this app can reach.

- **TMDB upcoming** is real and is ingested live.
- **Award ceremonies and sale events** have no API. They are annual, publicly announced,
  and slow-moving — so they are a small dated list in this module, marked as such, rather
  than a scraper that would be Batch 19's problem and would break every year anyway.
- **Boutique-label release announcements** are genuinely a scraper — Arrow, Indicator and
  Radiance publish them on their own sites in their own shapes — and that is **Batch 19's
  framework**, not a corner of this batch. Not ingested here, and the ledger says so.

Ingestion is idempotent on ``(tmdb_id, release_type, region)``: running it twice updates
the row rather than adding a second, which is what makes it safe to run on a schedule
someone else sets up.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utc_today, utcnow
from src.database import AsyncSessionLocal
from src.models.movie import Movie
from src.models.release_calendar import (
    CalendarFeedToken,
    CalendarRefreshState,
    ReleaseCalendarEntry,
)
from src.services.tmdb_refresh import refresh_stale_fields
from src.tmdb import TMDBClient
from src.tmdb.models import TMDB_RELEASE_PHYSICAL, SearchResult

logger = structlog.get_logger(__name__)

#: How far ahead the ingestion looks. §7.3's acceptance asks for rows "spanning the next 3
#: months", and TMDB's upcoming list is roughly that window anyway.
HORIZON = timedelta(days=93)

#: Fixed-date events with no API behind them. Dated deliberately: an entry that has gone
#: stale is visible as a past date rather than quietly wrong, and a future maintainer can
#: see at a glance which year's list this is.
#:
#: **Not scraped, and not guessed.** Every one of these is a publicly announced date; where
#: a date is not yet announced it is simply absent rather than estimated, because a calendar
#: event that turns out to be a guess is worse than a missing one.
CURATED_EVENTS: tuple[tuple[str, str, date], ...] = (
    ("Black Friday", "sale_event", date(2026, 11, 27)),
    ("Prime Day", "sale_event", date(2026, 10, 7)),
)


@dataclass
class IngestResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    #: Batch S6. Films TMDB was asked about, and how many had a GB physical date at all.
    #: **The pair is the coverage number**, reported rather than hidden: measured
    #: 2026-09-15 over three pages of `/movie/upcoming` GB, **1 of 58 (1%)**. A screen
    #: implying completeness it does not have is the failure mode snag 2 names.
    physical_checked: int = 0
    physical_found: int = 0

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged


#: Every string these match was read off live TMDB on 2026-09-15, across a 60-film sample
#: of this collection: `'4k Ultra HD Blu-ray'`, `'Blu-ray'`, `'DVD'`, `'DVD release'`,
#: `'VHS'`, `'Alien Anthology Blu-ray Box Set'`, `'The Alien Legacy DVD'`.
_FOUR_K_NOTE = re.compile(r"\b(4k|uhd|ultra\s*hd)\b", re.IGNORECASE)
_OBSOLETE_NOTE = re.compile(r"\b(vhs|laserdisc|betamax)\b", re.IGNORECASE)


def classify_physical(note: str) -> str | None:
    """Which of `RELEASE_TYPES`' two physical members a TMDB type-5 entry is.

    **TMDB type 5 means "Physical" and nothing more** — a 4K disc and a Blu-ray released
    the same day are one entry — so the free-text ``note`` a contributor typed is the only
    signal there is.

    - a note naming 4K/UHD → ``4k_uhd_release``
    - a note naming *only* an obsolete format → ``None``, skipped. A VHS date is a fact
      about 1994, and a calendar of upcoming releases has no use for it.
    - anything else, including an empty note → ``blu_ray_release``

    **The last line is a deliberate approximation, admitted here.** `RELEASE_TYPES` has no
    DVD member, so a DVD-only release is recorded as `blu_ray_release`, which reads as
    "out on disc". Inventing a vocabulary member for a format nobody in this collection is
    waiting for would be worse; widening the two labels slightly is the smaller lie.
    """
    if _OBSOLETE_NOTE.search(note) and not _FOUR_K_NOTE.search(note):
        return None
    return "4k_uhd_release" if _FOUR_K_NOTE.search(note) else "blu_ray_release"


def _release_year(raw: str | None) -> date | None:
    if not raw or len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


async def _movies_by_tmdb_id(db: AsyncSession, tmdb_ids: list[int]) -> dict[int, uuid.UUID]:
    if not tmdb_ids:
        return {}
    rows = (
        await db.execute(
            select(Movie.tmdb_id, Movie.id).where(
                Movie.tmdb_id.in_(tmdb_ids), Movie.deleted_at.is_(None)
            )
        )
    ).all()
    return {int(tmdb_id): movie_id for tmdb_id, movie_id in rows if tmdb_id is not None}


#: TMDB's release types. 5 is a physical release (disc), 2 and 3 are limited and wide
#: cinema releases. Pipe means "either" in TMDB's filter syntax.
PHYSICAL_TYPES = "5"
CINEMA_TYPES = "2|3"
TMDB_CINEMA_TYPES = frozenset({2, 3})

#: How many pages of each kind one run reads, at 20 films a page. 28 GB disc releases were
#: listed for the 14 weeks from 23 Sep 2026, so six months of discs is a few pages; the cap
#: is there so a run cannot walk TMDB's whole index.
MAX_PAGES = 10

#: The calendar refreshes itself when it is read and older than this.
REFRESH_AFTER = timedelta(hours=24)
#: A refresh that claimed the row this recently is assumed to be still running.
REFRESH_RUNNING_FOR = timedelta(minutes=30)


async def _discovered(
    tmdb: TMDBClient,
    *,
    region: str,
    release_types: str,
    today: date,
    horizon: date,
    result: IngestResult,
) -> list[SearchResult]:
    """Every film TMDB lists with a release of these types in the window, once each.

    Keyed by id, not appended: TMDB's paginated lists are re-sorted between requests, so a
    film can appear on two pages of one run — the defect the first live ingestion hit in
    Batch 17. A page that fails keeps the pages before it.
    """
    films: dict[int, SearchResult] = {}
    for page in range(1, MAX_PAGES + 1):
        try:
            batch = await tmdb.discover_by_release_type(
                region=region,
                release_types=release_types,
                date_from=today,
                date_to=horizon,
                page=page,
            )
        except Exception as exc:  # noqa: BLE001 - one bad page must not lose the others
            result.errors.append(f"{release_types} page {page}: {exc}")
            break
        for film in batch.results:
            films.setdefault(film.id, film)
        if page >= batch.total_pages or not batch.results:
            break
    return list(films.values())


async def ingest_releases(
    db: AsyncSession,
    tmdb: TMDBClient,
    *,
    region: str = "GB",
    genre_ids: set[int] | None = None,
    horizon_days: int = 183,
    dry_run: bool = False,
) -> IngestResult:
    """Fill `release_calendar` with disc and cinema releases, six months ahead — Batch T5.

    **It asks TMDB by release type.** Until Batch T5 this read `/movie/upcoming` — films
    about to reach cinemas — and looked for disc dates among them. Those films almost never
    have one yet: 1 of 58 when measured, and none written in production. Asked directly for
    GB physical releases, TMDB listed 28 for the 14 weeks from 23 Sep 2026, re-issues of
    older films among them.

    - **Discs** are every GB type-5 release in the window, classified 4K or Blu-ray by the
      note a contributor typed (:func:`classify_physical`). They are not genre-filtered: a
      collector's disc calendar is about the discs.
    - **Cinema dates** keep §7.3's genres of interest.
    - Each film's own GB date comes from its release dates, because the date on a discover
      result is the film's premiere. **The earliest date in the window wins**, per type.

    Idempotent on `(tmdb_id, release_type, region)`, as before.
    """
    result = IngestResult()
    today = utc_today()
    horizon = today + timedelta(days=horizon_days)

    discs = await _discovered(
        tmdb,
        region=region,
        release_types=PHYSICAL_TYPES,
        today=today,
        horizon=horizon,
        result=result,
    )
    cinema = await _discovered(
        tmdb, region=region, release_types=CINEMA_TYPES, today=today, horizon=horizon, result=result
    )

    #: (tmdb id, release type) -> (tmdb id, title, date, type, overview, poster)
    candidates: dict[tuple[int, str], tuple[int, str, date, str, str | None, str | None]] = {}

    def offer(film: SearchResult, kind: str, when: date) -> None:
        existing = candidates.get((film.id, kind))
        if existing is None or when < existing[2]:
            candidates[(film.id, kind)] = (
                film.id,
                film.title,
                when,
                kind,
                film.overview,
                film.poster_path,
            )

    wanted_cinema = {
        film.id: film
        for film in cinema
        if not genre_ids or genre_ids.intersection(film.genre_ids or [])
    }
    result.skipped += len(cinema) - len(wanted_cinema)
    disc_ids = {film.id for film in discs}
    everything = {film.id: film for film in [*discs, *wanted_cinema.values()]}

    for tmdb_id in sorted(everything):
        film = everything[tmdb_id]
        is_disc = tmdb_id in disc_ids
        if is_disc:
            result.physical_checked += 1
        try:
            dates = await tmdb.get_release_dates(tmdb_id)
        except Exception as exc:  # noqa: BLE001 - one film must not lose the others
            result.errors.append(f"release_dates {tmdb_id}: {exc}")
            continue
        found_disc = False
        for released in dates.for_country(region):
            when = _release_year(released.release_date)
            if when is None or when < today or when > horizon:
                continue
            if released.type == TMDB_RELEASE_PHYSICAL and is_disc:
                kind = classify_physical(released.note)
                if kind is None:
                    continue
                offer(film, kind, when)
                found_disc = True
            elif released.type in TMDB_CINEMA_TYPES and tmdb_id in wanted_cinema:
                offer(film, "theatrical", when)
        if found_disc:
            result.physical_found += 1

    await _write_candidates(db, candidates, region=region, result=result, dry_run=dry_run)
    await _write_curated_events(
        db, region=region, today=today, horizon=horizon, result=result, dry_run=dry_run
    )
    if not dry_run:
        await db.commit()
    return result


async def _write_candidates(
    db: AsyncSession,
    candidates: dict[tuple[int, str], tuple[int, str, date, str, str | None, str | None]],
    *,
    region: str,
    result: IngestResult,
    dry_run: bool,
) -> None:
    known = await _movies_by_tmdb_id(db, sorted({key[0] for key in candidates}))
    existing = {
        (row.tmdb_id, row.release_type, row.region): row
        for row in (
            await db.execute(
                select(ReleaseCalendarEntry).where(ReleaseCalendarEntry.tmdb_id.is_not(None))
            )
        )
        .scalars()
        .all()
    }

    for tmdb_id, title, when, kind, overview, poster in candidates.values():
        row = existing.get((tmdb_id, kind, region))
        if row is None:
            result.created += 1
            if not dry_run:
                db.add(
                    ReleaseCalendarEntry(
                        id=uuid.uuid4(),
                        movie_id=known.get(tmdb_id),
                        title=title,
                        release_type=kind,
                        release_date=when,
                        region=region,
                        tmdb_id=tmdb_id,
                        overview=overview,
                        poster_path=poster,
                        added_at=utcnow(),
                    )
                )
            continue

        if row.release_date == when and row.title == title:
            result.unchanged += 1
            continue
        result.updated += 1
        if not dry_run:
            # A release date moving is the *point* of a calendar. Updating in place means
            # a subscriber's existing event moves rather than duplicating.
            row.release_date = when
            row.title = title
            row.overview = overview
            row.poster_path = poster
            row.movie_id = known.get(tmdb_id) or row.movie_id


async def _write_curated_events(
    db: AsyncSession,
    *,
    region: str,
    today: date,
    horizon: date,
    result: IngestResult,
    dry_run: bool,
) -> None:
    for title, kind, when in CURATED_EVENTS:
        if when < today or when > horizon:
            result.skipped += 1
            continue
        present = (
            await db.execute(
                select(ReleaseCalendarEntry).where(
                    ReleaseCalendarEntry.title == title,
                    ReleaseCalendarEntry.release_type == kind,
                    ReleaseCalendarEntry.release_date == when,
                )
            )
        ).scalar_one_or_none()
        if present is not None:
            result.unchanged += 1
            continue
        result.created += 1
        if not dry_run:
            db.add(
                ReleaseCalendarEntry(
                    id=uuid.uuid4(),
                    movie_id=None,
                    title=title,
                    release_type=kind,
                    release_date=when,
                    region=region,
                    tmdb_id=None,
                    added_at=utcnow(),
                )
            )


# ---------------------------------------------------------------------------
# Batch T5 — the calendar keeps itself fresh
# ---------------------------------------------------------------------------


async def claim_refresh(db: AsyncSession, *, now: datetime, force: bool = False) -> bool:
    """Take the right to refresh, if the calendar is stale and nobody else has it.

    One conditional ``UPDATE``, so two readers at the same moment cannot both win: the
    database decides. ``force`` (the admin button, the command) skips the "is it stale"
    test but still respects a refresh that is running.
    """
    running_since = now - REFRESH_RUNNING_FOR
    stale_before = now - REFRESH_AFTER
    conditions = [
        CalendarRefreshState.id == 1,
        or_(
            CalendarRefreshState.last_started_utc.is_(None),
            CalendarRefreshState.last_started_utc < running_since,
            and_(
                CalendarRefreshState.last_finished_utc.is_not(None),
                CalendarRefreshState.last_finished_utc >= CalendarRefreshState.last_started_utc,
            ),
        ),
    ]
    if not force:
        conditions.append(
            or_(
                CalendarRefreshState.last_finished_utc.is_(None),
                CalendarRefreshState.last_finished_utc < stale_before,
            )
        )
    claimed = await db.execute(
        update(CalendarRefreshState)
        .where(*conditions)
        .values(last_started_utc=now)
        .returning(CalendarRefreshState.id)
    )
    won = claimed.scalar_one_or_none() is not None
    await db.commit()
    return won


async def refresh_calendar(
    db: AsyncSession, tmdb: TMDBClient, *, force: bool = False, now: datetime | None = None
) -> IngestResult | None:
    """Refresh the calendar if it is stale (or ``force``) and nobody else is — Batch T5.

    ``None`` when there was nothing to do. The run is recorded whether or not TMDB
    co-operated: a run that half-worked still wrote real rows, and the page says how fresh
    the calendar is from ``last_finished_utc``.
    """
    now = now or utcnow()
    if not await claim_refresh(db, now=now, force=force):
        return None
    from src.routers.discovery import _collected_genres

    genres = set(await _collected_genres(db, 8)) or None
    try:
        result = await ingest_releases(db, tmdb, region="GB", genre_ids=genres)
        # Batch X12c: TMDB's terms bar keeping its data over six months, so the films whose
        # fields are 150 days old are fetched again here, a few at a time. A failure is
        # reported in the run's errors and never fails the calendar.
        try:
            stale = await refresh_stale_fields(db, tmdb, now=now)
            if stale.refreshed or stale.failed:
                logger.info(
                    "tmdb_fields_refreshed",
                    refreshed=stale.refreshed,
                    failed=stale.failed,
                    remaining=stale.remaining,
                )
            result.errors.extend(stale.errors[:5])
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            result.errors.append(f"TMDB field refresh failed: {exc}"[:200])
    except Exception as exc:
        await db.rollback()
        await db.execute(
            update(CalendarRefreshState)
            .where(CalendarRefreshState.id == 1)
            .values(last_finished_utc=utcnow(), last_error=f"refresh failed: {exc}")
        )
        await db.commit()
        raise
    await db.execute(
        update(CalendarRefreshState)
        .where(CalendarRefreshState.id == 1)
        .values(
            last_finished_utc=utcnow(),
            last_error="; ".join(result.errors) or None,
            last_created=result.created,
            last_updated=result.updated,
            last_unchanged=result.unchanged,
            last_disc_releases=result.physical_found,
        )
    )
    await db.commit()
    return result


async def refresh_calendar_if_stale() -> None:
    """The background half of a read: refresh a stale calendar after the response is sent.

    Its own session and its own TMDB client, because the request's are gone by the time
    this runs. **This is not an in-process scheduler** (#60 rules those out): nothing runs
    on a timer. A read triggers idempotent work at most once a day, and a container
    restarting mid-run only means the next read finishes the job.
    """
    try:
        async with AsyncSessionLocal() as db, TMDBClient() as tmdb:
            await refresh_calendar(db, tmdb)
    except Exception:  # noqa: BLE001 - a background refresh must never surface to a reader
        logger.warning("calendar_refresh_failed", exc_info=True)


async def calendar_refreshed_at(db: AsyncSession) -> datetime | None:
    """When the calendar last finished refreshing, for the page to say."""
    return await db.scalar(
        select(CalendarRefreshState.last_finished_utc).where(CalendarRefreshState.id == 1)
    )


# ---------------------------------------------------------------------------
# Feed tokens — the credential for an unauthenticated URL
# ---------------------------------------------------------------------------


def hash_feed_token(token: str) -> str:
    """SHA-256 hex, matching ``refresh_tokens``' scheme.

    Not bcrypt, and deliberately: this is a high-entropy random string, not a password, so
    there is nothing to brute-force offline and no need for a slow KDF. Hashing exists so
    that a database leak yields no working URLs — and so that lookup is an indexed equality
    test on a fixed-width digest, which is the same amount of work for every candidate.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_feed_token() -> str:
    """A URL-safe token with 256 bits of entropy.

    This is the whole credential for a public endpoint, so it is sized as one:
    ``token_urlsafe(32)`` is 32 random bytes, ~43 characters. Guessing it is not a threat
    model anybody needs to think about again.
    """
    return secrets.token_urlsafe(32)


async def issue_feed_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Revoke whatever link this person had, and hand back a new one **once**.

    Rotating on every subscribe is what makes an accidentally-shared URL recoverable: there
    is no other way to take back a link that has already been pasted somewhere. The
    plaintext is returned here and never stored.
    """
    live = (
        (
            await db.execute(
                select(CalendarFeedToken).where(
                    CalendarFeedToken.user_id == user_id,
                    CalendarFeedToken.revoked_at_utc.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for row in live:
        row.revoked_at_utc = utcnow()
    await db.flush()

    token = new_feed_token()
    db.add(
        CalendarFeedToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=hash_feed_token(token),
            created_at_utc=utcnow(),
        )
    )
    await db.commit()
    return token


async def resolve_feed_token(db: AsyncSession, token: str) -> CalendarFeedToken | None:
    """Find the live token row for a presented string, and stamp its last use.

    Looked up **by hash**, so the plaintext is never compared against anything and a row
    is found by an indexed equality test rather than by scanning. A revoked row resolves to
    ``None`` — the same answer as a token that never existed, which is what the endpoint
    needs so that the two are indistinguishable from outside.
    """
    if not token or len(token) > 200:
        return None
    row = (
        await db.execute(
            select(CalendarFeedToken).where(
                CalendarFeedToken.token_hash == hash_feed_token(token),
                CalendarFeedToken.revoked_at_utc.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.last_used_at_utc = utcnow()
    await db.commit()
    return row
