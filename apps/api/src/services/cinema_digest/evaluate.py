"""One atomic evaluation per London day, based only on finished scheduled-run evidence."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.clock import utcnow
from src.models.cinema import (
    CinemaCoverage,
    CinemaFilm,
    CinemaRefreshRun,
    CinemaScreening,
    CinemaVenue,
)
from src.models.cinema_digest import (
    CinemaDigestAppearance,
    CinemaDigestDay,
    CinemaDigestFilm,
    CinemaDigestListing,
)
from src.models.notification import NotificationCategory
from src.models.profile import Profile
from src.services.cinemas.domain import LONDON
from src.services.cinemas.venues import BY_SLUG, VENUES
from src.services.notifications import get_or_create_preferences, queue_notification

LABELS = ("Preview", "First run", "Rerun", "Unclassified")
LOCK = text("SELECT pg_advisory_xact_lock(864387, 7)")


def london_day(now: datetime) -> date:
    return now.replace(tzinfo=UTC).astimezone(LONDON).date()


def tmdb_id(film: CinemaFilm) -> int | None:
    value = (film.evidence or {}).get("tmdbId")
    return (
        value if film.identity_status == "verified" and type(value) is int and value > 0 else None
    )


def run_label(showing: CinemaScreening) -> str:
    if showing.release_category == "olderFilm":
        return "Rerun"
    if showing.release_category == "newRelease":
        return (
            "Preview"
            if "preview" in str(showing.category_evidence.get("runReason", "")).lower()
            else "First run"
        )
    return "Unclassified"


def returned(film: CinemaDigestFilm, day: date) -> bool:
    return bool(
        film.absent_since_day
        and film.absence_checked_through_day == day - timedelta(days=1)
        and (day - film.absent_since_day).days >= 30
    )


def absence(film: CinemaDigestFilm, day: date, *, observed_all: bool, present: bool) -> None:
    if present:
        film.last_present_day = day
    if present or not observed_all:
        film.absent_since_day = film.absence_checked_through_day = None
    else:
        if film.absence_checked_through_day != day - timedelta(days=1):
            film.absent_since_day = day
        film.absence_checked_through_day = day


def words(
    items: list[CinemaDigestAppearance], older: bool, *, bounded: bool = False
) -> tuple[str, str]:
    count = len(items)
    noun = "film" if count == 1 else "films"
    title = f"{count} {'older ' if older else ''}{noun} newly listed at your cinemas"
    lines = []
    for item in items[:3] if bounded else items:
        labels = ["Rerun"] if older else item.run_labels
        name = item.title[:160] + ("…" if len(item.title) > 160 else "") if bounded else item.title
        lines.append(
            f"{name} — {' / '.join(labels)}"
            + (" · Back in the programme" if item.is_return else "")
        )
    if bounded and count > len(lines):
        lines.append(f"And {count - len(lines)} more. Open New this week.")
    return title, "\n".join(lines)


async def evaluate(db: AsyncSession, run: CinemaRefreshRun, *, now: datetime) -> dict[str, Any]:
    "Caller owns commit. Day/history/outbox roll back together; uniqueness is not a read race."
    await db.execute(LOCK)
    day = london_day(now)
    previous = await db.scalar(select(CinemaDigestDay).where(CinemaDigestDay.local_date == day))
    if previous:
        return {"status": "already_evaluated", **previous.report}
    if (
        run.trigger != "cron"
        or run.status not in ("healthy", "partial")
        or run.finished_utc is None
    ):
        return {"status": "ineligible_run"}
    if london_day(run.finished_utc) != day:
        return {"status": "missed_day"}
    outcomes = run.report.get("venues", {})
    good = {
        BY_SLUG[slug].id
        for slug, value in outcomes.items()
        if slug in BY_SLUG and not value.get("failed", True) and value.get("observedDates")
    }
    coverage = list(
        (
            await db.scalars(
                select(CinemaCoverage).where(
                    CinemaCoverage.run_id == run.id,
                    CinemaCoverage.observed.is_(True),
                    CinemaCoverage.venue_id.in_(good),
                )
            )
        ).all()
    )
    observed = {(c.venue_id, c.local_date): c.last_success_utc for c in coverage}
    good &= {c.venue_id for c in coverage}
    if not good:
        return {"status": "no_successful_venues"}
    rows = list(
        (
            await db.execute(
                select(CinemaScreening, CinemaFilm)
                .join(CinemaFilm, CinemaFilm.id == CinemaScreening.film_id)
                .where(
                    CinemaScreening.deleted_at.is_(None),
                    CinemaFilm.deleted_at.is_(None),
                    CinemaScreening.starts_utc > now,
                )
            )
        ).all()
    )
    # Retained/unconfirmed future rows block absence, but cannot create new appearances.
    present = {
        identity
        for s, f in rows
        if s.confirmation in ("confirmed", "unconfirmed") and (identity := tmdb_id(f)) is not None
    }
    states = {f.tmdb_id: f for f in (await db.scalars(select(CinemaDigestFilm))).all()}
    aliases = {
        (a.source, a.source_key, a.source_fingerprint): a
        for a in (await db.scalars(select(CinemaDigestListing))).all()
    }
    by_source: dict[tuple[str, str], list[CinemaDigestListing]] = {}
    for known_alias in aliases.values():
        by_source.setdefault((known_alias.source, known_alias.source_key), []).append(known_alias)
    linked: dict[int, list[tuple[CinemaScreening, CinemaFilm, CinemaDigestListing]]] = {}
    for showing, film in rows:
        if (
            showing.venue_id not in good
            or observed.get((showing.venue_id, showing.local_date)) != showing.last_seen_utc
        ):
            continue
        key = (
            film.source,
            film.source_key,
            str((film.evidence or {}).get("sourceFingerprint", "")),
        )
        alias = aliases.get(key)
        if alias is None:
            prior = by_source.get((film.source, film.source_key), [])
            alias = CinemaDigestListing(
                id=uuid.uuid4(),
                source=key[0],
                source_key=key[1],
                source_fingerprint=key[2],
                cinema_film_id=film.id,
                first_observed_utc=showing.first_seen_utc,
                last_observed_utc=showing.last_seen_utc,
                baseline=any(a.baseline for a in prior),
            )
            # A corrected listing is already known, even if the new fingerprint differs.
            if any(a.film_id is not None for a in prior):
                alias.baseline = True
            aliases[key] = alias
            by_source.setdefault((film.source, film.source_key), []).append(alias)
            db.add(alias)
        alias.last_observed_utc = showing.last_seen_utc
        identity = tmdb_id(film)
        if identity is None or showing.confirmation != "confirmed" or showing.source_expired:
            continue
        state = states.get(identity)
        if state is None:
            state = CinemaDigestFilm(
                id=uuid.uuid4(),
                tmdb_id=identity,
                first_observed_utc=alias.first_observed_utc,
                baseline=alias.baseline,
                episode_number=0,
            )
            states[identity] = state
            db.add(state)
        if alias.film_id is not None and alias.film_id != state.id:
            alias.baseline = True
        alias.film_id = state.id
        linked.setdefault(identity, []).append((showing, film, alias))
    await db.flush()
    appearances = []
    for identity, matches in linked.items():
        state = states[identity]
        is_return = returned(state, day)
        baseline = state.baseline or any(a.baseline for _, _, a in matches)
        first = state.episode_number == 0 and not baseline and state.last_present_day is None
        if first or is_return:
            state.episode_number += 1
            labels = {run_label(s) for s, _, _ in matches}
            appearance = CinemaDigestAppearance(
                id=uuid.uuid4(),
                film_id=state.id,
                episode_number=state.episode_number,
                first_listing_utc=min(a.first_observed_utc for _, _, a in matches),
                recognised_utc=now,
                run_id=run.id,
                title=matches[0][1].title,
                run_labels=[label for label in LABELS if label in labels],
                run_reasons=sorted(
                    {
                        str(s.category_evidence["runReason"])
                        for s, _, _ in matches
                        if s.category_evidence.get("runReason")
                    }
                ),
                is_return=is_return,
            )
            db.add(appearance)
            appearances.append(appearance)
        state.baseline = baseline
    all_venues = {v.id for v in VENUES}
    enabled = set(
        (
            await db.scalars(
                select(CinemaVenue.id).where(
                    CinemaVenue.collection_enabled.is_(True), CinemaVenue.deleted_at.is_(None)
                )
            )
        ).all()
    )
    for identity, state in states.items():
        absence(
            state,
            day,
            observed_all=all_venues <= good and all_venues <= enabled,
            present=identity in present,
        )
    recipients = {}
    for person in (
        await db.scalars(
            select(Profile)
            .where(Profile.is_active.is_(True))
            .order_by(Profile.id)
            .with_for_update()
        )
    ).all():
        pref = await get_or_create_preferences(db, person.id)
        eligible = sorted(
            [a for a in appearances if not pref.cinemas_older_only or "Rerun" in a.run_labels],
            key=lambda a: (a.title.casefold(), str(a.id)),
        )
        if not eligible:
            continue
        title, body = words(eligible, pref.cinemas_older_only)
        row = await queue_notification(
            db,
            user_id=person.id,
            category=NotificationCategory.cinemas,
            title=title,
            body=body,
            url="/movie-night/cinema?view=new-this-week"
            + ("&run=olderFilm" if pref.cinemas_older_only else ""),
            dedupe_key=f"cinemas:{person.id}:{day}",
            now=now,
        )
        if row:
            recipients[str(person.id)] = {
                "notificationId": str(row.id),
                "appearanceIds": [str(a.id) for a in eligible],
                "olderOnly": pref.cinemas_older_only,
                "status": row.status,
            }
    report = {
        "successfulVenues": sorted(str(v) for v in good),
        "failedVenues": sorted(str(v) for v in all_venues - good),
        "appearanceIds": [str(a.id) for a in appearances],
        "recipients": recipients,
    }
    db.add(CinemaDigestDay(local_date=day, run_id=run.id, evaluated_at_utc=now, report=report))
    await db.flush()
    return {"status": "evaluated", **report}


async def evaluate_run(engine: AsyncEngine, run_id: uuid.UUID) -> dict[str, Any]:
    async with async_sessionmaker(engine, expire_on_commit=False)() as db, db.begin():
        run = await db.get(CinemaRefreshRun, run_id)
        return await evaluate(db, run, now=utcnow()) if run else {"status": "missing_run"}


async def recover(engine: AsyncEngine) -> None:
    "Inside refresh exclusivity, before source rows can be overwritten. Never fetch sources."
    now = utcnow()
    async with async_sessionmaker(engine, expire_on_commit=False)() as db, db.begin():
        await db.execute(LOCK)
        runs = (
            await db.scalars(
                select(CinemaRefreshRun)
                .where(
                    CinemaRefreshRun.trigger == "cron",
                    CinemaRefreshRun.status.in_(("healthy", "partial")),
                    CinemaRefreshRun.finished_utc.is_not(None),
                )
                .order_by(CinemaRefreshRun.finished_utc.desc())
                .limit(1)
            )
        ).all()
        for run in runs:
            if london_day(run.finished_utc or now) == london_day(now):
                await evaluate(db, run, now=now)
            elif london_day(run.finished_utc or now) < london_day(now):
                missed_day = london_day(run.finished_utc or now)
                existing = await db.scalar(
                    select(CinemaDigestDay).where(CinemaDigestDay.local_date == missed_day)
                )
                if existing is None:
                    db.add(
                        CinemaDigestDay(
                            local_date=missed_day,
                            run_id=run.id,
                            evaluated_at_utc=now,
                            report={"status": "missed_day", "recipients": {}, "appearanceIds": []},
                        )
                    )
