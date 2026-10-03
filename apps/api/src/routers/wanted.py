"""The wanted list and retailer management — roadmap §5.1, §5.2, §6.5.

**This batch pays four debts.** Batch 13 dropped §11.2's "bulk add missing to wanted list",
Batch 15 made the trash *refuse* the name `wanted_list`, Batch 16 shipped a two-state
ownership enum where §7.2 asked for three, and Batch 17 created
`release_calendar.is_wishlist_match` and wrote nothing to it. Each was deferred here
because §3.5 had no table. The first three are wired up by this batch.

Both surfaces are **admin-only for writes**, matching Batch 7's collection surface: §5.1
calls it "movies the admin wants to purchase", and §3.16 says "admin can add, edit, or
disable retailers". Reads are open to both people — Mark can reasonably want to see what
is being looked for.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, cast

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AdminUser, CurrentUser
from src.clock import utcnow
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.models.reviews import FilmReview
from src.models.wanted import (
    DEFAULT_RETAILERS,
    RETAILERS_TABLE,
    WANTED_LIST_TABLE,
    Retailer,
    WantedItem,
)
from src.routers.movies import Database, TmdbClient
from src.schemas.wanted import (
    RetailerCreateRequest,
    RetailerListResponse,
    RetailerResponse,
    RetailerSeedResponse,
    RetailerUpdateRequest,
    ScrapeFrequency,
    ScraperType,
    WantedCreateRequest,
    WantedItemResponse,
    WantedListResponse,
    WantedUpdateRequest,
)
from src.services.audit import record_action
from src.services.movie_metadata import credit_rows, movie_metadata_values
from src.services.reviews.batch import search_for_want_in_background
from src.services.reviews.read import for_want, review_response, reviews_by_movie

router = APIRouter(prefix="/api/v1", tags=["wanted", "retailers"])


# ---------------------------------------------------------------------------
# §5.1 — the wanted list
# ---------------------------------------------------------------------------


async def _owned_movie_ids(db: AsyncSession, movie_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Which of these films still have a live disc.

    Wanting a film you own is **not** an error — upgrading a DVD to 4K is exactly that —
    so this is surfaced on the card rather than refused at the endpoint.
    """
    if not movie_ids:
        return set()
    rows = await db.execute(
        select(CollectionItem.movie_id)
        .where(CollectionItem.movie_id.in_(movie_ids), owned_copy())
        .distinct()
    )
    return set(rows.scalars().all())


def _wanted_response(
    item: WantedItem, movie: Movie, *, owned: bool, reviews: list[FilmReview] | None = None
) -> WantedItemResponse:
    return WantedItemResponse(
        id=item.id,
        movieId=item.movie_id,
        movieTitle=movie.title,
        year=movie.year,
        posterPath=movie.poster_path,
        preferredFormat=item.preferred_format,
        preferredEdition=item.preferred_edition,
        # A string on the wire. Money never round-trips through a float, and this value is
        # the threshold Batch 20's alerts compare against.
        maxPrice=str(item.max_price) if item.max_price is not None else None,
        currency=item.currency,
        isActive=item.is_active,
        notes=item.notes,
        ownedAlready=owned,
        addedAt=item.added_at,
        reviews=[review_response(row) for row in for_want(reviews or [], item.preferred_format)],
    )


@router.get("/wanted", response_model=WantedListResponse)
async def list_wanted(
    _user: CurrentUser,
    db: Database,
    active_only: Annotated[bool, Query(alias="activeOnly")] = False,
) -> WantedListResponse:
    """§5.1's list. Readable by both people."""
    predicates = [WantedItem.deleted_at.is_(None)]
    if active_only:
        predicates.append(WantedItem.is_active.is_(True))

    rows = (
        await db.execute(
            select(WantedItem, Movie)
            .join(Movie, Movie.id == WantedItem.movie_id)
            .where(*predicates)
            .order_by(WantedItem.is_active.desc(), WantedItem.added_at.desc())
        )
    ).all()
    owned = await _owned_movie_ids(db, [item.movie_id for item, _ in rows])
    reviews = await reviews_by_movie(db, [item.movie_id for item, _ in rows])
    items = [
        _wanted_response(
            item, movie, owned=item.movie_id in owned, reviews=reviews.get(item.movie_id, [])
        )
        for item, movie in rows
    ]
    return WantedListResponse(
        items=items,
        total=len(items),
        activeCount=sum(1 for item in items if item.isActive),
    )


