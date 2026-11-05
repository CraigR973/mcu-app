"""At the cinema, film first — AC4 (#335, point 3). Stored reads only, like the programme.

Two reads over the stored programme's fortnight, the refresh's run day through the thirteen
after it: every film and listing still to show, with its showings summarised by cinema, day and
run so the view filters without asking again; and one film's every showing across the nine.
Both draw a showing exactly as the programme does (`programme.Window.showing`), so the
coverage, staleness and ticket-link rules are the programme's own.

**A film is one TMDB film** across every cinema and listing title, by AC3's identities.
**Anything else stays its cinema's own listing**: not matched yet, waiting for Craig's check,
a listing that conflicts, or an event that is never one film. A listing gathers the rows one
source lists under one title and the same facts (AC3's `review_key`), because GFT and
CinemaTimes list some films once per showing; it never joins another cinema chain's listing or
a linked film on the title alone (#327, #342).

**Addresses are stable** (#341). A linked film is `tmdb-<id>`; a listing is `listing-<row id>`,
and that address keeps working once the listing is linked: it then opens the film.
"""

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.cinema import CinemaFilm, CinemaScreening
from src.models.movie import Movie
from src.schemas.cinemas import (
    AlsoListed,
    CinemaFilmCard,
    CinemaFilmDetail,
    CinemaFilmFacts,
    CinemaFilmSlot,
    CinemaFilmsResponse,
    FilmKind,
    IdentityStatus,
    ProgrammeWindow,
    ReleaseCategory,
)
from src.services.cinemas import identity
from src.services.cinemas.domain import LONDON, release_category
from src.services.cinemas.programme import Personal, Window, load_window, personal, window_rows
from src.services.cinemas.review import review_key

#: The refresh lists the run day and the thirteen after it.
FORTNIGHT = 14
#: "This week": today and the six days after it.
WEEK = 7
_IMDB = re.compile(r"tt\d{7,10}")
_KEY = re.compile(
    r"(?P<kind>tmdb)-(?P<tmdb>\d{1,10})"
    r"|(?P<uuidkind>movie|listing)-(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"|imdb-(?P<imdb>tt\d{7,10})"
)

Row = tuple[CinemaScreening, CinemaFilm]


def fortnight(now: datetime) -> list[date]:
    today = now.replace(tzinfo=UTC).astimezone(LONDON).date()
    return [today + timedelta(days=i) for i in range(FORTNIGHT)]


def linked_key(film: CinemaFilm, movie: Movie | None) -> str | None:
    """A linked film's address: its TMDB id, else its catalogue film, else its IMDb id."""
    if film.identity_status != "verified":
        return None
    tmdb = movie.tmdb_id if movie and movie.tmdb_id else (film.evidence or {}).get("tmdbId")
    if isinstance(tmdb, int) and not isinstance(tmdb, bool) and tmdb > 0:
        return f"tmdb-{tmdb}"
    if movie:
        return f"movie-{movie.id}"
    imdb = (film.evidence or {}).get("imdbId")
    if isinstance(imdb, str) and _IMDB.fullmatch(imdb):
        return f"imdb-{imdb}"
    return None


def _listing_of(film: CinemaFilm) -> tuple[str, str]:
    """The listing a row belongs to: its source's rows with one title and the same facts. A
    linked row with no film id (an AB6 link) is a listing of its own."""
    if film.identity_status == "verified":
        return ("row", str(film.id))
    return (film.source, review_key(film))


def _candidate(film: CinemaFilm) -> dict[str, Any] | None:
    """The TMDB record AC3 linked the row to, from the lookup it kept."""
    evidence = film.evidence or {}
    tmdb = evidence.get("tmdbId")
    for candidate in (evidence.get("metadata") or {}).get("candidates") or []:
        if isinstance(candidate, dict) and candidate.get("tmdb_id") == tmdb:
            return candidate
    return None


def _cleaned(title: str, shown: date) -> str:
    return identity.read_title(title, shown).query or title


@dataclass
class Group:
    """One film or listing and its rows, earliest showing first."""

    key: str
    kind: FilmKind
    rows: list[Row] = field(default_factory=list)
    movie: Movie | None = None

    @property
    def films(self) -> list[CinemaFilm]:
        seen: dict[uuid.UUID, CinemaFilm] = {}
        for _, film in self.rows:
            seen.setdefault(film.id, film)
        return list(seen.values())


