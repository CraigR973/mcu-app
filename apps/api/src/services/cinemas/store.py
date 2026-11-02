"""Atomic venue promotion, conservative disappearance and fenced writers."""

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.cinema import (
    CinemaCoverage,
    CinemaFilm,
    CinemaRefreshRun,
    CinemaScreening,
)
from src.models.movie import Movie
from src.services.cinemas.domain import (
    Showing,
    Snapshot,
    SourceError,
    days_between,
    release_category,
)
from src.services.cinemas.metadata import Metadata, category_evidence, corroboration, fingerprint
from src.services.cinemas.venues import Venue


class LostLease(SourceError):
    """A late or replaced run cannot publish a snapshot."""


async def fence(db: AsyncSession, run_id: uuid.UUID) -> CinemaRefreshRun:
    run = await db.scalar(
        select(CinemaRefreshRun).where(CinemaRefreshRun.id == run_id).with_for_update()
    )
    if run is None or run.status != "running" or run.lease_expires_utc <= utcnow():
        raise LostLease("Cinema refresh lease is missing, expired or replaced")
    run.heartbeat_utc = utcnow()
    return run


async def _film(
    db: AsyncSession,
    source: str,
    row: Showing,
    observed: datetime,
    metadata: Metadata | None = None,
    picked: bool = False,
) -> CinemaFilm:
    film = await db.scalar(
        select(CinemaFilm).where(CinemaFilm.source == source, CinemaFilm.source_key == row.film_key)
    )
    if film is None:
        film = CinemaFilm(source=source, source_key=row.film_key, title=row.title)
        db.add(film)
    prior_evidence = film.evidence or {}
    source_fingerprint = fingerprint(row)
    changed = bool(
        prior_evidence.get("sourceFingerprint")
        and prior_evidence["sourceFingerprint"] != source_fingerprint
    )
    if picked:
        if (
            metadata is None
            or metadata.candidate is None
            or not corroboration(row, metadata.candidate)
        ):
            raise SourceError("Reviewed mapping lacks corroboration")
        row = replace(row, tmdb_id=metadata.candidate.tmdb_id, imdb_id=metadata.candidate.imdb_id)
    conflict = bool(
        row.evidence.get("conflict")
        or row.evidence.get("combinedProgramme")
        or (film.identity_status == "conflict" and not picked)
    )
    if film.identity_status == "verified" and (film.title != row.title or changed) and not picked:
        conflict = True
    for key, supplied in (("tmdbId", row.tmdb_id), ("imdbId", row.imdb_id)):
        if supplied and prior_evidence.get(key) and supplied != prior_evidence[key] and not picked:
            conflict = True
    if (
        film.identity_status == "verified"
        and metadata
        and metadata.candidate
        and prior_evidence.get("tmdbId")
        and metadata.candidate.tmdb_id != prior_evidence["tmdbId"]
        and not picked
    ):
        conflict = True
    tmdb_id = row.tmdb_id
    imdb_id = row.imdb_id
    if film.identity_status == "verified" and not conflict:
        tmdb_id = tmdb_id or prior_evidence.get("tmdbId")
        imdb_id = imdb_id or prior_evidence.get("imdbId")
    conditions = []
    if tmdb_id is not None:
        conditions.append(Movie.tmdb_id == tmdb_id)
    if imdb_id is not None:
        conditions.append(Movie.imdb_id == imdb_id)
    candidates = (
        list(
            (
                await db.scalars(
                    select(Movie).where(
                        Movie.deleted_at.is_(None), Movie.is_tv.is_(False), or_(*conditions)
                    )
                )
            ).all()
        )
        if conditions
        else []
    )
    movie = candidates[0] if len(candidates) == 1 else None
    if len(candidates) > 1:
        conflict = True
    if movie and (
        (tmdb_id and movie.tmdb_id and movie.tmdb_id != tmdb_id)
        or (imdb_id and movie.imdb_id and movie.imdb_id != imdb_id)
    ):
        conflict = True
    # Previously verified source-key mappings may survive missing enrichment, but not
    # a changed source title or an explicit identity conflict. Never match title alone.
    if not conditions and film.identity_status == "verified" and film.movie_id and not conflict:
        movie = await db.get(Movie, film.movie_id)
        if movie and (movie.deleted_at is not None or movie.is_tv):
            movie = None
    identified = bool(movie or conditions) and not conflict
    film.title = row.title
    film.movie_id = movie.id if movie and not conflict else None
    film.original_year = (
        movie.year
        if movie and not conflict
        else (film.original_year if identified and not changed and not picked else None)
    )
    film.identity_status = "conflict" if conflict else "verified" if identified else "unverified"
    film.source_release_date = row.source_release
    retained = (
        {}
        if changed
        else {k: v for k, v in prior_evidence.items() if k in {"metadata", "reviewedMapping"}}
    )
    if metadata is not None:
        retained["metadata"] = metadata.model_dump(mode="json")
    if picked:
        assert metadata is not None and metadata.candidate is not None
        retained["reviewedMapping"] = {
            "tmdbId": tmdb_id,
            "fingerprint": source_fingerprint,
            "corroboration": corroboration(row, metadata.candidate),
        }
    film.evidence = {
        **retained,
        **row.evidence,
        "tmdbId": tmdb_id,
        "imdbId": imdb_id,
        "conflict": conflict,
        "sourceIdentity": row.identity_facts,
        "sourceFingerprint": source_fingerprint,
    }
    film.last_seen_utc = observed
    film.deleted_at = None
    await db.flush()
    return film


