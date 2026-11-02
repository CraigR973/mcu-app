"""Fenced refresh orchestration and reviewable artifacts; disabled until owner enablement."""

import asyncio
import hashlib
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime, model_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.cinema import CinemaCoverage, CinemaRefreshRun, CinemaScreening, CinemaVenue
from src.models.profile import Profile, UserRole
from src.services import heartbeat
from src.services.cinemas.collect import ADAPTER_VERSION, collect_venue
from src.services.cinemas.domain import (
    LONDON,
    Snapshot,
    SourceError,
    days_between,
    release_category,
)
from src.services.cinemas.fetch import Budget
from src.services.cinemas.store import fence, promote, retain
from src.services.cinemas.venues import BY_SLUG, VENUES, Venue

log = structlog.get_logger(__name__)
LOCK = "SELECT pg_try_advisory_lock(864387, 6)"
UNLOCK = "SELECT pg_advisory_unlock(864387, 6)"
HEARTBEAT = "cinema-programme"


class PreparedRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adapter_version: Literal["ab6-1"] = "ab6-1"
    prepared_utc: NaiveDatetime
    date_from: date
    date_to: date
    snapshots: dict[str, Snapshot]
    requests: int = Field(ge=0, le=120)
    decoded_bytes: int = Field(ge=0, le=64 * 1024 * 1024)

    @model_validator(mode="after")
    def validate_scope(self) -> "PreparedRun":
        dates = set(days_between(self.date_from, self.date_to))
        if not self.snapshots or not set(self.snapshots) <= set(BY_SLUG):
            raise ValueError("Artifact contains an unknown or empty venue scope")
        if sum(len(s.rows) for s in self.snapshots.values()) > 10000:
            raise ValueError("Artifact exceeds the run row limit")
        for snapshot in self.snapshots.values():
            snapshot.validate()
            if snapshot.observed_utc is None or snapshot.observed_utc.tzinfo is not None:
                raise ValueError("Artifact must retain each source's naive-UTC observation time")
            if (
                not snapshot.observed_dates <= dates
                or not snapshot.complete_dates <= snapshot.observed_dates
            ):
                raise ValueError("Artifact dates exceed observed/requested coverage")
            if any(row.start.date() not in dates for row in snapshot.rows):
                raise ValueError("Artifact showing is outside its selected civil dates")
        return self

    @property
    def row_count(self) -> int:
        return sum(len(s.rows) for s in self.snapshots.values() if not s.failed)

    def require_all_nine(self) -> None:
        if set(self.snapshots) != set(BY_SLUG):
            raise SourceError("Initial acceptance requires all nine venues")
        for slug, snapshot in self.snapshots.items():
            if snapshot.failed or not snapshot.observed_dates:
                raise SourceError(
                    f"{slug}: source acceptance unresolved; no reduced-coverage write"
                )
            if snapshot.observed_utc is None or not (
                utcnow() - timedelta(hours=30) <= snapshot.observed_utc <= utcnow()
            ):
                raise SourceError(f"{slug}: stale/future observation; no partial artifact write")


def save_artifact(prepared: PreparedRun, path: Path) -> str:
    data = prepared.model_dump_json(indent=2).encode() + b"\n"
    if len(data) > 16 * 1024 * 1024:
        raise SourceError("Review artifact exceeds 16 MiB")
    # Never overwrite an existing reviewed artifact or follow a caller's symlink.
    with path.open("xb") as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def load_artifact(path: Path, digest: str, count: int) -> PreparedRun:
    if path.stat().st_size > 16 * 1024 * 1024:
        raise SourceError("Review artifact exceeds 16 MiB")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise SourceError("Reviewed artifact digest differs; no write")
    prepared = PreparedRun.model_validate_json(data)
    prepared.require_all_nine()
    if prepared.row_count != count:
        raise SourceError("Reviewed row count differs; no write")
    if utcnow() - prepared.prepared_utc > timedelta(hours=30) or prepared.prepared_utc > utcnow():
        raise SourceError("Review artifact is stale or future-dated; do not reset observation age")
    return prepared


