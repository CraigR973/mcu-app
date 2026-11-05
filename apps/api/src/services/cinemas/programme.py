"""Stored programme reads: no network, refresh, model or catalogue side effects."""

import uuid
from datetime import date, datetime, timedelta
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


async def programme(
    db: AsyncSession,
    user_id: uuid.UUID,
    start: date,
    end: date,
    venue_ids: list[uuid.UUID] | None = None,
    category: ReleaseFilter = "all",
) -> CinemaProgrammeResponse:
    dates = days_between(start, end)
    now = utcnow()
    venues = list(
        (
            await db.scalars(
                select(CinemaVenue)
                .where(CinemaVenue.deleted_at.is_(None))
                .order_by(CinemaVenue.name)
            )
        ).all()
    )
    known = {v.id: v for v in venues}
    if venue_ids is not None and (not venue_ids or not set(venue_ids) <= set(known)):
        raise ValueError("Select known cinema venues")
    selected = set(venue_ids) if venue_ids is not None else set(known)
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
    venue_responses = [
        ProgrammeVenue(
            id=v.id,
            slug=v.slug,
            name=v.name,
            source=v.source,
            sourceUrl=v.programme_url,
            officialUrl=v.official_url,
            collectionEnabled=v.collection_enabled,
            coverage=[
                date_coverage(v, coverage.get((v.id, day)), day, now, failures.get((v.id, day)))
                for day in dates
            ],
        )
        for v in venues
    ]
    rows = (
        await db.execute(
            select(CinemaScreening, CinemaFilm)
            .join(CinemaFilm, CinemaScreening.film_id == CinemaFilm.id)
            .where(
                CinemaScreening.venue_id.in_(selected),
                CinemaScreening.local_date.in_(dates),
                CinemaScreening.starts_utc > now,
                CinemaScreening.deleted_at.is_(None),
                CinemaScreening.source_expired.is_(False),
                CinemaScreening.confirmation.in_(("confirmed", "unconfirmed")),
                CinemaFilm.deleted_at.is_(None),
            )
            .order_by(CinemaScreening.starts_utc, CinemaScreening.venue_id, CinemaScreening.id)
        )
    ).all()
    movie_ids = {f.movie_id for _, f in rows if f.movie_id}
    movies = (
        {
            m.id: m
            for m in (
                await db.scalars(
                    select(Movie).where(
                        Movie.id.in_(movie_ids), Movie.deleted_at.is_(None), Movie.is_tv.is_(False)
                    )
                )
            ).all()
        }
        if movie_ids
        else {}
    )
    owned = (
        set(
            (
                await db.scalars(
                    select(CollectionItem.movie_id).where(
                        CollectionItem.movie_id.in_(movies), owned_copy()
                    )
                )
            ).all()
        )
        if movies
        else set()
    )
    watched = (
        set(
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
        if movies
        else set()
    )
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
        record = coverage.get((showing.venue_id, showing.local_date))
        stale = now - showing.last_seen_utc > timedelta(hours=30)
        age = upstream_age(record, now)
        allowed = (
            showing.confirmation == "confirmed"
            and not stale
            and age != "stale"
            and known[showing.venue_id].collection_enabled
            and record is not None
            and record.status != "failed"
            and (showing.venue_id, showing.local_date) not in failures
        )
        effective = release_category(showing.category_evidence, identity_verified=verified)
        reason = showing.category_evidence.get("runReason") if verified else None
        groups[key].showings.append(
            ProgrammeShowing(
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
        )
    complete = not truncated and all(
        c.status in ("healthy", "empty")
        for v in venue_responses
        if v.id in selected
        for c in v.coverage
    )
    return CinemaProgrammeResponse(
        generatedAtUtc=now,
        window=ProgrammeWindow(dateFrom=start, dateTo=end),
        venues=venue_responses,
        films=list(groups.values()),
        categoryCounts=ProgrammeCategoryCounts(**counts),
        matchedShowingCount=len(matched),
        returnedShowingCount=min(len(matched), 2000),
        truncated=truncated,
        selectionComplete=complete,
    )
