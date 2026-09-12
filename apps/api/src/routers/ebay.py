"""eBay marketplace account deletion/closure notifications — Batch 28 prerequisite.

**This endpoint exists because eBay will not activate a production keyset without it.**
Before a developer's first production call, they must either subscribe to these
notifications or claim the "not persisting eBay data" exemption. We subscribe: Batch 28
persists eBay-derived listing data in ``price_checks`` (``title_snapshot``, ``url``,
``price``), and eBay attaches account suspension to claiming the exemption wrongly. The
exemption is aimed at user PII rather than listing data, but that is a judgement call and
this is not a judgement worth making with account disablement as the downside.

**This is the app's third unauthenticated public surface**, after Batch 17's ``.ics`` feed
and Batch 27's gift links. Three properties make that safe here, and each is deliberate:

1. **It reads nothing and writes nothing.** The GET hashes three values it was already
   given; the POST is a no-op. There is no database session in this module at all.
2. **It is not rate limited.** Every other public route carries ``@limiter.limit``. This
   one must not: eBay polls the endpoint and emails the owner when it stops answering, so
   a 429 reads to eBay as an outage. There is nothing here worth protecting from volume —
   see (1).
3. **It leaks nothing on failure.** An unconfigured deployment answers 503 rather than
   hashing an empty token into a plausible-looking but wrong digest.

**The endpoint URL is configuration, never derived from the request.** eBay hashes the URL
*it* has on file, so ours must match byte for byte — scheme, host, path, trailing slash and
all. Behind Railway's proxy the app sees a different host and scheme than the caller used,
so reconstructing it from ``request.url`` would produce a digest that is wrong in a way
nothing here could detect: eBay simply reports validation failed.

----

**Batch 28 added the rest of the integration below it**, and the contrast with the
notification endpoint above is the thing to notice: everything from here down is
``AdminUser``-authed and rate limited, because it spends a finite daily quota on eBay's
production keyset. The account-deletion endpoint must stay unauthenticated and *un*-limited
for the reasons above; these must not.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from ..auth import AdminUser
from ..config import settings
from ..ebay import (
    EbayClient,
    EbayError,
    EbayNotConfigured,
    listing_from_summary,
    match,
    prelist_url,
    suggested_price,
    suggested_title,
    summarise,
)
from ..ebay.pricing import PriceEstimate, PriceSegment
from ..schemas.ebay import (
    ListingUrlRequest,
    ListingUrlResponse,
    PriceEstimateRequest,
    PriceEstimateResponse,
    PriceSegmentResponse,
)
from ..services.scraping.extract import FORMAT_SEARCH_TERMS

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["ebay"])


class ChallengeResponse(BaseModel):
    """eBay's expected challenge reply. camelCase written directly — `DECISIONS.md` #6."""

    challengeResponse: str  # noqa: N815 - eBay's field name, not ours to style


def challenge_digest(challenge_code: str, verification_token: str, endpoint: str) -> str:
    """SHA-256 of ``challenge_code + verification_token + endpoint``, hex encoded.

    **The order is eBay's and is not arbitrary.** Any other permutation produces a
    valid-looking 64-character hex string that eBay rejects, which is the failure this
    function exists to make testable in isolation.
    """
    digest = hashlib.sha256()
    digest.update(challenge_code.encode("utf-8"))
    digest.update(verification_token.encode("utf-8"))
    digest.update(endpoint.encode("utf-8"))
    return digest.hexdigest()


@router.get(
    "/ebay/account-deletion",
    response_model=ChallengeResponse,
    summary="eBay endpoint validation challenge",
)
async def verify_endpoint(
    challenge_code: str = Query(
        ...,
        alias="challenge_code",
        description="Supplied by eBay when it validates or re-validates this endpoint.",
    ),
) -> ChallengeResponse | Response:
    """Answer eBay's validation challenge.

    eBay sends this GET immediately when the endpoint is saved, and again periodically to
    confirm the endpoint is still alive.
    """
    token = settings.ebay_verification_token
    endpoint = settings.ebay_account_deletion_endpoint

    if not token or not endpoint:
        # Answering with a hash over an empty token would be indistinguishable from a
        # correct answer at a glance, and would fail validation with no explanation.
        logger.error(
            "ebay_account_deletion_unconfigured",
            has_token=bool(token),
            has_endpoint=bool(endpoint),
        )
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    logger.info("ebay_account_deletion_challenge")
    return ChallengeResponse(challengeResponse=challenge_digest(challenge_code, token, endpoint))


@router.post(
    "/ebay/account-deletion",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="eBay account deletion notification",
)
async def receive_notification() -> Response:
    """Acknowledge a deletion notification.

    **Deliberately a no-op.** The app stores no eBay user identifier anywhere — Batch 28's
    ``price_checks`` rows hold a listing's price, title and URL, none of which is keyed to
    an eBay account — so there is nothing to erase when one closes. Acknowledging is still
    mandatory: an endpoint that stops answering is an endpoint eBay reports as down.

    **The body is not read and the signature is not verified, because nothing acts on
    either.** eBay signs these with a key retrievable from its Notification API, and if
    this handler is ever given real work to do, verifying that signature is the first thing
    to add — an unauthenticated POST that deleted rows would be a hole. Today it deletes
    nothing, so there is no privilege for a forged notification to exercise.
    """
    logger.info("ebay_account_deletion_notification_received")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Phase 4.1 — what is this disc currently being asked for?
# ---------------------------------------------------------------------------


