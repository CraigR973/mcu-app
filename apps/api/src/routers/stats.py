"""Stats dashboard and activity feed — roadmap §13.1, §13.2, and §6.5's own endpoints.

**Two of §13.1's five charts have no data in this collection yet, and the endpoint says so
rather than returning zeros.** `watch_log` is empty, so "most watched" has nothing to rank;
`purchase_price` is NULL on all 1,857 imported rows, because the spreadsheet never carried
one, so "collection value over time" has no series. Both return an empty list *plus* the
denominator a reader needs — `itemsWithPrice` — so the page can say "no prices recorded"
instead of drawing a flat line at zero. A chart that renders empty reads as a broken chart;
that is `STATUS.md` gotcha 19's lesson applied to a dashboard.

Everything is computed per request. §17 row 33 designs a 5-minute dashboard cache, and the
measurement that would justify one is in this batch's report rather than assumed here.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import Integer, and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.models.admin_action import AdminAction
from src.models.collection_item import (
    FORMAT_RANK,
    SECTIONS,
    CollectionItem,
    owned_copy,
    owned_film,
)
from src.models.movie import Movie
from src.models.profile import Profile
from src.models.valuation import VALUED_FORMATS
from src.models.watch_log import WatchLog
from src.routers.movies import Database
from src.schemas.stats import (
    ActivityEvent,
    ActivityKind,
    ActivityResponse,
    CountSlice,
    DecadeSlice,
    SpendPoint,
    StatsResponse,
    WatchedFilm,
)

router = APIRouter(prefix="/api/v1", tags=["stats"])

FORMAT_LABELS = {
    "4k_uhd": "4K UHD",
    "blu_ray": "Blu-ray",
    "dvd": "DVD",
    # Batch X12a: the Formats chart counts copies carrying the download format; "Digital" is
    # also a shelf section ("Where they live"), and the two differ (588 and 454 on 18 Oct).
    "download": "Downloads",
}

#: TMDB's genre vocabulary, mirrored so a bar chart can be labelled without a join. The
#: same list the web app's filter bar offers; both come from TMDB's fixed genre list.
GENRE_NAMES = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Science Fiction",
    53: "Thriller",
    10752: "War",
    37: "Western",
    10770: "TV Movie",
}


async def _format_slices(db: AsyncSession) -> list[CountSlice]:
    """Discs per format.

    ``formats`` is **JSONB holding an array**, not a Postgres array — so this is
    ``jsonb_array_elements_text``, and ``unnest`` would fail at runtime with
    "function unnest(jsonb) does not exist". Easy to get wrong because
    ``CollectionItem.formats.contains([...])`` works identically for both types, so the
    filter code gives no hint which one it is.
    """
    # ``table_valued`` + ``JOIN ... ON true`` — a lateral over each row's own array.
    # ``column_valued`` yields a column, which ``join()`` rejects as a FROM target, and
    # ``render_derived()`` emits the ``AS anon(col)`` alias list — without it the query
    # depends on Postgres's default output-column name, which differs per function
    # (``value`` for jsonb_array_elements_text, ``unnest`` for unnest).
    element = (
        func.jsonb_array_elements_text(CollectionItem.formats)
        .table_valued("format_code")
        .render_derived()
    )
    rows = (
        await db.execute(
            select(
                element.c.format_code,
                func.count(CollectionItem.id),
                func.count(func.distinct(CollectionItem.movie_id)),
            )
            .select_from(CollectionItem)
            .join(element, true())
            .where(owned_copy())
            .group_by(element.c.format_code)
        )
    ).all()
    by_code = {str(code): (int(items), int(movies)) for code, items, movies in rows}
    # FORMAT_RANK order — best first — so the chart reads the way the collection is
    # thought about rather than by whichever format happens to be commonest.
    return [
        CountSlice(
            key=code,
            label=FORMAT_LABELS.get(code, code.replace("_", " ")),
            itemCount=by_code[code][0],
            movieCount=by_code[code][1],
        )
        for code in FORMAT_RANK
        if code in by_code
    ]


async def _genre_slices(db: AsyncSession) -> list[CountSlice]:
    # ``genre_ids`` is a real Postgres ``INTEGER[]``, unlike ``formats`` — so this is
    # ``unnest`` and that one is ``jsonb_array_elements_text``. Two array-ish columns on
    # two tables with two different types, and nothing in the filter code says so.
    element = func.unnest(Movie.genre_ids).table_valued("genre_id").render_derived()
    rows = (
        await db.execute(
            select(element.c.genre_id, func.count(func.distinct(Movie.id)))
            .select_from(Movie)
            .join(element, true())
            .where(Movie.deleted_at.is_(None), owned_film())
            .group_by(element.c.genre_id)
            .order_by(func.count(func.distinct(Movie.id)).desc())
        )
    ).all()
    return [
        CountSlice(
            key=str(int(genre_id)),
            label=GENRE_NAMES.get(int(genre_id), f"Genre {int(genre_id)}"),
            itemCount=int(count),
            movieCount=int(count),
        )
        for genre_id, count in rows
    ]


async def _decade_slices(db: AsyncSession) -> list[DecadeSlice]:
    decade = (func.floor(Movie.year / 10) * 10).cast(Integer).label("decade")
    rows = (
        await db.execute(
            select(decade, func.count(Movie.id))
            .where(Movie.deleted_at.is_(None), Movie.year.is_not(None), owned_film())
            .group_by(decade)
            .order_by(decade)
        )
    ).all()
    return [
        DecadeSlice(decade=int(value), label=f"{int(value)}s", movieCount=int(count))
        for value, count in rows
    ]


async def _section_slices(db: AsyncSession) -> list[CountSlice]:
    # Labelled once and grouped by the label. Repeating the ``coalesce`` expression in
    # both clauses makes Postgres complain that ``collection_items.section`` is not in the
    # GROUP BY, because a bound parameter stops it proving the two are the same expression.
    section = func.coalesce(CollectionItem.section, "Unfiled").label("section_name")
    rows = (
        await db.execute(
            select(
                section,
                func.count(CollectionItem.id),
                func.count(func.distinct(CollectionItem.movie_id)),
            )
            .where(owned_copy())
            .group_by(section)
        )
    ).all()
    by_name = {str(name): (int(items), int(movies)) for name, items, movies in rows}
    # SECTIONS order, then Unfiled — the order the shelves are laid out in the room,
    # matching what `/collection/facets` already returns.
    ordered = [name for name in SECTIONS if name in by_name]
    if "Unfiled" in by_name:
        ordered.append("Unfiled")
    return [
        CountSlice(key=name, label=name, itemCount=by_name[name][0], movieCount=by_name[name][1])
        for name in ordered
    ]


async def _most_watched(db: AsyncSession, limit: int) -> list[WatchedFilm]:
    watches = func.count(WatchLog.id).label("watches")
    rows = (
        await db.execute(
            select(Movie, watches, func.max(WatchLog.watched_at))
            .join(WatchLog, WatchLog.movie_id == Movie.id)
            .where(WatchLog.deleted_at.is_(None), Movie.deleted_at.is_(None))
            .group_by(Movie.id)
            .order_by(watches.desc(), func.lower(Movie.title))
            .limit(limit)
        )
    ).all()
    return [
        WatchedFilm(
            movieId=movie.id,
            title=movie.title,
            posterPath=movie.poster_path,
            watchCount=int(count),
            lastWatched=last.isoformat() if last is not None else None,
        )
        for movie, count, last in rows
    ]


async def _spend_over_time(db: AsyncSession) -> tuple[list[SpendPoint], int]:
    """Cumulative spend by month of purchase, and how many discs carry a price at all.

    The second number is what stops an empty chart from lying. All 1,857 imported rows
    have ``purchase_price`` NULL — the spreadsheet never carried one — so an empty series
    means "nothing recorded", not "nothing bought", and only the denominator can say which.
    """
    priced = [
        CollectionItem.deleted_at.is_(None),
        CollectionItem.purchase_price.is_not(None),
    ]
    with_price = int(
        (await db.execute(select(func.count(CollectionItem.id)).where(*priced))).scalar_one()
    )

    month = func.to_char(CollectionItem.purchase_date, "YYYY-MM").label("month")
    rows = (
        await db.execute(
            select(
                month,
                func.sum(CollectionItem.purchase_price),
                func.count(CollectionItem.id),
            )
            .where(*priced, CollectionItem.purchase_date.is_not(None))
            .group_by(month)
            .order_by(month)
        )
    ).all()

    points: list[SpendPoint] = []
    running = 0
    for label, total, count in rows:
        # Integer pence throughout. A running total built from floats drifts, and this is
        # money — the same reason `purchasePrice` crosses the wire as a string.
        cents = int(round(float(total) * 100))
        running += cents
        points.append(
            SpendPoint(
                month=str(label),
                spentCents=cents,
                cumulativeCents=running,
                itemCount=int(count),
            )
        )
    return points, with_price


@router.get("/collection/stats", response_model=StatsResponse)
async def collection_stats(
    user: CurrentUser,
    db: Database,
    most_watched_limit: Annotated[int, Query(alias="mostWatchedLimit", ge=1, le=50)] = 10,
) -> StatsResponse:
    """§13.1's dashboard, in one request.

    One request rather than six, because six would make the page's load time the slowest
    of six round trips and the charts appear one at a time.
    """
    # Films in the collection: a row with an owned copy. Wanted films, and since Batch X5
    # films only watched, have rows too, and are not the collection's (#269).
    total_movies = int(
        (
            await db.execute(
                select(func.count(Movie.id)).where(Movie.deleted_at.is_(None), owned_film())
            )
        ).scalar_one()
    )
    download = CollectionItem.formats.contains(["download"])
    physical = and_(
        Movie.deleted_at.is_(None),
        or_(*(CollectionItem.formats.contains([code]) for code in VALUED_FORMATS)),
    )
    # One aggregate snapshot. Format tags overlap: subtracting downloads from copies
    # loses physical copies that also carry a download, and summing formats counts combos twice.
    total_items, downloads, physical_copies, physical_and_download = (
        await db.execute(
            select(
                func.count(CollectionItem.id),
                func.count(CollectionItem.id).filter(download),
                func.count(CollectionItem.id).filter(physical),
                func.count(CollectionItem.id).filter(and_(physical, download)),
            )
            .select_from(CollectionItem)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(owned_copy())
        )
    ).one()
    identified = int(
        (
            await db.execute(
                select(func.count(Movie.id)).where(
                    Movie.deleted_at.is_(None),
                    # Batch Y3: a series identified counts, as a film does.
                    or_(Movie.tmdb_id.is_not(None), Movie.tmdb_tv_id.is_not(None)),
                    owned_film(),
                )
            )
        ).scalar_one()
    )
    watched = int(
        (
            await db.execute(
                select(func.count(func.distinct(WatchLog.movie_id))).where(
                    WatchLog.user_id == user.id, WatchLog.deleted_at.is_(None)
                )
            )
        ).scalar_one()
    )

    owned_watched = int(
        (
            await db.execute(
                select(func.count(func.distinct(WatchLog.movie_id)))
                .join(Movie, Movie.id == WatchLog.movie_id)
                .where(
                    WatchLog.user_id == user.id,
                    WatchLog.deleted_at.is_(None),
                    Movie.deleted_at.is_(None),
                    owned_film(),
                )
            )
        ).scalar_one()
    )

    spend, items_with_price = await _spend_over_time(db)
    return StatsResponse(
        totalMovies=total_movies,
        totalItems=total_items,
        downloadCopies=downloads,
        physicalCopies=physical_copies,
        physicalAndDownloadCopies=physical_and_download,
        identifiedMovies=identified,
        watchedMovies=watched,
        ownedWatchedMovies=owned_watched,
        formats=await _format_slices(db),
        genres=await _genre_slices(db),
        decades=await _decade_slices(db),
        sections=await _section_slices(db),
        mostWatched=await _most_watched(db, most_watched_limit),
        spendOverTime=spend,
        itemsWithPrice=items_with_price,
    )


#: How an audit action reads in the feed.
_AUDIT_KINDS: dict[str, ActivityKind] = {
    "create": "added",
    "update": "edited",
    "delete": "removed",
    "restore": "restored",
}


@router.get("/activity", response_model=ActivityResponse)
async def activity_feed(
    _user: CurrentUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ActivityResponse:
    """§13.2's feed — "last 20 events across all users".

    **Two of the four sources §13.2 names do not exist yet.** Price drops are Batch 20 and
    loans are Batch 15; both add their rows to this endpoint when they land. What is here
    is real: watches from `watch_log`, and every admin write from `admin_actions`.

    Additions come from the audit log rather than from ``collection_items``, and the
    difference matters: ``added_at_utc`` is NULL on all 1,857 imported rows and
    ``created_at`` is the import timestamp, so ordering the feed by the item table would
    put 1,857 identical "added" events at the top and bury everything else forever.
    """
    events: list[ActivityEvent] = []

    watch_rows = (
        await db.execute(
            select(WatchLog, Movie, Profile)
            .join(Movie, Movie.id == WatchLog.movie_id)
            .outerjoin(Profile, Profile.id == WatchLog.user_id)
            .where(WatchLog.deleted_at.is_(None))
            .order_by(WatchLog.created_at.desc())
            .limit(limit)
        )
    ).all()
    events.extend(
        ActivityEvent(
            id=f"watch:{entry.id}",
            kind="watched",
            at=entry.created_at,
            actorName=profile.display_name if profile else None,
            actorId=profile.id if profile else None,
            movieId=movie.id,
            movieTitle=movie.title,
            posterPath=movie.poster_path,
            detail="rewatched" if entry.is_rewatch else None,
        )
        for entry, movie, profile in watch_rows
    )

    audit_rows = (
        await db.execute(
            select(AdminAction, Profile)
            .outerjoin(Profile, Profile.id == AdminAction.user_id)
            .where(AdminAction.action_type.in_(list(_AUDIT_KINDS)))
            .order_by(AdminAction.created_at.desc())
            .limit(limit)
        )
    ).all()

    # The audit row's target is a *collection item*, so its film has to be looked up —
    # one query for the page rather than one per row.
    item_ids = [
        uuid.UUID(entry.target_id)
        for entry, _ in audit_rows
        if entry.target_table == "collection_items" and _is_uuid(entry.target_id)
    ]
    titles = await _films_for_items(db, item_ids)

    for entry, profile in audit_rows:
        film = titles.get(entry.target_id)
        events.append(
            ActivityEvent(
                id=f"audit:{entry.id}",
                kind=_AUDIT_KINDS[entry.action_type],
                at=entry.created_at,
                actorName=profile.display_name if profile else None,
                actorId=profile.id if profile else None,
                movieId=film[0] if film else None,
                movieTitle=film[1] if film else None,
                posterPath=film[2] if film else None,
                detail=entry.target_table.replace("_", " "),
            )
        )

    events.sort(key=lambda event: event.at, reverse=True)
    return ActivityResponse(items=events[:limit], total=len(events[:limit]))


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


async def _films_for_items(
    db: AsyncSession, item_ids: list[uuid.UUID]
) -> dict[str, tuple[uuid.UUID, str, str | None]]:
    if not item_ids:
        return {}
    rows = (
        await db.execute(
            select(CollectionItem.id, Movie.id, Movie.title, Movie.poster_path)
            .join(Movie, Movie.id == CollectionItem.movie_id)
            .where(CollectionItem.id.in_(item_ids))
        )
    ).all()
    return {str(item_id): (movie_id, title, poster) for item_id, movie_id, title, poster in rows}
