"""Stored programme reads: no network, refresh, model or catalogue side effects."""

import uuid
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import cached_property
from typing import Literal, cast

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.cinema import (
    CinemaCoverage,
    CinemaFilm,
    CinemaRefreshRun,
    CinemaScreening,
    CinemaVenue,
)
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.watch_log import WatchLog
from src.schemas.cinemas import (
    CinemaProgrammeResponse,
    CoverageStatus,
    ProgrammeCategoryCounts,
    ProgrammeCategoryEvidence,
    ProgrammeDateCoverage,
    ProgrammeFilm,
    ProgrammeShowing,
    ProgrammeVenue,
    ProgrammeWindow,
    ReleaseFilter,
)
from src.services.cinemas.awaiting import awaiting_first_enable
from src.services.cinemas.domain import booking_url, days_between, release_category

Age = Literal["unknown", "current", "stale"]


def upstream_age(record: CinemaCoverage | None, now: datetime) -> Age:
    if record is None or record.upstream_utc is None:
        return "unknown"
    return "stale" if now - record.upstream_utc > timedelta(hours=36) else "current"


def date_coverage(
    venue: CinemaVenue,
    record: CinemaCoverage | None,
    day: date,
    now: datetime,
    failed_attempt: datetime | None = None,
) -> ProgrammeDateCoverage:
    age = upstream_age(record, now)
    status: CoverageStatus
    if failed_attempt is not None or (record and record.status == "failed"):
        status = "failed"
    elif not venue.collection_enabled:
        status = "notEnabled"
    elif record is None:
        status = "unavailable"
    elif record.last_success_utc is None:
        status = "partial" if record.status == "partial" else "unavailable"
    elif now - record.last_success_utc > timedelta(hours=30) or age == "stale":
        status = "stale"
    elif record.complete:
        status = "empty" if record.status == "empty" else "healthy"
    else:
        status = "partial"
    return ProgrammeDateCoverage(
        localDate=day,
        status=status,
        observed=bool(record and record.observed and not failed_attempt),
        complete=bool(record and record.complete and not failed_attempt),
        lastAttemptUtc=failed_attempt or (record.last_attempt_utc if record else None),
        lastSuccessUtc=record.last_success_utc if record else None,
        sourceUpdateLabel=record.source_update_label if record else None,
        upstreamUtc=record.upstream_utc if record else None,
        upstreamAge=age,
        error="Latest programme refresh did not finish"
        if failed_attempt
        else record.error
        if record
        else None,
    )


@dataclass
class Window:
    """One read's dates and venues, their coverage, and the unfinished runs that override it.

    Shared by the programme and AC4's film-first reads, so a showing's ticket link follows one
    rule wherever it is drawn.
    """

    now: datetime
    dates: list[date]
    venues: list[CinemaVenue]
    coverage: dict[tuple[uuid.UUID, date], CinemaCoverage]
    failures: dict[tuple[uuid.UUID, date], datetime]

    @cached_property
    def known(self) -> dict[uuid.UUID, CinemaVenue]:
        return {v.id: v for v in self.venues}

    def venue_responses(self) -> list[ProgrammeVenue]:
        return [
            ProgrammeVenue(
                id=v.id,
                slug=v.slug,
                name=v.name,
                source=v.source,
                sourceUrl=v.programme_url,
                officialUrl=v.official_url,
                collectionEnabled=v.collection_enabled,
                coverage=[
                    date_coverage(
                        v,
                        self.coverage.get((v.id, day)),
                        day,
                        self.now,
                        self.failures.get((v.id, day)),
                    )
                    for day in self.dates
                ],
            )
            for v in self.venues
        ]

    def showing(
        self, showing: CinemaScreening, film: CinemaFilm, *, verified: bool
    ) -> ProgrammeShowing:
        """One showing on the wire, with its ticket link only while its listing is current."""
        record = self.coverage.get((showing.venue_id, showing.local_date))
        stale = self.now - showing.last_seen_utc > timedelta(hours=30)
        age = upstream_age(record, self.now)
        allowed = (
            showing.confirmation == "confirmed"
            and not stale
            and age != "stale"
            and self.known[showing.venue_id].collection_enabled
            and record is not None
            and record.status != "failed"
            and (showing.venue_id, showing.local_date) not in self.failures
        )
        effective = release_category(showing.category_evidence, identity_verified=verified)
        reason = showing.category_evidence.get("runReason") if verified else None
        return ProgrammeShowing(
            id=showing.id,
            venueId=showing.venue_id,
            sourceTitle=film.title,
            startsAtUtc=showing.starts_utc,
            endsAtUtc=showing.ends_utc,
            screen=showing.screen,
            formats=showing.formats,
            releaseCategory=effective,
            sourceReleaseDate=film.source_release_date,
            reissue=True
            if effective == "olderFilm" and showing.category_evidence.get("reissue") is True
            else None,
            categoryConfidence="verified" if effective != "unclassified" else "unverified",
            categoryEvidence=ProgrammeCategoryEvidence(
                # AC3's runs rest on TMDB's UK dates, not a source page; AB6's on a quote.
                sourceUrl=showing.category_evidence.get("sourceUrl")
                if effective != "unclassified" and not reason
                else None,
                description=(reason or showing.category_evidence.get("quote") or "")
                if effective != "unclassified"
                else "Release run unverified",
            ),
            categoryReason=reason,
            confirmation=cast(Literal["confirmed", "unconfirmed"], showing.confirmation),
            lastSeenUtc=showing.last_seen_utc,
            observationStale=stale,
            upstreamAge=age,
            bookingUrl=booking_url(showing.booking_url) if allowed else None,
        )


