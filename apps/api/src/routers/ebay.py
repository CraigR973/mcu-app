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
"""

from __future__ import annotations

import hashlib

import structlog
from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel

from ..config import settings

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