async def _admin(db: AsyncSession, actor: uuid.UUID) -> None:
    role = await db.scalar(select(Profile.role).where(Profile.id == actor))
    if role != UserRole.admin:
        raise SourceError("An existing admin profile must own this audited action")


@asynccontextmanager
async def exclusive(
    engine: AsyncEngine, trigger: str | None, scope: dict[str, Any]
) -> AsyncIterator[uuid.UUID | None]:
    """Hold a dedicated session lock; dry-run takes no persistent lease/run/heartbeat."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.connect() as connection:
        if not await connection.scalar(text(LOCK)):
            raise SourceError("Another cinema pass holds the global lock")
        await connection.commit()
        run_id: uuid.UUID | None = None
        try:
            async with factory() as db, db.begin():
                previous = await db.scalar(
                    select(CinemaRefreshRun)
                    .where(CinemaRefreshRun.status == "running")
                    .with_for_update()
                )
                if previous and previous.lease_expires_utc > utcnow():
                    raise SourceError("A live cinema refresh lease already exists")
                if trigger is not None:
                    if previous:
                        previous.status = "abandoned"
                        previous.finished_utc = utcnow()
                        await db.flush()
                    run_id = uuid.uuid4()
                    db.add(
                        CinemaRefreshRun(
                            id=run_id,
                            trigger=trigger,
                            adapter_version=ADAPTER_VERSION,
                            status="running",
                            started_utc=utcnow(),
                            heartbeat_utc=utcnow(),
                            lease_expires_utc=utcnow() + timedelta(minutes=10),
                            request_count=0,
                            bytes_received=0,
                            report=scope,
                        )
                    )
            yield run_id
        finally:
            try:
                async with asyncio.timeout(4):
                    if run_id is not None:
                        async with factory() as db, db.begin():
                            run = await db.get(CinemaRefreshRun, run_id)
                            if run and run.status == "running":
                                run.status = "failed"
                                run.finished_utc = utcnow()
                                run.report = {
                                    **run.report,
                                    "error": (
                                        "Refresh did not finish; last observations are not "
                                        "a successful refresh"
                                    ),
                                }
            finally:
                try:
                    async with asyncio.timeout(1):
                        await connection.execute(text(UNLOCK))
                        await connection.commit()
                except Exception:  # noqa: BLE001 - discard a session whose advisory lock is uncertain
                    await connection.invalidate()
                    log.warning("cinema_lock_connection_discarded")


async def prepare(
    venues: list[Venue], start: date, end: date, client: httpx.AsyncClient
) -> PreparedRun:
    fetch = Budget(client)
    snapshots: dict[str, Snapshot] = {}
    try:
        # Reserve time inside the five-minute pass for atomic promotion/reporting.
        async with asyncio.timeout(240):
            for venue in venues:
                snapshot = await collect_venue(venue, start, end, fetch)
                if sum(len(s.rows) for s in snapshots.values()) + len(snapshot.rows) > 10000:
                    raise SourceError("Programme run normalised-row ceiling reached")
                snapshots[venue.slug] = snapshot
    except (TimeoutError, SourceError) as exc:
        for venue in venues:
            if venue.slug not in snapshots:
                snapshots[venue.slug] = Snapshot(
                    failed=True,
                    errors=[str(exc) or "Programme source deadline reached"],
                    observed_utc=utcnow(),
                )
    return PreparedRun(
        prepared_utc=utcnow(),
        date_from=start,
        date_to=end,
        snapshots=snapshots,
        requests=fetch.requests,
        decoded_bytes=fetch.bytes_read,
    )


def summary(prepared: PreparedRun) -> dict[str, Any]:
    categories = {"newRelease": 0, "olderFilm": 0, "unclassified": 0}
    for snapshot in prepared.snapshots.values():
        if not snapshot.failed:
            for row in snapshot.rows:
                categories[
                    release_category(
                        row.evidence, identity_verified=bool(row.tmdb_id or row.imdb_id)
                    )
                ] += 1
    return {
        "rows": prepared.row_count,
        "requests": prepared.requests,
        "decodedBodyBytes": prepared.decoded_bytes,
        "categoryCountsFromSourceEvidence": categories,
        "dateFrom": prepared.date_from.isoformat(),
        "dateTo": prepared.date_to.isoformat(),
        "venues": {
            slug: {
                "rows": len(s.rows),
                "failed": s.failed,
                "observedDates": sorted(d.isoformat() for d in s.observed_dates),
                "completeDates": sorted(d.isoformat() for d in s.complete_dates),
                "errors": s.errors[:10],
            }
            for slug, s in prepared.snapshots.items()
        },
    }


async def preview(db: AsyncSession, prepared: PreparedRun) -> dict[str, Any]:
    """Exact source-key changes against the selected database, without writing it."""
    report = summary(prepared)
    changes = {}
    for slug, snapshot in prepared.snapshots.items():
        venue = BY_SLUG[slug]
        existing = {
            s.source_key: s
            for s in (
                await db.scalars(
                    select(CinemaScreening).where(CinemaScreening.venue_id == venue.id)
                )
            ).all()
        }
        incoming = {r.key for r in snapshot.rows} if not snapshot.failed else set()
        missing = [
            r
            for key, r in existing.items()
            if key not in incoming
            and r.starts_utc > utcnow()
            and r.local_date in snapshot.observed_dates
            and r.confirmation == "confirmed"
            and not snapshot.failed
        ]
        changes[slug] = {
            "added": len(incoming - existing.keys()),
            "updated": len(incoming & existing.keys()),
            "unconfirmed": sum(r.local_date not in snapshot.complete_dates for r in missing),
            "withdrawn": sum(r.local_date in snapshot.complete_dates for r in missing),
            "deleted": 0,
        }
    report["changes"] = changes
    return report


async def apply_prepared(
    engine: AsyncEngine, prepared: PreparedRun, actor: uuid.UUID
) -> dict[str, Any]:
    prepared.require_all_nine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with asyncio.timeout(295):
        async with factory() as db:
            await _admin(db, actor)
        async with exclusive(engine, "manual", _scope(prepared)) as run_id:
            assert run_id is not None
            return await _promote_all(engine, prepared, run_id, actor)


def _scope(prepared: PreparedRun) -> dict[str, Any]:
    return {
        "venueIds": [str(BY_SLUG[s].id) for s in prepared.snapshots],
        "dateFrom": prepared.date_from.isoformat(),
        "dateTo": prepared.date_to.isoformat(),
    }


def _depends_on(venue: Venue, host: str) -> bool:
    return (
        urlsplit(venue.programme_url).hostname == host
        or (venue.source in ("everyman", "cineworld") and host == "cms-assets.webediamovies.pro")
        or (venue.source == "science" and host == "www.tickettailor.com")
    )


async def _promote_all(
    engine: AsyncEngine, prepared: PreparedRun, run_id: uuid.UUID, actor: uuid.UUID | None = None
) -> dict[str, Any]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    report: dict[str, Any] = {**_scope(prepared), "venues": {}}
    for slug, snapshot in prepared.snapshots.items():
        async with factory() as db, db.begin():
            counts = await promote(
                db, BY_SLUG[slug], snapshot, prepared.date_from, prepared.date_to, run_id
            )
            report["venues"][slug] = counts
            if snapshot.refused_host:
                affected = [v.id for v in VENUES if _depends_on(v, snapshot.refused_host)]
                for venue in (
                    await db.scalars(select(CinemaVenue).where(CinemaVenue.id.in_(affected)))
                ).all():
                    if venue.collection_enabled:
                        venue.collection_enabled = False
                        db.add(
                            AdminAction(
                                user_id=None,
                                action_type="update",
                                target_table="cinema_venues",
                                target_id=str(venue.id),
                                changes={
                                    "collectionEnabled": {"from": True, "to": False},
                                    "reason": (
                                        "Source host refusal; owner must review before re-enabling"
                                    ),
                                },
                            )
                        )
            run = await fence(db, run_id)
            run.report = report
    status = (
        "failed"
        if all(s.failed for s in prepared.snapshots.values())
        else (
            "partial"
            if any(
                s.failed
                or set(days_between(prepared.date_from, prepared.date_to)) != s.complete_dates
                for s in prepared.snapshots.values()
            )
            else "healthy"
        )
    )
    async with factory() as db, db.begin():
        run = await fence(db, run_id)
        await retain(db)
        run.status = status
        run.finished_utc = utcnow()
        run.request_count = prepared.requests
        run.bytes_received = prepared.decoded_bytes
        run.report = report
        if actor is not None:
            db.add(
                AdminAction(
                    user_id=actor,
                    action_type="bulk_import",
                    target_table="cinema_screenings",
                    target_id=str(run_id),
                    changes={"rows": prepared.row_count, "venues": len(prepared.snapshots)},
                )
            )
    # Heartbeat's helper commits/rolls back its session. Keep that boundary separate
    # so a heartbeat failure cannot undo the already published outcome and retention.
    async with factory() as db:
        await heartbeat.beat(
            db,
            HEARTBEAT,
            status,
            detail={
                "rows": prepared.row_count,
                "failedVenues": sum(s.failed for s in prepared.snapshots.values()),
            },
        )
    return {"status": status, **summary(prepared), "changes": report["venues"]}


async def refresh_due(engine: AsyncEngine) -> dict[str, Any]:
    """Morning child phase: its exception cannot undo the committed reminder pass."""
    started = time.monotonic()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            selected = set(
                (
                    await db.scalars(
                        select(CinemaVenue.slug).where(
                            CinemaVenue.collection_enabled.is_(True),
                            CinemaVenue.deleted_at.is_(None),
                        )
                    )
                ).all()
            )
        if not selected:
            return {"status": "disabled", "requests": 0}
        venues = [v for v in VENUES if v.slug in selected]
        start = utcnow().replace(tzinfo=UTC).astimezone(LONDON).date()
        end = start + timedelta(days=13)
        scope = {
            "venueIds": [str(v.id) for v in venues],
            "dateFrom": start.isoformat(),
            "dateTo": end.isoformat(),
        }
        async with asyncio.timeout(max(0.01, 295 - (time.monotonic() - started))):
            async with exclusive(engine, "cron", scope) as run_id:
                assert run_id is not None
                async with httpx.AsyncClient(
                    timeout=15, headers={"User-Agent": "MCU-private-cinema-programme/1.0"}
                ) as client:
                    prepared = await prepare(venues, start, end, client)
                report = await _promote_all(engine, prepared, run_id)
        log.info("cinema_programme_finished", **report)
        return report
    except Exception as exc:  # noqa: BLE001 - separate child phase, never roll back reminders
        log.warning("cinema_programme_failed", error_type=type(exc).__name__)
        return {"status": "failed", "error": type(exc).__name__}


async def set_enabled(engine: AsyncEngine, actor: uuid.UUID, enabled: bool, expected: int) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db, db.begin():
        await _admin(db, actor)
        venues = list(
            (
                await db.scalars(
                    select(CinemaVenue)
                    .where(
                        CinemaVenue.id.in_([v.id for v in VENUES]),
                        CinemaVenue.deleted_at.is_(None),
                        CinemaVenue.collection_enabled != enabled,
                    )
                    .with_for_update()
                )
            ).all()
        )
        if len(venues) != expected:
            raise SourceError("Enable/disable row count differs; no write")
        if enabled:
            checked = set(
                (
                    await db.scalars(
                        select(CinemaCoverage.venue_id).where(
                            CinemaCoverage.last_success_utc >= utcnow() - timedelta(hours=30),
                            CinemaCoverage.observed.is_(True),
                            CinemaCoverage.status != "failed",
                            CinemaCoverage.local_date
                            >= utcnow().replace(tzinfo=UTC).astimezone(LONDON).date(),
                        )
                    )
                ).all()
            )
            if not {v.id for v in venues} <= checked:
                raise SourceError("Fresh accepted coverage is required before enabling")
        for venue in venues:
            venue.collection_enabled = enabled
            db.add(
                AdminAction(
                    user_id=actor,
                    action_type="update",
                    target_table="cinema_venues",
                    target_id=str(venue.id),
                    changes={"collectionEnabled": {"from": not enabled, "to": enabled}},
                )
            )
    return len(venues)
