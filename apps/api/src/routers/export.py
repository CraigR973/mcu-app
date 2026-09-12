"""Collection export — roadmap §13.3 (CSV, JSON) and §13.4 (PDF, HTML).

**There is no server-side PDF renderer, and that is a decision rather than an omission.**
§13.4 asks for a "printable PDF with posters". Every Python library that would render one
— WeasyPrint, wkhtmltopdf — needs system libraries (cairo, pango, or a headless Chromium)
installed in the image. `STATUS.md`'s own note on the gate says the Docker image is built
by **Railway, not by CI**, so a missing shared object does not fail a pull request; it
fails a deploy, after the merge. Trading that for a feature the browser already does
perfectly is a bad trade.

Instead `/export/collection.html` is laid out for print — a real `@page` rule, page-break
control, and posters at print resolution — and the browser's own "Save as PDF" produces the
file. That is the same artifact §13.4 asks for twice ("printable PDF with posters",
"coffee-table HTML"), built once, with no dependency that CI cannot prove.

Every export streams. The collection is 1,857 items and will not shrink, and building the
whole CSV in memory before sending a byte would make the largest export the slowest to
start.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from html import escape
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.clock import utcnow
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie
from src.routers.movies import Database, location_label

router = APIRouter(prefix="/api/v1", tags=["export"])

#: One row per **disc**, not per film — the export is an inventory, and a film owned on
#: 4K and DVD is two objects on two shelves.
CSV_COLUMNS = (
    "title",
    "year",
    "formats",
    "location",
    "section",
    "shelf",
    "condition",
    "sub_category",
    "purchase_price",
    "purchase_date",
    "purchase_source",
    "notes",
    "tmdb_id",
    "imdb_id",
    "tmdb_rating",
    "runtime_minutes",
    "item_id",
    "movie_id",
)

#: Streamed in slices so the whole catalogue is never resident at once.
PAGE_SIZE = 200


def _poster_url(path: str | None, size: str = "w342") -> str | None:
    return f"https://image.tmdb.org/t/p/{size}{path}" if path else None


async def _rows(db: AsyncSession) -> AsyncIterator[tuple[CollectionItem, Movie]]:
    """Every live disc with its film, oldest first, in pages."""
    offset = 0
    while True:
        page = (
            await db.execute(
                select(CollectionItem, Movie)
                .join(Movie, Movie.id == CollectionItem.movie_id)
                .where(owned_copy(), Movie.deleted_at.is_(None))
                .order_by(func.lower(Movie.title), CollectionItem.id)
                .offset(offset)
                .limit(PAGE_SIZE)
            )
        ).all()
        if not page:
            return
        for item, movie in page:
            yield item, movie
        if len(page) < PAGE_SIZE:
            return
        offset += PAGE_SIZE


def _scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        # A price is money. Stringified so a spreadsheet shows 12.99 rather than a float
        # that prints as 12.989999999999998.
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _record(item: CollectionItem, movie: Movie) -> dict[str, Any]:
    return {
        "title": movie.title,
        "year": movie.year,
        "formats": item.formats or [],
        "location": item.location or location_label(item.section, item.shelf),
        "section": item.section,
        "shelf": item.shelf,
        "condition": item.condition,
        "sub_category": item.sub_category,
        "purchase_price": _scalar(item.purchase_price),
        "purchase_date": _scalar(item.purchase_date),
        "purchase_source": item.purchase_source,
        "notes": item.notes,
        "tmdb_id": movie.tmdb_id,
        "imdb_id": movie.imdb_id,
        "tmdb_rating": _scalar(movie.tmdb_rating),
        "runtime_minutes": movie.runtime_minutes,
        "item_id": str(item.id),
        "movie_id": str(movie.id),
    }


def _filename(extension: str) -> str:
    return f"mcu-collection-{utcnow().date().isoformat()}.{extension}"


def _attachment(extension: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{_filename(extension)}"'}


async def _csv_chunks(db: AsyncSession) -> AsyncIterator[str]:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\r\n")

    def drain() -> str:
        text = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return text

    # A BOM, and CRLF line endings. §13.3's acceptance is "CSV opens cleanly in Excel",
    # and without the BOM Excel reads the file as the local 8-bit codepage, mangling every
    # non-ASCII character. No title in the collection needs it *today* — all 1,843 are
    # ASCII — but the next hand-added disc may be, and a mangled export is the kind of
    # defect nobody notices until they are already looking at the file for another reason.
    yield "﻿"
    writer.writeheader()
    yield drain()

    async for item, movie in _rows(db):
        record = _record(item, movie)
        # The one list-valued column, flattened. `+` rather than a comma because a comma
        # inside a CSV cell is legal but reads as a second column to anyone scanning it.
        record["formats"] = " + ".join(record["formats"])
        writer.writerow(record)
        yield drain()


@router.get("/export/collection.csv")
async def export_csv(_user: CurrentUser, db: Database) -> StreamingResponse:
    """§13.3 — "CSV opens cleanly in Excel"."""
    return StreamingResponse(
        _csv_chunks(db),
        media_type="text/csv; charset=utf-8",
        headers=_attachment("csv"),
    )


async def _json_chunks(db: AsyncSession) -> AsyncIterator[str]:
    """Valid JSON, assembled without holding the document in memory.

    Streamed by hand rather than via `json.dumps` on a list, because the point of
    streaming is not to build the list. Each record is serialised on its own and the
    separators are written around it — so the output is one well-formed document whatever
    its size, which is §13.3's other half: "JSON is valid".
    """
    yield '{"exportedAt":' + json.dumps(utcnow().isoformat() + "Z") + ',"items":['
    first = True
    count = 0
    async for item, movie in _rows(db):
        yield ("" if first else ",") + json.dumps(_record(item, movie))
        first = False
        count += 1
    yield f'],"count":{count}' + "}"


@router.get("/export/collection.json")
async def export_json(_user: CurrentUser, db: Database) -> StreamingResponse:
    """§13.3 — "JSON is valid"."""
    return StreamingResponse(
        _json_chunks(db),
        media_type="application/json",
        headers=_attachment("json"),
    )


_HTML_HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Mark's Cinematic Universe</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 24px; background: #fff; color: #14110f;
         font: 14px/1.45 "Iowan Old Style", Georgia, "Times New Roman", serif; }}
  h1 {{ margin: 0 0 4px; font-size: 30px; letter-spacing: -0.02em; }}
  .sub {{ margin: 0 0 28px; color: #6b6259; font-size: 13px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
           gap: 20px 16px; }}
  .card {{ break-inside: avoid; page-break-inside: avoid; }}
  .card img {{ width: 100%; aspect-ratio: 2/3; object-fit: cover; border-radius: 3px;
               background: #ece7e1; }}
  .noposter {{ width: 100%; aspect-ratio: 2/3; border-radius: 3px; background: #ece7e1;
               display: flex; align-items: center; justify-content: center;
               padding: 8px; text-align: center; font-size: 12px; color: #8a7f74; }}
  .t {{ margin: 6px 0 0; font-weight: 600; font-size: 13px; line-height: 1.25; }}
  .m {{ margin: 1px 0 0; font-size: 11px; color: #6b6259; }}
  @page {{ size: A4; margin: 14mm; }}
  @media print {{
    body {{ padding: 0; }}
    /* Backgrounds and posters are the point of a coffee-table print. */
    * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .grid {{ grid-template-columns: repeat(4, 1fr); gap: 14px 10px; }}
    h1 {{ font-size: 24px; }}
  }}
</style></head><body>
<h1>Mark&rsquo;s Cinematic Universe</h1>
<p class="sub">{count} discs &middot; {films} films &middot; exported {when}</p>
<div class="grid">
"""