async def _movie_for_wanted(
    db: AsyncSession, payload: WantedCreateRequest, tmdb: TmdbClient
) -> Movie:
    """Resolve the film, creating it from TMDB if this collection has never seen it.

    **The whole point of wanting a film is that you do not own it**, so most wanted
    entries name something with no `movies` row. Creating one from TMDB here is what makes
    §11.2's "add missing to wanted list" and §7.2's recommendation cards possible at all —
    both of them start from a `tmdbId` and nothing else.
    """
    if payload.movieId is not None:
        movie = await db.get(Movie, payload.movieId)
        if movie is None or movie.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
        return movie

    if payload.tmdbId is None:  # pragma: no cover - the model validator rejects this
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supply exactly one of movieId or tmdbId",
        )

    existing = await db.scalar(select(Movie).where(Movie.tmdb_id == payload.tmdbId))
    if existing is not None:
        return existing

    try:
        tmdb_movie = await tmdb.get_movie_full(payload.tmdbId)
    except httpx.HTTPError as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail="TMDB film could not be loaded") from exc

    movie = Movie(id=uuid.uuid4(), **movie_metadata_values(tmdb_movie))
    db.add(movie)
    await db.flush()
    for row in credit_rows(movie.id, tmdb_movie):
        from src.models.movie import MovieCredit

        db.add(
            MovieCredit(
                id=uuid.UUID(row[0]),
                movie_id=movie.id,
                person_name=row[2],
                tmdb_person_id=row[3],
                role=row[4],
                character_name=row[5],
                display_order=row[6],
            )
        )
    await db.flush()
    return movie


@router.post("/wanted", response_model=WantedItemResponse, status_code=status.HTTP_201_CREATED)
async def add_wanted(
    payload: WantedCreateRequest,
    user: AdminUser,
    db: Database,
    tmdb: TmdbClient,
    background_tasks: BackgroundTasks,
) -> WantedItemResponse:
    """§5.1's acceptance: "adding to wanted list from detail page ... works".

    Batch V9: once the response has gone, Brave is searched for the film's reviews on
    Blu-ray.com and AVForums, so the links are there when the list is next opened.
    """
    if (payload.movieId is None) == (payload.tmdbId is None):
        # Both or neither. A `model_validator` would be the tidier home for this, and
        # `STATUS.md` gotcha 20 is why it is not a `field_validator`: one does not run for
        # a field the request omits, so "neither" would sail through as a 500.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supply exactly one of movieId or tmdbId",
        )

    movie = await _movie_for_wanted(db, payload, tmdb)
    item = WantedItem(
        id=uuid.uuid4(),
        movie_id=movie.id,
        preferred_format=payload.preferredFormat,
        preferred_edition=payload.preferredEdition,
        max_price=Decimal(payload.maxPrice) if payload.maxPrice else None,
        currency=payload.currency,
        notes=payload.notes,
        added_by=user.id,
        added_at=utcnow(),
    )
    db.add(item)
    record_action(
        db,
        user_id=user.id,
        action_type="create",
        target_table=WANTED_LIST_TABLE,
        target_id=item.id,
        changes={"movie": movie.title, "format": payload.preferredFormat},
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # `uq_wanted_list_live_movie`. Wanting the same film twice is a mistake, not a
        # plan — and Batch 20's alerts would fire twice for it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That film is already on the wanted list",
        ) from exc

    await db.refresh(item)
    owned = await _owned_movie_ids(db, [movie.id])
    background_tasks.add_task(search_for_want_in_background, movie.id)
    reviews = (await reviews_by_movie(db, [movie.id])).get(movie.id, [])
    return _wanted_response(item, movie, owned=movie.id in owned, reviews=reviews)