def gather(rows: list[Row], mine: Personal) -> dict[str, Group]:
    """Every film and listing in the rows, by address, in the order each first shows."""
    linked: dict[str, Group] = {}
    listings: dict[tuple[str, str], list[Row]] = defaultdict(list)
    for showing, film in rows:
        movie = mine.movies.get(film.movie_id) if film.movie_id else None
        key = linked_key(film, movie)
        if key is None:
            listings[_listing_of(film)].append((showing, film))
            continue
        group = linked.setdefault(key, Group(key, "film"))
        group.rows.append((showing, film))
        if movie is not None:
            group.movie = movie
    groups = dict(linked)
    for (scope, _), members in listings.items():
        ids = sorted({str(film.id) for _, film in members})
        statuses = {film.identity_status for _, film in members}
        kind: FilmKind = (
            "film" if scope == "row" else "event" if statuses == {"event"} else "listing"
        )
        key = f"listing-{ids[0]}"
        groups[key] = Group(key, kind, members)
    order = {key: min(s.starts_utc for s, _ in g.rows) for key, g in groups.items()}
    return dict(sorted(groups.items(), key=lambda item: (order[item[0]], item[0])))


def _status(group: Group) -> tuple[IdentityStatus, str | None]:
    if group.kind == "film":
        return "verified", None
    films = group.films
    # The status that asks the most of someone wins: Craig's check, then a conflict.
    order: tuple[IdentityStatus, ...] = ("review", "conflict", "unverified", "event")
    for status in order:
        match = next((f for f in films if f.identity_status == status), None)
        if match is not None:
            reason = ((match.evidence or {}).get("identity") or {}).get("reason")
            return status, reason if isinstance(reason, str) else None
    return "unverified", None


def facts(group: Group, mine: Personal, today: date) -> CinemaFilmFacts:
    """A film by TMDB's or the catalogue's name, year and poster; a listing by its cleaned
    title alone, with nothing borrowed from a film it may or may not be."""
    films = group.films
    movie = group.movie
    status, reason = _status(group)
    title = _cleaned(films[0].title, today)
    year: int | None = None
    poster: str | None = None
    directors: list[str] = []
    runtime: int | None = None
    if group.kind == "film":
        candidate = next((c for c in map(_candidate, films) if c), None) or {}
        title = movie.title if movie else candidate.get("title") or title
        year = (
            movie.year if movie else next((f.original_year for f in films if f.original_year), None)
        )
        stored = next(
            (f.evidence["posterPath"] for f in films if (f.evidence or {}).get("posterPath")), None
        )
        poster = (movie.poster_path if movie else None) or stored
        directors = [d for d in candidate.get("directors") or [] if isinstance(d, str)][:3]
        runtime = (movie.runtime_minutes if movie else None) or candidate.get("runtime")
    return CinemaFilmFacts(
        key=group.key,
        kind=group.kind,
        title=title,
        sourceTitles=list(dict.fromkeys(f.title for f in films)),
        posterPath=poster if isinstance(poster, str) else None,
        tmdbId=int(group.key[5:]) if group.key.startswith("tmdb-") else None,
        movieId=movie.id if movie else None,
        originalYear=year,
        yearConfidence="verified" if year is not None else "unverified",
        directors=directors,
        runtimeMinutes=runtime if isinstance(runtime, int) and runtime > 0 else None,
        identityStatus=status,
        identityReason=reason,
        owned=movie.id in mine.owned if movie else None,
        watched=movie.id in mine.watched if movie else None,
    )


def slots(group: Group) -> list[CinemaFilmSlot]:
    """The group's showings by cinema, day and run, each with its start times."""
    found: dict[tuple[uuid.UUID, date, ReleaseCategory, str | None], list[datetime]] = {}
    for showing, film in group.rows:
        verified = film.identity_status == "verified"
        category = release_category(showing.category_evidence, identity_verified=verified)
        reason = showing.category_evidence.get("runReason") if verified else None
        slot = (
            showing.venue_id,
            showing.local_date,
            category,
            reason if isinstance(reason, str) else None,
        )
        found.setdefault(slot, []).append(showing.starts_utc)
    return [
        CinemaFilmSlot(
            venueId=venue,
            localDate=day,
            releaseCategory=category,
            runReason=reason,
            startsAtUtc=sorted(starts),
        )
        for (venue, day, category, reason), starts in found.items()
    ]


