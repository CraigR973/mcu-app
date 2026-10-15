"""Identification in doubt — Batch X9 (CT46-01, CT46-03).

**An identified film can be the wrong one.** 30 copies were confidently the wrong film on 12
Oct, matched by the 8 Sep import's engine and the diary import, and nothing marked them. A
doubt is a proposal about one such film, with its evidence: it waits on Identify films, and
the film page says "identification in doubt" while it does.

Three things raise one:

- **The re-check** of the films the old paths decided (``scripts/recheck_identifications``),
  at Craig's word, when T9's identifier disagrees with the film the row holds.
- **The spec job**, when the disc page it chose by the film's own title is for another year.
  Until X9 it parked the disc with "pick the right page", when 8 of the 36 such pages were
  right and the film was wrong.
- **The review job**, the same way, for a review page.

Craig settles each one: the film is right (**keep**: a page that disagreed goes back to
"pick the right page"), it is another film (**identify it again**, which settles every open
doubt about it and is undone from the recent list, opening them again), or the copy is
another film (**move it**, ``services/identify/move_copy``). A doubt Craig kept is not raised
again by the same source while the film stays as he left it.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import CollectionItem, owned_copy
from src.models.identify import IdentifyDoubt, MovieTitleAlias
from src.models.movie import Movie
from src.models.reviews import FilmReview
from src.models.specs_backfill import SpecCandidate, SpecLookup
from src.models.watch_log import WatchLog
from src.services.audit import record_action
from src.services.identification import MOVIES_TABLE, Identified, identify_film
from src.services.identify.plan import FORMAT_NAMES
from src.services.identify.titles import compare
from src.services.specs.candidates import parse_release_title
from src.tmdb.client import TMDBClient

#: An open doubt older than this is counted by the daily check, as a waiting proposal is.
DOUBT_AGE = timedelta(days=14)

#: How the spec job's note reads while the film is in doubt, and once Craig keeps it.
SPECS_IN_DOUBT = "The film may be the wrong one: it waits on Identify films."
SPECS_KEPT = "Pick the right page."


class DoubtError(ValueError):
    """The doubt cannot take that decision."""


async def film_names(db: AsyncSession, movie: Movie) -> list[str]:
    """Every name the film answers to: its title, its original title, and the spreadsheet
    titles identification replaced."""
    aliases = (
        await db.scalars(select(MovieTitleAlias.title).where(MovieTitleAlias.movie_id == movie.id))
    ).all()
    names = [movie.title, movie.original_title or "", *aliases]
    return [name for name in dict.fromkeys(names) if name and name.strip()]


def names_the_film(page_name: str, names: Iterable[str]) -> bool:
    """The page's film is one of the film's names, by T9's title rule."""
    return bool(page_name.strip()) and any(compare(name, page_name).same_title for name in names)


async def raise_doubt(
    db: AsyncSession,
    movie: Movie,
    *,
    source: str,
    note: str,
    evidence: Sequence[str] = (),
    collection_item_id: uuid.UUID | None = None,
    candidates: Sequence[dict[str, Any]] = (),
    proposed_tmdb_id: int | None = None,
    search_hint: str | None = None,
    page_url: str | None = None,
) -> IdentifyDoubt | None:
    """Record that ``movie`` may be the wrong film. Does not commit.

    Returns ``None`` for a film not identified as a film, and for a doubt Craig already kept
    about the film as it stands. An open doubt from the same source about the same film or
    copy is brought up to date rather than doubled.
    """
    if movie.tmdb_id is None or movie.deleted_at is not None:
        return None
    same = (
        IdentifyDoubt.movie_id == movie.id,
        IdentifyDoubt.source == source,
        (
            IdentifyDoubt.collection_item_id.is_(None)
            if collection_item_id is None
            else IdentifyDoubt.collection_item_id == collection_item_id
        ),
    )
    kept = await db.scalar(
        select(IdentifyDoubt.id).where(
            *same, IdentifyDoubt.status == "kept", IdentifyDoubt.identified_as == movie.tmdb_id
        )
    )
    if kept is not None:
        return None
    doubt = await db.scalar(select(IdentifyDoubt).where(*same, IdentifyDoubt.status == "open"))
    if doubt is None:
        doubt = IdentifyDoubt(
            id=uuid.uuid4(),
            movie_id=movie.id,
            collection_item_id=collection_item_id,
            source=source,
            status="open",
        )
        db.add(doubt)
    doubt.identified_as = movie.tmdb_id
    doubt.note = note
    doubt.evidence = list(evidence)
    doubt.candidates = list(candidates)
    doubt.proposed_tmdb_id = proposed_tmdb_id
    doubt.search_hint = search_hint
    doubt.page_url = page_url
    await db.flush()
    return doubt


