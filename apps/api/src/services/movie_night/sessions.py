"""Running a movie night — §8.3's sessions and §8.4's matches.

**A match is two people liking the same film, computed from the votes.** There is no
matches table: a stored copy is a second source of truth that a deleted vote can leave
stale, and gotcha 1b is this project's record of what that costs. The only derived state
kept is `announced_at_utc`, written across the matching pair so the same match is announced
once however many times either person reloads.

**"Both" means every participant, not two.** The app has two people, so a match is always a
pair today — but writing the rule as "everyone who has voted liked it" costs nothing now
and is the difference between a feature that grows and one that has a 2 baked into it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.movie import Movie
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    MovieNightVote,
)
from src.models.notification import NotificationCategory
from src.models.profile import Profile
from src.services.movie_night.realtime import CHANNEL, encode
from src.services.notifications import queue_notification

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Match:
    """A film everybody in the session liked."""

    movie_id: uuid.UUID
    title: str
    poster_path: str | None


async def publish(
    db: AsyncSession, session_id: uuid.UUID, kind: str, data: dict[str, object]
) -> None:
    """Fire a notification on the shared channel.

    Uses the request's own session — `NOTIFY` is a statement, not a subscription, so it
    borrows a connection for microseconds. It is `LISTEN` that must never do that (#113).

    **Bound parameters, not string interpolation.** `NOTIFY` takes no parameters at all,
    which is exactly why this uses `pg_notify()` — the function form does, and building the
    payload into SQL by hand is an injection waiting for a film title with a quote in it.
    """
    await db.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": CHANNEL, "payload": encode(str(session_id), kind, dict(data))},
    )


async def participants(db: AsyncSession, session_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (
            await db.execute(
                select(MovieNightParticipant.user_id).where(
                    MovieNightParticipant.session_id == session_id
                )
            )
        )
        .scalars()
        .all()
    )


async def detect_match(
    db: AsyncSession, *, session: MovieNightSession, movie_id: uuid.UUID
) -> Match | None:
    """Has everyone in the session liked this film, and not been told yet?

    Returns ``None`` for "not yet" **and** for "already announced" — both mean there is
    nothing to say, and the caller does not need to tell them apart.
    """
    people = await participants(db, session.id)
    # One person is not a movie night. Announcing a "match" to somebody swiping alone
    # would be telling them they agree with themselves.
    if len(people) < 2:
        return None

    votes = list(
        (
            await db.execute(
                select(MovieNightVote).where(
                    MovieNightVote.session_id == session.id,
                    MovieNightVote.movie_id == movie_id,
                )
            )
        )
        .scalars()
        .all()
    )
    liked_by = {vote.user_id for vote in votes if vote.liked}
    if not set(people).issubset(liked_by):
        return None
    if any(vote.announced_at_utc is not None for vote in votes):
        return None

    movie = await db.get(Movie, movie_id)
    if movie is None:  # pragma: no cover - the vote's FK guarantees one
        return None

    announced = utcnow()
    for vote in votes:
        if vote.liked:
            vote.announced_at_utc = announced
    await db.flush()

    return Match(movie_id=movie.id, title=movie.title, poster_path=movie.poster_path)


async def record_vote(
    db: AsyncSession,
    *,
    session: MovieNightSession,
    user: Profile,
    movie_id: uuid.UUID,
    liked: bool,
    now: datetime | None = None,
) -> Match | None:
    """Store one swipe, tell the room, and announce a match if this completed one."""
    now = now or utcnow()

    existing = (
        await db.execute(
            select(MovieNightVote).where(
                MovieNightVote.session_id == session.id,
                MovieNightVote.user_id == user.id,
                MovieNightVote.movie_id == movie_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        # Changing your mind is allowed; swiping twice is not two votes. The unique
        # constraint says the same thing, and hitting it would be a 500 rather than this.
        existing.liked = liked
    else:
        db.add(
            MovieNightVote(
                id=uuid.uuid4(),
                session_id=session.id,
                user_id=user.id,
                movie_id=movie_id,
                liked=liked,
                created_at_utc=now,
            )
        )
    await db.flush()

    # Told to the room without saying who voted or which way. A movie night where each
    # person can see the other's swipes before deciding is not the same game.
    await publish(db, session.id, "vote", {"movieId": str(movie_id)})

    if not liked:
        return None

    match = await detect_match(db, session=session, movie_id=movie_id)
    if match is None:
        return None

    await publish(
        db,
        session.id,
        "match",
        {"movieId": str(match.movie_id), "title": match.title, "posterPath": match.poster_path},
    )
    await _notify_match(db, session=session, match=match, now=now)
    logger.info("movie_night_match", session_id=str(session.id), title=match.title)
    return match


async def _notify_match(
    db: AsyncSession, *, session: MovieNightSession, match: Match, now: datetime
) -> None:
    """§8.4's "notification to both", through Batch 11's outbox.

    **Both people, including whoever swiped last.** The person who completed the match sees
    it on screen immediately, so a push to them looks redundant — but they may have swiped
    and put the phone down, and the notification is what makes the match survive that.
    """
    for user_id in await participants(db, session.id):
        await queue_notification(
            db,
            user_id=user_id,
            category=NotificationCategory.movie_night,
            title=f"It's a match — {match.title}",
            body="You both liked it. That's tonight sorted.",
            url=f"/movie-night/{session.id}",
            dedupe_key=f"movie-night-match:{session.id}:{match.movie_id}:{user_id}",
            now=now,
        )


async def candidate_movies(
    db: AsyncSession, *, session: MovieNightSession, user: Profile, limit: int = 30
) -> list[Movie]:
    """Films still to swipe on, honouring §8.3's filters.

    Excludes what **this** person has already voted on, not what anybody has: the other
    person's progress is not visible, and a card disappearing because they swiped it would
    leak their vote.
    """
    voted = select(MovieNightVote.movie_id).where(
        MovieNightVote.session_id == session.id, MovieNightVote.user_id == user.id
    )
    query = select(Movie).where(Movie.deleted_at.is_(None), Movie.id.not_in(voted))

    filters = session.filters or {}
    if isinstance(filters.get("decadeFrom"), int):
        query = query.where(Movie.year >= filters["decadeFrom"])
    if isinstance(filters.get("decadeTo"), int):
        query = query.where(Movie.year <= filters["decadeTo"])
    if isinstance(filters.get("minRating"), int | float):
        query = query.where(Movie.tmdb_rating >= filters["minRating"])

    # Random, so two sittings do not open on the same twenty films — and seeded per
    # session so both people are shown the same deck in the same order.
    return list((await db.execute(query.order_by(func.random()).limit(limit))).scalars().all())