async def _read(db: AsyncSession, user_id: uuid.UUID) -> tuple[Window, list[Row], Personal]:
    now = utcnow()
    window = await load_window(db, fortnight(now), now)
    rows = await window_rows(db, window, list(window.known))
    mine = await personal(db, user_id, (f.movie_id for _, f in rows))
    return window, rows, mine


def _window(window: Window) -> ProgrammeWindow:
    return ProgrammeWindow(dateFrom=window.dates[0], dateTo=window.dates[-1])


async def films(db: AsyncSession, user_id: uuid.UUID) -> CinemaFilmsResponse:
    window, rows, mine = await _read(db, user_id)
    today = window.dates[0]
    venues = window.venue_responses()
    cards = [
        CinemaFilmCard(**facts(group, mine, today).model_dump(), slots=slots(group))
        for group in gather(rows, mine).values()
    ]
    cards.sort(key=lambda card: (card.title.casefold(), card.key))
    return CinemaFilmsResponse(
        generatedAtUtc=window.now,
        window=_window(window),
        thisWeekTo=window.dates[WEEK - 1],
        venues=venues,
        films=cards,
        complete=all(c.status in ("healthy", "empty") for v in venues for c in v.coverage),
    )


def _parse(key: str) -> re.Match[str]:
    match = _KEY.fullmatch(key)
    if match is None:
        raise HTTPException(status_code=404, detail="No such film at your cinemas")
    return match


async def _resting(
    db: AsyncSession, key: str, match: re.Match[str], groups: dict[str, Group]
) -> tuple[str, Group | None]:
    """Where an address points when the fortnight lists nothing under it: the film a listing
    has since been linked to, the TMDB film a catalogue film now carries, or the listing's
    other rows. ``None`` when only an earlier row can still name it."""
    if match["uuidkind"] == "listing":
        row = await db.get(CinemaFilm, uuid.UUID(match["uuid"]))
        if row is None or row.deleted_at is not None:
            raise HTTPException(
                status_code=404, detail="This listing is no longer in the programme"
            )
        movie = await _movie(db, row.movie_id)
        canonical = linked_key(row, movie)
        if canonical is not None:
            return canonical, groups.get(canonical) or Group(canonical, "film", [], movie)
        listing = _listing_of(row)
        for group in groups.values():
            if group.kind != "film" and any(_listing_of(f) == listing for f in group.films):
                return group.key, group
        return key, None
    if match["uuidkind"] == "movie":
        movie = await _movie(db, uuid.UUID(match["uuid"]))
        if movie is None:
            raise HTTPException(status_code=404, detail="No such film at your cinemas")
        canonical = f"tmdb-{movie.tmdb_id}" if movie.tmdb_id else key
        return canonical, groups.get(canonical) or Group(canonical, "film", [], movie)
    if match["imdb"]:
        for group in groups.values():
            if any((f.evidence or {}).get("imdbId") == match["imdb"] for f in group.films):
                return group.key, group
        return key, None
    movie = (
        await db.scalars(
            select(Movie).where(
                Movie.tmdb_id == int(match["tmdb"]),
                Movie.deleted_at.is_(None),
                Movie.is_tv.is_(False),
            )
        )
    ).first()
    return key, Group(key, "film", [], movie)


async def _movie(db: AsyncSession, movie_id: uuid.UUID | None) -> Movie | None:
    movie = await db.get(Movie, movie_id) if movie_id else None
    return movie if movie is not None and movie.deleted_at is None and not movie.is_tv else None


async def _unlisted(
    db: AsyncSession,
    user_id: uuid.UUID,
    match: re.Match[str],
    canonical: str,
    group: Group | None,
    today: date,
) -> CinemaFilmFacts:
    """A film or listing with nothing in the fortnight, under its own name where one is known:
    its catalogue film, else the last row that named it."""
    if group is not None and group.movie is not None:
        movie = group.movie
        mine = await personal(db, user_id, [movie.id])
        return CinemaFilmFacts(
            key=canonical,
            kind="film",
            title=movie.title,
            sourceTitles=[],
            posterPath=movie.poster_path,
            tmdbId=movie.tmdb_id,
            movieId=movie.id,
            originalYear=movie.year,
            yearConfidence="verified" if movie.year is not None else "unverified",
            directors=[],
            runtimeMinutes=movie.runtime_minutes,
            identityStatus="verified",
            identityReason=None,
            owned=movie.id in mine.owned,
            watched=movie.id in mine.watched,
        )
    named = await _last_named(db, _parse(canonical))
    if named is None and match["uuidkind"] == "listing":
        named = await db.get(CinemaFilm, uuid.UUID(match["uuid"]))
    if named is None:
        raise HTTPException(status_code=404, detail="No such film at your cinemas")
    return _row_facts(named, canonical, today)


