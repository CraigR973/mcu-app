"""Building and refreshing completion sets — roadmap §11.1.

Two jobs, kept apart on purpose:

**Choosing which sets exist** is a question about *this* collection, answered from
``movie_credits`` — the people this collection already holds several films by. No names
are typed, no TMDB search is run, and therefore nothing can be matched to the wrong
person: the TMDB id came from the film's own credits when it was identified.

**Filling a set in** is a question for TMDB, answered by one call per set.

The dangerous part is neither of those; it is **what counts as a member**. TMDB's
``/person/{id}/movie_credits`` returns everything a person touched — Hitchcock's producing
credits, his acting cameos, television, and entries with no release date that never came
out. A set that included them would report "12 of 91" where the truth is "12 of 54", and
the number would look entirely plausible. Every filter below exists because of that, and
each one is stated rather than inferred.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import owned_film
from src.models.completion_set import MIN_OWNED_FOR_SET, CompletionSet
from src.models.movie import Movie, MovieCredit
from src.tmdb import PersonMovieCredit, PersonMovieCredits, TMDBClient

#: Only films this person *directed*. TMDB puts a director's producing and writing credits
#: in the same ``crew`` array, and "the Hitchcock films" means the ones he directed.
DIRECTOR_JOB = "Director"

#: An actor's set counts films they were billed in the top ten of, not every walk-on. TMDB's
#: ``order`` counts from 0, so the ninth is the tenth billed (Batch X12c, CT46-07: 12 of the 20
#: actor sets had been chosen from background players, because the old rule counted any credit
#: and members were kept to 15).
MAX_BILLING_ORDER = 9

#: A credit with no release date has not come out. Counting unreleased films as "missing"
#: would make every set permanently incomplete by construction.
#:
#: A credit with a release date but no votes is usually a duplicate or a fragment TMDB has
#: not cleaned up; requiring *some* evidence the film exists keeps a filmography from
#: growing phantom denominators over time.
MIN_VOTE_COUNT = 1


@dataclass(frozen=True)
class SetCandidate:
    """A person this collection holds enough films by to be worth measuring against."""

    set_type: str
    tmdb_person_id: int
    name: str
    owned_count: int


@dataclass
class RefreshResult:
    """What a refresh did, in the shape a report can be read from.

    ``errors`` is a list rather than a count because `STATUS.md` gotcha 16's lesson from
    Batch 4's import was that a summary's success lines are not the interesting part.
    """

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged


async def candidate_people(
    db: AsyncSession, *, limit_per_type: int = 20, min_owned: int = MIN_OWNED_FOR_SET
) -> list[SetCandidate]:
    """The directors and actors this collection has the biggest stake in.

    Ordered by how many of their films are owned, which is the only ordering that makes
    the top of the insights page the part someone cares about. Ties break on name so a
    re-run produces the same set rather than an arbitrary slice of a tie.
    """
    candidates: list[SetCandidate] = []
    for set_type, role in (("director", "director"), ("actor", "cast")):
        owned = func.count(func.distinct(MovieCredit.movie_id)).label("owned")
        rows = (
            await db.execute(
                select(MovieCredit.tmdb_person_id, MovieCredit.person_name, owned)
                .join(Movie, Movie.id == MovieCredit.movie_id)
                .where(
                    MovieCredit.role == role,
                    MovieCredit.tmdb_person_id.is_not(None),
                    Movie.deleted_at.is_(None),
                    # An unidentified film has no TMDB id, so it can never be matched
                    # against a filmography — counting it as owned would overstate every
                    # set it appears in.
                    Movie.tmdb_id.is_not(None),
                    # A film only watched or wanted has a row, but is not owned (#269).
                    owned_film(),
                    # An actor counts only for films they are top-ten billed in (Batch X12c).
                    # Directors carry no billing position.
                    or_(MovieCredit.role != "cast", MovieCredit.display_order <= MAX_BILLING_ORDER),
                )
                .group_by(MovieCredit.tmdb_person_id, MovieCredit.person_name)
                .having(owned >= min_owned)
                .order_by(owned.desc(), MovieCredit.person_name.asc())
                .limit(limit_per_type)
            )
        ).all()
        candidates.extend(
            SetCandidate(
                set_type=set_type,
                tmdb_person_id=int(person_id),
                name=name,
                owned_count=int(count),
            )
            for person_id, name, count in rows
        )
    return candidates


def _year(release_date: str | None) -> int | None:
    if not release_date or len(release_date) < 4:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None


def _is_real_release(credit: PersonMovieCredit) -> bool:
    """Has this actually come out, and is there evidence it exists?"""
    if _year(credit.release_date) is None:
        return False
    return (credit.vote_count or 0) >= MIN_VOTE_COUNT


def select_members(
    credits: PersonMovieCredits, set_type: str, *, short_ids: frozenset[int] = frozenset()
) -> list[PersonMovieCredit]:
    """The films that belong in this person's set, deduplicated by TMDB id.

    Deduplication matters more than it looks: TMDB lists a person once per job, so someone
    credited as both director and writer appears twice in ``crew`` and would otherwise be
    counted twice in the denominator of their own set.
    """
    source = credits.crew if set_type == "director" else credits.cast
    chosen: dict[int, PersonMovieCredit] = {}
    for credit in source:
        # A compilation (TMDB's `video` flag) or a short is not a film in the set (CT46-07:
        # 6 of Nolan's 19 were shorts or compilations). `short_ids` is the person's films of
        # 40 minutes or less, from discover.
        if credit.video or credit.id in short_ids:
            continue
        if set_type == "director" and credit.job != DIRECTOR_JOB:
            continue
        if set_type == "actor" and (credit.order is None or credit.order > MAX_BILLING_ORDER):
            continue
        if not _is_real_release(credit):
            continue
        chosen.setdefault(credit.id, credit)
    return sorted(chosen.values(), key=lambda c: (_year(c.release_date) or 0, c.title))


def build_metadata(candidate: SetCandidate, members: Sequence[PersonMovieCredit]) -> dict[str, Any]:
    """The cached display rows §11.2's missing-films list reads, plus provenance."""
    return {
        "members": [
            {
                "tmdbId": member.id,
                "title": member.title,
                "year": _year(member.release_date),
                "posterPath": member.poster_path,
            }
            for member in members
        ],
        "tmdbPersonId": candidate.tmdb_person_id,
        "sourceRole": candidate.set_type,
    }


