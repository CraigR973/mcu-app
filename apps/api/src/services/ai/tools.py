"""What the assistant can do — §9.2's tool definitions and §9.4's write boundary.

**Every tool calls the same endpoint function the web app calls.** `DECISIONS.md` #12
warned that the assistant would be the second consumer of the API and would reopen the
response-envelope question. It does not: these dispatch to the handlers in
`src.routers.*`, which are plain async functions taking `(user, db, ...)`, and they come
back as the same pydantic models the browser parses. If a tool ever wants a shape no
endpoint returns, that is a finding to report — not a reason to add an envelope.

**The tool layer picks the fields** (Batch X7, AI45-03). Each film used to reach the model as
the endpoint's whole item, about 500 characters with two image paths and an original title,
and the totals came last, so the 6,000-character cut removed them first: the app's own
example question saw 13 of 162 films and never the count. Each result is now a compact view
(title, year, formats, place, watched), its total first, a page at a time, and a cut says how
many it left out. The endpoints keep their shapes.

**Two axes decide what a person's tool list contains, and they are different questions.**
`READ_TOOLS` and `WRITE_TOOLS` split by *what a tool does*; `ADMIN_ONLY` splits by *who may
do it*. A viewer keeps their own watch history (Batch 6 and 37 both scope watch data to the
caller), so `log_watch` is a write tool that is **not** admin-only — collapsing the two
axes into one would have taken it away from Mark for no reason.

**A write tool never executes before the person confirms.** That is §9.4 and it is a safety
boundary, not a nicety: the model is reading a conversation that may contain text from
anywhere, and "add this to the wanted list" arriving from a film synopsis rather than from
the person is exactly the case the card exists for. Since X7 the film a write is about is
settled when the model asks (:func:`prepare_write`), so the card names the exact film and
year, and a title shared by several films comes back to the model as a question to ask.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from anthropic.types.tool_param import ToolParam
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utc_today
from src.models.collection_item import SECTIONS, CollectionItem
from src.models.movie import Movie
from src.models.profile import Profile, UserRole

logger = structlog.get_logger(__name__)

#: How much of a result is handed back to the model. A page of 25 compact films is about
#: 3,000 characters, so the bound is now a backstop, and a cut says what it left out.
MAX_RESULT_CHARS = 6000

#: Films per page for search and browse.
PAGE_SIZE = 25

#: The search endpoint ranks at most this many matches, so search pages stop here.
SEARCH_MAX = 50

#: The release window when none is asked for.
DEFAULT_RELEASE_DAYS = 28

FORMATS = ["4k_uhd", "blu_ray", "dvd", "download"]

#: The release calendar's types, as the model asks for them.
RELEASE_KINDS: dict[str, frozenset[str]] = {
    "disc": frozenset({"4k_uhd_release", "blu_ray_release"}),
    "4k": frozenset({"4k_uhd_release"}),
    "blu_ray": frozenset({"blu_ray_release"}),
    "streaming": frozenset({"streaming_release"}),
    "theatrical": frozenset({"theatrical"}),
    "sale": frozenset({"sale_event"}),
    "award": frozenset({"award_ceremony"}),
}

#: Appended to each write tool's description (AI45-02). "Requires the person's confirmation
#: before it runs" read to the model as "ask first", so it asked in words, and the typed
#: "yes" could not be sent.
_CARD = (
    " The app shows the person a Yes/No card before anything is written, so call this as "
    "soon as they ask; do not ask them to confirm in words first. If the title matches more "
    "than one film the result says so: ask which one, then call again with its movieId."
)


def _tool(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> ToolParam:
    """One tool definition, with `strict` on.

    `strict: true` guarantees the arguments validate against the schema exactly, which
    matters most for the write tools: a malformed `max_price` reaching the wanted list is
    a 422 the person never sees, from a call they did confirm.
    """
    return ToolParam(
        name=name,
        description=description,
        # `strict` guarantees the arguments validate against the schema exactly. It needs
        # `additionalProperties: false` and `required` to be present, which is why they
        # are set here rather than left to each caller.
        strict=True,
        input_schema={
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    )


_PAGE = {"type": "integer", "description": "Which page of results, from 1. Defaults to 1."}
_MOVIE_ID = {
    "type": "string",
    "description": "The film's id from an earlier result, when its title is shared.",
}
_YEAR = {"type": "integer", "description": "The film's release year, when it is known."}

READ_TOOLS: list[ToolParam] = [
    _tool(
        "search_collection",
        "Search the films the collection owns by title, cast, director or keyword. Returns the "
        f"total number of matches first, then {PAGE_SIZE} films a page: id, title, year, formats "
        "owned, where each is kept, and whether the person asking has watched it.",
        {
            "query": {
                "type": "string",
                "description": "What to search for — a title, an actor, a director.",
            },
            "page": _PAGE,
        },
        ["query"],
    ),
    _tool(
        "browse_collection",
        "List the films the collection owns, with filters, for questions search cannot answer — "
        "'unwatched 4Ks from the 1980s', 'everything on the Front 2nd shelf'. Every argument is "
        f"optional. Returns the total first, then {PAGE_SIZE} films a page.",
        {
            "format": {
                "type": "string",
                "enum": FORMATS,
                "description": "Only films owned in this format.",
            },
            "section": {
                "type": "string",
                "enum": list(SECTIONS),
                # From the vocabulary itself, so a new place reaches the assistant with the
                # model: the hand-written list stopped at the five §3.4 names (Batch V4).
                "description": f"Where it is kept — one of {', '.join(SECTIONS)}.",
            },
            "shelf": {
                "type": "string",
                "description": "Which shelf, e.g. '2nd'; in the Lounge, 'Left' or 'Right'.",
            },
            # Decades as decades (AI45-07): "earliest release year" led the model to send
            # 1985, which the endpoint refuses, and the 1980s cost a retry.
            "decadeFrom": {
                "type": "integer",
                "description": "The earliest decade, as its first year: 1980 for the 1980s.",
            },
            "decadeTo": {
                "type": "integer",
                "description": (
                    "The latest decade, as its first year: 1980 for the 1980s. For one "
                    "decade, give it as both decadeFrom and decadeTo."
                ),
            },
            "watched": {
                "type": "boolean",
                "description": (
                    "True for films the person asking has watched, false for ones they have not."
                ),
            },
            "page": _PAGE,
        },
        [],
    ),
    _tool(
        "list_wanted",
        "The shared wanted list — films wanted and not owned yet, with the format wanted and any "
        "price limit. Returns the total first.",
        {},
        [],
    ),
    _tool(
        "collection_stats",
        "Summary numbers for the whole collection: how many films and copies, how many the "
        "person asking has watched, and the split by format, decade, genre and place.",
        {},
        [],
    ),
    _tool(
        "upcoming_releases",
        "Releases and events from the release calendar between two dates (the next "
        f"{DEFAULT_RELEASE_DAYS} days unless asked otherwise), soonest first. Returns the "
        f"total and a count by type first, then {PAGE_SIZE} a page.",
        {
            "fromDate": {
                "type": "string",
                "description": "The first day, as YYYY-MM-DD. Defaults to today.",
            },
            "toDate": {
                "type": "string",
                "description": (
                    f"The last day, as YYYY-MM-DD. Defaults to {DEFAULT_RELEASE_DAYS} days "
                    "after the first."
                ),
            },
            "kind": {
                "type": "string",
                "enum": ["all", *RELEASE_KINDS],
                "description": (
                    "Which releases: 'disc' (4K and Blu-ray), '4k', 'blu_ray', 'streaming', "
                    "'theatrical', 'sale', 'award' or 'all'. Defaults to 'all'."
                ),
            },
            "page": _PAGE,
        },
        [],
    ),
]

WRITE_TOOLS: list[ToolParam] = [
    _tool(
        "add_to_wanted",
        "Add a film to the shared wanted list. The film need not be in the collection: one "
        "that is not is found on TMDB." + _CARD,
        {
            "title": {"type": "string", "description": "The film's title."},
            "year": _YEAR,
            "movieId": _MOVIE_ID,
            "preferredFormat": {
                "type": "string",
                "enum": FORMATS,
                "description": "The format wanted.",
            },
            "maxPrice": {
                "type": "string",
                "description": "Alert below this price in pounds, as a decimal like '19.99'.",
            },
        },
        ["title"],
    ),
    _tool(
        "log_watch",
        "Record that the person asking watched a film in the catalogue. Watch history is "
        "personal — this only ever writes the caller's own." + _CARD,
        {
            "title": {"type": "string", "description": "The film they watched."},
            "year": _YEAR,
            "movieId": _MOVIE_ID,
            "rating": {
                "type": "number",
                "description": "Their rating out of 5, in half stars.",
            },
            "watchedAt": {
                "type": "string",
                "description": "The date, as YYYY-MM-DD. Defaults to today.",
            },
        },
        ["title"],
    ),
]

#: Tools only an admin may use. **Not the same question as "is it a write":** watch history
#: is personal and a viewer keeps their own, so `log_watch` is a write that both people get.
ADMIN_ONLY = frozenset({"add_to_wanted"})

_WRITE_NAMES = frozenset(tool["name"] for tool in WRITE_TOOLS)


def is_write_tool(name: str) -> bool:
    """Whether this tool changes something, and therefore needs §9.4's confirmation."""
    return name in _WRITE_NAMES