async def _last_named(db: AsyncSession, match: re.Match[str]) -> CinemaFilm | None:
    """The most recently seen linked row a film's address names."""
    query = select(CinemaFilm).where(CinemaFilm.identity_status == "verified")
    if match["tmdb"]:
        query = query.where(CinemaFilm.evidence["tmdbId"].as_integer() == int(match["tmdb"]))
    elif match["imdb"]:
        query = query.where(CinemaFilm.evidence["imdbId"].as_string() == match["imdb"])
    else:
        return None
    return (await db.scalars(query.order_by(CinemaFilm.last_seen_utc.desc()).limit(1))).first()


async def film(db: AsyncSession, user_id: uuid.UUID, key: str) -> CinemaFilmDetail:
    match = _parse(key)
    window, rows, mine = await _read(db, user_id)
    today = window.dates[0]
    groups = gather(rows, mine)
    canonical, group = (
        (key, groups[key]) if key in groups else await _resting(db, key, match, groups)
    )
    if group is not None and group.rows:
        header = facts(group, mine, today)
        showings = [
            window.showing(showing, row, verified=row.identity_status == "verified")
            for showing, row in group.rows
        ]
    else:
        header = await _unlisted(db, user_id, match, canonical, group, today)
        showings = []
    return CinemaFilmDetail(
        generatedAtUtc=window.now,
        window=_window(window),
        thisWeekTo=window.dates[WEEK - 1],
        film=header,
        venues=window.venue_responses(),
        showings=showings,
        alsoListed=_also(header.title, header.key, groups, today),
    )


def _row_facts(film: CinemaFilm, key: str, today: date) -> CinemaFilmFacts:
    """A film or listing with nothing listed now, from the last row that named it."""
    evidence = film.evidence or {}
    verified = film.identity_status == "verified"
    candidate = _candidate(film) if verified else None
    kind: FilmKind = (
        "film" if verified else "event" if film.identity_status == "event" else "listing"
    )
    reason = (evidence.get("identity") or {}).get("reason")
    return CinemaFilmFacts(
        key=key,
        kind=kind,
        title=(candidate or {}).get("title") or _cleaned(film.title, today),
        sourceTitles=[film.title],
        posterPath=evidence.get("posterPath") if verified else None,
        tmdbId=int(key[5:]) if key.startswith("tmdb-") else None,
        movieId=None,
        originalYear=film.original_year if verified else None,
        yearConfidence="verified" if verified and film.original_year is not None else "unverified",
        directors=[d for d in (candidate or {}).get("directors") or [] if isinstance(d, str)][:3],
        runtimeMinutes=(candidate or {}).get("runtime"),
        identityStatus=cast(IdentityStatus, film.identity_status),
        identityReason=reason if isinstance(reason, str) and not verified else None,
        owned=None,
        watched=None,
    )


def _also(title: str, key: str, groups: dict[str, Group], today: date) -> list[AlsoListed]:
    """Other films and listings of the same title: during AC3's backfill, often the same film
    listed by another cinema chain; after it, a namesake. Never merged on the title alone."""
    wanted = identity.normal(_cleaned(title, today))
    out = []
    for other in groups.values():
        if other.key == key or not other.rows:
            continue
        names = {identity.normal(_cleaned(f.title, today)) for f in other.films}
        if other.movie is not None:
            names.add(identity.normal(other.movie.title))
        candidate = next((c for c in map(_candidate, other.films) if c), None)
        if candidate and isinstance(candidate.get("title"), str):
            names.add(identity.normal(candidate["title"]))
        if wanted not in names:
            continue
        out.append(
            AlsoListed(
                key=other.key,
                kind=other.kind,
                title=other.movie.title
                if other.movie is not None
                else (candidate or {}).get("title") or _cleaned(other.films[0].title, today),
                venueIds=sorted({s.venue_id for s, _ in other.rows}, key=str),
                showingCount=len(other.rows),
            )
        )
    return out
