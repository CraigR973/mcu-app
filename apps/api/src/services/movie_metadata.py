"""Translate TMDB payloads into the application's movie and credit shapes.

The import command and the in-app identify flow must enrich films identically. Keeping
the translation here prevents the two paths from silently drifting as TMDB fields are
added or corrected.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from src.tmdb.models import Movie

CREW_ROLE_BY_JOB: dict[str, str] = {
    "Director": "director",
    "Writer": "writer",
    "Screenplay": "writer",
    "Story": "writer",
    "Producer": "producer",
    "Original Music Composer": "composer",
    "Music": "composer",
}

MAX_CAST_STORED = 50
TOP_CAST_SUMMARY_SIZE = 5


def parse_year(raw: str | None) -> int | None:
    """Extract the release year from a TMDB ``YYYY-MM-DD`` string."""
    if not raw:
        return None
    try:
        return int(raw.split("-", 1)[0])
    except (ValueError, IndexError):
        return None


def pick_trailer_key(movie: Movie) -> str | None:
    """Return the YouTube key of the film's trailer, preferring the official one."""
    if movie.videos is None:
        return None
    youtube = [v for v in movie.videos.results if v.site == "YouTube" and v.type == "Trailer"]
    if not youtube:
        return None
    for video in youtube:
        if video.official:
            return video.key
    return youtube[0].key


def build_top_cast_summary(movie: Movie) -> list[dict[str, Any]] | None:
    """Build the five-person, poster-ready cast summary stored on ``movies``."""
    if movie.credits is None or not movie.credits.cast:
        return None
    ordered = sorted(movie.credits.cast, key=lambda member: member.order)
    return [
        {
            "tmdb_person_id": member.id,
            "name": member.name,
            "character_name": member.character,
            "profile_path": member.profile_path,
        }
        for member in ordered[:TOP_CAST_SUMMARY_SIZE]
    ]


def movie_metadata_values(movie: Movie) -> dict[str, Any]:
    """Return every §3.2 value supplied by a full TMDB movie payload."""
    genres = [{"id": genre.id, "name": genre.name} for genre in movie.genres]
    return {
        "tmdb_id": movie.id,
        "imdb_id": movie.imdb_id,
        "title": movie.title,
        "original_title": movie.original_title,
        "year": parse_year(movie.release_date),
        "runtime_minutes": movie.runtime,
        "overview": movie.overview or None,
        "tagline": movie.tagline or None,
        "poster_path": movie.poster_path,
        "backdrop_path": movie.backdrop_path,
        "tmdb_rating": movie.vote_average,
        "tmdb_vote_count": movie.vote_count,
        "genres": genres or None,
        "genre_ids": [genre.id for genre in movie.genres] or None,
        "top_cast_summary": build_top_cast_summary(movie),
        "trailer_key": pick_trailer_key(movie),
        "media_type": "film",
        "is_tv": False,
        "last_tmdb_sync_utc": datetime.now(UTC).replace(tzinfo=None),
    }


def credit_rows(movie_id: uuid.UUID, movie: Movie) -> list[tuple[Any, ...]]:
    """Flatten TMDB credits into rows matching ``movie_credits``."""
    if movie.credits is None:
        return []

    rows: list[tuple[Any, ...]] = []
    ordered_cast = sorted(movie.credits.cast, key=lambda member: member.order)
    for member in ordered_cast[:MAX_CAST_STORED]:
        rows.append(
            (
                str(uuid.uuid4()),
                str(movie_id),
                member.name,
                member.id,
                "cast",
                member.character,
                member.order,
            )
        )

    for crew in movie.credits.crew:
        role = CREW_ROLE_BY_JOB.get(crew.job)
        if role is not None:
            rows.append((str(uuid.uuid4()), str(movie_id), crew.name, crew.id, role, None, None))

    return rows