def tools_for(role: UserRole) -> list[ToolParam]:
    """§9.2's role-aware filtering — *"the tool list differs correctly between admin and
    viewer"*.

    Filtered here rather than refused at execution time, and both matter. Sending a viewer
    a tool they cannot use produces a confident offer followed by a permission error, which
    reads as the app being broken; the execution-time check stays as well, because a tool
    list is a hint to the model and not a security boundary.
    """
    tools = [*READ_TOOLS, *WRITE_TOOLS]
    if role is UserRole.admin:
        return tools
    return [tool for tool in tools if tool["name"] not in ADMIN_ONLY]


@dataclass(frozen=True)
class ToolOutcome:
    """A tool's answer for the model, and whether it did what it was asked.

    ``ok`` is false when a tool could not run or a write did not happen; the loop marks such a
    write `failed` (AI45-06: a write that failed was recorded as `confirmed`) and sends the
    text as an error result.
    """

    text: str
    ok: bool = True


@dataclass(frozen=True)
class Proposal:
    """A write the model asked for, made ready for the card, or the reason it cannot be.

    Exactly one of ``input`` (the model's arguments plus ``resolved``: the film and its label)
    and ``refusal`` (text the model reads instead of a card) is set.
    """

    input: dict[str, Any] | None = None
    refusal: str | None = None