async def doubt_from_page(
    db: AsyncSession,
    movie: Movie,
    *,
    source: str,
    page_name: str | None,
    page_year: int,
    page_url: str | None,
    collection_item_id: uuid.UUID | None = None,
) -> IdentifyDoubt | None:
    """A disc page or review for the film's own title in another year: the page may be
    right and the film wrong (CT46-03). Raises a doubt when the page names the film."""
    if movie.tmdb_id is None or movie.year is None or not page_name:
        return None
    if not names_the_film(page_name, await film_names(db, movie)):
        return None
    what = "disc page" if source == "specs" else "review"
    note = (
        f"Blu-ray.com's {what} for “{page_name}” is a {page_year} film, and this film is "
        f"identified as {movie.year}. The copy may be the {page_year} film."
    )
    return await raise_doubt(
        db,
        movie,
        source=source,
        note=note,
        evidence=[note],
        collection_item_id=collection_item_id,
        search_hint=f"{page_name} {page_year}",
        page_url=page_url,
    )


async def spec_page_name(db: AsyncSession, lookup_id: uuid.UUID, url: str) -> str | None:
    """The film a chosen disc page names, from the search result it was chosen from."""
    titles = (
        await db.scalars(
            select(SpecCandidate.title).where(
                SpecCandidate.lookup_id == lookup_id, SpecCandidate.url == url
            )
        )
    ).all()
    return parse_release_title(titles[0]).name if titles else None


async def review_page_name(db: AsyncSession, row: FilmReview) -> str | None:
    """The film a review page names: Brave's title for it, or, for a page reached from a
    disc page, the search result that disc page was chosen from."""
    if row.title:
        return parse_release_title(row.title).name or None
    for url in (row.found_url, row.url):
        if not url:
            continue
        title = await db.scalar(
            select(SpecCandidate.title).where(SpecCandidate.url == url).limit(1)
        )
        if title:
            return parse_release_title(title).name or None
    return None


# ---------------------------------------------------------------------------
# The queue
# ---------------------------------------------------------------------------


@dataclass
class DoubtEntry:
    doubt: IdentifyDoubt
    movie: Movie
    discs: list[str]
    copies: int
    watches: int


def _disc_label(item: CollectionItem) -> str:
    best = next((code for code in FORMAT_NAMES if code in (item.formats or [])), None)
    parts = [FORMAT_NAMES.get(best or "", best or "No format")]
    parts += [part for part in (item.sub_category, item.location) if part]
    return " · ".join(parts)


def _open_on_live_film() -> tuple[Any, ...]:
    return (
        IdentifyDoubt.status == "open",
        Movie.deleted_at.is_(None),
        Movie.tmdb_id.is_not(None),
    )


async def open_doubts(db: AsyncSession, *, limit: int) -> tuple[list[DoubtEntry], int]:
    """Open doubts, oldest first, each with the copy it names (or the film's copies)."""
    base = (
        select(IdentifyDoubt, Movie)
        .join(Movie, Movie.id == IdentifyDoubt.movie_id)
        .where(*_open_on_live_film())
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(base.order_by(IdentifyDoubt.created_utc, IdentifyDoubt.id).limit(limit))
    ).all()
    entries: list[DoubtEntry] = []
    for doubt, movie in rows:
        items = list(
            (
                await db.scalars(
                    select(CollectionItem)
                    .where(CollectionItem.movie_id == movie.id, owned_copy())
                    .order_by(CollectionItem.id)
                )
            ).all()
        )
        named = [item for item in items if item.id == doubt.collection_item_id]
        watches = await db.scalar(
            select(func.count(WatchLog.id)).where(WatchLog.movie_id == movie.id)
        )
        entries.append(
            DoubtEntry(
                doubt=doubt,
                movie=movie,
                discs=[_disc_label(item) for item in (named or items)],
                copies=len(items),
                watches=int(watches or 0),
            )
        )
    return entries, int(total or 0)


async def count_open(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count(IdentifyDoubt.id))
            .join(Movie, Movie.id == IdentifyDoubt.movie_id)
            .where(*_open_on_live_film())
        )
        or 0
    )


async def count_old(db: AsyncSession, now: datetime) -> int:
    """Open doubts older than a fortnight, for the daily check."""
    return int(
        await db.scalar(
            select(func.count(IdentifyDoubt.id))
            .join(Movie, Movie.id == IdentifyDoubt.movie_id)
            .where(*_open_on_live_film(), IdentifyDoubt.created_utc < now - DOUBT_AGE)
        )
        or 0
    )


