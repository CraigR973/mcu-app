"""At the match: where the disc is, and "Log it for both of us" — AE10's proposal D (#355).

**One viewing for each person in the night, dated the day it is logged**, in the diary the
Letterboxd sync also fills. Everyone in the night liked the film, or it would not have matched,
so everyone is logged. Whoever already had a viewing of it gets this one as a rewatch.

**Logged once.** ``logged_suggestion_id`` records the match that was logged; a second tap, on
either phone, finds it and writes nothing. The night's row is held while it checks, as voting
does, so two taps at once still log once.

**Merged with Letterboxd, not doubled.** The sync skips only viewing ids it already holds, so a
viewing logged here and again on Letterboxd would become two. The importer now gives a viewing
it brings in to a viewing logged in the app for the same person and film within a day
(`services/letterboxd/importer.claim_app_viewing`).

**A film nobody owns gets its row, with no copy**, as the Letterboxd sync already does for a
film it does not know (#269): a rented film is still watched, and a viewing needs a film to
hang on.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.movie import Movie
from src.models.movie_night import MovieNightSession, MovieNightSuggestion
from src.models.watch_log import WatchLog
from src.services.movie_night.sessions import participants, publish

LONDON = ZoneInfo("Europe/London")


class NothingToLog(Exception):
    """The night has no match to log."""


class FilmInTrash(Exception):
    """The matched film is in the Trash: logging it would bring it back, which is a decision
    for the Trash, not for a movie night."""


def london_day(now: datetime) -> date:
    """The day a viewing logged at ``now`` (naive UTC) is dated: the evening's own date."""
    return now.replace(tzinfo=UTC).astimezone(LONDON).date()


async def film_for_match(db: AsyncSession, suggestion: MovieNightSuggestion) -> Movie:
    """The film row a viewing of this suggestion hangs on, made now if there is none."""
    if suggestion.movie_id is not None:
        movie = await db.get(Movie, suggestion.movie_id)
        if movie is None or movie.deleted_at is not None:
            raise FilmInTrash("That film is in the Trash")
        return movie
    # A film suggested from TMDB: its row if it has one now (bought, or watched since), with
    # the Trash counted, since `movies.tmdb_id` is unique.
    existing = await db.scalar(select(Movie).where(Movie.tmdb_id == suggestion.tmdb_id))
    if existing is not None:
        if existing.deleted_at is not None:
            raise FilmInTrash("That film is in the Trash")
        return existing
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=suggestion.tmdb_id,
        title=suggestion.title,
        original_title=suggestion.title,
        year=suggestion.year,
        poster_path=suggestion.poster_path,
        overview=suggestion.overview,
        runtime_minutes=suggestion.runtime_minutes,
        imdb_id=suggestion.imdb_id,
        media_type="film",
    )
    db.add(movie)
    await db.flush()
    return movie


async def log_the_match(
    db: AsyncSession, *, session: MovieNightSession, now: datetime | None = None
) -> list[WatchLog]:
    """Log the night's match for everyone in it. The caller commits.

    Returns the viewings written: none when this match was logged already.
    """
    now = now or utcnow()
    # Hold the night and read it fresh, so a second tap waits and then finds the first.
    locked = (
        await db.execute(
            select(MovieNightSession)
            .where(MovieNightSession.id == session.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    if locked.matched_suggestion_id is None:
        raise NothingToLog("Nothing has matched yet")
    if locked.logged_suggestion_id == locked.matched_suggestion_id:
        return []
    suggestion = await db.get(MovieNightSuggestion, locked.matched_suggestion_id)
    if suggestion is None:
        raise NothingToLog("Nothing has matched yet")

    movie = await film_for_match(db, suggestion)
    day = london_day(now)
    written: list[WatchLog] = []
    for person in await participants(db, locked.id):
        seen_before = await db.scalar(
            select(
                exists().where(
                    WatchLog.movie_id == movie.id,
                    WatchLog.user_id == person,
                    WatchLog.deleted_at.is_(None),
                )
            )
        )
        viewing = WatchLog(
            id=uuid.uuid4(),
            movie_id=movie.id,
            user_id=person,
            watched_at=day,
            is_rewatch=bool(seen_before),
            # What the viewing was of, as the sync records it; null for a film with no TMDB id.
            tmdb_id=movie.tmdb_id,
        )
        db.add(viewing)
        written.append(viewing)
    locked.logged_suggestion_id = suggestion.id
    locked.logged_at_utc = now
    await db.flush()
    await publish(db, locked.id, "logged", {})
    return written