@router.put("/wanted/{item_id}", response_model=WantedItemResponse)
async def update_wanted(
    item_id: uuid.UUID, payload: WantedUpdateRequest, user: AdminUser, db: Database
) -> WantedItemResponse:
    item = await db.get(WantedItem, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    before = {
        "preferred_format": item.preferred_format,
        "max_price": str(item.max_price) if item.max_price else None,
        "is_active": item.is_active,
    }
    item.preferred_format = payload.preferredFormat
    item.preferred_edition = payload.preferredEdition
    item.max_price = Decimal(payload.maxPrice) if payload.maxPrice else None
    item.currency = payload.currency
    item.is_active = payload.isActive
    item.notes = payload.notes
    after = {
        "preferred_format": item.preferred_format,
        "max_price": str(item.max_price) if item.max_price else None,
        "is_active": item.is_active,
    }
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table=WANTED_LIST_TABLE,
        target_id=item.id,
        changes={k: {"from": before[k], "to": after[k]} for k in before if before[k] != after[k]},
    )
    await db.commit()
    await db.refresh(item)

    movie = await db.get(Movie, item.movie_id)
    if movie is None:  # pragma: no cover - RESTRICT guarantees it
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    owned = await _owned_movie_ids(db, [movie.id])
    reviews = (await reviews_by_movie(db, [movie.id])).get(movie.id, [])
    return _wanted_response(item, movie, owned=movie.id in owned, reviews=reviews)


