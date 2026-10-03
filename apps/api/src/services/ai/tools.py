"""What the assistant can do — §9.2's tool definitions and §9.4's write boundary.

**Every tool calls the same endpoint function the web app calls.** `DECISIONS.md` #12
warned that the assistant would be the second consumer of the API and would reopen the
response-envelope question. It does not: these dispatch to the handlers in
`src.routers.*`, which are plain async functions taking `(user, db, ...)`, and they come
back as the same pydantic models the browser parses. If a tool ever wants a shape no
endpoint returns, that is a finding to report — not a reason to add an envelope.

**Two axes decide what a person's tool list contains, and they are different questions.**
`READ_TOOLS` and `WRITE_TOOLS` split by *what a tool does*; `ADMIN_ONLY` splits by *who may
do it*. A viewer keeps their own watch history (Batch 6 and 37 both scope watch data to the
caller), so `log_watch` is a write tool that is **not** admin-only — collapsing the two
axes into one would have taken it away from Mark for no reason.

**A write tool never executes before the person confirms.** That is §9.4 and it is a safety
boundary, not a nicety: the model is reading a conversation that may contain text from
anywhere, and "add this to the wanted list" arriving from a film synopsis rather than from
the person is exactly the case the prompt exists for.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from anthropic.types.tool_param import ToolParam
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection_item import SECTIONS
from src.models.profile import Profile, UserRole

logger = structlog.get_logger(__name__)

#: How much of a result is handed back to the model. A tool that returns the whole
#: catalogue would blow the context window and cost a fortune doing it; the model needs
#: enough to answer, not everything that matched.
MAX_RESULT_CHARS = 6000


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


READ_TOOLS: list[ToolParam] = [
    _tool(
        "search_collection",
        "Search the film collection by title, cast, director or keyword. Returns matching "
        "films with the formats owned and where each disc is shelved. Use this for any "
        "question about what is in the collection.",
        {
            "query": {
                "type": "string",
                "description": "What to search for — a title, an actor, a director.",
            },
            "limit": {
                "type": "integer",
                "description": "How many results to return. Defaults to 10.",
            },
        },
        ["query"],
    ),
    _tool(
        "browse_collection",
        "List films in the collection with filters, for questions search cannot answer — "
        "'unwatched 4Ks from the 2010s', 'everything on the Front 2nd shelf'. Every "
        "argument is optional.",
        {
            "format": {
                "type": "string",
                "description": "One of 4k_uhd, blu_ray, dvd, download.",
            },
            "section": {
                "type": "string",
                # From the vocabulary itself, so a new place reaches the assistant with the
                # model: the hand-written list stopped at the five §3.4 names (Batch V4).
                "description": f"Where it is shelved — one of {', '.join(SECTIONS)}.",
            },
            "shelf": {"type": "string", "description": "Which shelf, e.g. '2nd'."},
            "decadeFrom": {"type": "integer", "description": "Earliest release year."},
            "decadeTo": {"type": "integer", "description": "Latest release year."},
            "watched": {
                "type": "boolean",
                "description": "True for watched only, false for unwatched only.",
            },
            "limit": {"type": "integer", "description": "How many to return. Defaults to 20."},
        },
        [],
    ),
    _tool(
        "list_wanted",
        "List the shared wanted list — films not owned yet, with the format wanted and any "
        "price limit set.",
        {},
        [],
    ),
    _tool(
        "collection_stats",
        "Summary numbers for the whole collection: how many discs, the split by format, "
        "by decade and by shelf.",
        {},
        [],
    ),
    _tool(
        "upcoming_releases",
        "Upcoming disc releases and sale events from the release calendar.",
        {},
        [],
    ),
]

WRITE_TOOLS: list[ToolParam] = [
    _tool(
        "add_to_wanted",
        "Add a film to the shared wanted list. Requires the person's confirmation before it runs.",
        {
            "title": {"type": "string", "description": "The film's title."},
            "preferredFormat": {
                "type": "string",
                "description": "One of 4k_uhd, blu_ray, dvd, download.",
            },
            "maxPrice": {
                "type": "string",
                "description": "Alert below this price, as a decimal string like '19.99'.",
            },
        },
        ["title"],
    ),
    _tool(
        "log_watch",
        "Record that the person asking watched a film. Watch history is personal — this "
        "only ever writes the caller's own. Requires confirmation before it runs.",
        {
            "title": {"type": "string", "description": "The film they watched."},
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


def _truncate(payload: Any) -> str:
    """Serialise a result for the model, bounded."""
    text = json.dumps(payload, default=str)
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[:MAX_RESULT_CHARS] + "… (truncated; ask for fewer results or narrow the query)"


async def execute_tool(
    name: str, tool_input: dict[str, Any], *, user: Profile, db: AsyncSession
) -> str:
    """Run one tool and return its result as text for the model.

    **Never raises.** A tool that blows up must come back as a `tool_result` the model can
    read and explain, because the alternative is a 500 in the middle of somebody's
    conversation with the turn half-written and unreplayable.
    """
    # Imported here rather than at module scope: the routers import the auth and database
    # modules, and importing them at import time makes a cycle through `src.routers.ai`.
    from src.routers.calendar import list_calendar
    from src.routers.movies import list_movies, search_movies
    from src.routers.stats import collection_stats
    from src.routers.wanted import add_wanted, list_wanted
    from src.routers.watch_log import log_watch as log_watch_endpoint
    from src.schemas.wanted import WantedCreateRequest
    from src.tmdb.client import TMDBClient

    if name in ADMIN_ONLY and user.role is not UserRole.admin:
        # The list already excluded it, so reaching here means the model invented the call
        # or the list was stale. Either way this is the boundary that actually holds.
        return "Only an admin can do that."

    try:
        if name == "search_collection":
            query = str(tool_input.get("query", "")).strip()
            if len(query) < 2:
                return "The search needs at least two characters."
            limit = min(int(tool_input.get("limit", 10) or 10), 25)
            return _truncate((await search_movies(user, db, q=query, limit=limit)).model_dump())

        if name == "browse_collection":
            page = await list_movies(
                user,
                db,
                page=1,
                per_page=min(int(tool_input.get("limit", 20) or 20), 50),
                format_code=tool_input.get("format"),
                section=tool_input.get("section"),
                shelf=tool_input.get("shelf"),
                decade_from=tool_input.get("decadeFrom"),
                decade_to=tool_input.get("decadeTo"),
                watched=tool_input.get("watched"),
            )
            return _truncate(page.model_dump())

        if name == "list_wanted":
            return _truncate((await list_wanted(user, db)).model_dump())

        if name == "collection_stats":
            return _truncate((await collection_stats(user, db)).model_dump())

        if name == "upcoming_releases":
            # A task list nobody runs: the assistant reading the calendar should not wait on
            # Batch T5's refresh, and the next page view will start it anyway.
            return _truncate((await list_calendar(user, db, BackgroundTasks())).model_dump())

        if name == "add_to_wanted":
            movie_id = await _find_movie(db, str(tool_input.get("title", "")))
            if movie_id is None:
                return (
                    f"No film called {tool_input.get('title')!r} is known to this "
                    "collection, so there is nothing to add to the wanted list."
                )
            # `add_wanted` takes a TMDB client because it can also add by `tmdbId`, for a
            # film the collection has never seen. This path always supplies a `movieId`,
            # so the client is never reached — but the signature still wants one, and
            # opening it here keeps the handler unmodified rather than forking it.
            async with TMDBClient() as tmdb:
                created = await add_wanted(
                    WantedCreateRequest(
                        movieId=movie_id,
                        preferredFormat=tool_input.get("preferredFormat"),
                        maxPrice=tool_input.get("maxPrice"),
                    ),
                    user,
                    db,
                    tmdb,
                    # A task list nobody runs, as the calendar's above: the assistant's
                    # answer should not wait on Brave, and the nightly batch searches for
                    # the film's reviews anyway (Batch V9).
                    BackgroundTasks(),
                )
            return _truncate(created.model_dump())

        if name == "log_watch":
            movie_id = await _find_movie(db, str(tool_input.get("title", "")))
            if movie_id is None:
                return f"No film called {tool_input.get('title')!r} is in the collection."
            from src.schemas.movies import WatchLogCreateRequest

            entry = await log_watch_endpoint(
                # The tool's argument is `rating` because that is what a person says; the
                # schema's field is `personalRating` because a watch log has no other kind.
                # Mapped here rather than renaming either side.
                WatchLogCreateRequest(
                    movieId=movie_id,
                    personalRating=tool_input.get("rating"),
                    watchedAt=tool_input.get("watchedAt"),
                ),
                user,
                db,
            )
            return _truncate(entry.model_dump())

    except Exception as exc:  # noqa: BLE001 - see the docstring
        logger.warning("ai_tool_failed", tool=name, error=str(exc)[:300])
        return f"That did not work: {exc}"

    return f"There is no tool called {name!r}."


async def _find_movie(db: AsyncSession, title: str) -> uuid.UUID | None:
    """The film a write tool is about, by title.

    Write tools take a **title** rather than an id because that is what the model has —
    it is reading a conversation, not a database. The lookup is exact-ish and deliberately
    unclever: a fuzzy match here would let "add Heat" attach to the wrong film in a
    confirmation prompt that says only "Heat", and the person would confirm it.
    """
    from sqlalchemy import func, select

    from src.models.movie import Movie

    cleaned = title.strip()
    if not cleaned:
        return None
    return (
        await db.execute(
            select(Movie.id)
            .where(Movie.deleted_at.is_(None), func.lower(Movie.title) == cleaned.lower())
            .limit(1)
        )
    ).scalar_one_or_none()
