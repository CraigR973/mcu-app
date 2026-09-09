"""Shareable gift links — roadmap §12.1, §12.2, §6.26, §3.21.

**`GET /api/v1/gift/{slug}` is the application's second unauthenticated endpoint**, after
Batch 17's `.ics` feed, and the ledger singles this batch out as needing its own security
review. What that produced:

- **128-bit slug**, its own column rather than §3.21's primary key. §6.26's worked example
  is eight hex characters — 32 bits, enumerable — and what would be enumerated is a named
  person's wish list.
- **Every reason a link does not work answers identically**: deleted, deactivated, expired
  and never-existed are all the same 404 with the same body. A visitor cannot confirm that
  a guessed slug was ever real.
- **Rate-limited.** It is the one place a stranger can cause a database write, because
  §6.26 asks for a view count.
- **`noindex, nofollow` and `no-store`.** A capability URL must not end up in a search
  index, and must not sit in a shared cache.
- **A response model that is not a superset of the admin one.** The public page carries no
  slug, no view count, no creator, no ids, and — the one that matters most — **no
  indication of what the recipient already owns**. The wanted list is the point; the
  collection is not being shared.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Path, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.auth import AdminUser
from src.clock import utcnow
from src.models.gift_link import GIFT_LINKS_TABLE, GiftLink, new_slug
from src.models.movie import Movie
from src.models.wanted import Retailer, WantedItem
from src.rate_limit import limiter
from src.routers.movies import Database
from src.schemas.gift import (
    GiftFilmResponse,
    GiftFilterConfig,
    GiftLinkCreateRequest,
    GiftLinkListResponse,
    GiftLinkResponse,
    GiftLinkUpdateRequest,
    GiftPageResponse,
    GiftRetailerLink,
)
from src.services.audit import record_action

router = APIRouter(prefix="/api/v1", tags=["gift"])

#: The one endpoint a stranger can reach, and the one that writes a counter. Generous for
#: a family sharing a link around, far below what enumeration would need.
GIFT_LIMIT = "60/hour"


def _path_for(slug: str) -> str:
    return f"/gift/{slug}"


def _admin_response(link: GiftLink, now: datetime) -> GiftLinkResponse:
    return GiftLinkResponse(
        id=link.id,
        slug=link.slug,
        path=_path_for(link.slug),
        title=link.title,
        filterConfig=GiftFilterConfig.model_validate(link.filter_config or {}),
        expiresAt=link.expires_at,
        viewCount=link.view_count,
        lastViewedAt=link.last_viewed_at,
        isActive=link.is_active,
        isUsable=link.is_usable(now),
        createdAt=link.created_at,
    )


# ---------------------------------------------------------------------------
# §12.1 — the admin side
# ---------------------------------------------------------------------------


@router.get("/gift-links", response_model=GiftLinkListResponse)
async def list_gift_links(_user: AdminUser, db: Database) -> GiftLinkListResponse:
    now = utcnow()
    rows = (
        (
            await db.execute(
                select(GiftLink)
                .where(GiftLink.deleted_at.is_(None))
                .order_by(GiftLink.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    items = [_admin_response(link, now) for link in rows]
    return GiftLinkListResponse(items=items, total=len(items))


@router.post("/gift-links", response_model=GiftLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_gift_link(
    payload: GiftLinkCreateRequest, user: AdminUser, db: Database
) -> GiftLinkResponse:
    """§12.1's acceptance: "Admin creates a link; visiting the slug renders public list"."""
    link = GiftLink(
        id=uuid.uuid4(),
        slug=new_slug(),
        created_by=user.id,
        title=payload.title.strip(),
        filter_config=payload.filterConfig.stored(),
        expires_at=payload.expiresAt,
        is_active=payload.isActive,
        created_at=utcnow(),
    )
    db.add(link)
    record_action(
        db,
        user_id=user.id,
        action_type="create",
        target_table=GIFT_LINKS_TABLE,
        target_id=link.id,
        # The slug is **not** recorded in the audit log. It is a credential, and an audit
        # log is read far more widely and kept far longer than the link it would leak.
        changes={"title": link.title, "expires_at": str(link.expires_at)},
    )
    try:
        await db.commit()
    except IntegrityError as exc:  # pragma: no cover - 128 bits does not collide
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Could not create a link"
        ) from exc
    await db.refresh(link)
    return _admin_response(link, utcnow())


@router.put("/gift-links/{link_id}", response_model=GiftLinkResponse)
async def update_gift_link(
    link_id: uuid.UUID, payload: GiftLinkUpdateRequest, user: AdminUser, db: Database
) -> GiftLinkResponse:
    """Update filters, expiry or active status — §6.5's own description.

    **The slug is never changed here.** Rotating it would silently break a link already
    shared with family, which is the opposite of what "deactivate without deleting" is for.
    Revoking is `isActive: false` or a delete, both of which say so.
    """
    link = await db.get(GiftLink, link_id)
    if link is None or link.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    before = {"title": link.title, "is_active": link.is_active}
    link.title = payload.title.strip()
    link.filter_config = payload.filterConfig.stored()
    link.expires_at = payload.expiresAt
    link.is_active = payload.isActive
    after = {"title": link.title, "is_active": link.is_active}
    record_action(
        db,
        user_id=user.id,
        action_type="update",
        target_table=GIFT_LINKS_TABLE,
        target_id=link.id,
        changes={k: {"from": before[k], "to": after[k]} for k in before if before[k] != after[k]},
    )
    await db.commit()
    await db.refresh(link)
    return _admin_response(link, utcnow())