@router.delete("/wanted/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wanted(item_id: uuid.UUID, user: AdminUser, db: Database) -> None:
    """Soft-delete, so §13.5's Trash can restore it — the tab Batch 15 built and could not
    fill."""
    item = await db.get(WantedItem, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    item.deleted_at = utcnow()
    record_action(
        db,
        user_id=user.id,
        action_type="delete",
        target_table=WANTED_LIST_TABLE,
        target_id=item.id,
        changes={"movie_id": str(item.movie_id)},
    )
    await db.commit()


# ---------------------------------------------------------------------------
# §5.2 — retailers
# ---------------------------------------------------------------------------


def _retailer_response(retailer: Retailer) -> RetailerResponse:
    return RetailerResponse(
        id=retailer.id,
        name=retailer.name,
        baseUrl=retailer.base_url,
        dealsUrl=retailer.deals_url,
        searchUrlTemplate=retailer.search_url_template,
        scraperType=cast(ScraperType, retailer.scraper_type),
        scraperConfig=retailer.scraper_config or {},
        scrapeFrequency=cast(ScrapeFrequency, retailer.scrape_frequency),
        enabled=retailer.enabled,
        currency=retailer.currency,
        region=retailer.region,
        notes=retailer.notes,
        lastScrapedAt=retailer.last_scraped_at,
        lastScrapeStatus=retailer.last_scrape_status,
        lastScrapeError=retailer.last_scrape_error,
        consecutiveFailures=retailer.consecutive_failures,
        # Selectors are Batch 19's. Saying "not configured" is the honest version of
        # §5.2's "seeded default retailers" — a seeded row is a name and a URL, not a
        # working scraper.
        isConfigured=bool(retailer.scraper_config),
        addedAt=retailer.added_at,
    )


def _apply_retailer(
    retailer: Retailer, payload: RetailerCreateRequest | RetailerUpdateRequest
) -> None:
    retailer.name = payload.name.strip()
    retailer.base_url = payload.baseUrl
    retailer.deals_url = payload.dealsUrl
    retailer.search_url_template = payload.searchUrlTemplate
    retailer.scraper_type = payload.scraperType
    retailer.scraper_config = payload.scraperConfig
    retailer.scrape_frequency = payload.scrapeFrequency
    retailer.enabled = payload.enabled
    retailer.currency = payload.currency
    retailer.region = payload.region
    retailer.notes = payload.notes


@router.get("/retailers", response_model=RetailerListResponse)
async def list_retailers(_user: CurrentUser, db: Database) -> RetailerListResponse:
    rows = (
        (
            await db.execute(
                select(Retailer)
                .where(Retailer.deleted_at.is_(None))
                .order_by(func.lower(Retailer.name))
            )
        )
        .scalars()
        .all()
    )
    items = [_retailer_response(retailer) for retailer in rows]
    return RetailerListResponse(
        items=items,
        total=len(items),
        enabledCount=sum(1 for item in items if item.enabled),
        configuredCount=sum(1 for item in items if item.isConfigured),
    )


@router.post("/retailers", response_model=RetailerResponse, status_code=status.HTTP_201_CREATED)
async def add_retailer(
    payload: RetailerCreateRequest, user: AdminUser, db: Database
) -> RetailerResponse:
    """§5.2's acceptance: "Admin adds a new retailer; it's saved and enabled"."""
    retailer = Retailer(id=uuid.uuid4(), added_by=user.id, added_at=utcnow())
    _apply_retailer(retailer, payload)
    db.add(retailer)
    record_action(
        db,
        user_id=user.id,
        action_type="create",
        target_table=RETAILERS_TABLE,
        target_id=retailer.id,
        changes={"name": retailer.name, "base_url": retailer.base_url},
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A retailer with that name already exists",
        ) from exc
    await db.refresh(retailer)
    return _retailer_response(retailer)


@router.put("/retailers/{retailer_id}", response_model=RetailerResponse)
async def update_retailer(
    retailer_id: uuid.UUID, payload: RetailerUpdateRequest, user: AdminUser, db: Database
) -> RetailerResponse:
    retailer = await db.get(Retailer, retailer_id)
    if retailer is None or retailer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    before = {"name": retailer.name, "enabled": retailer.enabled}
    _apply_retailer(retailer, payload)
    after = {"name": retailer.name, "enabled": retailer.enabled}
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table=RETAILERS_TABLE,
        target_id=retailer.id,
        changes={k: {"from": before[k], "to": after[k]} for k in before if before[k] != after[k]},
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A retailer with that name already exists",
        ) from exc
    await db.refresh(retailer)
    return _retailer_response(retailer)


@router.delete("/retailers/{retailer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_retailer(retailer_id: uuid.UUID, user: AdminUser, db: Database) -> None:
    retailer = await db.get(Retailer, retailer_id)
    if retailer is None or retailer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    retailer.deleted_at = utcnow()
    record_action(
        db,
        user_id=user.id,
        action_type="delete",
        target_table=RETAILERS_TABLE,
        target_id=retailer.id,
        changes={"name": retailer.name},
    )
    await db.commit()


@router.post("/retailers/seed", response_model=RetailerSeedResponse)
async def seed_retailers(user: AdminUser, db: Database) -> RetailerSeedResponse:
    """§5.2's "seeded default retailers", as an action rather than a migration.

    **Not seeded by migration `016`,** deliberately: a migration that inserts rows makes
    `downgrade` ambiguous (does it delete rows an admin has since edited?) and CI's
    migration job cannot prove either direction. As an idempotent endpoint it can be run,
    re-run and inspected.

    **Every seeded retailer has an empty `scraper_config`.** The CSS a real page needs is
    Batch 19's work, and inventing selectors here would be worse than none: the ledger's
    own risk note for Batch 19 says a wrong selector *"does not error — it selects the
    wrong node and persists a plausible wrong number"*. An empty config is visibly
    unconfigured.
    """
    existing_names = {
        str(name).lower()
        for name in (
            await db.execute(select(Retailer.name).where(Retailer.deleted_at.is_(None)))
        ).scalars()
    }

    created: list[str] = []
    for default in DEFAULT_RETAILERS:
        if default["name"].lower() in existing_names:
            continue
        retailer = Retailer(
            id=uuid.uuid4(),
            name=default["name"],
            base_url=default["base_url"],
            deals_url=default.get("deals_url"),
            scraper_type="generic_css",
            scraper_config={},
            added_by=user.id,
            added_at=utcnow(),
        )
        db.add(retailer)
        created.append(default["name"])

    if created:
        record_action(
            db,
            user_id=user.id,
            action_type="bulk_import",
            target_table=RETAILERS_TABLE,
            target_id=str(uuid.uuid4()),
            changes={"seeded": created},
        )
    await db.commit()
    return RetailerSeedResponse(
        created=len(created),
        existing=len(existing_names),
        names=created,
    )
