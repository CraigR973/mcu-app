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
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

import structlog
from sqlalchemy import Text, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import owned_film
from src.models.movie import Movie
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    MovieNightSuggestion,
    MovieNightVote,
)
from src.models.notification import NotificationCategory
from src.models.profile import Profile
from src.models.watch_log import WatchLog
from src.services.movie_night.realtime import CHANNEL, encode
from src.services.notifications import deliver_pending, queue_notification
from src.services.push_transport import push_sender

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Match:
    """A film everybody in the session liked.

    ``movie_id`` is ``None`` for a film outside the Archive — Batch S7 allows those to be
    suggested, and a match on one is still a match. The notification and the SSE payload
    both carry the title regardless, which is what a person actually reads.
    """

    movie_id: uuid.UUID | None
    title: str
    poster_path: str | None
    year: int | None = None


async def film_face(
    db: AsyncSession, suggestion: MovieNightSuggestion
) -> tuple[str, int | None, str | None]:
    """The title, year and poster to show for a suggestion: **the film's own** when it is on
    the shelf, the snapshot taken when it was suggested otherwise (Batch X12a, UX48-05).

    The snapshot is what the film was called that evening. After Craig identified *The
    Exorcist* (1973) the shortlist and the push still read "Exorcist, the", with no year and
    no poster, because they read the copy and not the film.
    """
    if suggestion.movie_id is not None:
        movie = await db.get(Movie, suggestion.movie_id)
        if movie is not None:
            return movie.title, movie.year, movie.poster_path or suggestion.poster_path
    return suggestion.title, suggestion.year, suggestion.poster_path


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
    db: AsyncSession, *, session: MovieNightSession, suggestion: MovieNightSuggestion
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
                    MovieNightVote.suggestion_id == suggestion.id,
                )
            )
        )
        .scalars()
        .all()
    )
    liked_by = {vote.user_id for vote in votes if vote.liked}
    # **Everyone, not two.** `issubset` was already right for 3+ people in Batch 35 and is
    # unchanged here — one of the two of Craig's five points that were already met.
    if not set(people).issubset(liked_by):
        return None
    if any(vote.announced_at_utc is not None for vote in votes):
        return None

    announced = utcnow()
    for vote in votes:
        if vote.liked:
            vote.announced_at_utc = announced
    await db.flush()

    title, year, poster = await film_face(db, suggestion)
    return Match(movie_id=suggestion.movie_id, title=title, poster_path=poster, year=year)