# ---------------------------------------------------------------------------
# Results: totals first, a page at a time, and a cut that counts what it cut
# ---------------------------------------------------------------------------


def _fit(header: dict[str, Any], key: str, items: list[dict[str, Any]]) -> str:
    """Serialise ``header`` then as many of ``items`` as fit, saying how many did not.

    The header carries the totals and goes first, so no cut can remove them.
    """
    kept: list[dict[str, Any]] = []
    for item in items:
        trial = json.dumps({**header, key: [*kept, item]}, default=str)
        if len(trial) > MAX_RESULT_CHARS - 200:
            break
        kept.append(item)
    left_out = len(items) - len(kept)
    if left_out:
        header = {
            **header,
            "leftOut": (
                f"{left_out} more on this page were left out to keep the answer short; ask "
                "for a narrower list."
            ),
        }
    return json.dumps({**header, key: kept}, default=str)


def _page_of(value: Any) -> int:
    try:
        return max(int(value or 1), 1)
    except (TypeError, ValueError):
        return 1


def _decade(value: Any) -> int | None:
    """A year as its decade's first year: 1985 is the 1980s."""
    if value is None:
        return None
    year = int(value)
    return year - year % 10


async def _formats_by_movie(
    db: AsyncSession, movie_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """Each film's formats across its live copies, in one query for the page."""
    if not movie_ids:
        return {}
    rows = (
        await db.execute(
            select(CollectionItem.movie_id, CollectionItem.formats).where(
                CollectionItem.movie_id.in_(movie_ids), CollectionItem.deleted_at.is_(None)
            )
        )
    ).all()
    found: dict[uuid.UUID, set[str]] = {}
    for movie_id, formats in rows:
        found.setdefault(movie_id, set()).update(formats or [])
    order = {code: index for index, code in enumerate(FORMATS)}
    return {
        movie_id: sorted(codes, key=lambda code: (order.get(code, len(order)), code))
        for movie_id, codes in found.items()
    }


async def _films(db: AsyncSession, items: list[Any]) -> list[dict[str, Any]]:
    """The compact view of a page of the endpoint's film items."""
    formats = await _formats_by_movie(db, [item.id for item in items])
    films = []
    for item in items:
        film: dict[str, Any] = {
            "id": str(item.id),
            "title": item.title,
            "year": item.year,
            "formats": formats.get(item.id, []),
            "place": ", ".join(location.label for location in item.locations) or None,
            "watched": item.watched,
        }
        if item.lastWatchedAt is not None:
            film["lastWatched"] = item.lastWatchedAt.isoformat()
        films.append(film)
    return films


def _page_header(
    total: int, page: int, per_page: int, *, reachable: int | None = None
) -> dict[str, Any]:
    reachable = total if reachable is None else min(total, reachable)
    pages = max(math.ceil(reachable / per_page), 1)
    first = (page - 1) * per_page + 1
    last = min(page * per_page, reachable)
    header: dict[str, Any] = {"total": total, "page": page, "pages": pages}
    if first <= last:
        header["showing"] = f"{first}–{last} of {total}"
    else:
        header["showing"] = f"none: page {page} is past the last page, {pages}"
    if page < pages:
        header["more"] = f"{reachable - last} more; ask for page {page + 1}."
    return header


async def _search(user: Profile, db: AsyncSession, tool_input: dict[str, Any]) -> str:
    from src.routers.movies import search_movies

    query = str(tool_input.get("query", "")).strip()
    if len(query) < 2:
        return "The search needs at least two characters."
    page = _page_of(tool_input.get("page"))
    found = await search_movies(user, db, q=query, limit=min(page * PAGE_SIZE, SEARCH_MAX))
    items = found.items[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    header = {"query": query, **_page_header(found.total, page, PAGE_SIZE, reachable=SEARCH_MAX)}
    if found.total > SEARCH_MAX:
        header["note"] = (
            f"Only the best {SEARCH_MAX} matches can be listed; {found.total - SEARCH_MAX} more "
            "need a narrower search or browse_collection."
        )
    return _fit(header, "films", await _films(db, items))


async def _browse(user: Profile, db: AsyncSession, tool_input: dict[str, Any]) -> str:
    from src.routers.movies import list_movies

    page = _page_of(tool_input.get("page"))
    decade_from = _decade(tool_input.get("decadeFrom"))
    decade_to = _decade(tool_input.get("decadeTo"))
    result = await list_movies(
        user,
        db,
        page=page,
        per_page=PAGE_SIZE,
        format_code=tool_input.get("format"),
        section=tool_input.get("section"),
        shelf=tool_input.get("shelf"),
        decade_from=decade_from,
        decade_to=decade_to,
        watched=tool_input.get("watched"),
    )
    filters = {
        key: value
        for key, value in {
            "format": tool_input.get("format"),
            "section": tool_input.get("section"),
            "shelf": tool_input.get("shelf"),
            "decades": (
                f"{decade_from or '…'}s to {decade_to or '…'}s"
                if decade_from is not None or decade_to is not None
                else None
            ),
            "watched": tool_input.get("watched"),
        }.items()
        if value is not None
    }
    header = {"filters": filters, **_page_header(result.totalMovies, page, PAGE_SIZE)}
    return _fit(header, "films", await _films(db, result.items))


async def _wanted(user: Profile, db: AsyncSession) -> str:
    from src.routers.wanted import list_wanted

    found = await list_wanted(user, db)
    items = [
        {
            "movieId": str(item.movieId),
            "title": item.movieTitle,
            "year": item.year,
            "format": item.preferredFormat,
            "edition": item.preferredEdition,
            "maxPrice": item.maxPrice,
            "active": item.isActive,
            "ownedAlready": item.ownedAlready,
        }
        for item in found.items
    ]
    return _fit({"total": found.total, "active": found.activeCount}, "films", items)


async def _stats(user: Profile, db: AsyncSession) -> str:
    from src.routers.stats import collection_stats

    stats = await collection_stats(user, db)
    payload = {
        "films": stats.totalMovies,
        "copies": stats.totalItems,
        "watchedByThePersonAsking": stats.watchedMovies,
        "copiesByFormat": {slice_.label: slice_.itemCount for slice_ in stats.formats},
        "filmsByDecade": {slice_.label: slice_.movieCount for slice_ in stats.decades},
        "copiesByPlace": {slice_.label: slice_.itemCount for slice_ in stats.sections},
        "filmsByGenre, top 10": {slice_.label: slice_.movieCount for slice_ in stats.genres[:10]},
    }
    return json.dumps(payload, default=str)


async def _releases(
    user: Profile, db: AsyncSession, tool_input: dict[str, Any], today: date
) -> str:
    from src.routers.calendar import list_calendar

    try:
        start = (
            date.fromisoformat(str(tool_input["fromDate"])) if tool_input.get("fromDate") else today
        )
        end = (
            date.fromisoformat(str(tool_input["toDate"]))
            if tool_input.get("toDate")
            else start + timedelta(days=DEFAULT_RELEASE_DAYS)
        )
    except ValueError:
        return "Dates must be written YYYY-MM-DD."
    start = max(start, today)
    if end < start:
        return "The calendar holds only releases from today on; give a later toDate."
    kind = str(tool_input.get("kind") or "all")
    page = _page_of(tool_input.get("page"))

    # A task list nobody runs: the assistant reading the calendar should not wait on Batch
    # T5's refresh, and the next page view will start it anyway.
    calendar = await list_calendar(
        user, db, BackgroundTasks(), days=min(max((end - today).days, 1), 730)
    )
    window = [entry for entry in calendar.items if start <= entry.releaseDate <= end]
    by_type: dict[str, int] = {}
    for entry in window:
        by_type[entry.typeLabel] = by_type.get(entry.typeLabel, 0) + 1
    wanted_types = RELEASE_KINDS.get(kind)
    chosen = [e for e in window if wanted_types is None or e.releaseType in wanted_types]
    on_page = chosen[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    header = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "kind": kind,
        "inWindowByType": by_type,
        **_page_header(len(chosen), page, PAGE_SIZE),
    }
    items = [
        {
            "date": entry.releaseDate.isoformat(),
            "title": entry.title,
            "type": entry.typeLabel,
            "label": entry.label,
            "inCollection": entry.movieId is not None,
        }
        for entry in on_page
    ]
    return _fit(header, "releases", items)


# ---------------------------------------------------------------------------
# Writes: the film settled when the model asks, run only on a Yes
# ---------------------------------------------------------------------------


def _label(title: str, year: int | None) -> str:
    return f"{title} ({year})" if year else title


async def _catalogue_matches(db: AsyncSession, title: str, year: int | None) -> list[Movie]:
    """Films in the catalogue with exactly this title (and year, when given).

    Exact and deliberately unclever: a fuzzy match would let "add Heat" attach to the wrong
    film on a card that the person would confirm.
    """
    query = select(Movie).where(
        Movie.deleted_at.is_(None), func.lower(Movie.title) == title.strip().lower()
    )
    if year is not None:
        query = query.where(Movie.year == year)
    return list((await db.execute(query.order_by(Movie.year))).scalars().all())


def _ambiguous(title: str, films: list[Movie]) -> str:
    listed = "; ".join(f"{_label(film.title, film.year)}, movieId {film.id}" for film in films)
    return (
        f"{len(films)} films in the catalogue are called {title!r}: {listed}. Ask which one "
        "they mean, then call again with its movieId."
    )


async def _film_by_id(db: AsyncSession, value: Any) -> Movie | None:
    try:
        movie_id = uuid.UUID(str(value))
    except ValueError:
        return None
    movie = await db.get(Movie, movie_id)
    return movie if movie is not None and movie.deleted_at is None else None


async def _tmdb_match(db: AsyncSession, title: str, year: int | None) -> Proposal | dict[str, Any]:
    """The one TMDB film this title means, as ``resolved``, or a refusal to read back."""
    from src.tmdb.client import TMDBClient

    try:
        async with TMDBClient() as tmdb:
            results = (await tmdb.search_movie(title, year=year)).results[:5]
    except Exception as exc:  # noqa: BLE001 - a missing token, a refusal, a timeout
        logger.warning("ai_tmdb_search_failed", error=str(exc)[:300])
        return Proposal(refusal="TMDB couldn't be searched just now, so nothing was added.")
    exact = [result for result in results if result.title.strip().lower() == title.strip().lower()]
    if len(exact) != 1:
        if not results:
            return Proposal(
                refusal=f"Neither the catalogue nor TMDB knows a film called {title!r}."
            )
        listed = "; ".join(_label(result.title, result.year) for result in results)
        return Proposal(
            refusal=(
                f"TMDB has no single film called {title!r}; its closest are: {listed}. Ask "
                "which one they mean, then call again with the exact title and year."
            )
        )
    match = exact[0]
    known = (
        await db.execute(
            select(Movie.id).where(Movie.tmdb_id == match.id, Movie.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    return {
        "movieId": str(known) if known else None,
        "tmdbId": None if known else match.id,
        "label": _label(match.title, match.year),
    }


async def prepare_write(
    name: str, tool_input: dict[str, Any], *, user: Profile, db: AsyncSession, today: date
) -> Proposal:
    """Settle which film a write is about, and check its arguments, before the card shows.

    A write that cannot be settled — a title shared by several films, an unknown film, a
    rating that is not a half star — never reaches a card: the model reads why and asks the
    person (AI45-07). What is settled is stored with the call, so a Yes writes exactly the
    film the card named.
    """
    if name in ADMIN_ONLY and user.role is not UserRole.admin:
        return Proposal(refusal="Only an admin can do that.")

    title = str(tool_input.get("title", "")).strip()
    year = tool_input.get("year")
    year = int(year) if isinstance(year, int | float) else None
    extra: dict[str, Any] = {}

    if name == "log_watch":
        rating = tool_input.get("rating")
        if rating is not None and not (
            0.5 <= float(rating) <= 5 and float(rating) * 2 == int(float(rating) * 2)
        ):
            return Proposal(refusal="A rating is out of 5 in half stars, from 0.5 to 5.")
        try:
            watched = (
                date.fromisoformat(str(tool_input["watchedAt"]))
                if tool_input.get("watchedAt")
                else today
            )
        except ValueError:
            return Proposal(refusal="watchedAt must be a date written YYYY-MM-DD.")
        if watched > today:
            return Proposal(
                refusal=f"{watched:%-d %b %Y} is in the future; today is {today:%-d %b %Y}."
            )
        extra["watchedAt"] = watched.isoformat()
    if name == "add_to_wanted" and tool_input.get("maxPrice") not in (None, ""):
        try:
            price = Decimal(str(tool_input["maxPrice"]))
        except InvalidOperation:
            return Proposal(refusal="maxPrice must be a price in pounds, like '19.99'.")
        if not price.is_finite() or price <= 0:
            return Proposal(refusal="maxPrice must be more than £0.")

    if tool_input.get("movieId"):
        film = await _film_by_id(db, tool_input["movieId"])
        if film is None:
            return Proposal(refusal="No film in the catalogue has that movieId.")
        resolved: dict[str, Any] = {
            "movieId": str(film.id),
            "tmdbId": None,
            "label": _label(film.title, film.year),
        }
    else:
        if not title:
            return Proposal(refusal="Which film? No title was given.")
        films = await _catalogue_matches(db, title, year)
        if len(films) > 1:
            return Proposal(refusal=_ambiguous(title, films))
        if films:
            film = films[0]
            resolved = {
                "movieId": str(film.id),
                "tmdbId": None,
                "label": _label(film.title, film.year),
            }
        elif name == "log_watch":
            return Proposal(refusal=f"No film called {title!r} is in the catalogue.")
        else:
            # The web adds a film nobody owns by TMDB search, and so does this (AI45-07):
            # 22 of 1,890 catalogued films have no copy, so "add a film we don't own" by
            # catalogue title almost always failed.
            match = await _tmdb_match(db, title, year)
            if isinstance(match, Proposal):
                return match
            resolved = match

    return Proposal(input={**tool_input, **extra, "resolved": resolved})


async def _run_write(
    name: str, tool_input: dict[str, Any], *, user: Profile, db: AsyncSession
) -> ToolOutcome:
    from src.routers.wanted import add_wanted
    from src.routers.watch_log import log_watch as log_watch_endpoint
    from src.schemas.movies import WatchLogCreateRequest
    from src.schemas.wanted import WantedCreateRequest
    from src.tmdb.client import TMDBClient

    resolved = tool_input.get("resolved")
    if not isinstance(resolved, dict):
        # A call proposed before X7 carries no film; settle it now, by the same rules.
        proposal = await prepare_write(name, tool_input, user=user, db=db, today=utc_today())
        if proposal.input is None:
            return ToolOutcome(proposal.refusal or "That could not be done.", ok=False)
        resolved = proposal.input["resolved"]
    label = str(resolved.get("label") or tool_input.get("title"))
    movie_id = uuid.UUID(resolved["movieId"]) if resolved.get("movieId") else None

    if name == "add_to_wanted":
        # `add_wanted` takes a TMDB client because it can add by `tmdbId`, for a film the
        # collection has never seen; a catalogued film never reaches it.
        async with TMDBClient() as tmdb:
            await add_wanted(
                WantedCreateRequest(
                    movieId=movie_id,
                    tmdbId=None if movie_id else resolved.get("tmdbId"),
                    preferredFormat=tool_input.get("preferredFormat"),
                    maxPrice=tool_input.get("maxPrice") or None,
                ),
                user,
                db,
                tmdb,
                # A task list nobody runs, as the calendar's above: the assistant's
                # answer should not wait on Brave, and the nightly batch searches for
                # the film's reviews anyway (Batch V9).
                BackgroundTasks(),
            )
        return ToolOutcome(f"Added {label} to the wanted list.")

    if movie_id is None:
        return ToolOutcome(f"{label} is not in the catalogue, so no watch was logged.", ok=False)
    entry = await log_watch_endpoint(
        # The tool's argument is `rating` because that is what a person says; the schema's
        # field is `personalRating` because a watch log has no other kind.
        WatchLogCreateRequest(
            movieId=movie_id,
            personalRating=tool_input.get("rating"),
            watchedAt=tool_input.get("watchedAt"),
        ),
        user,
        db,
    )
    rated = f", rated {entry.personalRating}/5" if entry.personalRating is not None else ""
    return ToolOutcome(f"Logged {label} as watched on {entry.watchedAt:%-d %b %Y}{rated}.")


async def execute_tool(
    name: str,
    tool_input: dict[str, Any],
    *,
    user: Profile,
    db: AsyncSession,
    today: date | None = None,
) -> ToolOutcome:
    """Run one tool and return its result for the model.

    **Never raises.** A tool that blows up must come back as a `tool_result` the model can
    read and explain, because the alternative is a 500 in the middle of somebody's
    conversation with the turn half-written and unreplayable.
    """
    if name in ADMIN_ONLY and user.role is not UserRole.admin:
        # The list already excluded it, so reaching here means the model invented the call
        # or the list was stale. Either way this is the boundary that actually holds.
        return ToolOutcome("Only an admin can do that.", ok=False)

    try:
        if name == "search_collection":
            return ToolOutcome(await _search(user, db, tool_input))
        if name == "browse_collection":
            return ToolOutcome(await _browse(user, db, tool_input))
        if name == "list_wanted":
            return ToolOutcome(await _wanted(user, db))
        if name == "collection_stats":
            return ToolOutcome(await _stats(user, db))
        if name == "upcoming_releases":
            return ToolOutcome(await _releases(user, db, tool_input, today or utc_today()))
        if is_write_tool(name):
            # No savepoint: the endpoints commit their own writes, as they do for the web.
            return await _run_write(name, tool_input, user=user, db=db)
    except HTTPException as exc:
        logger.warning(
            "ai_tool_refused", tool=name, status=exc.status_code, detail=str(exc.detail)[:300]
        )
        return ToolOutcome(f"That did not work: {exc.detail}", ok=False)
    except Exception as exc:  # noqa: BLE001 - see the docstring
        logger.warning("ai_tool_failed", tool=name, error=str(exc)[:300])
        return ToolOutcome(f"That did not work: {exc}", ok=False)

    return ToolOutcome(f"There is no tool called {name!r}.", ok=False)
