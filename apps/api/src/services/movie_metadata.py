"""Translate TMDB payloads into the application's movie and credit shapes.

The import command and the in-app identify flow must enrich films identically. Keeping
the translation here prevents the two paths from silently drifting as TMDB fields are
added or corrected.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from src.tmdb.models import Keyword, Movie, TvShow, Videos

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
    return _trailer_key(movie.videos)


def _trailer_key(videos: Videos | None) -> str | None:
    if videos is None:
        return None
    youtube = [v for v in videos.results if v.site == "YouTube" and v.type == "Trailer"]
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


def keyword_ids(keywords: list[Keyword] | None) -> list[int] | None:
    """A record's TMDB keyword ids — Batch Y5. None when the record carries no keywords
    (it was fetched without them, so they are unknown), an empty list when TMDB has none."""
    if keywords is None:
        return None
    return list(dict.fromkeys(keyword.id for keyword in keywords))


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
        "tmdb_keyword_ids": keyword_ids(movie.keywords.keywords if movie.keywords else None),
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


# ---------------------------------------------------------------------------
# A TV series — Batch Y3
# ---------------------------------------------------------------------------

#: TMDB files series under genres of their own. Each is also filed under the film genres it
#: covers, because the Archive's genre filter offers film genres: without this a series
#: tagged "Sci-Fi & Fantasy" would never answer "Science Fiction". The genres TV and film
#: share (Drama, Crime, Mystery, Comedy and the rest) already have the same id in both.
TV_GENRE_AS_FILM: dict[int, tuple[int, ...]] = {
    10759: (28, 12),  # Action & Adventure: Action, Adventure
    10762: (10751,),  # Kids: Family
    10765: (878, 14),  # Sci-Fi & Fantasy: Science Fiction, Fantasy
    10768: (10752,),  # War & Politics: War
}

#: A series' crew is hundreds of episode credits. Its creators are what a film's director
#: and writers are to it, and ``movie_credits`` has no "creator" role, so they are stored as
#: writers, which they nearly always are; composers are kept as a film's are.
TV_CREW_ROLE_BY_JOB: dict[str, str] = {
    "Original Music Composer": "composer",
    "Music": "composer",
}


def tv_genre_ids(show: TvShow) -> list[int]:
    ids: list[int] = []
    for genre in show.genres:
        for genre_id in (genre.id, *TV_GENRE_AS_FILM.get(genre.id, ())):
            if genre_id not in ids:
                ids.append(genre_id)
    return ids


def build_tv_top_cast_summary(show: TvShow) -> list[dict[str, Any]] | None:
    """The five-person cast summary, from the whole run's cast."""
    if show.aggregate_credits is None or not show.aggregate_credits.cast:
        return None
    ordered = sorted(show.aggregate_credits.cast, key=lambda member: member.order)
    return [
        {
            "tmdb_person_id": member.id,
            "name": member.name,
            "character_name": member.character,
            "profile_path": member.profile_path,
        }
        for member in ordered[:TOP_CAST_SUMMARY_SIZE]
    ]


def tv_metadata_values(show: TvShow) -> dict[str, Any]:
    """Every value a TMDB series supplies, in the shape :func:`movie_metadata_values` gives a
    film's. ``tmdb_id`` is cleared: a row is a film or a series, never both."""
    genres = [{"id": genre.id, "name": genre.name} for genre in show.genres]
    imdb_id = show.external_ids.imdb_id if show.external_ids else None
    return {
        "tmdb_id": None,
        "tmdb_tv_id": show.id,
        "imdb_id": imdb_id or None,
        "title": show.name,
        "original_title": show.original_name or show.name,
        "year": parse_year(show.first_air_date),
        # A series has no one running time. TMDB's per-episode figure would have "under two
        # hours" find a sixty-hour series, so it is left unknown, which the filter excludes.
        "runtime_minutes": None,
        "overview": show.overview or None,
        "tagline": show.tagline or None,
        "poster_path": show.poster_path,
        "backdrop_path": show.backdrop_path,
        "tmdb_rating": show.vote_average,
        "tmdb_vote_count": show.vote_count,
        "genres": genres or None,
        "genre_ids": tv_genre_ids(show) or None,
        "tmdb_keyword_ids": keyword_ids(show.keywords.results if show.keywords else None),
        "top_cast_summary": build_tv_top_cast_summary(show),
        "trailer_key": _trailer_key(show.videos),
        "media_type": "tv",
        "is_tv": True,
        "last_tmdb_sync_utc": datetime.now(UTC).replace(tzinfo=None),
    }


def tv_credit_rows(movie_id: uuid.UUID, show: TvShow) -> list[tuple[Any, ...]]:
    """A series' cast, creators and composers, as rows matching ``movie_credits``."""
    rows: list[tuple[Any, ...]] = []
    credits = show.aggregate_credits
    cast = sorted(credits.cast, key=lambda member: member.order) if credits else []
    for member in cast[:MAX_CAST_STORED]:
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
    for creator in show.created_by:
        rows.append(
            (str(uuid.uuid4()), str(movie_id), creator.name, creator.id, "writer", None, None)
        )
    seen: set[tuple[int, str]] = set()
    for crew in credits.crew if credits else []:
        for job in crew.jobs:
            role = TV_CREW_ROLE_BY_JOB.get(job.job or "")
            if role is not None and (crew.id, role) not in seen:
                seen.add((crew.id, role))
                rows.append(
                    (str(uuid.uuid4()), str(movie_id), crew.name, crew.id, role, None, None)
                )
    return rows
