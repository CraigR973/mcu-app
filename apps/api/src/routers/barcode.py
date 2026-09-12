"""Scanning a disc into the collection — Batch 24, Phase 3.4.

Two endpoints, and the split between them is §3.4's *"confirmation UI before adding"*
made structural: :func:`lookup` only ever **suggests**, and :func:`confirm` is the
separate, deliberate act that writes anything down. There is no path from a scan to a
catalogued disc that does not pass through a person.

That is not caution for its own sake. The ledger's risk note for this batch says to expect
*"a low hit rate on unknown discs and wrong-edition matches"*, and the eBay leg returns
seller prose rather than catalogue entries — "Blade Runner 2049 [Blu-ray] [2017] - DVD
KZVG The Cheap Fast Free Post" is a typical input. An endpoint that resolved that to a
film and added it would be wrong often enough to poison the catalogue, and confidently
enough that nobody would notice for months.
"""

from __future__ import annotations

import uuid

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from src.auth import AdminUser
from src.ebay import EbayClient, EbayError, EbayNotConfigured
from src.models.movie import Movie
from src.rate_limit import limiter
from src.routers.movies import Database, TmdbClient
from src.schemas.barcode import (
    BarcodeCandidateResponse,
    BarcodeConfirmRequest,
    BarcodeLookupRequest,
    BarcodeLookupResponse,
)
from src.services.barcode import (
    BarcodeCandidate,
    check_digit_valid,
    from_cache,
    from_collection,
    normalise,
    rank_titles,
    remember,
    titles_from_ebay,
)

router = APIRouter(prefix="/api/v1", tags=["barcode"])

logger = structlog.get_logger()

#: How many TMDB search hits to offer per suggested title. Three is enough to cover a
#: remake and a sequel sharing a name, and few enough that the confirmation step is still
#: a glance rather than a reading task.
TMDB_CANDIDATES = 3

#: How many distinct titles from the eBay leg to take through to TMDB. Each costs a TMDB
#: search, and beyond the second the agreement signal has usually collapsed to one seller
#: each — which is noise rather than a candidate.
EBAY_TITLES = 2

#: Each uncached lookup can spend one of eBay Browse's 5,000 daily calls. This is an
#: ordinary in-process spend limit, not an authentication control; a restart resetting it
#: is harmless, while one stuck or scripted client draining the shared quota is not.
BARCODE_LOOKUP_LIMIT = "60/hour"


def _to_response(candidate: BarcodeCandidate) -> BarcodeCandidateResponse:
    return BarcodeCandidateResponse(
        title=candidate.title,
        source=candidate.source,
        confidence=round(candidate.confidence, 2),
        movieId=candidate.movie_id,
        tmdbId=candidate.tmdb_id,
        year=candidate.year,
        posterPath=candidate.poster_path,
        evidence=candidate.evidence,
    )


@router.post("/barcode/lookup", response_model=BarcodeLookupResponse)
@limiter.limit(BARCODE_LOOKUP_LIMIT)
async def lookup(
    request: Request,
    payload: BarcodeLookupRequest,
    _user: AdminUser,
    db: Database,
    tmdb: TmdbClient,
) -> BarcodeLookupResponse:
    """§3.4's chain: cached mapping → the collection → eBay Browse → TMDB.

    **Amazon is not the third leg, and that is a correction rather than an omission.**
    `DECISIONS.md` #91 ruled it out permanently in September 2026 — it blocks automated
    access and its Product Advertising API is unsuitable here. `docs/phase-batches.md`
    records the substitution.

    **Each leg stops the chain when it answers**, because the legs are in order of
    certainty and cost. A confirmed mapping and a disc already owned are both free and
    both certain; eBay costs a unit of a 5,000-a-day quota; TMDB costs a call and can only
    be asked once something has produced a title.

    **An empty result is an answer.** §3.4's second half is *"unknown UPCs prompt manual
    search"*, so nothing matching returns 200 with no candidates — never a 404, which the
    client would have to special-case into the same screen anyway.
    """
    del request  # Required by slowapi, which reads the client address from it.
    barcode = normalise(payload.barcode)
    if not check_digit_valid(barcode):
        # A misread scan, not a rare disc. Looking it up would spend a quota call
        # searching for a number that does not exist, and the check digit is the only
        # free signal that separates the two.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That does not look like a product barcode — try scanning again.",
        )

    cached = await from_cache(db, barcode)
    if cached is not None:
        # The cache answers what the product is; the collection still answers whether
        # this particular code is already on a shelf. Once a scanned add persists its
        # barcode, a second scan must not lose the duplicate warning merely because the
        # cache is earlier in the resolution chain.
        owned = await from_collection(db, barcode)
        return BarcodeLookupResponse(
            barcode=barcode,
            source="cache",
            alreadyOwned=owned is not None,
            candidates=[_to_response(cached)],
        )

    owned = await from_collection(db, barcode)
    if owned is not None:
        return BarcodeLookupResponse(
            barcode=barcode,
            source="collection",
            alreadyOwned=True,
            candidates=[_to_response(owned)],
        )

    titles = await _ebay_titles(barcode)
    candidates: list[BarcodeCandidate] = []
    for index, name in enumerate(titles[:EBAY_TITLES]):
        candidates.extend(await _tmdb_candidates(tmdb, name, penalty=index))

    # A film already in the catalogue is a better answer than the same film as a TMDB
    # search hit — it can be opened, and it carries whatever has already been recorded
    # about it. Same TMDB id, so this is a lookup rather than a guess.
    await _attach_local_movies(db, candidates)

    candidates.sort(key=lambda item: -item.confidence)
    logger.info(
        "barcode_lookup",
        barcode=barcode,
        ebay_titles=len(titles),
        candidates=len(candidates),
    )
    return BarcodeLookupResponse(
        barcode=barcode,
        source="ebay" if candidates else None,
        alreadyOwned=False,
        candidates=[_to_response(candidate) for candidate in candidates],
    )


