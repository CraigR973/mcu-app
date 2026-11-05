"""Atomic venue promotion, conservative disappearance and fenced writers."""

import uuid
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
from src.services.cinemas import identity
from src.services.cinemas.domain import (
    Showing,
    Snapshot,
    SourceError,
    days_between,
    release_category,
)
from src.services.cinemas.metadata import Metadata, facts_of, fingerprint
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
    picked: int | None = None,
) -> tuple[CinemaFilm, identity.Candidate | None]:
    """The programme film for ``row``, identified by #335's rule (`identity.identify`).

    A linked film is ``verified``; ``review`` waits for Craig; ``event`` is never a film;
    anything else stays ``unverified``. A decision Craig made (the review list, or a reviewed
    mapping from the refresh CLI, ``picked``) holds while the listing's title and facts do.
    Returns the film and the candidate it is linked to, for the showings' run labels.
    """
    film = await db.scalar(
        select(CinemaFilm).where(CinemaFilm.source == source, CinemaFilm.source_key == row.film_key)
    )
    if film is None:
        film = CinemaFilm(source=source, source_key=row.film_key, title=row.title)
        db.add(film)
    prior = film.evidence or {}
    source_fingerprint = fingerprint(row)
    unchanged = prior.get("sourceFingerprint") == source_fingerprint
    title = identity.read_title(row.title, row.start.date())
    # Only an AC3 lookup of this very listing answers #335's rule; AB6's are asked again.
    if metadata is not None and (
        metadata.fingerprint != source_fingerprint or metadata.rule != "ac3"
    ):
        metadata = None
    if metadata is None and unchanged and prior.get("metadata"):
        try:
            stored = Metadata.model_validate(prior["metadata"])
        except ValueError:
            stored = None
        metadata = stored if stored is not None and stored.rule == "ac3" else None
    candidates = metadata.identities() if metadata else []
    reviewed = prior.get("reviewed") if unchanged else None
    if picked is not None:
        reviewed = {"tmdbId": picked, "by": "refresh CLI"}
    decision: identity.Decision
    if title.event:
        decision = identity.identify(title, facts_of(row), [], row.start.date())
    elif row.evidence.get("combinedProgramme"):
        # The source's own double-bill flag, whatever the title says.
        decision = identity.Decision("event", reason="a double bill, not one film")
    elif row.evidence.get("conflict"):
        decision = identity.Decision("conflict", reason="the cinema's own listing conflicts")
    elif reviewed and reviewed.get("notAFilm"):
        decision = identity.Decision("event", reason="Craig marked it as not a film")
    elif reviewed and reviewed.get("tmdbId"):
        chosen = next((c for c in candidates if c.tmdb_id == reviewed["tmdbId"]), None)
        decision = (
            identity.Decision("linked", chosen, ("Craig's review",))
            if chosen
            else identity.Decision("review", reason="Craig's choice is no longer a candidate")
        )
    elif metadata is None:
        # Not looked up yet (the budget ran out, or the listing changed): unlinked, and never
        # "not found" or a review, which only a lookup can say.
        decision = identity.Decision("unlinked", reason="not yet looked up on TMDB")
    else:
        decision = identity.identify(title, facts_of(row), candidates, row.start.date())
    linked = decision.candidate if decision.outcome == "linked" else None
    movie = None
    if linked is not None:
        conditions = [Movie.tmdb_id == linked.tmdb_id]
        if linked.imdb_id:
            conditions.append(Movie.imdb_id == linked.imdb_id)
        found = (
            await db.scalars(
                select(Movie).where(
                    Movie.deleted_at.is_(None), Movie.is_tv.is_(False), or_(*conditions)
                )
            )
        ).all()
        movie = found[0] if len(found) == 1 else None
    film.title = row.title
    film.movie_id = movie.id if movie else None
    film.identity_status = {
        "linked": "verified",
        "review": "review",
        "event": "event",
        "conflict": "conflict",
    }.get(decision.outcome, "unverified")
    film.original_year = linked.release_date.year if linked and linked.release_date else None
    film.first_uk_release_date = linked.first_uk_release if linked else None
    film.source_release_date = row.source_release
    film.evidence = {
        **({"metadata": metadata.model_dump(mode="json")} if metadata else {}),
        **({"reviewed": reviewed} if reviewed else {}),
        **row.evidence,
        "tmdbId": linked.tmdb_id if linked else None,
        "imdbId": linked.imdb_id if linked else None,
        "posterPath": linked.poster_path if linked else None,
        "identity": {
            "outcome": decision.outcome,
            "reason": decision.reason,
            "corroboration": list(decision.corroboration),
            "others": list(decision.others),
        },
        "sourceIdentity": row.identity_facts,
        "sourceFingerprint": source_fingerprint,
    }
    film.last_seen_utc = observed
    film.deleted_at = None
    await db.flush()
    return film, linked


async def promote(
    db: AsyncSession,
    venue: Venue,
    snapshot: Snapshot,
    start: date,
    end: date,
    run_id: uuid.UUID,
    metadata: dict[tuple[str, str], Metadata] | None = None,
    picks: dict[tuple[str, str], int] | None = None,
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
    films: dict[str, tuple[CinemaFilm, identity.Candidate | None]] = {}
    if not snapshot.failed:
        for source in snapshot.rows:
            if source.start.date() not in dates:
                raise SourceError("A source row lies outside the requested civil window")
            known = films.get(source.film_key)
            if known is None:
                key = (venue.source, source.film_key)
                known = await _film(
                    db,
                    venue.source,
                    source,
                    observed,
                    (metadata or {}).get(key),
                    (picks or {}).get(key),
                )
                films[source.film_key] = known
            film, linked = known
            if film.title != source.title:
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
            # #335's run, from the linked film's first UK cinema release or the cinema's own
            # reissue label, with its reason in words; anything unlinked stays Unclassified.
            evidence = dict(source.evidence)
            if linked is not None:
                category, reason = identity.classify(
                    linked.first_uk_release,
                    source.start.date(),
                    identity.read_title(source.title, source.start.date()),
                )
                evidence.update(
                    run={"newRelease": "firstRun", "olderFilm": "rerun"}.get(category, "between"),
                    runReason=reason,
                    reissue=True
                    if category == "olderFilm" and source.evidence.get("returningLabel")
                    else None,
                )
            row.release_category = release_category(
                evidence, identity_verified=film.identity_status == "verified"
            )
            row.category_evidence = {k: v for k, v in evidence.items() if v is not None}
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