async def record_vote(
    db: AsyncSession,
    *,
    session: MovieNightSession,
    user: Profile,
    suggestion: MovieNightSuggestion,
    liked: bool,
    now: datetime | None = None,
) -> Match | None:
    """Store one swipe, tell the room, and announce a match if this completed one.

    **Votes are cast on a suggestion, not on a film** (Batch S7). That is what lets
    everyone vote on anyone's suggestion, and what lets a film outside the Archive be
    voted on at all — it has no `movies` row to key against.
    """
    now = now or utcnow()

    # **One vote at a time per night** (Batch Z1, `DECISIONS.md` #287). Without this, two
    # likes committed within milliseconds each ran `detect_match` seeing only their own
    # uncommitted vote, and neither announced. Holding the night's row until commit makes the
    # second voter wait, and its read then sees the first like. Taken first, before any vote
    # row, so the order of locks is always the same.
    await db.execute(
        select(MovieNightSession.id).where(MovieNightSession.id == session.id).with_for_update()
    )

    existing = (
        await db.execute(
            select(MovieNightVote).where(
                MovieNightVote.session_id == session.id,
                MovieNightVote.user_id == user.id,
                MovieNightVote.suggestion_id == suggestion.id,
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
                # Kept in step where there is one, so the pre-S7 unique constraint still
                # does its job for owned films and the legacy rows stay comparable.
                movie_id=suggestion.movie_id,
                suggestion_id=suggestion.id,
                liked=liked,
                created_at_utc=now,
            )
        )
    await db.flush()

    # Told to the room without saying who voted or which way. A movie night where each
    # person can see the other's swipes before deciding is not the same game.
    await publish(db, session.id, "vote", {"suggestionId": str(suggestion.id)})

    if not liked:
        return None

    match = await detect_match(db, session=session, suggestion=suggestion)
    if match is None:
        return None
    # Remembered on the session, so the night page shows it after the event and the push
    # are gone (Batch X12a).
    session.matched_suggestion_id = suggestion.id
    await db.flush()

    await publish(
        db,
        session.id,
        "match",
        {
            "movieId": str(match.movie_id) if match.movie_id else None,
            "title": match.title,
            "posterPath": match.poster_path,
            "year": match.year,
        },
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


def invite_key(session_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """The dedupe key for tonight's invite to one person — one push per person per night."""
    return f"movie-night-invite:{session_id}:{user_id}"


async def deliver_now(db: AsyncSession, user_ids: Iterable[uuid.UUID]) -> None:
    """Send what was just queued for these people now, not at the next scheduled pass.

    **Batch T4.** Until 2026-09-23 a movie-night notification was queued and nothing else:
    only the reminder and scrape jobs deliver, and both crashed on import every night
    (`DECISIONS.md` #204), so "It's a match" never reached a phone. Quiet hours still
    hold: a notification deferred by them is not due yet and waits for the morning pass.

    **A failed push never fails the request.** The vote, the invite and the rows are
    already committed; the notification stays queued for the next pass to retry.
    """
    try:
        async with push_sender() as sender:
            for user_id in user_ids:
                await deliver_pending(db, sender=sender, user_id=user_id)
        await db.commit()
    except Exception:  # noqa: BLE001 - see the docstring
        logger.warning("movie_night_push_failed", exc_info=True)
        await db.rollback()


async def seeded_candidates(
    db: AsyncSession, *, session: MovieNightSession, limit: int = 30
) -> list[Movie]:
    """Films from the Archive to open the session with, honouring §8.3's filters.

    **The deck is the same for everyone, and Batch S7 is where that became true.** The
    docstring on Batch 35's `candidate_movies` claimed it was *"seeded per session so both
    people are shown the same deck in the same order"* and the query was
    ``order_by(func.random())`` with no seed — every call returned a different order, per
    person and per refetch (`DECISIONS.md` #157 names this as a defect to fix regardless).

    Ordering on ``md5(session_id || movie_id)`` gives a shuffle that is **stable per
    session, different between sessions, and identical for everyone in one** — without
    `setseed()`, which is connection state and would leak into whatever ran next on that
    connection.

    These become suggestions credited to nobody: Batch 35 dealt them, no one put them
    forward.
    """
    # The deck is the shelf: a film only watched or wanted has a row too (#269).
    query = select(Movie).where(Movie.deleted_at.is_(None), owned_film())

    filters = session.filters or {}
    if isinstance(filters.get("decadeFrom"), int):
        query = query.where(Movie.year >= filters["decadeFrom"])
    if isinstance(filters.get("decadeTo"), int):
        query = query.where(Movie.year <= filters["decadeTo"])
    if isinstance(filters.get("minRating"), int | float):
        query = query.where(Movie.tmdb_rating >= filters["minRating"])

    shuffle = func.md5(func.concat(str(session.id), func.cast(Movie.id, Text)))
    return list((await db.execute(query.order_by(shuffle).limit(limit))).scalars().all())


async def ensure_seeded(db: AsyncSession, *, session: MovieNightSession, limit: int = 30) -> None:
    """Fill a session's shortlist the first time somebody looks at it.

    Seeding on demand rather than at creation keeps a session that nobody opened from
    writing thirty rows, and means a session created before Batch S7 gets its shortlist
    the moment it is next opened.
    """
    already = await db.scalar(
        select(func.count(MovieNightSuggestion.id)).where(
            MovieNightSuggestion.session_id == session.id
        )
    )
    if already:
        return
    for movie in await seeded_candidates(db, session=session, limit=limit):
        db.add(
            MovieNightSuggestion(
                id=uuid.uuid4(),
                session_id=session.id,
                suggested_by=None,
                movie_id=movie.id,
                title=movie.title,
                year=movie.year,
                poster_path=movie.poster_path,
                overview=movie.overview,
            )
        )
    await db.flush()


class SuggestionRefused(Exception):
    """The film cannot be suggested — already on the list, or not identifiable."""


async def add_suggestion(
    db: AsyncSession,
    *,
    session: MovieNightSession,
    user: Profile,
    movie_id: uuid.UUID | None = None,
    tmdb_id: int | None = None,
    title: str | None = None,
    year: int | None = None,
    poster_path: str | None = None,
    overview: str | None = None,
) -> MovieNightSuggestion:
    """Put a film forward — `DECISIONS.md` #157's first point.

    **Anyone in the session, and any film.** A film on the shelf is named by `movie_id`;
    one outside the Archive by `tmdb_id` plus the metadata captured now, because there is
    no row to read it back from later.

    A film already on the list is refused rather than duplicated — two people wanting the
    same film is agreement, not two cards.
    """
    if (movie_id is None) == (tmdb_id is None):
        raise SuggestionRefused("Name exactly one of a collection film or a TMDB film")

    if movie_id is not None:
        movie = await db.get(Movie, movie_id)
        if movie is None or movie.deleted_at is not None:
            raise SuggestionRefused("That film is not in the collection")
        title, year, poster_path, overview = (
            movie.title,
            movie.year,
            movie.poster_path,
            movie.overview,
        )
    elif not title:
        raise SuggestionRefused("A film outside the collection needs a title")

    clash = await db.scalar(
        select(MovieNightSuggestion)
        .where(
            MovieNightSuggestion.session_id == session.id,
            (MovieNightSuggestion.movie_id == movie_id)
            if movie_id is not None
            else (MovieNightSuggestion.tmdb_id == tmdb_id),
        )
        .with_for_update()
    )
    if clash is not None and clash.suggested_by is None:
        # A person's pick takes precedence over a random seed, with the same id and votes.
        clash.suggested_by = user.id
        clash.created_at_utc = utcnow()
        await db.flush()
        await publish(db, session.id, "suggestion", {"suggestionId": str(clash.id)})
        return clash
    if clash is not None:
        raise SuggestionRefused("That film is already on tonight's list")

    suggestion = MovieNightSuggestion(
        id=uuid.uuid4(),
        session_id=session.id,
        suggested_by=user.id,
        movie_id=movie_id,
        tmdb_id=tmdb_id,
        title=title or "Untitled",
        year=year,
        poster_path=poster_path,
        overview=overview,
    )
    db.add(suggestion)
    await db.flush()

    await publish(db, session.id, "suggestion", {"suggestionId": str(suggestion.id)})
    return suggestion


async def session_suggestions(
    db: AsyncSession, *, session: MovieNightSession
) -> list[MovieNightSuggestion]:
    return list(
        (
            await db.execute(
                select(MovieNightSuggestion)
                .where(MovieNightSuggestion.session_id == session.id)
                .order_by(MovieNightSuggestion.created_at_utc)
            )
        )
        .scalars()
        .all()
    )


async def watched_by_others(
    db: AsyncSession, *, session: MovieNightSession, user: Profile, movie_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[str, date]]]:
    """Who else in the session has seen each film, and when — #157's fourth point.

    **Everyone except the person asking.** "Have *I* seen it" is on the film's own page;
    what a card needs to say is whether the people you are choosing with have.

    Empty for every film until the S8 import runs — `watch_log` holds 0 rows today, which
    is why #157 put S7 after it.
    """
    if not movie_ids:
        return {}
    others = [person for person in await participants(db, session.id) if person != user.id]
    if not others:
        return {}

    rows = (
        await db.execute(
            select(WatchLog.movie_id, Profile.display_name, WatchLog.watched_at)
            .join(Profile, Profile.id == WatchLog.user_id)
            .where(
                WatchLog.movie_id.in_(movie_ids),
                WatchLog.user_id.in_(others),
                WatchLog.deleted_at.is_(None),
            )
            .order_by(WatchLog.watched_at.desc())
        )
    ).all()

    seen: dict[uuid.UUID, list[tuple[str, date]]] = {}
    for movie_id, name, watched_at in rows:
        # Most recent per person: "Mark saw it in March" is the useful sentence, not a
        # list of every time he has ever seen it.
        entries = seen.setdefault(movie_id, [])
        if any(existing[0] == name for existing in entries):
            continue
        entries.append((name, watched_at))
    return seen