async def load_window(db: AsyncSession, dates: list[date], now: datetime) -> Window:
    # AE4 (#355): a cinema awaiting its first enable is read for its evidence, not shown.
    hidden = await awaiting_first_enable(db)
    venues = [
        venue
        for venue in (
            await db.scalars(
                select(CinemaVenue)
                .where(CinemaVenue.deleted_at.is_(None))
                .order_by(CinemaVenue.name)
            )
        ).all()
        if venue.id not in hidden
    ]
    known = {v.id for v in venues}
    coverage = {
        (r.venue_id, r.local_date): r
        for r in (
            await db.scalars(select(CinemaCoverage).where(CinemaCoverage.local_date.in_(dates)))
        ).all()
    }
    # A crash/deadline can precede per-venue coverage writes. Do not let an old success
    # keep live showing actions just because that failed attempt never reached promotion.
    failures: dict[tuple[uuid.UUID, date], datetime] = {}
    incomplete = (
        await db.scalars(
            select(CinemaRefreshRun).where(
                CinemaRefreshRun.started_utc >= now - timedelta(hours=30),
                or_(
                    CinemaRefreshRun.status.in_(("failed", "abandoned")),
                    and_(
                        CinemaRefreshRun.status == "running",
                        CinemaRefreshRun.started_utc < now - timedelta(minutes=5),
                    ),
                ),
            )
        )
    ).all()
    for run in incomplete:
        try:
            first = date.fromisoformat(run.report["dateFrom"])
            last = date.fromisoformat(run.report["dateTo"])
            affected = set(run.report["venueIds"])
        except (KeyError, ValueError, TypeError):
            continue
        for venue_id in known:
            for day in dates:
                date_key = (venue_id, day)
                previous = coverage.get(date_key)
                if (
                    str(venue_id) in affected
                    and first <= day <= last
                    and run.started_utc > (previous.last_attempt_utc if previous else datetime.min)
                ):
                    failures[date_key] = max(failures.get(date_key, datetime.min), run.started_utc)
    return Window(now, dates, venues, coverage, failures)


async def window_rows(
    db: AsyncSession, window: Window, venue_ids: Collection[uuid.UUID]
) -> list[tuple[CinemaScreening, CinemaFilm]]:
    """Every listed showing still to start in the window, earliest first."""
    rows = (
        await db.execute(
            select(CinemaScreening, CinemaFilm)
            .join(CinemaFilm, CinemaScreening.film_id == CinemaFilm.id)
            .where(
                CinemaScreening.venue_id.in_(venue_ids),
                CinemaScreening.local_date.in_(window.dates),
                CinemaScreening.starts_utc > window.now,
                CinemaScreening.deleted_at.is_(None),
                CinemaScreening.source_expired.is_(False),
                CinemaScreening.confirmation.in_(("confirmed", "unconfirmed")),
                CinemaFilm.deleted_at.is_(None),
            )
            .order_by(CinemaScreening.starts_utc, CinemaScreening.venue_id, CinemaScreening.id)
        )
    ).all()
    return [(showing, film) for showing, film in rows]


@dataclass
class Personal:
    """The catalogue films a programme names, and which the reader owns or has watched."""

    movies: dict[uuid.UUID, Movie]
    owned: set[uuid.UUID]
    watched: set[uuid.UUID]