@router.delete("/gift-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_gift_link(link_id: uuid.UUID, user: AdminUser, db: Database) -> None:
    """Revoke — §6.5's verb. Soft, so §13.5's Trash can restore it."""
    link = await db.get(GiftLink, link_id)
    if link is None or link.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    link.deleted_at = utcnow()
    record_action(
        db,
        user_id=user.id,
        action_type="delete",
        target_table=GIFT_LINKS_TABLE,
        target_id=link.id,
        changes={"title": link.title},
    )
    await db.commit()


# ---------------------------------------------------------------------------
# §12.2 — the public page
# ---------------------------------------------------------------------------


async def _searchable_retailers(db: AsyncSession) -> list[tuple[str, str]]:
    """The shops that can be linked to, fetched **once** per request.

    Previously this ran inside the per-film loop, re-reading the whole `retailers` table
    for every film on the page — 50 identical queries for a 50-film list, on the
    unauthenticated endpoint. Found by this batch's security review. The rows do not vary
    by film; only the query string does.
    """
    rows = (
        (
            await db.execute(
                select(Retailer).where(
                    Retailer.deleted_at.is_(None),
                    Retailer.enabled.is_(True),
                    Retailer.search_url_template.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        (retailer.name, str(retailer.search_url_template))
        for retailer in rows
        if retailer.search_url_template and "{query}" in retailer.search_url_template
    ]


def _retailer_links(retailers: list[tuple[str, str]], title: str) -> list[GiftRetailerLink]:
    """Where a family member could buy this — §6.26's "direct retailer links".

    Built from `retailers.search_url_template`, whose scheme is http/https by CHECK *and*
    by the API validator. This is admin-supplied text rendered onto a **public** page, so
    the constraint is doing real work rather than being belt and braces. The title is
    percent-encoded, so a film called "Fast & Furious" cannot break out of the query string.
    """
    return [
        GiftRetailerLink(name=name, url=template.replace("{query}", quote(title)))
        for name, template in retailers
    ]


@router.get("/gift/{slug}", response_model=GiftPageResponse)
@limiter.limit(GIFT_LIMIT)
async def public_gift_page(
    request: Request,
    response: Response,
    slug: Annotated[str, Path(min_length=16, max_length=64)],
    db: Database,
) -> GiftPageResponse:
    """§12.2 — "Non-logged-in visitor can browse Dad's wanted list".

    ``request`` is required by slowapi's decorator, which reads the client address off it.

    **A missing, deactivated, expired or deleted link all answer the same 404.** Nobody on
    this endpoint can be told apart from someone guessing, so none of them learns whether a
    slug was ever real.
    """
    del request
    now = utcnow()
    link = (await db.execute(select(GiftLink).where(GiftLink.slug == slug))).scalar_one_or_none()
    if link is None or not link.is_usable(now):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    filters = GiftFilterConfig.model_validate(link.filter_config or {})

    predicates: list[ColumnElement[bool]] = [
        WantedItem.deleted_at.is_(None),
        WantedItem.is_active.is_(True),
        Movie.deleted_at.is_(None),
    ]
    if filters.maxPrice:
        # Films with no threshold recorded are kept: "under £30" is about what the buyer
        # wants to spend, and an unpriced entry has not claimed to cost more.
        predicates.append(
            (WantedItem.max_price.is_(None)) | (WantedItem.max_price <= Decimal(filters.maxPrice))
        )
    if filters.formats:
        predicates.append(WantedItem.preferred_format.in_(list(filters.formats)))

    rows = (
        await db.execute(
            select(WantedItem, Movie)
            .join(Movie, Movie.id == WantedItem.movie_id)
            .where(*predicates)
            .order_by(func.lower(Movie.title))
        )
    ).all()

    # Once, not once per film.
    retailers = await _searchable_retailers(db)

    films: list[GiftFilmResponse] = []
    for item, movie in rows:
        films.append(
            GiftFilmResponse(
                title=movie.title,
                year=movie.year,
                posterPath=movie.poster_path,
                preferredFormat=item.preferred_format,
                maxPrice=str(item.max_price) if item.max_price is not None else None,
                currency=item.currency,
                retailerLinks=_retailer_links(retailers, movie.title),
            )
        )

    # §6.26 step 5: "track view count". This is the one place an unauthenticated request
    # causes a write, which is why the endpoint is rate-limited.
    #
    # An atomic `view_count = view_count + 1` in SQL, not `link.view_count += 1` in Python:
    # the latter is a read-modify-write, so two family members opening the link at the same
    # moment would record one view between them.
    await db.execute(
        update(GiftLink)
        .where(GiftLink.id == link.id)
        .values(view_count=GiftLink.view_count + 1, last_viewed_at=now)
    )
    await db.commit()

    # A capability URL must not end up in a search index, and must not sit in a shared
    # cache where the next person on that proxy could read it.
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "private, no-store"

    return GiftPageResponse(title=link.title, films=films, total=len(films), filterConfig=filters)
