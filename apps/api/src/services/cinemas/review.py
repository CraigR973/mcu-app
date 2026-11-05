"""Craig's review list for programme films AC3 could not settle alone (#335).

A film goes here when its title matches but nothing else agrees, when two films both fit, or
when the cinema's own id names a film with another title. It stays unlinked until Craig picks
one of the films the lookup found, or says it is not a film. His decision is kept on each of
the film's rows and holds through the daily run while the listing's title and facts do
(`store._film`); a changed listing is a new question.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cinema import CinemaFilm, CinemaScreening, CinemaVenue
from src.models.movie import Movie
from src.schemas.cinemas import ReviewCandidate, ReviewDecision, ReviewItem, ReviewList
from src.services.audit import record_action
from src.services.cinemas import identity
from src.services.cinemas.domain import release_category
from src.services.cinemas.metadata import Metadata


def review_key(film: CinemaFilm) -> str:
    """The same question asked by several rows: cleaned title, labels and source facts."""
    read = identity.read_title(film.title, (film.last_seen_utc or datetime.min).date())
    facts = (film.evidence or {}).get("sourceIdentity") or {}
    value = [
        identity.normal(read.query),
        read.anniversary_year,
        bool(read.rerun_label),
        film.source_release_date.isoformat() if film.source_release_date else None,
        facts.get("director"),
        facts.get("runtimeMinutes"),
    ]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()[:16]


def _candidates(film: CinemaFilm) -> list[identity.Candidate]:
    stored = (film.evidence or {}).get("metadata")
    if not stored:
        return []
    try:
        return Metadata.model_validate(stored).identities()
    except ValueError:
        return []


async def _groups(db: AsyncSession, now: datetime) -> dict[str, list[CinemaFilm]]:
    films = (
        await db.scalars(
            select(CinemaFilm).where(
                CinemaFilm.identity_status == "review", CinemaFilm.deleted_at.is_(None)
            )
        )
    ).all()
    groups: dict[str, list[CinemaFilm]] = defaultdict(list)
    for film in films:
        groups[review_key(film)].append(film)
    return groups


async def review_list(db: AsyncSession, now: datetime) -> ReviewList:
    groups = await _groups(db, now)
    ids = [film.id for films in groups.values() for film in films]
    showings: dict[uuid.UUID, int] = {}
    venues: dict[uuid.UUID, set[str]] = defaultdict(set)
    if ids:
        rows = (
            await db.execute(
                select(CinemaScreening.film_id, CinemaVenue.name, func.count(CinemaScreening.id))
                .join(CinemaVenue, CinemaVenue.id == CinemaScreening.venue_id)
                .where(
                    CinemaScreening.film_id.in_(ids),
                    CinemaScreening.deleted_at.is_(None),
                    CinemaScreening.starts_utc > now,
                )
                .group_by(CinemaScreening.film_id, CinemaVenue.name)
            )
        ).all()
        for film_id, venue, count in rows:
            showings[film_id] = showings.get(film_id, 0) + count
            venues[film_id].add(venue)
    items = []
    for key, films in groups.items():
        future = sum(showings.get(f.id, 0) for f in films)
        if future == 0:
            continue
        found: dict[int, identity.Candidate] = {}
        for film in films:
            for candidate in _candidates(film):
                found.setdefault(candidate.tmdb_id, candidate)
        votes = _votes(films)
        first = films[0]
        items.append(
            ReviewItem(
                key=key,
                title=identity.read_title(first.title, now.date()).query,
                sourceTitles=sorted({f.title for f in films}),
                venues=sorted({v for f in films for v in venues.get(f.id, set())}),
                futureShowings=future,
                reason=((first.evidence or {}).get("identity") or {}).get("reason")
                or "Waiting for your review",
                candidates=[
                    ReviewCandidate(
                        tmdbId=c.tmdb_id,
                        title=c.title,
                        year=c.release_date.year if c.release_date else None,
                        posterPath=c.poster_path,
                        voteCount=votes.get(c.tmdb_id, 0),
                    )
                    for c in found.values()
                ],
            )
        )
    items.sort(key=lambda item: (-item.futureShowings, item.title.casefold()))
    return ReviewList(items=items)


def _votes(films: list[CinemaFilm]) -> dict[int, int]:
    votes: dict[int, int] = {}
    for film in films:
        stored = (film.evidence or {}).get("metadata") or {}
        for candidate in stored.get("candidates", []):
            votes[int(candidate["tmdb_id"])] = int(candidate.get("vote_count") or 0)
    return votes


def _relabel(film: CinemaFilm, showing: CinemaScreening, linked: identity.Candidate | None) -> None:
    evidence: dict[str, Any] = {
        k: v
        for k, v in (showing.category_evidence or {}).items()
        if k not in ("run", "runReason", "reissue")
    }
    if linked is not None:
        category, reason = identity.classify(
            linked.first_uk_release,
            showing.local_date,
            identity.read_title(film.title, showing.local_date),
        )
        evidence.update(
            run={"newRelease": "firstRun", "olderFilm": "rerun"}.get(category, "between"),
            runReason=reason,
        )
        if category == "olderFilm" and evidence.get("returningLabel"):
            evidence["reissue"] = True
    showing.category_evidence = evidence
    showing.release_category = release_category(
        evidence, identity_verified=film.identity_status == "verified"
    )


async def decide(
    db: AsyncSession, key: str, decision: ReviewDecision, actor: uuid.UUID, now: datetime
) -> None:
    """Apply Craig's decision to every row of one review item, and relabel its showings."""
    films = (await _groups(db, now)).get(key)
    if not films:
        raise HTTPException(status_code=404, detail="That film is no longer waiting for review")
    chosen: identity.Candidate | None = None
    if decision.tmdbId is not None:
        chosen = next(
            (c for f in films for c in _candidates(f) if c.tmdb_id == decision.tmdbId), None
        )
        if chosen is None:
            raise HTTPException(status_code=422, detail="Choose one of the films listed for it")
    movie = None
    if chosen is not None:
        movie = await db.scalar(
            select(Movie).where(
                Movie.tmdb_id == chosen.tmdb_id, Movie.deleted_at.is_(None), Movie.is_tv.is_(False)
            )
        )
    reviewed = (
        {"tmdbId": chosen.tmdb_id, "byProfileId": str(actor), "atUtc": now.isoformat()}
        if chosen
        else {"notAFilm": True, "byProfileId": str(actor), "atUtc": now.isoformat()}
    )
    for film in films:
        film.identity_status = "verified" if chosen else "event"
        film.movie_id = movie.id if movie else None
        film.original_year = chosen.release_date.year if chosen and chosen.release_date else None
        film.first_uk_release_date = chosen.first_uk_release if chosen else None
        film.evidence = {
            **(film.evidence or {}),
            "reviewed": reviewed,
            "tmdbId": chosen.tmdb_id if chosen else None,
            "imdbId": chosen.imdb_id if chosen else None,
            "posterPath": chosen.poster_path if chosen else None,
            "identity": {
                "outcome": "linked" if chosen else "event",
                "reason": "Craig's review" if chosen else "Craig marked it as not a film",
                "corroboration": ["Craig's review"] if chosen else [],
                "others": [],
            },
        }
        for showing in (
            await db.scalars(
                select(CinemaScreening).where(
                    CinemaScreening.film_id == film.id, CinemaScreening.deleted_at.is_(None)
                )
            )
        ).all():
            _relabel(film, showing, chosen)
    record_action(
        db,
        user_id=actor,
        action_type="update",
        target_table="cinema_films",
        target_id=films[0].id,
        changes={
            "review": key,
            "films": [str(f.id) for f in films],
            "decision": {"tmdbId": chosen.tmdb_id} if chosen else {"notAFilm": True},
        },
    )
    await db.flush()