async def promote(
    db: AsyncSession,
    venue: Venue,
    snapshot: Snapshot,
    start: date,
    end: date,
    run_id: uuid.UUID,
    metadata: dict[tuple[str, str], Metadata] | None = None,
    picks: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Caller owns the transaction: either this entire venue/date window lands or none."""
    await fence(db, run_id)
    now = utcnow()
    observed = snapshot.observed_utc
    if observed is None or observed.tzinfo is not None or observed > now + timedelta(minutes=1):
        raise SourceError("Snapshot observation time is missing or not naive UTC")
    if not snapshot.failed and now - observed > timedelta(hours=30):
        raise SourceError("Snapshot is stale; do not reset its age by importing it")
    snapshot.validate()
    dates = days_between(start, end)
    coverage = {
        r.local_date: r
        for r in (
            await db.scalars(
                select(CinemaCoverage).where(
                    CinemaCoverage.venue_id == venue.id, CinemaCoverage.local_date.in_(dates)
                )
            )
        ).all()
    }
    existing = {
        r.source_key: r
        for r in (
            await db.scalars(
                select(CinemaScreening).where(
                    CinemaScreening.venue_id == venue.id,
                    or_(
                        CinemaScreening.local_date.in_(dates),
                        CinemaScreening.source_key.in_([r.key for r in snapshot.rows]),
                    ),
                )
            )
        ).all()
    }
    counts = {"added": 0, "updated": 0, "unconfirmed": 0, "withdrawn": 0, "cancelled": 0}
    seen: set[str] = set()
    films: dict[str, CinemaFilm] = {}
    if not snapshot.failed:
        for source in snapshot.rows:
            if source.start.date() not in dates:
                raise SourceError("A source row lies outside the requested civil window")
            film = films.get(source.film_key)
            if film is None:
                key = (venue.source, source.film_key)
                film = await _film(
                    db,
                    venue.source,
                    source,
                    observed,
                    (metadata or {}).get(key),
                    key in (picks or set()),
                )
                films[source.film_key] = film
            elif film.title != source.title:
                raise SourceError("One film identity has conflicting programme titles")
            row = existing.get(source.key)
            added = row is None
            if row is None:
                row = CinemaScreening(
                    venue_id=venue.id, source_key=source.key, first_seen_utc=observed
                )
                db.add(row)
            row.film_id = film.id
            row.identity_strength = source.strength
            row.local_date = source.start.date()
            row.source_local_start = source.source_local
            row.starts_utc = source.start.astimezone(UTC).replace(tzinfo=None)
            row.ends_utc = source.end.astimezone(UTC).replace(tzinfo=None) if source.end else None
            row.screen = source.screen
            row.formats = list(source.formats)
            row.source_expired = source.expired
            row.booking_url = source.booking
            record = film.evidence.get("metadata")
            evidence = category_evidence(
                source, Metadata.model_validate(record) if record else None
            )
            row.release_category = release_category(
                evidence, identity_verified=film.identity_status == "verified"
            )
            row.category_evidence = evidence
            row.confirmation = "cancelled" if source.cancelled else "confirmed"
            if source.expired:
                row.booking_url = None
            row.last_seen_utc = observed
            row.deleted_at = None
            seen.add(source.key)
            counts["added" if added else "updated"] += 1
            counts["cancelled"] += int(source.cancelled)
        for row in existing.values():
            if (
                row.source_key not in seen
                and row.deleted_at is None
                and row.starts_utc > now
                and row.local_date in snapshot.observed_dates
                and row.confirmation in ("confirmed", "unconfirmed")
            ):
                confirmation = (
                    "withdrawn" if row.local_date in snapshot.complete_dates else "unconfirmed"
                )
                # Keep the original URL as history; the read path never exposes it as
                # a showing action while unconfirmed/withdrawn/cancelled/stale.
                if row.confirmation != confirmation:
                    row.confirmation = confirmation
                    counts["withdrawn" if confirmation == "withdrawn" else "unconfirmed"] += 1
    by_date = {d: sum(x.start.date() == d for x in snapshot.rows) for d in dates}
    for day in dates:
        record = coverage.get(day)
        if record is None:
            record = CinemaCoverage(venue_id=venue.id, local_date=day)
            db.add(record)
        record.last_attempt_utc = now
        record.run_id = run_id
        record.error = "; ".join(snapshot.errors)[:1000] or None
        record.observed = day in snapshot.observed_dates and not snapshot.failed
        record.complete = day in snapshot.complete_dates and not snapshot.failed
        record.status = (
            "failed"
            if snapshot.failed
            else (
                "healthy"
                if record.complete and by_date[day]
                else "empty"
                if record.complete
                else "partial"
            )
        )
        if record.observed:
            record.last_success_utc = observed
            record.source_update_label = snapshot.source_update_label
            record.upstream_utc = snapshot.upstream_utc
    # A worker can lose its lease while preparing many rows. Fence again before its
    # caller commits; expired ownership rolls back the whole venue transaction.
    await db.flush()
    await fence(db, run_id)
    return {
        **counts,
        "rows": len(snapshot.rows),
        "observedDates": sorted(d.isoformat() for d in snapshot.observed_dates),
        "completeDates": sorted(d.isoformat() for d in snapshot.complete_dates),
        "errors": snapshot.errors[:10],
        "failed": snapshot.failed,
    }


async def retain(db: AsyncSession, *, limit: int = 500) -> dict[str, int]:
    """Bounded cleanup of this domain only. Caller must hold the refresh fence."""
    now = utcnow()
    if not 0 < limit <= 500:
        raise SourceError("Retention batches are limited to 500 records per table")
    old_showings = (
        select(CinemaScreening.id)
        .where(
            func.coalesce(CinemaScreening.ends_utc, CinemaScreening.starts_utc)
            < now - timedelta(days=30)
        )
        .order_by(CinemaScreening.starts_utc)
        .limit(limit)
    )
    showings = await db.execute(delete(CinemaScreening).where(CinemaScreening.id.in_(old_showings)))
    old_coverage = (
        select(CinemaCoverage.id)
        .where(CinemaCoverage.local_date < (now - timedelta(days=90)).date())
        .limit(limit)
    )
    await db.execute(delete(CinemaCoverage).where(CinemaCoverage.id.in_(old_coverage)))
    old_runs = (
        select(CinemaRefreshRun.id)
        .where(
            CinemaRefreshRun.started_utc < now - timedelta(days=90),
            CinemaRefreshRun.status != "running",
        )
        .limit(limit)
    )
    await db.execute(delete(CinemaRefreshRun).where(CinemaRefreshRun.id.in_(old_runs)))
    old_films = (
        select(CinemaFilm.id)
        .where(
            CinemaFilm.last_seen_utc < now - timedelta(days=90),
            ~select(CinemaScreening.id).where(CinemaScreening.film_id == CinemaFilm.id).exists(),
        )
        .limit(limit)
    )
    await db.execute(delete(CinemaFilm).where(CinemaFilm.id.in_(old_films)))
    return {"screeningsPurged": int(getattr(showings, "rowcount", 0) or 0)}