async def _ebay_titles(barcode: str) -> list[str]:
    """Disc listings mentioning this barcode, as distinct film titles, commonest first.

    **An eBay outage is not a lookup failure.** The chain's later legs can still run, and
    the manual-search fallback is always there, so this returns an empty list rather than
    propagating — the scan still reaches a screen the person can act on.
    """
    try:
        async with EbayClient() as client:
            payload = await client.search(barcode, limit=50)
    except EbayNotConfigured:
        logger.info("barcode_lookup_no_ebay_keyset")
        return []
    except EbayError as exc:
        logger.warning("barcode_lookup_ebay_failed", error=str(exc))
        return []
    return rank_titles(titles_from_ebay(payload))


async def _tmdb_candidates(tmdb: TmdbClient, title: str, *, penalty: int) -> list[BarcodeCandidate]:
    """TMDB search hits for one suggested title.

    ``penalty`` demotes titles that fewer sellers agreed on, so the ordering carries the
    agreement signal through rather than discarding it at the TMDB boundary.
    """
    try:
        results = await tmdb.search_movie(title)
    except httpx.HTTPError as exc:
        logger.warning("barcode_lookup_tmdb_failed", title=title, error=str(exc))
        return []

    candidates: list[BarcodeCandidate] = []
    for rank, result in enumerate(results.results[:TMDB_CANDIDATES]):
        year = int(result.release_date[:4]) if result.release_date else None
        candidates.append(
            BarcodeCandidate(
                title=result.title,
                source="ebay",
                # Coarse on purpose — it orders the list and is never a reason to skip
                # confirmation. First title, first hit: 0.7. Everything else below it.
                confidence=max(0.2, 0.7 - 0.15 * penalty - 0.1 * rank),
                tmdb_id=result.id,
                year=year,
                poster_path=result.poster_path,
                evidence=f"eBay listings for this barcode read as {title!r}",
            )
        )
    return candidates


async def _attach_local_movies(db: Database, candidates: list[BarcodeCandidate]) -> None:
    tmdb_ids = [c.tmdb_id for c in candidates if c.tmdb_id is not None]
    if not tmdb_ids:
        return
    rows = (
        (
            await db.execute(
                select(Movie).where(Movie.tmdb_id.in_(tmdb_ids), Movie.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    by_tmdb = {movie.tmdb_id: movie for movie in rows}
    for candidate in candidates:
        movie = by_tmdb.get(candidate.tmdb_id)
        if movie is not None:
            candidate.movie_id = movie.id
            candidate.confidence = min(1.0, candidate.confidence + 0.1)


@router.post("/barcode/confirm", response_model=BarcodeLookupResponse)
async def confirm(
    payload: BarcodeConfirmRequest,
    user: AdminUser,
    db: Database,
) -> BarcodeLookupResponse:
    """Record what a barcode turned out to be — §3.4's confirmation, persisted.

    **This adds no disc.** It writes the mapping so the *next* scan of the same code is
    instant and certain; adding the disc is the existing `POST /collection`, which the
    client calls with the confirmed film. Keeping them apart means a confirmation that is
    right about the film but wrong about the shelf does not have to be undone twice.
    """
    barcode = normalise(payload.barcode)
    if not check_digit_valid(barcode):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That does not look like a product barcode.",
        )

    movie_id: uuid.UUID | None = payload.movieId
    title = payload.title.strip()
    tmdb_id = payload.tmdbId
    if movie_id is not None:
        movie = await db.get(Movie, movie_id)
        if movie is None or movie.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
        # A local id is authoritative. Trusting the caller's title/TMDB id independently
        # could cache a plausible but internally contradictory answer — exactly the
        # wrong-data-that-looks-right failure this batch is built to contain.
        title = movie.title
        tmdb_id = movie.tmdb_id

    row = await remember(
        db,
        barcode=barcode,
        title=title,
        source=payload.source,
        movie_id=movie_id,
        tmdb_id=tmdb_id,
        confirmed_by=user.id,
    )
    await db.commit()
    logger.info("barcode_confirmed", barcode=barcode, source=payload.source)

    return BarcodeLookupResponse(
        barcode=barcode,
        source="cache",
        alreadyOwned=False,
        candidates=[
            BarcodeCandidateResponse(
                title=row.title,
                source="cache",
                confidence=1.0,
                movieId=row.movie_id,
                tmdbId=row.tmdb_id,
                year=None,
                posterPath=None,
                evidence="confirmed just now",
            )
        ],
    )
