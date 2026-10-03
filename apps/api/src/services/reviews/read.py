"""Which reviews a page shows, and how — Batch V9, `DECISIONS.md` #228, #241.

A Wanted item shows one review per site, of its own format where there is one; a film's
page shows every review found for it. Only reviews with a page to open are shown: a search
that found nothing, a page without a review and another year's film are not.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.reviews import FilmReview
from src.schemas.reviews import FilmReviewResponse, ReviewScoreResponse

SITE_NAMES = {"bluray_com": "Blu-ray.com", "avforums": "AVForums"}
SITE_ORDER = ("bluray_com", "avforums")
FORMAT_ORDER: tuple[str | None, ...] = ("4k_uhd", "blu_ray", None, "dvd")
SHOWN = ("found", "scored")

#: Why an AVForums review never has scores (#241).
AVFORUMS_NOTE = "AVForums does not allow apps to read its pages, so its scores are not shown."
#: A Blu-ray.com review whose page has not been read yet.
WAITING_NOTE = "Its scores are read overnight."


def _order(row: FilmReview) -> tuple[int, int]:
    format_rank = FORMAT_ORDER.index(row.format_code) if row.format_code in FORMAT_ORDER else 9
    return SITE_ORDER.index(row.site), format_rank


async def reviews_by_movie(
    db: AsyncSession, movie_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[FilmReview]]:
    """The reviews to show for each film, Blu-ray.com's first, 4K before Blu-ray."""
    if not movie_ids:
        return {}
    rows = (
        (
            await db.execute(
                select(FilmReview).where(
                    FilmReview.movie_id.in_(movie_ids), FilmReview.status.in_(SHOWN)
                )
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[uuid.UUID, list[FilmReview]] = defaultdict(list)
    for row in sorted(rows, key=_order):
        grouped[row.movie_id].append(row)
    return grouped


def for_want(rows: list[FilmReview], format_code: str | None) -> list[FilmReview]:
    """One review per site for a Wanted item: its own format's, else the best there is."""
    chosen: list[FilmReview] = []
    for site in SITE_ORDER:
        mine = [row for row in rows if row.site == site]
        if not mine:
            continue
        same = [row for row in mine if format_code is not None and row.format_code == format_code]
        chosen.append((same or mine)[0])
    return chosen


def review_response(row: FilmReview) -> FilmReviewResponse:
    scored = row.status == "scored" and row.scores is not None
    note: str | None = None
    if row.site == "avforums":
        note = AVFORUMS_NOTE
    elif not scored:
        note = WAITING_NOTE
    return FilmReviewResponse(
        site="avforums" if row.site == "avforums" else "bluray_com",
        siteName=SITE_NAMES[row.site],
        url=row.url or "",
        formatCode=row.format_code,
        title=row.title,
        description=row.description,
        scores=[
            ReviewScoreResponse(heading=str(score["heading"]), score=float(score["score"]))
            for score in (row.scores or [])
            if scored
        ],
        overall=float(row.overall) if scored and row.overall is not None else None,
        outOf=row.out_of if scored else None,
        scoresReadAt=row.scores_read_utc if scored else None,
        note=note,
    )