async def doubt_for_film(db: AsyncSession, movie_id: uuid.UUID) -> IdentifyDoubt | None:
    """The film's oldest open doubt, for the film page."""
    found = await db.scalars(
        select(IdentifyDoubt)
        .where(IdentifyDoubt.movie_id == movie_id, IdentifyDoubt.status == "open")
        .order_by(IdentifyDoubt.created_utc, IdentifyDoubt.id)
        .limit(1)
    )
    return found.first()


async def doubted_films(db: AsyncSession, movie_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """Which of these films have an open doubt."""
    ids = list(movie_ids)
    if not ids:
        return set()
    found = await db.scalars(
        select(IdentifyDoubt.movie_id).where(
            IdentifyDoubt.movie_id.in_(ids), IdentifyDoubt.status == "open"
        )
    )
    return set(found.all())


async def _open_doubt(db: AsyncSession, doubt_id: uuid.UUID) -> tuple[IdentifyDoubt, Movie]:
    doubt = await db.get(IdentifyDoubt, doubt_id)
    movie = await db.get(Movie, doubt.movie_id) if doubt is not None else None
    if doubt is None or movie is None or movie.deleted_at is not None:
        raise LookupError("No such doubt.")
    if doubt.status != "open":
        raise DoubtError("This doubt has already been settled.")
    return doubt, movie


async def _spec_lookup_waiting(db: AsyncSession, doubt: IdentifyDoubt) -> SpecLookup | None:
    if doubt.source != "specs" or doubt.collection_item_id is None:
        return None
    lookup = await db.scalar(
        select(SpecLookup).where(SpecLookup.collection_item_id == doubt.collection_item_id)
    )
    if lookup is None or lookup.status != "needs_you":
        return None
    return lookup


async def keep(db: AsyncSession, doubt_id: uuid.UUID, *, by: uuid.UUID) -> IdentifyDoubt:
    """The film is right. A disc page that disagreed is the wrong page after all."""
    doubt, movie = await _open_doubt(db, doubt_id)
    now = utcnow()
    audit = record_action(
        db,
        user_id=by,
        action_type="update",
        target_table=MOVIES_TABLE,
        target_id=movie.id,
        changes={
            "kind": "doubt_kept",
            "doubt": str(doubt.id),
            "source": doubt.source,
            "tmdbId": movie.tmdb_id,
            "note": doubt.note,
        },
    )
    await db.flush()
    doubt.status = "kept"
    doubt.decided_by = by
    doubt.decided_utc = now
    doubt.decided_action_id = audit.id
    lookup = await _spec_lookup_waiting(db, doubt)
    if lookup is not None and lookup.note and SPECS_IN_DOUBT in lookup.note:
        lookup.note = lookup.note.replace(SPECS_IN_DOUBT, SPECS_KEPT)
    await db.commit()
    return doubt


async def correct(
    db: AsyncSession,
    doubt_id: uuid.UUID,
    tmdb_id: int,
    tmdb: TMDBClient,
    *,
    by: uuid.UUID,
    merge: bool,
    searched: bool,
) -> Identified:
    """The film is another one: identify it again, settling every open doubt about it.

    A disc page that disagreed is chosen again, so the next spec run reads it against the
    film's new year.
    """
    doubt, movie = await _open_doubt(db, doubt_id)
    if movie.tmdb_id == tmdb_id:
        raise DoubtError("That is the film it is already identified as. Keep it instead.")
    record = await tmdb.get_movie_full(tmdb_id)
    identified = await identify_film(
        db,
        movie,
        record,
        by=by,
        how="searched" if searched else "picked",
        evidence=["Chosen by Craig.", doubt.note],
        allow_merge=merge,
    )
    await reaccept_disagreeing_page(db, doubt, by=by)
    await db.commit()
    return identified


async def reaccept_disagreeing_page(
    db: AsyncSession, doubt: IdentifyDoubt, *, by: uuid.UUID | None
) -> None:
    """Choose again the disc page that raised a doubt, once the copy is another film, so the
    next spec run reads it against that film's year. Does not commit."""
    lookup = await _spec_lookup_waiting(db, doubt)
    if lookup is None or not doubt.page_url:
        return
    lookup.status = "accepted"
    lookup.accepted_url = doubt.page_url
    lookup.how = "auto"
    lookup.note = None
    lookup.decided_by = by
    lookup.decided_utc = utcnow()