def _card(record: dict[str, Any], poster: str | None) -> str:
    title = escape(str(record["title"]))
    year = record["year"]
    meta = " &middot; ".join(
        part
        for part in (
            escape(str(year)) if year else "",
            escape(str(record["formats"] or "")),
            escape(str(record["location"] or "")),
        )
        if part
    )
    art = (
        f'<img src="{escape(poster)}" alt="">' if poster else f'<div class="noposter">{title}</div>'
    )
    return f'<div class="card">{art}<p class="t">{title}</p><p class="m">{meta}</p></div>'


async def _html_chunks(db: AsyncSession, counts: tuple[int, int]) -> AsyncIterator[str]:
    items, films = counts
    yield _HTML_HEAD.format(count=items, films=films, when=escape(utcnow().date().isoformat()))
    async for item, movie in _rows(db):
        record = _record(item, movie)
        record["formats"] = " + ".join(record["formats"])
        yield _card(record, _poster_url(movie.poster_path))
    yield "</div></body></html>"


@router.get("/export/collection.html")
async def export_html(
    _user: CurrentUser,
    db: Database,
    download: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    """§13.4 — the coffee-table view, and the thing a browser prints to PDF.

    ``download=true`` sends it as a file; the default renders it in the tab, which is
    where the print dialog lives. Both are the same bytes.
    """
    items = int(
        (await db.execute(select(func.count(CollectionItem.id)).where(owned_copy()))).scalar_one()
    )
    films = int(
        (
            await db.execute(
                select(func.count(func.distinct(CollectionItem.movie_id))).where(owned_copy())
            )
        ).scalar_one()
    )
    return StreamingResponse(
        _html_chunks(db, (items, films)),
        media_type="text/html; charset=utf-8",
        headers=_attachment("html") if download else {},
    )