def _search_query(film_title: str, format_code: str | None) -> str:
    """The keyword string sent to Browse.

    The format word is part of *finding* the disc, not a nicety — the same reasoning
    ``extract.FORMAT_SEARCH_TERMS`` exists for on the retailer side. A bare film title
    returns the soundtrack, the novel and the poster before it returns a disc; adding
    "Blu-ray" puts discs at the top of a result set that is capped at 200.

    The match filter still does the judging. This only decides which 200 it judges.
    """
    term = FORMAT_SEARCH_TERMS.get(format_code or "", "Blu-ray")
    return f"{film_title} {term}"


def _to_segment(segment: PriceSegment) -> PriceSegmentResponse:
    return PriceSegmentResponse(
        formatCode=segment.format_code,
        edition="collector" if segment.edition == "collector" else "standard",
        conditionId=segment.condition_id,
        conditionLabel=segment.condition_label,
        sampleSize=segment.sample_size,
        median=str(segment.median),
        low=str(segment.low),
        high=str(segment.high),
        currency=segment.currency,
    )


async def _estimate(payload: PriceEstimateRequest) -> PriceEstimate:
    """Search eBay and judge what comes back. One Browse call.

    Raises 503 when the deployment has no keyset, and 502 when eBay refuses — never a
    silent empty result. `AGENTS.md`'s standing lesson from the TMDB outage is that a
    misconfiguration which merely returns nothing is invisible for days.
    """
    try:
        async with EbayClient() as client:
            raw = await client.search(_search_query(payload.filmTitle, payload.formatCode))
            marketplace_id = client.marketplace_id
    except EbayNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="eBay is not configured in this deployment.",
        ) from exc
    except EbayError as exc:
        logger.warning("ebay_price_estimate_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="eBay did not answer."
        ) from exc

    summaries = raw.get("itemSummaries") or []
    judged = []
    unusable = 0
    for summary in summaries:
        listing = listing_from_summary(summary)
        if listing is None:
            unusable += 1
            continue
        judged.append(
            (
                listing,
                match(
                    listing,
                    film_title=payload.filmTitle,
                    format_code=payload.formatCode,
                    country=payload.country,
                ),
            )
        )

    return summarise(
        judged,
        film_title=payload.filmTitle,
        format_code=payload.formatCode,
        marketplace_id=marketplace_id,
        unusable=unusable,
    )


@router.post("/ebay/price-estimate", response_model=PriceEstimateResponse)
async def price_estimate(payload: PriceEstimateRequest, _user: AdminUser) -> PriceEstimateResponse:
    """Phase 4.1 — a median per segment, with the sample size and the rejections.

    **A POST rather than a GET, and not for tidiness.** A film title in a query string ends
    up in access logs and proxy caches; more practically, this spends a unit of a 5,000-a-day
    production quota, and a GET invites a browser, a prefetcher or a retry to spend it again.

    **Sandbox cannot prove this endpoint** — its GB catalogue is empty — so Phase 4.1's
    acceptance, *"querying 'Blade Runner 2049 Blu-ray' returns a reasonable UK median
    price"*, is a live production call and therefore the owner's, per
    `docs/agent-commands/group-start.md`. What ships here is the whole path plus its tests
    against two captured 200-listing payloads.
    """
    estimate = await _estimate(payload)
    headline = estimate.headline()
    logger.info(
        "ebay_price_estimate",
        film=payload.filmTitle,
        considered=estimate.considered,
        matched=estimate.matched,
        segments=len(estimate.segments),
    )
    return PriceEstimateResponse(
        filmTitle=estimate.film_title,
        formatCode=estimate.format_code,
        marketplaceId=estimate.marketplace_id,
        considered=estimate.considered,
        matched=estimate.matched,
        segments=[_to_segment(segment) for segment in estimate.segments],
        headline=_to_segment(headline) if headline else None,
        rejected=estimate.rejected,
        unusable=estimate.unusable,
        basis=estimate.basis,
    )


# ---------------------------------------------------------------------------
# Phase 4.3 — getting it listed
# ---------------------------------------------------------------------------


@router.post("/ebay/listing-url", response_model=ListingUrlResponse)
async def listing_url(payload: ListingUrlRequest, _user: AdminUser) -> ListingUrlResponse:
    """Phase 4.3 — the pre-filled listing link, and what to ask for the disc.

    **Option B promoted to primary.** Option A, a Sell API draft listing, describes
    something eBay does not do: an Inventory API offer is invisible until published, at
    which point it is a live listing with a buyer on the other end. `DECISIONS.md` #142.

    **No eBay call is made unless a price is wanted.** The URL is built locally; the
    suggested price needs a search, so this asks for one only when a format is given —
    which is the case where the number means something.
    """
    price: Decimal | None = None
    if payload.formatCode:
        try:
            estimate = await _estimate(
                PriceEstimateRequest(filmTitle=payload.filmTitle, formatCode=payload.formatCode)
            )
        except HTTPException:
            # A missing keyset or an eBay outage must not stop someone listing a disc.
            # The link is the feature; the price is an aid to it.
            logger.info("ebay_listing_url_without_price", film=payload.filmTitle)
        else:
            headline = estimate.headline()
            price = suggested_price(headline.median if headline else None)

    return ListingUrlResponse(
        url=prelist_url(
            payload.filmTitle,
            year=payload.year,
            format_code=payload.formatCode,
            condition=payload.condition,
        ),
        suggestedTitle=suggested_title(
            payload.filmTitle,
            year=payload.year,
            format_code=payload.formatCode,
            condition=payload.condition,
        ),
        suggestedPrice=str(price) if price is not None else None,
    )
