"""eBay marketplace account deletion endpoint — Batch 28 prerequisite.

The properties worth asserting here are not "does it return 200". They are the four ways
this endpoint fails *silently*: a permuted hash order, a digest taken over the request's
own URL instead of the registered one, a 429 that eBay reads as an outage, and an
unconfigured deployment answering with a confident-looking hash over an empty token.
"""

from __future__ import annotations

import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

import src.routers.ebay as ebay_router
from src.main import app
from src.routers.ebay import challenge_digest

PATH = "/api/v1/ebay/account-deletion"

CHALLENGE = "challenge-abc-123"
TOKEN = "T" * 64
ENDPOINT = "https://api-production-a8fe.up.railway.app/api/v1/ebay/account-deletion"

#: Computed once, by hand, from eBay's documented order:
#: sha256(challenge_code + verification_token + endpoint). Hard-coded rather than
#: recomputed in the assertion — a test that rebuilds the value the same way the code
#: does would pass just as happily with the operands in the wrong order.
EXPECTED_DIGEST = "ac8fabaca07d426b84f090fd6a2718d444a59aeaaf02207169c0254f0678f49e"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ebay_router.settings, "ebay_verification_token", TOKEN)
    monkeypatch.setattr(ebay_router.settings, "ebay_account_deletion_endpoint", ENDPOINT)


async def _get(params: dict[str, str] | None = None, base_url: str = "http://test") -> object:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        return await client.get(PATH, params=params)


def test_digest_matches_ebays_documented_order() -> None:
    assert challenge_digest(CHALLENGE, TOKEN, ENDPOINT) == EXPECTED_DIGEST


def test_digest_is_order_sensitive() -> None:
    """Every permutation is a valid-looking 64-char hex string that eBay rejects."""
    permuted = hashlib.sha256((TOKEN + CHALLENGE + ENDPOINT).encode()).hexdigest()
    assert permuted != EXPECTED_DIGEST
    assert challenge_digest(TOKEN, CHALLENGE, ENDPOINT) == permuted


@pytest.mark.asyncio
async def test_challenge_is_answered_with_the_digest(configured: None) -> None:
    response = await _get({"challenge_code": CHALLENGE})
    assert response.status_code == 200
    assert response.json() == {"challengeResponse": EXPECTED_DIGEST}


@pytest.mark.asyncio
async def test_digest_uses_the_registered_url_not_the_request_url(configured: None) -> None:
    """The property that breaks behind a proxy.

    Railway terminates TLS and forwards on another host, so ``request.url`` is not what
    eBay hashed. Two requests arriving at different apparent origins must still produce
    the digest over the *configured* endpoint — identical to each other, and to the value
    eBay computes.
    """
    first = await _get({"challenge_code": CHALLENGE}, base_url="http://internal:8000")
    second = await _get({"challenge_code": CHALLENGE}, base_url="https://someone-elses-host")

    assert first.json() == second.json() == {"challengeResponse": EXPECTED_DIGEST}


@pytest.mark.asyncio
async def test_challenge_requires_a_code(configured: None) -> None:
    response = await _get()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unconfigured_deployment_refuses_rather_than_guessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hash over an empty token looks exactly as convincing as a correct one."""
    monkeypatch.setattr(ebay_router.settings, "ebay_verification_token", "")
    monkeypatch.setattr(ebay_router.settings, "ebay_account_deletion_endpoint", ENDPOINT)
    assert (await _get({"challenge_code": CHALLENGE})).status_code == 503

    monkeypatch.setattr(ebay_router.settings, "ebay_verification_token", TOKEN)
    monkeypatch.setattr(ebay_router.settings, "ebay_account_deletion_endpoint", "")
    assert (await _get({"challenge_code": CHALLENGE})).status_code == 503


@pytest.mark.asyncio
async def test_notification_is_acknowledged(configured: None) -> None:
    """204 is one of the four codes eBay accepts (200, 201, 202, 204)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            PATH, json={"metadata": {"topic": "MARKETPLACE_ACCOUNT_DELETION"}}
        )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_endpoint_is_unauthenticated(configured: None) -> None:
    """eBay has no credential of ours. It must answer with no Authorization header."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(PATH, params={"challenge_code": CHALLENGE})
        assert "authorization" not in {k.lower() for k in response.request.headers}
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_endpoint_is_not_rate_limited(configured: None) -> None:
    """A 429 reads to eBay as an outage, and it emails the owner about those.

    60 hits is well past every other public route's ceiling — Batch 17's feed allows
    30/hour — so a limiter accidentally applied here would show up as a 429 in this loop.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        codes = {
            (await client.get(PATH, params={"challenge_code": CHALLENGE})).status_code
            for _ in range(60)
        }
    assert codes == {200}
