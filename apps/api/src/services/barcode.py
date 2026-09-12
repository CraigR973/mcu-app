"""Turning a scanned barcode into a film — Batch 24, Phase 3.4.

§3.4's chain, verbatim: *"UPC-to-title resolution (try cached mapping, then eBay/Amazon UPC
search, then TMDB)"*.

**Amazon is not in it, and that is not an omission.** `DECISIONS.md` #91 ruled Amazon UK
out permanently on 2026-09-09: it blocks automated access, and its Product Advertising API
is unsuitable for a private two-person app. The workable chain is **cached mapping → the
collection itself → eBay Browse → TMDB**, and `docs/phase-batches.md` records the
substitution as a known correction rather than a discovery for this batch to make.

**The collection is the second leg, and the spec did not have it.** If a disc you already
own carries this barcode, the answer is certain and free — no quota, no matching, no
edition ambiguity. It also turns a scan into duplicate detection, which is the thing
somebody standing in a shop actually wants to know.

**Nothing here adds anything.** Every path returns *candidates*, and §3.4's confirmation UI
is mandatory for the reason the ledger's risk note gives: expect a low hit rate on unknown
discs and wrong-edition matches. The one place this module writes is
:func:`remember` — after a person has confirmed.

**A barcode that fails its own check digit is refused before any of that.** A misread scan
is not a rare disc, and looking one up spends a quota call to search for a number that
does not exist. The check digit is the only signal available that separates the two, and
it is free.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.ebay.matching import (
    DISC_LEAF_CATEGORY_IDS,
    FORMAT_TOKENS,
    listing_from_summary,
    tokens,
)
from src.models.barcode import BarcodeLookup
from src.models.collection_item import CollectionItem, owned_copy
from src.models.movie import Movie

_DIGITS = re.compile(r"[^0-9]")

#: The symbologies a disc carries. EAN-13 is the European retail standard, UPC-A the North
#: American one, and EAN-8 turns up on small packaging. Anything else a scanner hands us —
#: a QR code, a Code-128 shelf label — is not a product code and is refused by length.
VALID_LENGTHS = (8, 12, 13)


@dataclass
class BarcodeCandidate:
    """One possible answer, with where it came from and how sure it is.

    ``confidence`` is deliberately coarse — 1.0 for a confirmed mapping or a disc already
    owned, lower for anything derived from a search. It orders the list; it is never a
    reason to skip the confirmation step.
    """

    title: str
    #: Which leg produced it. Typed as the same closed set the wire model uses, so a new
    #: leg has to be declared in both places rather than arriving as a free string.
    source: Literal["cache", "collection", "ebay", "tmdb", "manual"]
    confidence: float
    movie_id: uuid.UUID | None = None
    tmdb_id: int | None = None
    year: int | None = None
    poster_path: str | None = None
    #: What the source actually said, kept so a wrong match is diagnosable afterwards
    #: rather than only at the moment somebody noticed — the same reasoning as
    #: ``price_checks.title_snapshot``.
    evidence: str | None = None


@dataclass
class BarcodeResolution:
    """What a scan produced."""

    barcode: str
    candidates: list[BarcodeCandidate] = field(default_factory=list)
    #: Which leg answered. ``None`` when nothing did — §3.4's *"unknown UPCs prompt manual
    #: search"*, which is an answer rather than an error.
    source: str | None = None
    #: True when the barcode matches a disc already in the collection. The most useful
    #: single fact a scan can produce while standing in a shop.
    alreadyOwned: bool = False  # noqa: N815 - carried straight to the wire


def normalise(raw: str) -> str:
    """Strip everything that is not a digit. Scanners add spaces, hyphens and prefixes."""
    return _DIGITS.sub("", raw or "")


def check_digit_valid(barcode: str) -> bool:
    """GS1 modulo-10, which EAN-8, UPC-A and EAN-13 all use.

    Weights alternate 3 and 1 from the **right**, excluding the check digit itself; the
    check digit is what makes the weighted sum a multiple of ten. Working right-to-left
    rather than left-to-right is what makes one implementation serve all three lengths —
    doing it from the left needs a different starting weight per length, which is where
    this is usually got wrong.
    """
    if len(barcode) not in VALID_LENGTHS or not barcode.isdigit():
        return False
    digits = [int(char) for char in barcode]
    body, check = digits[:-1], digits[-1]
    total = sum(digit * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


async def from_cache(db: AsyncSession, barcode: str) -> BarcodeCandidate | None:
    row = await db.scalar(select(BarcodeLookup).where(BarcodeLookup.barcode == barcode))
    if row is None:
        return None

    # The mapping is allowed to outlive its movie (`ON DELETE SET NULL`), and a
    # soft-deleted movie does not fire that FK action at all. Never send a stale local id
    # to the add form: the retained TMDB id/title can still identify the disc.
    movie_id = row.movie_id
    if movie_id is not None:
        movie = await db.get(Movie, movie_id)
        if movie is None or movie.deleted_at is not None:
            movie_id = None
    return BarcodeCandidate(
        title=row.title,
        source="cache",
        confidence=1.0,
        movie_id=movie_id,
        tmdb_id=row.tmdb_id,
        evidence=f"confirmed {row.confirmed_at_utc:%Y-%m-%d}",
    )


async def from_collection(db: AsyncSession, barcode: str) -> BarcodeCandidate | None:
    """A disc you already own, which is both the answer and the duplicate warning."""
    row = (
        await db.execute(
            select(Movie, CollectionItem)
            .join(CollectionItem, CollectionItem.movie_id == Movie.id)
            .where(CollectionItem.barcode == barcode, owned_copy())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    movie, item = row
    return BarcodeCandidate(
        title=movie.title,
        source="collection",
        confidence=1.0,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        year=movie.year,
        poster_path=movie.poster_path,
        evidence=f"already owned on {'/'.join(item.formats) or 'an unrecorded format'}",
    )


def titles_from_ebay(payload: dict[str, object]) -> list[str]:
    """Listing titles for a barcode search, best first, discs only.

    eBay has no "look up this UPC" endpoint on the Browse API available here — searching
    `q=<barcode>` is what there is, and it works because sellers put the code in the
    title or the product aspects. So the result is **seller prose**, not a catalogue
    entry, and the category gate is doing the same job it does in
    :mod:`src.ebay.matching`: a barcode search returns the disc, and also a cable, a
    listing for "any 3 for £10", and whatever else happens to contain those digits.
    """
    summaries = payload.get("itemSummaries")
    if not isinstance(summaries, list):
        return []
    titles: list[str] = []
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        listing = listing_from_summary(summary)
        if listing is None:
            continue
        if not set(listing.leaf_category_ids) & DISC_LEAF_CATEGORY_IDS:
            continue
        titles.append(listing.title)
    return titles


def film_title_from_listing(title: str) -> str:
    """The film's name, as far as it can be recovered from a listing title.

    Everything from the first format word onwards is about the disc rather than the film,
    so the title is cut there. "Blade Runner 2049 [Blu-ray] [2017] - DVD KZVG The Cheap
    Fast Free Post" becomes "Blade Runner 2049", which is what TMDB can answer about.

    Crude on purpose: this feeds a **search**, whose results a person then confirms. A
    cleverer extraction would produce a more confident wrong answer.
    """
    words = tokens(title)
    kept: list[str] = []
    for word in words:
        if word in FORMAT_TOKENS:
            break
        kept.append(word)
    return " ".join(kept).strip()


def rank_titles(titles: list[str]) -> list[str]:
    """The distinct film titles a barcode search suggested, commonest first.

    Agreement is the only evidence available here. Six sellers describing the same disc
    the same way is a much better signal than any one of them, and it is the cheapest
    defence against the first listing happening to be a bundle.
    """
    counts: dict[str, int] = {}
    for title in titles:
        name = film_title_from_listing(title)
        if len(name) < 2:
            continue
        counts[name] = counts.get(name, 0) + 1
    return [name for name, _ in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))]


async def remember(
    db: AsyncSession,
    *,
    barcode: str,
    title: str,
    source: str,
    movie_id: uuid.UUID | None,
    tmdb_id: int | None,
    confirmed_by: uuid.UUID | None,
) -> BarcodeLookup:
    """Write a confirmed mapping, replacing any earlier one for the same code.

    Replacing rather than refusing: a barcode identifies one product, and if the earlier
    answer was a wrong-edition match — which the risk note expects — the correction has to
    be able to land. The unique constraint is what makes "one answer per code" true; this
    is how the answer changes.
    """
    existing = await db.scalar(select(BarcodeLookup).where(BarcodeLookup.barcode == barcode))
    if existing is not None:
        existing.title = title
        existing.source = source
        existing.movie_id = movie_id
        existing.tmdb_id = tmdb_id
        existing.confirmed_by = confirmed_by
        existing.confirmed_at_utc = utcnow()
        return existing

    row = BarcodeLookup(
        id=uuid.uuid4(),
        barcode=barcode,
        title=title,
        source=source,
        movie_id=movie_id,
        tmdb_id=tmdb_id,
        confirmed_by=confirmed_by,
        confirmed_at_utc=utcnow(),
    )
    db.add(row)
    return row
