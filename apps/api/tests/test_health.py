from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_health_returns_running_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.routers.health as health_router

    monkeypatch.setattr(health_router.settings, "railway_git_commit_sha", "abc1234")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "commitSha": "abc1234"}


@pytest.mark.asyncio
async def test_health_reports_unknown_commit_when_not_in_railway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.routers.health as health_router

    monkeypatch.setattr(health_router.settings, "railway_git_commit_sha", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "commitSha": "unknown"}


@pytest.mark.asyncio
async def test_readiness_returns_ok_when_database_responds() -> None:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with patch("src.routers.health.AsyncSessionLocal", return_value=session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    # `push` is "not_configured" here because the test environment holds no VAPID key,
    # which is the honest answer for it — see the dedicated tests below.
    assert response.json() == {"status": "ready", "db": "ok", "push": "not_configured"}
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_is_unreachable() -> None:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(side_effect=ConnectionError("database unavailable"))
    session.__aexit__ = AsyncMock(return_value=False)

    with patch("src.routers.health.AsyncSessionLocal", return_value=session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "db": "unreachable",
        "push": "not_configured",
    }


def test_application_route_surface_is_exactly_as_intended() -> None:
    """Every reachable route, enumerated.

    Batch 2 asserted health was the *only* route, because nothing was meant to be
    reachable yet. Batch 3 adds authentication, so that assertion could not survive
    unchanged — it is replaced here by the stronger one rather than deleted: the full
    surface is pinned, so a route added by accident still fails this test.
    """
    assert set(app.openapi()["paths"]) == {
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/auth/pin",
        "/api/v1/auth/onboarding/complete",
        "/api/v1/movies",
        "/api/v1/movies/{movie_id}",
        "/api/v1/movies/{movie_id}/copies",
        "/api/v1/collection/facets",
        "/api/v1/watch-log",
        "/api/v1/watch-log/{entry_id}",
        # Batch 37. Both are private, caller-scoped views over watch history.
        "/api/v1/memories/on-this-day",
        "/api/v1/memories/rewatch-suggestions",
        "/api/v1/movies/{movie_id}/candidates",
        "/api/v1/movies/{movie_id}/identify",
        "/api/v1/search",
        # Batch 7's write surface. Admin-only, every one of them.
        "/api/v1/collection",
        "/api/v1/collection/duplicate-check",
        "/api/v1/collection/{item_id}",
        "/api/v1/trash",
        "/api/v1/trash/{table}/{item_id}/restore",
        "/api/v1/admin/audit",
        "/api/v1/tmdb/search",
        # Batch 12. Box sets read by either person and written by an admin; smart
        # collections read and written by their owner and nobody else.
        "/api/v1/box-sets",
        "/api/v1/box-sets/{box_set_id}",
        "/api/v1/box-sets/{box_set_id}/items",
        "/api/v1/box-sets/{box_set_id}/items/{collection_item_id}",
        "/api/v1/smart-collections",
        "/api/v1/smart-collections/{collection_id}",
        "/api/v1/smart-collections/{collection_id}/results",
        # Batch 13. Insights are readable by both; the refresh is admin-only because it
        # spends a shared TMDB budget and rewrites a table everyone reads.
        "/api/v1/insights/completion",
        "/api/v1/insights/completion/{set_id}",
        "/api/v1/insights/completion/refresh",
        # Batch 14. Stats and the activity feed are readable by both people; the exports
        # are too — they carry nothing the app does not already show on screen.
        "/api/v1/collection/stats",
        "/api/v1/activity",
        "/api/v1/export/collection.csv",
        "/api/v1/export/collection.json",
        "/api/v1/export/collection.html",
        # Batch 15. `/trash/all` sits beside Batch 7's `/trash` rather than replacing it —
        # the offline queue and the existing page both call the older shape.
        "/api/v1/trash/all",
        "/api/v1/trash/{table}/{row_id}/restore-row",
        "/api/v1/trash/{table}/{row_id}/permanent",
        "/api/v1/trash/purge",
        "/api/v1/loans",
        "/api/v1/loans/{loan_id}/return",
        # Batch 16. Live TMDB reads, nothing stored — streaming rights move too fast for
        # a cache to be anything but a confidently wrong answer.
        "/api/v1/movies/{movie_id}/streaming",
        "/api/v1/movies/{movie_id}/recommendations",
        "/api/v1/discover/new-releases",
        # Batch 17. `/calendar.ics` is the **only** route in this application that answers
        # without a bearer token — the URL is its own credential, hashed at rest.
        "/api/v1/calendar",
        "/api/v1/calendar/month",
        "/api/v1/calendar/subscribe",
        "/api/v1/calendar.ics",
        "/api/v1/calendar/ingest",
        # Batch 18. The table four earlier batches were waiting on.
        "/api/v1/wanted",
        "/api/v1/wanted/{item_id}",
        "/api/v1/retailers",
        "/api/v1/retailers/{retailer_id}",
        "/api/v1/retailers/seed",
        # Batch 19. None of these runs on a schedule: §5.5 is Batch 20, and §5.3's
        # acceptance is a live run against real shops, which the owner performs.
        "/api/v1/scrapers/built-in",
        "/api/v1/scrapers/test",
        "/api/v1/scrapers/run",
        "/api/v1/scrapers/apply-built-ins",
        # Batch 20. `/daily` is the whole schedule — a Railway cron calls it, because #60
        # rules out an in-process timer that would double every scrape at two containers.
        # It is the one scrape endpoint whose `dryRun` defaults to **false**: a scheduled
        # job that quietly wrote nothing every night would be indistinguishable from one
        # that worked.
        "/api/v1/scrapers/daily",
        "/api/v1/scrapers/runs",
        "/api/v1/scrapers/aggregate",
        # Batch 27. `/gift/{slug}` is the **second** unauthenticated route in this
        # application, after `/calendar.ics`. Both are capability URLs.
        "/api/v1/gift-links",
        "/api/v1/gift-links/{link_id}",
        "/api/v1/gift/{slug}",
        # Batch 11. Devices, preferences and the outbox are caller-scoped: there is no
        # admin view of somebody else's phone. The three jobs are admin-only because they
        # act on the whole app, and `run-reminders` is the entire scheduler — `#60` ruled
        # out an in-process timer, so a Railway cron calls this.
        "/api/v1/notifications",
        "/api/v1/notifications/vapid-key",
        "/api/v1/notifications/preferences",
        "/api/v1/notifications/subscriptions",
        "/api/v1/notifications/subscriptions/{subscription_id}",
        "/api/v1/notifications/subscriptions/{subscription_id}/test",
        "/api/v1/notifications/run-reminders",
        "/api/v1/notifications/seed-sale-seasons",
        "/api/v1/notifications/deliver",
    }


@pytest.mark.asyncio
async def test_readiness_reports_push_as_configured_when_a_key_loads() -> None:
    """**The check the TMDB outage should have had.**

    `TMDB_READ_TOKEN` was absent from Railway for an unknown length of time behind a fully
    green gate, because nothing in the code could observe a hosting variable's absence.
    Push has the same shape, so readiness reports it.
    """
    from cryptography.hazmat.primitives.asymmetric import ec

    from src.config import settings as live_settings
    from src.services.webpush import b64url_encode

    key = ec.generate_private_key(ec.SECP256R1())
    raw = key.private_numbers().private_value.to_bytes(32, "big")

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(live_settings, "vapid_private_key", b64url_encode(raw)),
        patch.object(live_settings, "vapid_subject", "mailto:owner@example.com"),
        patch("src.routers.health.AsyncSessionLocal", return_value=session),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.json()["push"] == "configured"


@pytest.mark.asyncio
async def test_readiness_distinguishes_an_unreadable_key_from_a_missing_one() -> None:
    """A malformed key passes "is the variable set?" and then fails at the first send.

    Reporting it as `invalid` rather than `configured` is the whole point: the two have
    different fixes, and only one of them is "go and set the variable".
    """
    from src.config import settings as live_settings

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(live_settings, "vapid_private_key", "this-is-not-a-p256-scalar"),
        patch.object(live_settings, "vapid_subject", "mailto:owner@example.com"),
        patch("src.routers.health.AsyncSessionLocal", return_value=session),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.json()["push"] == "invalid"
    assert response.status_code == 200, "a missing notification key is not an unhealthy API"