async def personal(
    db: AsyncSession, user_id: uuid.UUID, movie_ids: Iterable[uuid.UUID | None]
) -> Personal:
    wanted = {movie_id for movie_id in movie_ids if movie_id}
    if not wanted:
        return Personal({}, set(), set())
    movies = {
        m.id: m
        for m in (
            await db.scalars(
                select(Movie).where(
                    Movie.id.in_(wanted), Movie.deleted_at.is_(None), Movie.is_tv.is_(False)
                )
            )
        ).all()
    }
    if not movies:
        return Personal({}, set(), set())
    owned = set(
        (
            await db.scalars(
                select(CollectionItem.movie_id).where(
                    CollectionItem.movie_id.in_(movies), owned_copy()
                )
            )
        ).all()
    )
    watched = set(
        (
            await db.scalars(
                select(WatchLog.movie_id).where(
                    WatchLog.movie_id.in_(movies),
                    WatchLog.user_id == user_id,
                    WatchLog.deleted_at.is_(None),
                )
            )
        ).all()
    )
    return Personal(movies, owned, watched)


async def programme(
    db: AsyncSession,
    user_id: uuid.UUID,
    start: date,
    end: date,
    venue_ids: list[uuid.UUID] | None = None,
    category: ReleaseFilter = "all",
) -> CinemaProgrammeResponse:
    dates = days_between(start, end)
    window = await load_window(db, dates, utcnow())
    known = window.known
    if venue_ids is not None and (not venue_ids or not set(venue_ids) <= set(known)):
        raise ValueError("Select known cinema venues")
    selected = set(venue_ids) if venue_ids is not None else set(known)
    venue_responses = window.venue_responses()
    rows = await window_rows(db, window, selected)
    mine = await personal(db, user_id, (f.movie_id for _, f in rows))
    movies, owned, watched = mine.movies, mine.owned, mine.watched
    counts = {"newRelease": 0, "olderFilm": 0, "unclassified": 0}
    matched = []
    for showing, film in rows:
        effective = release_category(
            showing.category_evidence, identity_verified=film.identity_status == "verified"
        )
        counts[effective] += 1
        if category == "all" or effective == category:
            matched.append((showing, film))
    truncated = len(matched) > 2000
    groups: dict[str, ProgrammeFilm] = {}
    for showing, film in matched[:2000]:
        movie = movies.get(film.movie_id) if film.movie_id else None
        verified = film.identity_status == "verified"
        global_id = film.evidence.get("tmdbId") if verified else None
        if movie and movie.tmdb_id:
            global_id = movie.tmdb_id
        key = (
            f"tmdb:{global_id}"
            if global_id
            else (
                f"movie:{movie.id}"
                if movie
                else f"imdb:{film.evidence['imdbId']}"
                if verified and film.evidence.get("imdbId")
                else f"source:{film.id}"
            )
        )
        if key not in groups:
            groups[key] = ProgrammeFilm(
                id=key,
                title=movie.title if movie else film.title,
                movieId=movie.id if movie else None,
                originalYear=film.original_year if verified else None,
                yearConfidence="verified"
                if verified and film.original_year is not None
                else "unverified",
                identityStatus=cast(
                    Literal["verified", "unverified", "conflict", "review", "event"],
                    film.identity_status,
                ),
                owned=movie.id in owned if movie else None,
                watched=movie.id in watched if movie else None,
                showings=[],
            )
        if movie and verified:
            group = groups[key]
            group.title = movie.title
            group.movieId = movie.id
            group.originalYear = movie.year
            group.yearConfidence = "verified" if movie.year is not None else "unverified"
            group.owned = movie.id in owned
            group.watched = movie.id in watched
        groups[key].showings.append(window.showing(showing, film, verified=verified))
    complete = not truncated and all(
        c.status in ("healthy", "empty")
        for v in venue_responses
        if v.id in selected
        for c in v.coverage
    )
    return CinemaProgrammeResponse(
        generatedAtUtc=window.now,
        window=ProgrammeWindow(dateFrom=start, dateTo=end),
        venues=venue_responses,
        films=list(groups.values()),
        categoryCounts=ProgrammeCategoryCounts(**counts),
        matchedShowingCount=len(matched),
        returnedShowingCount=min(len(matched), 2000),
        truncated=truncated,
        selectionComplete=complete,
    )