async def refresh_sets(
    db: AsyncSession,
    tmdb: TMDBClient,
    *,
    limit_per_type: int = 20,
    dry_run: bool = False,
) -> RefreshResult:
    """Rebuild every candidate set from TMDB. Idempotent, keyed on ``(set_type, set_key)``.

    An error on one person is recorded and the rest continue. A refresh that abandoned 24
    good sets because TMDB 500'd on the 25th would leave the table in a state nobody could
    reason about, and the next run would hit the same wall.

    ``dry_run`` reads TMDB and writes nothing — gotcha 16 is the record of what the first
    real write against real data cost when it was not rehearsed.
    """
    result = RefreshResult()
    candidates = await candidate_people(db, limit_per_type=limit_per_type)

    existing = {
        (row.set_type, row.set_key): row
        for row in (await db.execute(select(CompletionSet))).scalars().all()
    }

    for candidate in candidates:
        try:
            credits = await tmdb.get_person_movie_credits(candidate.tmdb_person_id)
        except Exception as exc:  # noqa: BLE001 - one bad person must not end the run
            result.errors.append(f"{candidate.name} ({candidate.tmdb_person_id}): {exc}")
            continue

        try:
            shorts = await tmdb.get_short_film_ids(
                candidate.tmdb_person_id, role=candidate.set_type
            )
        except Exception as exc:  # noqa: BLE001 - one bad person must not end the run
            # Left as it was: writing the set with its shorts back in would undo the filter
            # for it, and the next run tries again.
            result.errors.append(f"{candidate.name}: shorts not checked, set left as it was: {exc}")
            continue
        members = select_members(credits, candidate.set_type, short_ids=frozenset(shorts))
        if not members:
            # A person TMDB has no releasable films for. Writing an empty set would show
            # "you own 3 of 0", which is worse than not showing the set.
            result.skipped += 1
            continue

        member_ids = [member.id for member in members]
        metadata = build_metadata(candidate, members)
        key = (candidate.set_type, str(candidate.tmdb_person_id))
        row = existing.get(key)

        if row is None:
            result.created += 1
            if not dry_run:
                db.add(
                    CompletionSet(
                        id=uuid.uuid4(),
                        set_type=candidate.set_type,
                        set_key=str(candidate.tmdb_person_id),
                        set_name=candidate.name,
                        member_tmdb_ids=member_ids,
                        set_metadata=metadata,
                        last_refreshed=utcnow(),
                    )
                )
            continue

        if row.member_tmdb_ids == member_ids and row.set_name == candidate.name:
            result.unchanged += 1
            # `last_refreshed` still moves: "we checked and nothing changed" is a
            # different fact from "we have not looked since Tuesday", and the weekly job
            # needs the second one to decide what is stale.
            if not dry_run:
                row.last_refreshed = utcnow()
            continue

        result.updated += 1
        if not dry_run:
            row.set_name = candidate.name
            row.member_tmdb_ids = member_ids
            row.set_metadata = metadata
            row.last_refreshed = utcnow()

    if not dry_run:
        await db.commit()
    return result
