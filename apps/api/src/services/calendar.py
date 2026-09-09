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
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utc_today, utcnow
from src.models.movie import Movie
from src.models.release_calendar import CalendarFeedToken, ReleaseCalendarEntry
from src.tmdb import TMDBClient

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

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged


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


async def ingest_upcoming(
    db: AsyncSession,
    tmdb: TMDBClient,
    *,
    region: str = "GB",
    genre_ids: set[int] | None = None,
    pages: int = 3,
    dry_run: bool = False,
) -> IngestResult:
    """Populate `release_calendar` from TMDB's upcoming list — §7.3.

    ``genre_ids`` is §7.3's "filter by genres of interest". Passing ``None`` keeps
    everything, which is what the first run wants: an empty calendar is worse than one with
    a few films nobody will buy.
    """
    result = IngestResult()
    today = utc_today()
    horizon = today + HORIZON

    # Keyed, not appended. **TMDB's paginated `upcoming` list is not stable**: it is
    # re-sorted between requests, so a film can appear on page 2 and again on page 3 of
    # the same run. Found by the first live ingestion — *Shadows of Beirut* came back
    # twice and the unique constraint fired mid-insert.
    #
    # A `--dry-run` cannot catch this: it never writes, so it never reaches the
    # constraint. `STATUS.md` gotcha 16, restated — "the first real write against real
    # data is its own test stage".
    candidates: dict[int, tuple[int, str, date, str, str | None, str | None]] = {}
    for page in range(1, pages + 1):
        try:
            batch = await tmdb.get_upcoming(region=region, page=page)
        except Exception as exc:  # noqa: BLE001 - one bad page must not lose the others
            result.errors.append(f"page {page}: {exc}")
            break
        if not batch.results:
            break
        for entry in batch.results:
            when = _release_year(entry.release_date)
            if when is None or when < today or when > horizon:
                result.skipped += 1
                continue
            if genre_ids and not genre_ids.intersection(entry.genre_ids or []):
                result.skipped += 1
                continue
            if entry.id in candidates:
                # The same film on two pages. Counted once, not skipped — it is a
                # duplicate of something already accepted, not a rejection.
                continue
            candidates[entry.id] = (
                entry.id,
                entry.title,
                when,
                "theatrical",
                entry.overview,
                entry.poster_path,
            )

    known = await _movies_by_tmdb_id(db, list(candidates))
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

    if not dry_run:
        await db.commit()
    return result


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
